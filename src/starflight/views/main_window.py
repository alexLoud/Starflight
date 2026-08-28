"""Build the main window and coordinate project, preview, and export actions.

The window owns the long lived controllers and connects their state to menus, the toolbar, the
settings panel, and the preview workspace. Rendering and file operations stay in their services.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QRect, QSize, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QScreen
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from starflight.app.constants import (
    APP_DISPLAY_NAME,
    SETTINGS_KEY_SPLITTER_STATE,
    SETTINGS_KEY_WINDOW_GEOMETRY,
)
from starflight.app.context import AppContext
from starflight.controllers.export_controller import ExportController
from starflight.controllers.preview_controller import PreviewController
from starflight.controllers.project_controller import ProjectController
from starflight.i18n import install_translators, retranslate_ui
from starflight.services.preview_service import PreviewService
from starflight.services.recent_projects_service import (
    read_recent_project_paths,
    remember_recent_project,
    remove_recent_project,
)
from starflight.types.preset import LookPreset, apply_look
from starflight.views.dialogs.about_dialog import AboutDialog
from starflight.views.dialogs.presets_dialog import PresetsDialog
from starflight.views.dialogs.settings_dialog import SettingsDialog
from starflight.views.widgets.main_toolbar import MainToolbar
from starflight.views.widgets.preview_workspace import PreviewWorkspace
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

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(120)
        self._refresh_timer.timeout.connect(self.refresh_preview)

        self._menu_by_path: dict[tuple[str, ...], QMenu] = {}
        self._recent_projects_menu: QMenu | None = None

        self._workspace_active = False
        self._active_look_preset_id: str | None = None
        self._constraining_window = False

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

    def build_menu_shell(self) -> None:
        """Build the window shell through the legacy public entry point."""

        self.build_shell()

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
        self.settings_panel.ui_state_changed.connect(self._on_non_preview_settings_changed)
        self.settings_panel.meta_settings_changed.connect(self._on_non_preview_settings_changed)
        self.settings_panel.timeline_settings_changed.connect(self._on_timeline_settings_changed)
        self.settings_panel.load_image_requested.connect(self.load_image)
        self.preview_workspace.timeline.frame_index_changed.connect(self._on_frame_changed)
        self.preview_workspace.zoom_toolbar.stars_enabled_changed.connect(
            self._on_preview_stars_changed,
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
        self.preview_workspace.timeline.set_frame_index(0, emit_signal=False)
        self.preview_workspace.timeline.pause()
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
        registry.set_enabled("app.file.save_as", dirty)
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

    def _on_non_preview_settings_changed(self) -> None:
        """persist ui/meta settings that do not change the preview image."""

        self._sync_project_from_ui()
        self._project_controller.mark_dirty()
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
        self._update_window_title()
        self._update_action_states()

    def _on_settings_changed(self) -> None:
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
        self._refresh_timer.start()
        self._update_action_states()

    def _on_frame_changed(self, _frame_index: int) -> None:
        self.refresh_preview(sync_settings=False)

    def _on_preview_stars_changed(self, _enabled: bool) -> None:
        """refresh preview when the session stars toggle changes."""

        self.refresh_preview(sync_settings=False)

    def refresh_preview(self, *, sync_settings: bool = True) -> None:
        """
        render and show current preview frame.

        sync_settings
            when true, copy sidebar values into the project first
        """

        if not self._workspace_active:
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
            )
        except Exception as exc:
            self._preview_controller.invalidate()
            self._refresh_timer.stop()
            self._context.error_service.show_crash_report(
                "preview rendering failed",
                exc,
                self,
            )

    def new_project_action(self) -> None:
        if not self._project_controller.confirm_discard_changes(self):
            return
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

        answer = QMessageBox.question(
            self,
            self.tr("Reset settings"),
            self.tr("Reset all settings? The loaded image will be kept."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._apply_settings_reset()

    def _apply_settings_reset(self) -> None:
        """restore default settings while keeping the loaded source image."""

        self._project_controller.reset_settings_keep_image()
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
        self._update_window_title()
        self._refresh_timer.start()
        self._update_action_states()

    def export_video(self) -> None:
        self._sync_project_from_ui()
        self._export_controller.open_export_dialog(
            self._project_controller.project,
            self._project_controller.project_path,
            self,
        )

    def open_settings(self) -> None:
        dialog = SettingsDialog(
            self._context.settings,
            self,
            on_language_changed=self._change_language,
        )
        dialog.exec()

    def open_about(self) -> None:
        dialog = AboutDialog(self)
        dialog.exec()

    def _change_language(self, language_code: str) -> None:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return
        install_translators(app, language_code)
        retranslate_ui(self)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._project_controller.confirm_discard_changes(self):
            self._save_layout()
            event.accept()
        else:
            event.ignore()


__all__ = ["MainWindow"]
