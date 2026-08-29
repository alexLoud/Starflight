"""Build the main window and coordinate project, preview, and export actions.

The window owns the long lived controllers and connects their state to menus, the toolbar, the
settings panel, and the preview workspace. Rendering and file operations stay in their services.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEvent, QRect, QSize, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QScreen
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QMainWindow,
    QMenu,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from starflight.app.constants import (
    APP_DISPLAY_NAME,
    SETTINGS_KEY_SPLITTER_STATE,
    SETTINGS_KEY_WELCOME_TOUR_SUPPRESSED,
    SETTINGS_KEY_WINDOW_GEOMETRY,
)
from starflight.app.context import AppContext
from starflight.app.settings import (
    background_preview_preload_fraction_from_settings,
    background_preview_update_from_settings,
    playback_preview_fps_from_settings,
    render_worker_count_from_settings,
)
from starflight.controllers.export_controller import ExportController
from starflight.controllers.playback_preview_controller import (
    PlaybackPreparePlan,
    PlaybackPreviewController,
)
from starflight.controllers.preview_controller import PreviewController
from starflight.controllers.project_controller import ProjectController
from starflight.i18n import install_translators, retranslate_ui, tr_validation
from starflight.services.parallax_preview_service import ParallaxPreviewWorker
from starflight.services.playback_preview_service import PlaybackPreviewWorker
from starflight.services.preview_service import PreviewService
from starflight.services.project_service import resolve_source_image_path
from starflight.services.recent_projects_service import (
    read_recent_project_paths,
    remember_recent_project,
    remove_recent_project,
)
from starflight.types.preset import LookPreset, apply_look
from starflight.types.preview import PreparedParallaxPreview
from starflight.types.settings import ImageMotionMode
from starflight.views.dialogs.about_dialog import AboutDialog
from starflight.views.dialogs.presets_dialog import PresetsDialog
from starflight.views.dialogs.settings_dialog import SettingsDialog
from starflight.views.dialogs.welcome_dialog import WelcomeDialog
from starflight.views.widgets.main_toolbar import MainToolbar
from starflight.views.widgets.preview_workspace import PreviewWorkspace
from starflight.views.widgets.reset_confirm_popover import ResetConfirmPopover
from starflight.views.widgets.settings_panel import SettingsPanel
from starflight.views.widgets.welcome_splash import WelcomeSplash

_MIN_WINDOW_SIZE = QSize(800, 520)


class MainWindow(QMainWindow):
    """starflight main window."""

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.setObjectName("main_window")

        self._context = context
        self._preview_service = PreviewService()
        self._project_controller = ProjectController(context.error_service)
        self._preview_controller = PreviewController(self._preview_service)
        self._export_controller = ExportController(context.error_service, context.settings)
        self._parallax_preview_worker: ParallaxPreviewWorker | None = None
        self._parallax_preview_preparing = False
        self._parallax_preview_revision = 0
        self._parallax_preview_generation_token = 0
        self._parallax_preview_stale = False
        self._parallax_preview_auto_enabled = False
        self._parallax_status_active = False
        self._playback_controller = PlaybackPreviewController(
            self._preview_service,
            self._preview_controller,
            duration_seconds=self._project_controller.project.settings.duration_seconds,
            preview_fps=playback_preview_fps_from_settings(context.settings),
        )
        self._background_renderers_idle_callback: Callable[[], None] | None = None
        self._background_renderers_pending = 0
        self._closing_after_background_renderers = False

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(120)
        self._refresh_timer.timeout.connect(self.refresh_preview)

        self._parallax_preview_refresh_timer = QTimer(self)
        self._parallax_preview_refresh_timer.setSingleShot(True)
        self._parallax_preview_refresh_timer.setInterval(80)
        self._parallax_preview_refresh_timer.timeout.connect(
            self._create_or_update_parallax_preview,
        )

        self._playback_preview_refresh_timer = QTimer(self)
        self._playback_preview_refresh_timer.setSingleShot(True)
        self._playback_preview_refresh_timer.setInterval(350)
        self._playback_preview_refresh_timer.timeout.connect(
            self._start_background_playback_preview,
        )

        self._menu_by_path: dict[tuple[str, ...], QMenu] = {}
        self._recent_projects_menu: QMenu | None = None

        self._workspace_active = False
        self._active_look_preset_id: str | None = None
        self._constraining_window = False
        self._reset_popover: ResetConfirmPopover | None = None

        self._build_ui()
        self._connect_signals()
        self._restore_layout()
        self._apply_project_to_ui()

    def build_shell(self) -> None:
        """build top bar and menu after commands are registered."""

        self._toolbar = MainToolbar(self._context.command_registry)
        central = self.centralWidget()
        wrapper = QWidget()
        wrapper.setObjectName("central_wrapper")
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)
        wrapper_layout.addWidget(self._toolbar, stretch=0)
        wrapper_layout.addWidget(central, stretch=1)
        self.setCentralWidget(wrapper)
        wrapper_layout.activate()
        self._build_menu_from_registry()
        self._setup_recent_projects_menu()
        self._setup_menu_separators()
        self.refresh_actions_from_registry()
        self._apply_chrome_visibility()
        self.showMaximized()
        self._apply_window_minimum()

    def _build_menu_from_registry(self) -> None:
        menu_bar = self.menuBar()
        menu_bar.setNativeMenuBar(False)
        self._menu_by_path = {}

        for command in self._context.command_registry.list():
            parent_menu = menu_bar
            path = command.menu_path
            for depth in range(len(path)):
                sub_path = path[: depth + 1]
                if sub_path not in self._menu_by_path:
                    label = path[depth]
                    if depth == 0:
                        self._menu_by_path[sub_path] = menu_bar.addMenu(label)
                    else:
                        parent = self._menu_by_path[path[:depth]]
                        self._menu_by_path[sub_path] = parent.addMenu(label)
                parent_menu = self._menu_by_path[sub_path]

            action = QAction(parent_menu)
            self._context.command_registry.connect_action(command.id, action)
            parent_menu.addAction(action)

    def _setup_recent_projects_menu(self) -> None:
        file_menu = self._menu_by_path.get(("File",))
        if file_menu is None:
            return

        save_action = self._menu_action(file_menu, "app.file.save")
        if save_action is None:
            return

        self._recent_projects_menu = QMenu(self.tr("Open Recent"), self)
        self._recent_projects_menu.setObjectName("menu_open_recent")
        file_menu.insertMenu(save_action, self._recent_projects_menu)
        file_menu.insertSeparator(save_action)
        self._refresh_recent_projects_menu()

    def _setup_menu_separators(self) -> None:
        """insert separators between grouped items in rebuilt menus."""

        self._insert_separator_before(("File",), "app.file.quit")
        self._insert_separator_before(("Project",), "app.project.export")

    def _insert_separator_before(self, menu_path: tuple[str, ...], command_id: str) -> None:
        """
        insert a separator before a menu command.

        menu_path
            top-level menu path
        command_id
            command whose action should follow the separator
        """

        menu = self._menu_by_path.get(menu_path)
        if menu is None:
            return
        action = self._menu_action(menu, command_id)
        if action is not None:
            menu.insertSeparator(action)

    def _menu_action(self, menu: QMenu, command_id: str) -> QAction | None:
        target_name = f"action_{command_id}"
        for action in menu.actions():
            if action.objectName() == target_name:
                return action
        return None

    def _refresh_recent_projects_menu(self) -> None:
        self._refresh_start_recent_projects()
        if self._recent_projects_menu is None:
            return

        self._recent_projects_menu.setTitle(self.tr("Open Recent"))
        self._recent_projects_menu.clear()
        recent_paths = read_recent_project_paths(self._context.settings)
        if not recent_paths:
            empty_action = self._recent_projects_menu.addAction(self.tr("No Recent Projects"))
            empty_action.setEnabled(False)
            return

        for path in recent_paths:
            action = self._recent_projects_menu.addAction(path.name)
            action.setToolTip(str(path))
            action.triggered.connect(
                lambda _checked=False, project_path=path: self._open_recent_project(project_path),
            )

    def _remember_current_project(self) -> None:
        project_path = self._project_controller.project_path
        if project_path is None:
            return
        remember_recent_project(self._context.settings, project_path)
        self._refresh_recent_projects_menu()

    def _open_recent_project(self, path: Path) -> None:
        if not self._project_controller.confirm_discard_changes(self):
            return

        if not self._project_controller.open_project_at(self, path):
            remove_recent_project(self._context.settings, path)
            self._refresh_recent_projects_menu()
            return

        self._clear_parallax_preview()
        self._active_look_preset_id = None
        self._remember_current_project()
        self._preview_controller.invalidate()
        self._show_workspace()
        self._apply_project_to_ui()
        self.refresh_preview()

    def _on_start_recent_project(self, path_text: str) -> None:
        """
        open a recent project chosen on the start screen.

        path_text
            stored project file path
        """

        self._open_recent_project(Path(path_text))

    def _refresh_start_recent_projects(self) -> None:
        """copy recent project paths onto the start screen."""

        self.welcome_splash.set_recent_projects(
            read_recent_project_paths(self._context.settings),
        )

    def _show_workspace(self) -> None:
        """reveal editor chrome after the start screen is left."""

        if self._workspace_active:
            return
        self._workspace_active = True
        self._root_stack.setCurrentWidget(self._workspace_page)
        self._apply_chrome_visibility()
        self._constrain_window_to_screen()
        self._update_window_title()
        QTimer.singleShot(0, self.maybe_show_welcome_tour)

    def _apply_chrome_visibility(self) -> None:
        """show or hide toolbar, menu, and status bar."""

        visible = self._workspace_active
        self.menuBar().setVisible(visible)
        if hasattr(self, "_toolbar"):
            self._toolbar.setVisible(visible)
        self.statusBar().setVisible(visible)

    def _current_screen(self) -> QScreen | None:
        """return the screen that currently owns this window."""

        screen = self.screen()
        if screen is not None:
            return screen
        app = QApplication.instance()
        if app is None:
            return None
        return app.primaryScreen()

    def _apply_window_minimum(self) -> None:
        """keep a shrinkable floor that still fits small displays."""

        screen = self._current_screen()
        if screen is None:
            self.setMinimumSize(_MIN_WINDOW_SIZE)
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        client = self.geometry()
        chrome_width = max(frame.width() - client.width(), 0)
        chrome_height = max(frame.height() - client.height(), 0)
        self.setMinimumSize(
            min(_MIN_WINDOW_SIZE.width(), max(available.width() - chrome_width, 0)),
            min(_MIN_WINDOW_SIZE.height(), max(available.height() - chrome_height, 0)),
        )

    def _constrain_window_to_screen(self) -> None:
        """fit a maximized editor window back into the dock-safe area."""

        if self._constraining_window or not self.isVisible():
            return
        screen = self._current_screen()
        if screen is None:
            return
        available = screen.availableGeometry()
        self._constraining_window = True
        try:
            self._apply_window_minimum()

            was_maximized = self.isMaximized()
            if was_maximized:
                self.showMaximized()

            frame = self.frameGeometry()
            if frame.width() <= available.width() and frame.height() <= available.height():
                return

            if was_maximized:
                self.showNormal()
            frame = self.frameGeometry()
            client = self.geometry()
            target = self._client_rect_for_frame(available, frame, client)
            min_size = self.minimumSize()
            self.setGeometry(
                target.x(),
                target.y(),
                max(target.width(), min_size.width()),
                max(target.height(), min_size.height()),
            )
        finally:
            self._constraining_window = False

    @staticmethod
    def _client_rect_for_frame(available: QRect, frame: QRect, client: QRect) -> QRect:
        """
        map a dock-safe frame onto the window's client geometry.

        available
            usable screen area excluding menu bar and dock
        frame
            current outer window frame
        client
            current inner client rectangle
        """

        left = client.x() - frame.x()
        top = client.y() - frame.y()
        right = frame.right() - client.right()
        bottom = frame.bottom() - client.bottom()
        return QRect(
            available.x() + left,
            available.y() + top,
            max(available.width() - left - right, 0),
            max(available.height() - top - bottom, 0),
        )

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() != QEvent.Type.WindowStateChange:
            return
        if self._workspace_active and self.isMaximized():
            self._constrain_window_to_screen()

    def _build_ui(self) -> None:
        self.menuBar().setVisible(False)
        self.statusBar().setVisible(False)

        self._root_stack = QStackedWidget()
        self._root_stack.setObjectName("root_stack")
        self.setCentralWidget(self._root_stack)

        self.welcome_splash = WelcomeSplash()

        workspace = QWidget()
        workspace.setObjectName("central_workspace")
        self._workspace_page = workspace

        root_layout = QVBoxLayout(workspace)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        content_splitter = QSplitter()
        content_splitter.setChildrenCollapsible(False)
        self._content_splitter = content_splitter

        self.preview_workspace = PreviewWorkspace()
        self.settings_panel = SettingsPanel()

        content_splitter.addWidget(self.preview_workspace)
        content_splitter.addWidget(self.settings_panel)
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 0)
        content_splitter.setSizes([1100, 460])

        root_layout.addWidget(content_splitter, stretch=1)

        self._root_stack.addWidget(self.welcome_splash)
        self._root_stack.addWidget(workspace)
        self._root_stack.setCurrentWidget(self.welcome_splash)
        self._refresh_start_recent_projects()

    def _connect_signals(self) -> None:
        self.settings_panel.settings_changed.connect(self._on_settings_changed)
        self.settings_panel.background_settings_changed.connect(
            self._on_background_settings_changed,
        )
        self.settings_panel.ui_state_changed.connect(self._on_ui_state_changed)
        self.settings_panel.meta_settings_changed.connect(self._on_meta_settings_changed)
        self.settings_panel.timeline_settings_changed.connect(self._on_timeline_settings_changed)
        self.settings_panel.load_image_requested.connect(self.load_image)
        self.settings_panel.preview_adjustment_finished.connect(
            self._on_preview_adjustment_finished,
        )
        self.settings_panel.background_adjustment_finished.connect(
            self._on_background_adjustment_finished,
        )
        self.settings_panel.image_load_failed.connect(self._on_settings_image_load_failed)
        self.preview_workspace.timeline.frame_index_changed.connect(self._on_frame_changed)
        self.preview_workspace.timeline.play_state_changed.connect(self._on_playback_state_changed)
        self.preview_workspace.timeline.scrub_finished.connect(self._on_timeline_scrub_finished)
        self.preview_workspace.timeline.play_requested.connect(self._on_play_requested)
        self.preview_workspace.zoom_toolbar.stars_enabled_changed.connect(
            self._on_preview_stars_changed,
        )
        self.preview_workspace.zoom_toolbar.parallax_preview_enabled_changed.connect(
            self._on_preview_mode_changed,
        )
        self.welcome_splash.new_project_requested.connect(self.new_project_action)
        self.welcome_splash.open_project_requested.connect(self.open_project)
        self.welcome_splash.recent_project_requested.connect(self._on_start_recent_project)

    def _restore_layout(self) -> None:
        geometry = self._context.settings.value(SETTINGS_KEY_WINDOW_GEOMETRY)
        if geometry is not None:
            self.restoreGeometry(geometry)

        splitter_state = self._context.settings.value(SETTINGS_KEY_SPLITTER_STATE)
        if splitter_state is not None:
            self._content_splitter.restoreState(splitter_state)

    def _save_layout(self) -> None:
        self._context.settings.setValue(SETTINGS_KEY_WINDOW_GEOMETRY, self.saveGeometry())
        self._context.settings.setValue(
            SETTINGS_KEY_SPLITTER_STATE,
            self._content_splitter.saveState(),
        )

    def _apply_project_to_ui(self) -> None:
        project = self._project_controller.project
        self.settings_panel.set_project(project, project_path=self._project_controller.project_path)
        self.preview_workspace.preview_panel.set_target_resolution(
            project.settings.resolution.width,
            project.settings.resolution.height,
        )
        self.preview_workspace.timeline.configure(
            project.settings.duration_seconds,
            project.settings.fps,
        )
        self._invalidate_playback_preview()
        self.preview_workspace.timeline.set_frame_index(0, emit_signal=False)
        self._sync_parallax_preview_ui()
        self._schedule_parallax_preview_refresh()
        self.preview_workspace.timeline.pause(emit_frame=False)
        if self._workspace_active:
            self.refresh_preview()
        self._update_window_title()
        if self._workspace_active:
            self._set_status(self.tr("Ready"))
        self._update_action_states()

    def retranslate_ui(self) -> None:
        """refresh all translatable ui texts."""

        self._update_command_texts()
        if hasattr(self, "_toolbar"):
            self._toolbar.refresh_action_texts()
        self._rebuild_menu_texts()
        self._update_menu_action_texts()
        self._refresh_recent_projects_menu()
        self.welcome_splash.retranslate_ui()
        self.settings_panel.retranslate_ui()
        self.preview_workspace.retranslate_ui()
        if self._reset_popover is not None:
            self._reset_popover.retranslate_ui()
        self._update_window_title()
        if self._workspace_active and not self._project_controller.project.source_image:
            self.preview_workspace.preview_panel.show_empty_preview_message()

    def _update_command_texts(self) -> None:
        titles = {
            "app.file.new": self.tr("New"),
            "app.file.open": self.tr("Open…"),
            "app.file.save": self.tr("Save"),
            "app.file.save_as": self.tr("Save as…"),
            "app.file.quit": self.tr("Quit"),
            "app.project.load_image": self.tr("Load image…"),
            "app.project.presets": self.tr("Presets"),
            "app.project.reset_settings": self.tr("Reset all settings"),
            "app.project.export": self.tr("Export video…"),
            "app.settings.open": self.tr("Settings…"),
            "app.help.welcome": self.tr("Welcome tour…"),
            "app.help.about": self.tr("About Starflight"),
        }
        registry = self._context.command_registry
        for command_id, title in titles.items():
            registry.update_command(command_id, title=title)
            try:
                action = registry.action(command_id)
                action.setText(title)
                action.setToolTip(title)
            except KeyError:
                pass

    def _update_menu_action_texts(self) -> None:
        registry = self._context.command_registry

        def walk_menu(menu) -> None:
            for action in menu.actions():
                sub_menu = action.menu()
                if sub_menu is not None:
                    walk_menu(sub_menu)
                    continue
                object_name = action.objectName()
                if not object_name.startswith("action_"):
                    continue
                command_id = object_name.removeprefix("action_")
                try:
                    command = registry.get(command_id)
                except KeyError:
                    continue
                action.setText(command.title)

        walk_menu(self.menuBar())

    def _rebuild_menu_texts(self) -> None:
        labels = {
            "File": self.tr("File"),
            "Project": self.tr("Project"),
            "Settings": self.tr("Settings"),
            "Help": self.tr("Help"),
        }
        for path, menu in self._menu_by_path.items():
            if len(path) == 1 and path[0] in labels:
                menu.setTitle(labels[path[0]])

    def refresh_actions_from_registry(self) -> None:
        """refresh toolbar and menu action states from registry."""

        self._toolbar.refresh_action_texts()
        self._update_action_states()

    def _update_action_states(self) -> None:
        """enable or disable commands based on current project state."""

        registry = self._context.command_registry
        required_commands = ("app.file.save", "app.file.save_as", "app.project.export")
        if not all(registry.has(command_id) for command_id in required_commands):
            return

        dirty = self._project_controller.is_dirty()
        has_image = bool(self._project_controller.project.source_image)

        registry.set_enabled("app.file.save", dirty)
        registry.set_enabled("app.file.save_as", True)
        registry.set_enabled("app.project.export", has_image)

    def _update_window_title(self) -> None:
        if not self._workspace_active:
            self.setWindowTitle(APP_DISPLAY_NAME)
            return
        self.setWindowTitle(self._project_controller.window_title())

    def _set_status(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _sync_project_from_ui(self) -> None:
        self.settings_panel.apply_to_project(self._project_controller.project)

    def _on_ui_state_changed(self) -> None:
        """Persist sidebar layout without invalidating generated image data."""

        self._sync_project_from_ui()
        self._project_controller.mark_dirty()
        self._update_window_title()
        self._update_action_states()

    def _on_meta_settings_changed(self) -> None:
        """Persist parallax metadata and update an active parallax preview."""

        self._sync_project_from_ui()
        self._project_controller.mark_dirty()
        if self._playback_prerender_enabled():
            self._invalidate_playback_preview()
        self._mark_parallax_preview_stale()
        self._update_window_title()
        self._update_action_states()

    def _on_timeline_settings_changed(self) -> None:
        """update timeline fps while keeping the current preview time."""

        self._sync_project_from_ui()
        self._project_controller.mark_dirty()
        project = self._project_controller.project
        self.preview_workspace.timeline.configure(
            project.settings.duration_seconds,
            project.settings.fps,
            preserve_time=True,
        )
        if self._playback_prerender_enabled():
            self._invalidate_playback_preview()
        self._update_window_title()
        self._update_action_states()

    def _on_background_settings_changed(self) -> None:
        """Refresh parallax snapshots after background-affecting sidebar edits."""

        if self.preview_workspace.timeline.is_playing:
            self.preview_workspace.timeline.pause(emit_frame=True)
        self._sync_project_from_ui()
        self._project_controller.mark_dirty()
        self._update_window_title()
        self._mark_parallax_preview_stale()
        self._update_action_states()
        if self._preview_refresh_deferred():
            self._refresh_timer.stop()
            self._playback_preview_refresh_timer.stop()
            if self._playback_controller.worker is not None:
                self._playback_controller.cancel_active_worker()
            return

        if self._playback_prerender_enabled():
            self._invalidate_playback_preview()
        self._refresh_timer.start()

    def _on_settings_changed(self) -> None:
        if self.preview_workspace.timeline.is_playing:
            self.preview_workspace.timeline.pause(emit_frame=True)
        self._sync_project_from_ui()
        self._project_controller.mark_dirty()
        project = self._project_controller.project
        self.preview_workspace.preview_panel.set_target_resolution(
            project.settings.resolution.width,
            project.settings.resolution.height,
        )
        self.preview_workspace.timeline.configure(
            project.settings.duration_seconds,
            project.settings.fps,
            preserve_time=True,
        )
        self._update_window_title()
        self._update_action_states()
        if self._preview_refresh_deferred():
            self._refresh_timer.stop()
            self._playback_preview_refresh_timer.stop()
            if self._playback_controller.worker is not None:
                self._playback_controller.cancel_active_worker()
            return

        if self._playback_prerender_enabled():
            self._invalidate_playback_preview()
        self._refresh_timer.start()

    def _preview_refresh_deferred(self) -> bool:
        """Return whether interactive edits should defer preview rendering."""

        return (
            self.settings_panel.preview_adjustment_active
            or self.preview_workspace.timeline.is_scrubbing
        )

    def _on_preview_adjustment_finished(self) -> None:
        """Refresh previews after an interactive sidebar edit ends."""

        self._sync_project_from_ui()
        self._project_controller.mark_dirty()
        if self._playback_prerender_enabled():
            self._invalidate_playback_preview()
        self._refresh_timer.start()

    def _on_background_adjustment_finished(self) -> None:
        """Refresh parallax snapshots after background slider or crop edits."""

        if self._parallax_effect_enabled():
            self._mark_parallax_preview_stale()

    def _on_timeline_scrub_finished(self) -> None:
        """Render the selected frame once timeline scrubbing ends."""

        self.refresh_preview(sync_settings=False)

    def _on_frame_changed(self, _frame_index: int) -> None:
        if self.preview_workspace.timeline.is_playing:
            if not self._playback_prerender_enabled():
                if not self.preview_workspace.timeline.is_scrubbing:
                    self.refresh_preview(sync_settings=False)
                return
            controller = self._playback_controller
            should_show, sample_index = controller.should_emit_frame(
                self.preview_workspace.timeline.current_time_seconds(),
            )
            if not should_show:
                return
            _sample_index, frame = controller.frame_for_time(
                self.preview_workspace.timeline.current_time_seconds(),
            )
            if frame is not None:
                controller.mark_sample_shown(sample_index)
                self.preview_workspace.preview_panel.show_frame(frame)
                return
            self.preview_workspace.timeline.pause(emit_frame=False)
        if self.preview_workspace.timeline.is_scrubbing:
            return
        self.refresh_preview(sync_settings=False)

    def _on_playback_state_changed(self, is_playing: bool) -> None:
        """Return to the live full-resolution preview once timeline playback stops."""

        if is_playing:
            self._playback_preview_refresh_timer.stop()
            return

        self._playback_controller.clear_last_sample()
        self._playback_preview_refresh_timer.stop()
        if (
            self._playback_controller.worker is not None
            and not self._playback_controller.starts_playback
        ):
            self._playback_controller.cancel_active_worker()
        if self._parallax_preview_auto_enabled:
            self.preview_workspace.zoom_toolbar.set_parallax_preview_enabled(False)
            self._parallax_preview_auto_enabled = False
        if self._workspace_active and not self.preview_workspace.timeline.is_scrubbing:
            self.refresh_preview(sync_settings=False, force_live_preview=True)

    def _on_preview_stars_changed(self, enabled: bool) -> None:
        """refresh preview when the session stars toggle changes."""

        if enabled:
            self._invalidate_playback_preview()
        else:
            self._playback_controller.cancel_active_worker()
            self._playback_controller.invalidate(
                duration_seconds=self._project_controller.project.settings.duration_seconds,
                preview_fps=playback_preview_fps_from_settings(self._context.settings),
            )
            self.preview_workspace.timeline.set_playback_preparing(False)
            self._playback_preview_refresh_timer.stop()
        self.refresh_preview(sync_settings=False)

    def _on_preview_mode_changed(self, enabled: bool) -> None:
        """Switch immediately between the live and generated preview sources."""

        if enabled:
            self._parallax_preview_auto_enabled = False
            self._schedule_parallax_preview_refresh()
        else:
            self._parallax_preview_auto_enabled = False
            self._parallax_preview_refresh_timer.stop()
        if self._playback_prerender_enabled():
            self._invalidate_playback_preview()
        self.refresh_preview(sync_settings=False)

    def refresh_preview(
        self,
        *,
        sync_settings: bool = True,
        force_live_preview: bool = False,
    ) -> None:
        """
        render and show current preview frame.

        sync_settings
            when true, copy sidebar values into the project first
        force_live_preview
            when true, bypass the generated parallax preview source
        """

        if not self._workspace_active:
            return
        if self._playback_controller.starts_playback:
            self._refresh_timer.stop()
            return
        if sync_settings:
            self._sync_project_from_ui()
        try:
            self._preview_controller.refresh_preview(
                self._project_controller.project,
                self._project_controller.project_path,
                self.preview_workspace.preview_panel,
                self.preview_workspace.timeline.current_time_seconds(),
                include_stars=self.preview_workspace.zoom_toolbar.stars_enabled,
                use_parallax_preview=(
                    not force_live_preview
                    and self.preview_workspace.zoom_toolbar.parallax_preview_enabled
                ),
            )
        except Exception as exc:
            self._preview_controller.invalidate()
            self._clear_parallax_preview()
            self._refresh_timer.stop()
            self._context.error_service.show_user_warning(
                self.tr("Preview unavailable"),
                str(exc),
                self,
            )

    def _on_settings_image_load_failed(self, message: str) -> None:
        """Surface image reload failures from the settings panel."""

        self._context.error_service.show_user_warning(
            self.tr("Could not load image"),
            message,
            self,
        )

    def _reset_playback_preparation_state(self) -> None:
        """Clear playback-preparing UI state."""

        self._playback_controller.reset_preparation()
        self.preview_workspace.timeline.set_playback_preparing(False)

    def _playback_prerender_enabled(self) -> bool:
        """Return whether timeline playback should use the star frame cache."""

        return self.preview_workspace.zoom_toolbar.stars_enabled

    def _parallax_preview_blocks_playback_preload(self) -> bool:
        """Return whether star preload must wait for the parallax snapshot."""

        if not self._parallax_effect_enabled():
            return False
        if not self.preview_workspace.zoom_toolbar.parallax_preview_enabled:
            return False
        return (
            self._parallax_preview_preparing
            or self._parallax_preview_stale
            or not self._preview_service.has_parallax_preview
        )

    def _invalidate_playback_preview(self, *, schedule: bool = True) -> None:
        """Discard playback frames whenever their visual inputs change."""

        self._playback_controller.invalidate(
            duration_seconds=self._project_controller.project.settings.duration_seconds,
            preview_fps=playback_preview_fps_from_settings(self._context.settings),
        )
        self.preview_workspace.timeline.set_playback_preparing(False)
        self._playback_preview_refresh_timer.stop()
        if not self._playback_prerender_enabled():
            return
        if (
            schedule
            and self._workspace_active
            and background_preview_preload_fraction_from_settings(self._context.settings) > 0.0
            and not self._parallax_preview_blocks_playback_preload()
        ):
            self._playback_preview_refresh_timer.start()

    def _start_background_playback_preview(self) -> None:
        """Preload playback frames in the background after preview-affecting edits."""

        if self.preview_workspace.timeline.is_playing:
            return
        if not self._playback_prerender_enabled():
            return
        if self._parallax_preview_blocks_playback_preload():
            return
        preload_fraction = background_preview_preload_fraction_from_settings(
            self._context.settings,
        )
        if preload_fraction <= 0.0:
            return
        plan = self._playback_controller.background_warmup_plan(preload_fraction)
        if plan.missing:
            self._start_playback_preview_worker(
                PlaybackPreparePlan(
                    sample_indices=plan.sample_indices,
                    start_playback=False,
                    missing=plan.missing,
                    required=[],
                ),
            )

    def _on_play_requested(self) -> None:
        """Fill the six-fps cache from the playhead before starting playback."""

        if self._playback_controller.starts_playback:
            return
        self._refresh_timer.stop()
        self._playback_preview_refresh_timer.stop()
        if not self._playback_prerender_enabled():
            self.preview_workspace.timeline.play()
            return
        plan = self._playback_controller.play_plan(
            self.preview_workspace.timeline.current_time_seconds(),
        )
        if not plan.missing:
            self._begin_cached_playback()
            return
        self._playback_controller.arm_playback_prepare(plan.required)
        self.preview_workspace.timeline.set_playback_preparing(True)
        self._set_playback_prepare_progress(0, len(plan.missing))
        self._start_playback_preview_worker(
            PlaybackPreparePlan(
                sample_indices=plan.sample_indices,
                start_playback=True,
                missing=plan.missing,
                required=plan.required,
            ),
        )

    def _start_playback_preview_worker(self, plan: PlaybackPreparePlan) -> None:
        """Start or queue one cache-fill operation for the current revision."""

        if not plan.missing:
            if plan.start_playback:
                self._begin_cached_playback()
            return
        if self._playback_controller.worker is not None:
            if plan.start_playback:
                self._playback_controller.worker.request_cancel()
                self._playback_controller.worker = None
                self._playback_controller.pending = None
            else:
                self._playback_controller.queue_worker(plan)
                return

        spec = self._playback_controller.build_render_spec(
            self._project_controller.project,
            self._project_controller.project_path,
            self.preview_workspace.preview_panel,
            crop_target_size=(
                self._project_controller.project.settings.resolution.width,
                self._project_controller.project.settings.resolution.height,
            ),
            include_stars=self.preview_workspace.zoom_toolbar.stars_enabled,
            parallax_preview_enabled=(self.preview_workspace.zoom_toolbar.parallax_preview_enabled),
        )
        if spec is None:
            self.preview_workspace.timeline.set_playback_preparing(False)
            self._playback_controller.reset_preparation()
            return
        token = self._playback_controller.generation
        worker = PlaybackPreviewWorker(
            spec,
            plan.missing,
            render_workers=render_worker_count_from_settings(self._context.settings),
            parent=self,
        )
        self._playback_controller.attach_worker(
            worker,
            start_playback=plan.start_playback,
            required=plan.required,
        )
        worker.frame_ready.connect(
            lambda index, frame, active=worker, current=token: self._on_playback_frame_ready(
                active,
                current,
                index,
                frame,
            ),
        )
        worker.progress_changed.connect(
            lambda current, total, active=worker: self._on_playback_preview_progress(
                active,
                current,
                total,
            ),
        )
        worker.completed.connect(
            lambda active=worker, current=token: self._on_playback_preview_completed(
                active,
                current,
            ),
        )
        worker.failed.connect(
            lambda failure, active=worker, current=token: self._on_playback_preview_failed(
                active,
                current,
                failure,
            ),
        )
        worker.finished.connect(
            lambda active=worker: self._on_playback_preview_worker_finished(active),
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_playback_frame_ready(
        self,
        worker: PlaybackPreviewWorker,
        token: int,
        sample_index: int,
        frame: object,
    ) -> None:
        if worker is not self._playback_controller.worker:
            return
        if not self._playback_controller.is_current(token):
            return
        if isinstance(frame, bytes):
            self._playback_controller.store_frame(sample_index, frame)

    def _on_playback_preview_progress(
        self,
        worker: PlaybackPreviewWorker,
        current: int,
        total: int,
    ) -> None:
        if worker is not self._playback_controller.worker:
            return
        if self._playback_controller.starts_playback:
            self._set_playback_prepare_progress(current, total)

    def _set_playback_prepare_progress(self, current: int, total: int) -> None:
        """Show playback cache preparation progress as a percentage."""

        progress = 0 if total <= 0 else min(100, round(current * 100 / total))
        self._set_status(self.tr("Preparing preview… {progress}%").format(progress=progress))

    def _on_playback_preview_completed(
        self,
        worker: PlaybackPreviewWorker,
        token: int,
    ) -> None:
        if worker is not self._playback_controller.worker:
            return
        if not self._playback_controller.is_current(token):
            return
        if (
            self._playback_controller.starts_playback
            and self._playback_controller.playback_cache_ready()
        ):
            self._begin_cached_playback()

    def _on_playback_preview_failed(
        self,
        worker: PlaybackPreviewWorker,
        token: int,
        failure: object,
    ) -> None:
        if worker is not self._playback_controller.worker:
            return
        if not self._playback_controller.is_current(token):
            return
        self._reset_playback_preparation_state()
        if isinstance(failure, BaseException):
            self._context.error_service.show_user_warning(
                self.tr("Preview unavailable"),
                str(failure),
                self,
            )

    def _on_playback_preview_worker_finished(self, worker: PlaybackPreviewWorker) -> None:
        if worker is not self._playback_controller.worker:
            self._notify_background_renderer_idle(worker)
            return
        pending, should_reset = self._playback_controller.detach_worker()
        if should_reset and pending is None:
            self._reset_playback_preparation_state()
            self._set_status(self.tr("Ready"))
        self._notify_background_renderer_idle(worker)
        if pending is not None:
            indices, start_playback = pending
            missing = self._playback_controller.frame_cache.missing(indices)
            required = list(indices) if start_playback else []
            if start_playback:
                self.preview_workspace.timeline.set_playback_preparing(True)
                self._set_playback_prepare_progress(0, len(missing))
            self._start_playback_preview_worker(
                PlaybackPreparePlan(
                    sample_indices=list(indices),
                    start_playback=start_playback,
                    missing=missing,
                    required=required,
                ),
            )

    def _begin_cached_playback(self) -> None:
        """Start the timeline only after every required six-fps frame is cached."""

        self._playback_controller.reset_preparation()
        sample_index, frame = self._playback_controller.frame_for_time(
            self.preview_workspace.timeline.current_time_seconds(),
        )
        if frame is not None:
            self.preview_workspace.preview_panel.show_frame(frame)
        self.preview_workspace.timeline.set_playback_preparing(False)
        self._set_status(self.tr("Ready"))
        self.preview_workspace.timeline.play()

    def _parallax_effect_enabled(self) -> bool:
        """Return whether the current project exports with parallax."""

        return (
            self._project_controller.project.settings.background.motion_mode
            == ImageMotionMode.PARALLAX
        )

    def _sync_parallax_preview_ui(self) -> None:
        """Keep the timeline control aligned with the cached snapshot."""

        has_preview = self._preview_service.has_parallax_preview
        parallax_enabled = self._parallax_effect_enabled()
        if not parallax_enabled:
            timeline_status = "disabled"
        elif self._parallax_preview_preparing:
            timeline_status = "generating"
        elif has_preview:
            timeline_status = "ready"
        else:
            timeline_status = "none"
        self.preview_workspace.zoom_toolbar.set_parallax_preview_state(
            available=has_preview and parallax_enabled,
            status=timeline_status,
        )

    def _mark_parallax_preview_stale(self) -> None:
        """Record a project revision and refresh an active parallax preview."""

        self._parallax_preview_revision += 1
        if self._preview_service.has_parallax_preview:
            self._parallax_preview_stale = True
        self._sync_parallax_preview_ui()
        if not self._preview_refresh_deferred():
            self._schedule_parallax_preview_refresh()
        else:
            self._parallax_preview_refresh_timer.stop()

    def _schedule_parallax_preview_refresh(self) -> None:
        """Debounce preparation while preserving the latest project revision."""

        project = self._project_controller.project
        if not self._parallax_effect_enabled() or not project.source_image:
            self._parallax_preview_refresh_timer.stop()
            return
        if self._preview_refresh_deferred():
            self._parallax_preview_refresh_timer.stop()
            return

        has_preview = self._preview_service.has_parallax_preview
        preview_active = self.preview_workspace.zoom_toolbar.parallax_preview_enabled
        needs_preview = not has_preview or self._parallax_preview_stale
        if needs_preview and (not has_preview or preview_active):
            self._parallax_preview_refresh_timer.start()
        else:
            self._parallax_preview_refresh_timer.stop()

    def _clear_parallax_preview(self) -> None:
        """Cancel preparation and remove a snapshot that belongs to another project."""

        self._invalidate_playback_preview(schedule=False)
        self._parallax_preview_refresh_timer.stop()
        self._parallax_preview_generation_token += 1
        self._parallax_preview_revision += 1
        if self._parallax_preview_worker is not None:
            self._parallax_preview_worker.request_cancel()
            self._parallax_preview_preparing = True
        self._preview_service.clear_parallax_preview()
        self._parallax_preview_stale = False
        self._parallax_preview_auto_enabled = False
        self._sync_parallax_preview_ui()

    def _create_or_update_parallax_preview(self) -> None:
        """Prepare the latest low-resolution V4 snapshot in the background."""

        if self._parallax_preview_worker is not None:
            return
        if self._preview_refresh_deferred():
            return
        self._sync_project_from_ui()
        project = self._project_controller.project
        if project.settings.background.motion_mode != ImageMotionMode.PARALLAX:
            return
        if self._preview_service.has_parallax_preview and (
            not self._parallax_preview_stale
            or not self.preview_workspace.zoom_toolbar.parallax_preview_enabled
        ):
            return
        validation = self._preview_service.validate(
            project,
            self._project_controller.project_path,
        )
        if not validation.ok:
            self._context.error_service.show_user_warning(
                self.tr("Preview unavailable"),
                tr_validation(validation.message),
                self,
            )
            return
        image_path = resolve_source_image_path(
            self._project_controller.project_path,
            project.source_image,
        )
        if image_path is None:
            return

        self._parallax_preview_generation_token += 1
        token = self._parallax_preview_generation_token
        source_revision = self._parallax_preview_revision
        worker = ParallaxPreviewWorker(
            str(image_path),
            project.settings,
            self,
        )
        self._parallax_preview_worker = worker
        self._parallax_preview_preparing = True
        self._parallax_status_active = True
        worker.progress_changed.connect(
            lambda progress, active=worker: self._on_parallax_preview_progress(active, progress),
        )
        worker.preview_ready.connect(
            lambda preview, active=worker, current=token, revision=source_revision: (
                self._on_parallax_preview_ready(active, current, revision, preview)
            ),
        )
        worker.failed.connect(
            lambda failure, active=worker, current=token: self._on_parallax_preview_failed(
                active,
                current,
                failure,
            ),
        )
        worker.finished.connect(
            lambda active=worker: self._on_parallax_preview_worker_finished(active),
        )
        worker.finished.connect(worker.deleteLater)
        self._sync_parallax_preview_ui()
        worker.start()

    def _on_parallax_preview_ready(
        self,
        worker: ParallaxPreviewWorker,
        token: int,
        source_revision: int,
        preview: object,
    ) -> None:
        if worker is not self._parallax_preview_worker:
            return
        if token != self._parallax_preview_generation_token:
            return
        if not isinstance(preview, PreparedParallaxPreview):
            self._on_parallax_preview_failed(
                worker,
                token,
                TypeError("invalid parallax preview result"),
            )
            return

        had_preview = self._preview_service.has_parallax_preview
        was_enabled = self.preview_workspace.zoom_toolbar.parallax_preview_enabled
        self._preview_service.install_parallax_preview(preview)
        self._invalidate_playback_preview()
        self._parallax_preview_preparing = False
        self._parallax_preview_stale = source_revision != self._parallax_preview_revision
        self._sync_parallax_preview_ui()
        self._clear_parallax_prepare_status()
        if self._parallax_effect_enabled():
            if (
                not had_preview
                and not self.preview_workspace.timeline.is_playing
                and not self._playback_controller.starts_playback
            ):
                self.preview_workspace.zoom_toolbar.set_parallax_preview_enabled(True)
                self._parallax_preview_auto_enabled = True
            if was_enabled:
                self.refresh_preview(sync_settings=False)
            if (
                self._parallax_preview_stale
                and self.preview_workspace.zoom_toolbar.parallax_preview_enabled
            ):
                self._schedule_parallax_preview_refresh()

    def _on_parallax_preview_failed(
        self,
        worker: ParallaxPreviewWorker,
        token: int,
        failure: object,
    ) -> None:
        if worker is not self._parallax_preview_worker:
            return
        if token != self._parallax_preview_generation_token:
            return
        self._parallax_preview_preparing = False
        self._sync_parallax_preview_ui()
        self._clear_parallax_prepare_status()
        if isinstance(failure, BaseException):
            self._context.error_service.show_user_warning(
                self.tr("Preview unavailable"),
                str(failure),
                self,
            )

    def _on_parallax_preview_worker_finished(
        self,
        worker: ParallaxPreviewWorker,
    ) -> None:
        if worker is not self._parallax_preview_worker:
            self._notify_background_renderer_idle(worker)
            return
        self._parallax_preview_worker = None
        self._parallax_preview_preparing = False
        self._sync_parallax_preview_ui()
        self._clear_parallax_prepare_status()
        self._notify_background_renderer_idle(worker)

    def new_project_action(self) -> None:
        if not self._project_controller.confirm_discard_changes(self):
            return
        self._clear_parallax_preview()
        self._project_controller.new_project()
        self._active_look_preset_id = None
        self._preview_controller.invalidate()
        self.preview_workspace.preview_panel.viewport.reset_zoom()
        self._show_workspace()
        self._apply_project_to_ui()

    def open_project(self) -> None:
        if not self._project_controller.confirm_discard_changes(self):
            return
        if not self._project_controller.open_project(self):
            return
        self._clear_parallax_preview()
        self._active_look_preset_id = None
        self._remember_current_project()
        self._preview_controller.invalidate()
        self._show_workspace()
        self._apply_project_to_ui()
        self.refresh_preview()

    def save_project(self) -> None:
        self._sync_project_from_ui()
        if self._project_controller.save_project(self):
            self._remember_current_project()
            self._update_window_title()
            path = self._project_controller.project_path
            if path is not None:
                self._set_status(self.tr("Project saved: {path}").format(path=path))
            self._update_action_states()

    def save_project_as(self) -> None:
        self._sync_project_from_ui()
        if self._project_controller.save_project_as(self):
            self._remember_current_project()
            self._update_window_title()
            path = self._project_controller.project_path
            if path is not None:
                self._set_status(self.tr("Project saved: {path}").format(path=path))
            self._update_action_states()

    def load_image(self) -> None:
        if self._project_controller.load_image(self):
            self._clear_parallax_preview()
            self._preview_controller.invalidate()
            project = self._project_controller.project
            self.settings_panel.set_project(
                project,
                project_path=self._project_controller.project_path,
            )
            self.preview_workspace.preview_panel.set_target_resolution(
                project.settings.resolution.width,
                project.settings.resolution.height,
            )
            self._update_window_title()
            self.preview_workspace.timeline.set_frame_index(0, emit_signal=False)
            self.refresh_preview()
            self._invalidate_playback_preview()
            self._schedule_parallax_preview_refresh()
            self.preview_workspace.preview_panel.viewport.reset_to_fit()
            self._update_action_states()

    def open_presets(self) -> None:
        """open the look preset library and apply a selected look."""

        self._sync_project_from_ui()
        dialog = PresetsDialog(
            get_settings=lambda: self._project_controller.project.settings,
            parent=self,
            selected_id=self._active_look_preset_id,
        )
        dialog.preset_applied.connect(self._apply_look_preset)
        dialog.exec()
        self._active_look_preset_id = dialog.selected_id

    def reset_settings_keep_image(self) -> None:
        """ask, then restore default settings while keeping the loaded image."""

        if not hasattr(self, "_toolbar"):
            return
        anchor = self._toolbar.button_for_command("app.project.reset_settings")
        if anchor is None:
            return
        if self._reset_popover is not None and self._reset_popover.isVisible():
            self._reset_popover.close()
            return

        popover = ResetConfirmPopover(self)
        popover.confirmed.connect(self._apply_settings_reset)
        popover.destroyed.connect(self._clear_reset_popover)
        self._reset_popover = popover
        popover.show_below(anchor)

    def _clear_reset_popover(self, *_args: object) -> None:
        """drop the closed reset confirmation popup."""

        self._reset_popover = None

    def _apply_settings_reset(self) -> None:
        """restore default settings while keeping the loaded source image."""

        self._project_controller.reset_settings_keep_image()
        self._clear_parallax_preview()
        self._active_look_preset_id = None
        self._preview_controller.invalidate()
        self._apply_project_to_ui()
        if self._workspace_active:
            self.preview_workspace.preview_panel.viewport.reset_to_fit()

    def _apply_look_preset(self, preset: LookPreset) -> None:
        """
        merge a look preset into the current project and refresh the preview.

        preset
            selected look preset
        """

        apply_look(self._project_controller.project.settings, preset)
        self._active_look_preset_id = preset.id
        self.settings_panel.set_project(
            self._project_controller.project,
            project_path=self._project_controller.project_path,
        )
        self._project_controller.mark_dirty()
        if self._playback_prerender_enabled():
            self._invalidate_playback_preview()
        self._mark_parallax_preview_stale()
        self._update_window_title()
        self._refresh_timer.start()
        self._update_action_states()

    def _on_parallax_preview_progress(
        self,
        worker: ParallaxPreviewWorker,
        progress: int,
    ) -> None:
        if worker is not self._parallax_preview_worker:
            return
        self._parallax_status_active = True
        self._set_status(self.tr("Preparing parallax… {progress}%").format(progress=progress))

    def _clear_parallax_prepare_status(self) -> None:
        """Reset the status bar after parallax preparation finishes."""

        if not self._parallax_status_active:
            return
        self._parallax_status_active = False
        if self._playback_controller.starts_playback:
            return
        self._set_status(self.tr("Ready"))

    def _notify_background_renderer_idle(self, worker: object) -> None:
        """Invoke the deferred callback once every requested background worker has stopped."""

        if worker is self._parallax_preview_worker:
            self._parallax_preview_worker = None
        if self._background_renderers_pending <= 0:
            return
        self._background_renderers_pending -= 1
        if self._background_renderers_pending > 0:
            return
        callback = self._background_renderers_idle_callback
        self._background_renderers_idle_callback = None
        if callback is not None:
            callback()

    def _cancel_background_renderers(
        self,
        *,
        on_idle: Callable[[], None] | None = None,
    ) -> None:
        """Stop background preview workers without blocking the GUI thread."""

        self._playback_preview_refresh_timer.stop()
        self._parallax_preview_refresh_timer.stop()
        self._playback_controller.cancel_active_worker()
        self._reset_playback_preparation_state()
        if self.preview_workspace.timeline.is_playing:
            self.preview_workspace.timeline.pause(emit_frame=False)

        workers: list[object] = []
        playback_worker = self._playback_controller.worker
        if playback_worker is not None:
            workers.append(playback_worker)
            playback_worker.request_cancel()
        if self._parallax_preview_worker is not None:
            workers.append(self._parallax_preview_worker)
            self._parallax_preview_worker.request_cancel()

        if not workers:
            if on_idle is not None:
                on_idle()
            return

        self._background_renderers_idle_callback = on_idle
        self._background_renderers_pending = len(workers)

    def export_video(self) -> None:
        self._sync_project_from_ui()
        self._cancel_background_renderers()
        self._export_controller.open_export_dialog(
            self._project_controller.project,
            self._project_controller.project_path,
            self,
        )
        if self._workspace_active:
            self._mark_parallax_preview_stale()
            self._invalidate_playback_preview()

    def _pause_background_renderers_for_export(self) -> None:
        """Backward-compatible alias for export entry points."""

        self._cancel_background_renderers()

    def _resume_background_renderers_after_export(self) -> None:
        """Backward-compatible alias for export entry points."""

        if not self._workspace_active:
            return
        self._mark_parallax_preview_stale()
        self._invalidate_playback_preview()

    def open_settings(self) -> None:
        previous_preview_fps = playback_preview_fps_from_settings(self._context.settings)
        previous_background_update = background_preview_update_from_settings(
            self._context.settings,
        )
        dialog = SettingsDialog(
            self._context.settings,
            self,
            on_language_changed=self._change_language,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_preview_fps = playback_preview_fps_from_settings(self._context.settings)
        new_background_update = background_preview_update_from_settings(
            self._context.settings,
        )
        if (
            new_preview_fps != previous_preview_fps
            or new_background_update != previous_background_update
        ):
            self._invalidate_playback_preview()

    def open_about(self) -> None:
        dialog = AboutDialog(self)
        dialog.exec()

    def maybe_show_welcome_tour(self) -> None:
        if not self._context.settings.value(SETTINGS_KEY_WELCOME_TOUR_SUPPRESSED, False, type=bool):
            self.open_welcome_tour()

    def open_welcome_tour(self) -> None:
        dialog = WelcomeDialog(self._context.settings, self)
        dialog.exec()

    def _change_language(self, language_code: str) -> None:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return
        install_translators(app, language_code)
        retranslate_ui(self)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._project_controller.confirm_discard_changes(self):
            event.ignore()
            return

        if (
            self._playback_controller.worker is not None
            or self._parallax_preview_worker is not None
        ):
            event.ignore()
            self._closing_after_background_renderers = True
            self._cancel_background_renderers(on_idle=self._finish_deferred_window_close)
            return

        self._save_layout()
        event.accept()

    def _finish_deferred_window_close(self) -> None:
        """Complete a close request once background preview workers have stopped."""

        if not self._closing_after_background_renderers:
            return
        self._closing_after_background_renderers = False
        self._save_layout()
        self.close()


__all__ = ["MainWindow"]
