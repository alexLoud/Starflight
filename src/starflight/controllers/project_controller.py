"""Coordinate project file operations, dialogs, and unsaved changes."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QMessageBox, QWidget

from starflight.services.error_service import ErrorService
from starflight.services.project_service import (
    Project,
    ProjectError,
    load_project,
    make_relative_image_path,
    new_project,
    normalize_project_path,
    resolve_source_image_path,
    save_project,
)
from starflight.types.settings import reset_project_settings, resolution_for_image_orientation
from starflight.utils.image import read_image_dimensions
from starflight.views.dialogs.image_open_dialog import ImageOpenDialog
from starflight.views.dialogs.project_open_dialog import ProjectOpenDialog
from starflight.views.dialogs.project_save_dialog import ProjectSaveDialog


class ProjectController:
    """handles project file operations and dirty state."""

    @staticmethod
    def tr(text: str) -> str:
        """translate project controller message."""

        return QCoreApplication.translate("ProjectController", text)

    def __init__(self, error_service: ErrorService) -> None:
        self._error_service = error_service
        self.project = new_project(self.tr("Untitled Project"))
        self.project_path: Path | None = None
        self._dirty = False

    def is_dirty(self) -> bool:
        """return whether project has unsaved changes."""

        return self._dirty

    def mark_dirty(self) -> None:
        """mark project as modified."""

        self._dirty = True

    def mark_clean(self) -> None:
        """Mark the project as saved."""

        self._dirty = False

    def window_title(self) -> str:
        """build window title with dirty marker."""

        title = f"Starflight — {self.project.name}"
        if self._dirty:
            title = f"{title} *"
        if self.project_path is not None:
            title = f"{title} [{self.project_path.name}]"
        return title

    def default_project_dialog_path(self, filename: str) -> str:
        """
        build default path for project dialogs.

        filename
            suggested file name
        """

        if self.project_path is not None:
            return str(self.project_path.parent / filename)

        workspace = Path.cwd()
        if (workspace / "example_starless_image.jpg").exists():
            return str(workspace / filename)

        return str(Path.home() / filename)

    def confirm_discard_changes(self, parent: QWidget) -> bool:
        """
        ask user to save unsaved changes.

        parent
            parent widget for dialog

        returns True if operation may continue
        """

        if not self._dirty:
            return True

        answer = self._error_service.ask_save_discard_cancel(
            parent,
            self.tr("Unsaved changes"),
            self.tr("Do you want to save your changes?"),
        )
        if answer == QMessageBox.StandardButton.Save:
            return self.save_project(parent)
        if answer == QMessageBox.StandardButton.Discard:
            return True
        return False

    def new_project(self) -> Project:
        """create a fresh project instance."""

        self.project = new_project(self.tr("Untitled Project"))
        self.project_path = None
        self._dirty = False
        return self.project

    def reset_settings_keep_image(self) -> None:
        """reset all project settings without removing the loaded image."""

        image_size: tuple[int, int] | None = None
        if self.project.source_image:
            image_path = resolve_source_image_path(self.project_path, self.project.source_image)
            if image_path is not None and image_path.is_file():
                try:
                    image_size = read_image_dimensions(str(image_path))
                except (OSError, ValueError):
                    image_size = None
        reset_project_settings(self.project, image_size)
        self._dirty = True

    def open_project(self, parent: QWidget) -> bool:
        """
        open project from disk.

        parent
            parent widget

        returns True when a project was loaded
        """

        path = ProjectOpenDialog.run(
            initial_dir=self.default_project_dialog_path(""),
            parent=parent,
        )
        if path is None:
            return False

        return self.open_project_at(parent, path)

    def open_project_at(self, parent: QWidget, path: Path) -> bool:
        """
        open project from a known path.

        parent
            parent widget
        path
            project file path

        returns True when a project was loaded
        """

        selection = path.expanduser().resolve()
        if not selection.is_file():
            self._error_service.show_user_warning(
                self.tr("Could not open project"),
                self.tr("The project file no longer exists:\n{path}").format(path=selection),
                parent,
            )
            return False

        try:
            self.project = load_project(selection)
        except ProjectError as exc:
            self._error_service.show_user_warning(
                self.tr("Could not open project"),
                str(exc),
                parent,
            )
            return False

        self.project_path = selection
        self._dirty = False
        return True

    def save_project(self, parent: QWidget) -> bool:
        """
        save current project.

        parent
            parent widget

        returns True on success
        """

        if self.project_path is None:
            return self.save_project_as(parent)
        return self._save_to_path(parent, self.project_path)

    def save_project_as(self, parent: QWidget) -> bool:
        """
        save project to a new path.

        parent
            parent widget

        returns True on success
        """

        default_name = f"{self.project.name}.sf"
        dialog = ProjectSaveDialog(
            initial_target=Path(self.default_project_dialog_path(default_name)),
            parent=parent,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return False

        selection = dialog.selected_path()
        if selection is None:
            return False
        return self._save_to_path(parent, normalize_project_path(selection))

    def _save_to_path(self, parent: QWidget, path: Path) -> bool:
        target = normalize_project_path(path)
        previous_source_image = self.project.source_image
        try:
            self.project.source_image = self._source_image_for_save_target(target)
            save_project(self.project, target)
        except ProjectError as exc:
            self.project.source_image = previous_source_image
            self._error_service.show_user_warning(
                self.tr("Save failed"),
                str(exc),
                parent,
            )
            return False
        except Exception as exc:
            self.project.source_image = previous_source_image
            self._error_service.show_crash_report(
                "unexpected save failure",
                exc,
                parent,
            )
            return False

        self.project_path = target
        self._dirty = False
        return True

    def _source_image_for_save_target(self, target_path: Path) -> str | None:
        """Rewrite the stored image path so it stays valid for the destination project."""

        source_image = self.project.source_image
        if not source_image:
            return None

        if self.project_path is not None:
            image_path = resolve_source_image_path(self.project_path, source_image)
            if image_path is None:
                return source_image
            return make_relative_image_path(target_path, image_path)

        image_path = Path(source_image).expanduser()
        if not image_path.is_absolute():
            image_path = image_path.resolve()
        return make_relative_image_path(target_path, image_path)

    def load_image(self, parent: QWidget) -> bool:
        """
        load source image.

        parent
            parent widget

        returns True when image path was selected
        """

        path = ImageOpenDialog.run(parent)
        if path is None:
            return False

        image_path = path
        try:
            image_width, image_height = read_image_dimensions(str(image_path))
        except (OSError, ValueError) as exc:
            self._error_service.show_user_warning(
                self.tr("Could not load image"),
                str(exc),
                parent,
            )
            return False

        if self.project_path is not None:
            self.project.source_image = make_relative_image_path(self.project_path, image_path)
        else:
            self.project.source_image = str(image_path)

        self.project.name = image_path.stem
        target_width, target_height = resolution_for_image_orientation(image_width, image_height)
        self.project.settings.resolution.width = target_width
        self.project.settings.resolution.height = target_height
        crop = self.project.settings.crop
        crop.center_x = 0.5
        crop.center_y = 0.5
        crop.scale = 1.0
        background = self.project.settings.background
        background.start_focus_enabled = False
        background.start_focus_x = 0.5
        background.start_focus_y = 0.5
        background.end_focus_enabled = False
        background.end_focus_x = 0.5
        background.end_focus_y = 0.5
        self._dirty = True
        return True


__all__ = ["ProjectController"]
