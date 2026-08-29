"""Guided introduction shown to new Starflight users."""

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from starflight.app.constants import SETTINGS_KEY_WELCOME_TOUR_SUPPRESSED
from starflight.views.icons import load_icon_asset


@dataclass(frozen=True, slots=True)
class _WelcomeStep:
    icon: str
    title: str
    body: str


class WelcomeDialog(QDialog):
    """Present the main workflow in a short, skippable tour."""

    def __init__(self, settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._step_index = 0
        self._steps: list[_WelcomeStep] = []

        self.setObjectName("welcome_dialog")
        self.setModal(True)
        self.setMinimumSize(720, 480)
        self.resize(720, 480)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QFrame(self)
        header.setObjectName("welcome_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(22, 16, 22, 16)
        header_layout.setSpacing(12)

        self._header_icon = QLabel(header)
        self._header_icon.setObjectName("welcome_header_icon")
        self._header_icon.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._header_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._header_icon.setFixedSize(44, 44)
        header_layout.addWidget(self._header_icon)

        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        self._header_title = QLabel(header)
        self._header_title.setObjectName("welcome_title")
        header_text.addWidget(self._header_title)
        header_layout.addLayout(header_text)
        header_layout.addStretch(1)
        root_layout.addWidget(header)

        content = QFrame(self)
        content.setObjectName("welcome_content")
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(34, 30, 34, 28)
        content_layout.setSpacing(32)

        icon_card = QFrame(content)
        icon_card.setObjectName("welcome_icon_card")
        icon_card.setFixedSize(190, 190)
        icon_layout = QVBoxLayout(icon_card)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        self._step_icon = QLabel(icon_card)
        self._step_icon.setObjectName("welcome_step_icon")
        self._step_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(self._step_icon)
        content_layout.addWidget(icon_card, 0, Qt.AlignmentFlag.AlignVCenter)

        copy_layout = QVBoxLayout()
        copy_layout.setSpacing(12)
        copy_layout.addStretch(1)
        self._step_number = QLabel(content)
        self._step_number.setObjectName("welcome_step_number")
        self._step_title = QLabel(content)
        self._step_title.setObjectName("welcome_step_title")
        self._step_title.setWordWrap(True)
        self._step_body = QLabel(content)
        self._step_body.setObjectName("welcome_step_body")
        self._step_body.setWordWrap(True)
        self._step_body.setAlignment(Qt.AlignmentFlag.AlignTop)
        copy_layout.addWidget(self._step_number)
        copy_layout.addWidget(self._step_title)
        copy_layout.addWidget(self._step_body)
        copy_layout.addStretch(1)
        content_layout.addLayout(copy_layout, 1)
        root_layout.addWidget(content, 1)

        footer = QFrame(self)
        footer.setObjectName("welcome_footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(22, 12, 22, 14)
        footer_layout.setSpacing(10)

        self._dont_show_again = QCheckBox(footer)
        self._dont_show_again.setChecked(
            self._settings.value(SETTINGS_KEY_WELCOME_TOUR_SUPPRESSED, False, type=bool)
        )

        self._close_button = QPushButton(footer)
        self._close_button.clicked.connect(self.reject)
        self._back_button = QPushButton(footer)
        self._back_button.clicked.connect(self._previous_step)
        self._next_button = QPushButton(footer)
        self._next_button.setObjectName("primary_button")
        self._next_button.clicked.connect(self._next_step)
        footer_layout.addWidget(self._close_button)
        footer_layout.addWidget(self._dont_show_again, 0, Qt.AlignmentFlag.AlignVCenter)
        footer_layout.addStretch(1)

        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(6)
        self._progress_dots: list[QFrame] = []
        for _ in range(6):
            dot = QFrame(footer)
            dot.setObjectName("welcome_progress_dot")
            dot.setFixedSize(7, 7)
            self._progress_dots.append(dot)
            progress_layout.addWidget(dot)
        footer_layout.addLayout(progress_layout)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self._back_button)
        footer_layout.addWidget(self._next_button)
        root_layout.addWidget(footer)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Welcome to Starflight"))
        self._header_title.setText(self.tr("Welcome to Starflight"))
        self._dont_show_again.setText(self.tr("Don't show this again"))
        self._close_button.setText(self.tr("Close"))
        self._back_button.setText(self.tr("Back"))
        self._steps = [
            _WelcomeStep(
                "app-icon.png",
                self.tr("Your flight starts here"),
                self.tr(
                    "Turn a deep-sky image into a short flight through space. "
                    "This quick tour shows you the essentials."
                ),
            ),
            _WelcomeStep(
                "load-image.svg",
                self.tr("Load an image"),
                self.tr(
                    "Start with a starless JPG, PNG, or TIFF. It becomes the background "
                    "of your animation."
                ),
            ),
            _WelcomeStep(
                "section-background.svg",
                self.tr("Set the background in motion"),
                self.tr(
                    "In the sidebar, set crop, zoom and rotation for your background. "
                    "Enable parallax for extra depth if you like."
                ),
            ),
            _WelcomeStep(
                "section-stars.svg",
                self.tr("Shape the stars"),
                self.tr("Adjust count, size, color and glow to shape your star field."),
            ),
            _WelcomeStep(
                "export-video.svg",
                self.tr("Review and export"),
                self.tr(
                    "Review your animation in the timeline. When you are satisfied, "
                    "export the video from the toolbar."
                ),
            ),
            _WelcomeStep(
                "settings.svg",
                self.tr("Settings"),
                self.tr(
                    "Set language, preview speed and CPU usage for rendering in Settings."
                ),
            ),
        ]
        self._show_step()

    def done(self, result: int) -> None:
        self._settings.setValue(
            SETTINGS_KEY_WELCOME_TOUR_SUPPRESSED,
            self._dont_show_again.isChecked(),
        )
        super().done(result)

    def _show_step(self) -> None:
        step = self._steps[self._step_index]
        self._header_icon.setPixmap(load_icon_asset(step.icon).pixmap(24, 24))
        self._step_icon.setPixmap(load_icon_asset(step.icon).pixmap(76, 76))
        self._step_number.setText(self.tr("STEP {current}").format(current=self._step_index + 1))
        self._step_title.setText(step.title)
        self._step_body.setText(step.body)
        self._back_button.setEnabled(self._step_index > 0)
        self._next_button.setText(
            self.tr("Let's go") if self._step_index == len(self._steps) - 1 else self.tr("Next")
        )
        for index, dot in enumerate(self._progress_dots):
            dot.setProperty("active", index == self._step_index)
            dot.style().unpolish(dot)
            dot.style().polish(dot)

    def _previous_step(self) -> None:
        if self._step_index > 0:
            self._step_index -= 1
            self._show_step()

    def _next_step(self) -> None:
        if self._step_index == len(self._steps) - 1:
            self.accept()
            return
        self._step_index += 1
        self._show_step()
