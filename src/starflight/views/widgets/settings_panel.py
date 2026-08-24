"""Edit all project settings in grouped sidebar sections.

The panel copies values from a project into Qt controls and writes them back after user changes.
Signal blocking keeps programmatic updates from marking a project as modified.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from starflight.services.project_service import resolve_source_image_path
from starflight.types.settings import (
    DENSITY_STAR_COUNTS,
    MAX_BACKGROUND_ROTATION_DEGREES,
    MAX_BACKGROUND_SCALE_PERCENT,
    MAX_BACKGROUND_ZOOM_PERCENT,
    MAX_STAR_COUNT,
    MIN_BACKGROUND_SCALE_PERCENT,
    MIN_STAR_COUNT,
    DensityPreset,
    Project,
    ProjectSettings,
    coerce_density_preset,
    density_preset_from_count,
)
from starflight.utils.image import bgr_to_rgb, load_image_bgr, numpy_rgb_to_qimage
from starflight.views.icons import load_icon_asset
from starflight.views.widgets.collapsible_section import CollapsibleSection
from starflight.views.widgets.focus_points_control import FocusPointsControl
from starflight.views.widgets.no_wheel_widgets import NoWheelComboBox, NoWheelSpinBox
from starflight.views.widgets.setting_label import (
    SettingLabel,
    apply_form_label_palette,
    apply_settings_group_title_style,
)
from starflight.views.widgets.setting_field_row import SettingFieldRow
from starflight.views.widgets.slider_spinbox_row import SliderSpinBoxRow

_RESOLUTION_CHOICES: tuple[tuple[str, tuple[int, int]], ...] = (
    ("portrait_1080", (1080, 1920)),
    ("landscape_1080", (1920, 1080)),
    ("portrait_4k", (2160, 3840)),
)

_FIELD_MIN_WIDTH = 228
_LABEL_MIN_WIDTH = 132
_SPIN_WIDTH = 88
_DEFAULT_SETTINGS = ProjectSettings()


class SettingsPanel(QWidget):
    """project settings sidebar."""

    settings_changed = Signal()
    load_image_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settings_panel")
        self.setMinimumWidth(420)
        self.setMaximumWidth(520)
        self._update_block_depth = 0
        self._project_path: Path | None = None
        self._setting_field_rows: list[SettingFieldRow] = []
        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        scroll = QScrollArea(self)
        scroll.setObjectName("settings_scroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.project_section = CollapsibleSection(
            "",
            icon=load_icon_asset("section-project.svg"),
            expanded=True,
        )
        self.background_section = CollapsibleSection(
            "",
            icon=load_icon_asset("section-background.svg"),
            expanded=True,
        )
        self.focus_section = CollapsibleSection(
            "",
            icon=load_icon_asset("section-camera.svg"),
            expanded=True,
        )
        self.star_appearance_section = CollapsibleSection(
            "",
            icon=load_icon_asset("section-stars.svg"),
            expanded=True,
        )
        self.star_effects_section = CollapsibleSection(
            "",
            icon=load_icon_asset("section-effects.svg"),
            expanded=True,
        )
        self.star_animation_section = CollapsibleSection(
            "",
            icon=load_icon_asset("section-animation.svg"),
            expanded=True,
        )

        self._build_project_section(self.project_section.content_layout)
        self._build_background_section(self.background_section.content_layout)
        self._build_focus_section(self.focus_section.content_layout)
        self._build_star_appearance_section(self.star_appearance_section.content_layout)
        self._build_star_effects_section(self.star_effects_section.content_layout)
        self._build_star_animation_section(self.star_animation_section.content_layout)

        for section in (
            self.project_section,
            self.background_section,
            self.focus_section,
            self.star_appearance_section,
            self.star_effects_section,
            self.star_animation_section,
        ):
            layout.addWidget(section)
        layout.addStretch(1)

        self._connect_section_state_signals()

        scroll.setWidget(content)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(scroll)

    @staticmethod
    def _configure_form(form: QFormLayout) -> None:
        """apply consistent alignment and spacing to a settings form."""

        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    @staticmethod
    def _style_label(label: QLabel) -> None:
        label.setObjectName("form_label")
        label.setMinimumWidth(_LABEL_MIN_WIDTH)
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        apply_form_label_palette(label)

    def _create_setting_label(self) -> SettingLabel:
        """create a form label with optional info hint icon."""

        label = SettingLabel(self)
        label.setMinimumWidth(_LABEL_MIN_WIDTH)
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        return label

    @staticmethod
    def _style_field(widget: QWidget) -> None:
        widget.setMinimumWidth(_FIELD_MIN_WIDTH)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _wrap_setting_field(
        self,
        field: QWidget,
        reset_handler: Callable[[], None],
    ) -> SettingFieldRow:
        """
        wrap an input widget with a trailing reset button.

        field
            primary setting input widget
        reset_handler
            callback that restores the default value
        """

        row = SettingFieldRow(field, reset_handler)
        self._style_field(row)
        self._setting_field_rows.append(row)
        return row

    def _add_setting_row(
        self,
        form: QFormLayout,
        label: SettingLabel,
        field: QWidget,
        reset_handler: Callable[[], None],
    ) -> None:
        """
        add a labeled setting row with reset control to a form.

        form
            target form layout
        label
            setting label widget
        field
            primary input widget
        reset_handler
            callback that restores the default value
        """

        form.addRow(label, self._wrap_setting_field(field, reset_handler))

    def _reset_slider_value(self, row: SliderSpinBoxRow, value: float) -> None:
        """
        restore one slider row and persist the change.

        row
            slider row to update
        value
            default value to apply
        """

        row.set_value(value)
        self._emit_settings_changed()

    def _reset_density(self) -> None:
        """restore star density preset and count to defaults."""

        preset = _DEFAULT_SETTINGS.stars.density_preset
        index = self.density_combo.findData(preset)
        if index >= 0:
            self.density_combo.blockSignals(True)
            self.density_combo.setCurrentIndex(index)
            self.density_combo.blockSignals(False)
        self.star_count_row.set_value(_DEFAULT_SETTINGS.stars.star_count)
        self._emit_settings_changed()

    def _reset_star_count(self) -> None:
        """restore star count and matching density preset to defaults."""

        self.star_count_row.set_value(_DEFAULT_SETTINGS.stars.star_count)
        preset = density_preset_from_count(_DEFAULT_SETTINGS.stars.star_count)
        index = self.density_combo.findData(preset)
        if index >= 0:
            self.density_combo.blockSignals(True)
            self.density_combo.setCurrentIndex(index)
            self.density_combo.blockSignals(False)
        self._emit_settings_changed()

    def _build_project_section(self, layout: QVBoxLayout) -> None:
        form = QFormLayout()
        self._configure_form(form)

        image_widget = QWidget()
        image_layout = QVBoxLayout(image_widget)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(6)

        self.load_image_button = QPushButton()
        self.load_image_button.clicked.connect(self.load_image_requested.emit)
        image_layout.addWidget(self.load_image_button)

        self.image_label = QLabel()
        self.image_label.setObjectName("image_filename_label")
        self.image_label.setWordWrap(False)
        image_layout.addWidget(self.image_label)
        self._style_field(image_widget)

        self._label_source_image = self._create_setting_label()
        form.addRow(self._label_source_image, image_widget)

        self.resolution_combo = NoWheelComboBox()
        self.resolution_combo.currentIndexChanged.connect(self._on_resolution_changed)
        self._style_field(self.resolution_combo)
        self._label_resolution = self._create_setting_label()
        form.addRow(self._label_resolution, self.resolution_combo)

        custom_widget = QWidget()
        custom_row = QHBoxLayout(custom_widget)
        custom_row.setContentsMargins(0, 0, 0, 0)
        custom_row.setSpacing(8)
        self.width_spin = NoWheelSpinBox()
        self.width_spin.setRange(480, 7680)
        self.width_spin.setSingleStep(2)
        self.width_spin.setFixedWidth(_SPIN_WIDTH)
        self.height_spin = NoWheelSpinBox()
        self.height_spin.setRange(480, 7680)
        self.height_spin.setSingleStep(2)
        self.height_spin.setFixedWidth(_SPIN_WIDTH)
        self.width_spin.valueChanged.connect(self._on_custom_resolution_changed)
        self.height_spin.valueChanged.connect(self._on_custom_resolution_changed)
        self._label_width = QLabel()
        self._label_height = QLabel()
        custom_row.addWidget(self._label_width)
        custom_row.addWidget(self.width_spin)
        custom_row.addWidget(self._label_height)
        custom_row.addWidget(self.height_spin)
        custom_row.addStretch(1)
        self._style_field(custom_widget)
        self._label_custom = self._create_setting_label()
        form.addRow(self._label_custom, custom_widget)

        self.duration_row = SliderSpinBoxRow(3.0, 60.0, decimals=0, step=1.0, suffix=" s")
        self.duration_row.value_changed.connect(self._emit_settings_changed)
        self._style_field(self.duration_row)
        self._label_duration = self._create_setting_label()
        form.addRow(self._label_duration, self.duration_row)

        self.fps_combo = NoWheelComboBox()
        for fps in (24, 30, 60):
            self.fps_combo.addItem(f"{fps}", fps)
        self.fps_combo.currentIndexChanged.connect(self._emit_settings_changed)
        self._style_field(self.fps_combo)
        self._label_fps = self._create_setting_label()
        form.addRow(self._label_fps, self.fps_combo)

        layout.addLayout(form)

    def _build_background_section(self, layout: QVBoxLayout) -> None:
        form = QFormLayout()
        self._configure_form(form)

        self.scale_row = SliderSpinBoxRow(
            MIN_BACKGROUND_SCALE_PERCENT,
            MAX_BACKGROUND_SCALE_PERCENT,
            decimals=0,
            step=1.0,
            suffix=" %",
        )
        self.scale_row.value_changed.connect(self._emit_settings_changed)
        self._style_field(self.scale_row)
        self._label_scale = self._create_setting_label()
        self._add_setting_row(
            form,
            self._label_scale,
            self.scale_row,
            lambda: self._reset_slider_value(
                self.scale_row,
                _DEFAULT_SETTINGS.background.scale_percent,
            ),
        )

        self.zoom_row = SliderSpinBoxRow(
            0.0,
            MAX_BACKGROUND_ZOOM_PERCENT,
            decimals=1,
            step=0.5,
            suffix=" %",
        )
        self.zoom_row.value_changed.connect(self._emit_settings_changed)
        self._style_field(self.zoom_row)
        self._label_zoom = self._create_setting_label()
        self._add_setting_row(
            form,
            self._label_zoom,
            self.zoom_row,
            lambda: self._reset_slider_value(
                self.zoom_row,
                _DEFAULT_SETTINGS.background.zoom_percent,
            ),
        )

        self.rotation_row = SliderSpinBoxRow(
            -MAX_BACKGROUND_ROTATION_DEGREES,
            MAX_BACKGROUND_ROTATION_DEGREES,
            decimals=1,
            step=0.5,
            suffix="°",
        )
        self.rotation_row.value_changed.connect(self._emit_settings_changed)
        self._style_field(self.rotation_row)
        self._label_rotation = self._create_setting_label()
        self._add_setting_row(
            form,
            self._label_rotation,
            self.rotation_row,
            lambda: self._reset_slider_value(
                self.rotation_row,
                _DEFAULT_SETTINGS.background.rotation_degrees,
            ),
        )

        self.fill_frame_checkbox = QCheckBox()
        self.fill_frame_checkbox.setChecked(False)
        self.fill_frame_checkbox.toggled.connect(self._emit_settings_changed)
        self._label_fill_frame = self._create_setting_label()
        form.addRow(self._label_fill_frame, self.fill_frame_checkbox)

        layout.addLayout(form)

    def _build_focus_section(self, layout: QVBoxLayout) -> None:
        """
        build the top-level camera path section.

        layout
            section content layout
        """

        self.focus_points = FocusPointsControl()
        self.focus_points.focus_changed.connect(self._emit_settings_changed)
        self._style_field(self.focus_points)
        layout.addWidget(self.focus_points)

    def _connect_section_state_signals(self) -> None:
        """wire section expand/collapse changes to project dirty tracking."""

        for section in (
            self.project_section,
            self.background_section,
            self.focus_section,
            self.star_appearance_section,
            self.star_effects_section,
            self.star_animation_section,
        ):
            section.expanded_changed.connect(self._emit_settings_changed)

    def _apply_ui_state(self, settings: ProjectSettings) -> None:
        """restore sidebar section expand/collapse state from project settings."""

        ui = settings.ui
        self.project_section.set_expanded(ui.project_section_expanded)
        self.background_section.set_expanded(ui.background_section_expanded)
        self.focus_section.set_expanded(ui.focus_section_expanded)
        self.star_appearance_section.set_expanded(ui.star_appearance_section_expanded)
        self.star_effects_section.set_expanded(ui.star_effects_section_expanded)
        self.star_animation_section.set_expanded(ui.star_animation_section_expanded)

    def _write_ui_state(self, settings: ProjectSettings) -> None:
        """persist sidebar section expand/collapse state into project settings."""

        ui = settings.ui
        ui.project_section_expanded = self.project_section.is_expanded
        ui.background_section_expanded = self.background_section.is_expanded
        ui.focus_section_expanded = self.focus_section.is_expanded
        ui.star_appearance_section_expanded = self.star_appearance_section.is_expanded
        ui.star_effects_section_expanded = self.star_effects_section.is_expanded
        ui.star_animation_section_expanded = self.star_animation_section.is_expanded

    def _build_star_appearance_section(self, layout: QVBoxLayout) -> None:
        form = QFormLayout()
        self._configure_form(form)

        self.density_combo = NoWheelComboBox()
        for preset in (
            DensityPreset.LOW,
            DensityPreset.MEDIUM,
            DensityPreset.HIGH,
            DensityPreset.CUSTOM,
        ):
            self.density_combo.addItem("", preset)
        self.density_combo.currentIndexChanged.connect(self._on_density_changed)
        self._style_field(self.density_combo)
        self._label_density = self._create_setting_label()
        self._add_setting_row(form, self._label_density, self.density_combo, self._reset_density)

        self.star_count_row = SliderSpinBoxRow(
            MIN_STAR_COUNT,
            MAX_STAR_COUNT,
            decimals=0,
            step=1.0,
        )
        self.star_count_row.value_changed.connect(self._on_star_count_changed)
        self._style_field(self.star_count_row)
        self._label_star_count = self._create_setting_label()
        self._add_setting_row(form, self._label_star_count, self.star_count_row, self._reset_star_count)

        self.min_size_row = SliderSpinBoxRow(0.3, 3.0, decimals=1, step=0.1, suffix=" px")
        self.min_size_row.value_changed.connect(self._emit_settings_changed)
        self._style_field(self.min_size_row)
        self._label_min_size = self._create_setting_label()
        self._add_setting_row(
            form,
            self._label_min_size,
            self.min_size_row,
            lambda: self._reset_slider_value(self.min_size_row, _DEFAULT_SETTINGS.stars.min_size),
        )

        self.max_size_row = SliderSpinBoxRow(1.0, 15.0, decimals=1, step=0.1, suffix=" px")
        self.max_size_row.value_changed.connect(self._emit_settings_changed)
        self._style_field(self.max_size_row)
        self._label_max_size = self._create_setting_label()
        self._add_setting_row(
            form,
            self._label_max_size,
            self.max_size_row,
            lambda: self._reset_slider_value(self.max_size_row, _DEFAULT_SETTINGS.stars.max_size),
        )

        self.size_spread_row = SliderSpinBoxRow(0.0, 100.0, decimals=0, step=1.0, suffix=" %")
        self.size_spread_row.value_changed.connect(self._emit_settings_changed)
        self._style_field(self.size_spread_row)
        self._label_size_spread = self._create_setting_label()
        self._add_setting_row(
            form,
            self._label_size_spread,
            self.size_spread_row,
            lambda: self._reset_slider_value(
                self.size_spread_row,
                _DEFAULT_SETTINGS.stars.size_spread * 100.0,
            ),
        )

        layout.addLayout(form)

    @staticmethod
    def _create_group_separator() -> QFrame:
        """create a subtle horizontal line between setting groups."""

        line = QFrame()
        line.setObjectName("settings_group_separator")
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setFixedHeight(1)
        return line

    @staticmethod
    def _create_group_title(text: str) -> QLabel:
        """create a compact heading for a related settings group."""

        label = QLabel(text)
        label.setObjectName("settings_group_title")
        apply_settings_group_title_style(label)
        return label

    def _add_slider_row(
        self,
        form: QFormLayout,
        minimum: float,
        maximum: float,
        *,
        decimals: int = 0,
        step: float = 1.0,
        suffix: str = "",
        reset_value: float,
        after_reset: Callable[[], None] | None = None,
    ) -> tuple[SettingLabel, SliderSpinBoxRow]:
        """add a labeled slider row to a form and return label plus control."""

        row = SliderSpinBoxRow(minimum, maximum, decimals=decimals, step=step, suffix=suffix)
        self._style_field(row)
        label = self._create_setting_label()

        def reset() -> None:
            row.set_value(reset_value)
            if after_reset is not None:
                after_reset()
            self._emit_settings_changed()

        self._add_setting_row(form, label, row, reset)
        return label, row

    def _sync_dependent_slider(
        self,
        parent_row: SliderSpinBoxRow,
        child_row: SliderSpinBoxRow,
        child_label: SettingLabel,
    ) -> None:
        """
        disable a child slider when its parent is at zero.

        parent_row
            primary control
        child_row
            dependent control
        child_label
            label for the dependent control
        """

        parent_active = float(parent_row.value()) > 0.0
        child_label.setEnabled(parent_active)
        child_row.setEnabled(parent_active)

    def _build_star_effects_section(self, layout: QVBoxLayout) -> None:
        self._brightness_group_title = self._create_group_title("")
        layout.addWidget(self._brightness_group_title)

        brightness_form = QFormLayout()
        self._configure_form(brightness_form)
        self._label_brightness, self.brightness_row = self._add_slider_row(
            brightness_form,
            0.0,
            100.0,
            suffix=" %",
            reset_value=_DEFAULT_SETTINGS.stars.brightness * 100.0,
        )
        self.brightness_row.value_changed.connect(self._emit_settings_changed)
        self._label_magnitude, self.magnitude_realism_row = self._add_slider_row(
            brightness_form,
            0.0,
            100.0,
            suffix=" %",
            reset_value=_DEFAULT_SETTINGS.stars.magnitude_realism * 100.0,
        )
        self.magnitude_realism_row.value_changed.connect(self._emit_settings_changed)
        layout.addLayout(brightness_form)

        layout.addWidget(self._create_group_separator())

        self._glow_group_title = self._create_group_title("")
        layout.addWidget(self._glow_group_title)

        glow_form = QFormLayout()
        self._configure_form(glow_form)
        self._label_glow, self.glow_row = self._add_slider_row(
            glow_form,
            0.0,
            100.0,
            suffix=" %",
            reset_value=_DEFAULT_SETTINGS.stars.glow_intensity * 100.0,
            after_reset=self._sync_glow_depth_controls,
        )
        self.glow_row.value_changed.connect(self._on_glow_changed)
        self._label_glow_depth, self.glow_depth_row = self._add_slider_row(
            glow_form,
            0.0,
            100.0,
            suffix=" %",
            reset_value=_DEFAULT_SETTINGS.stars.glow_depth_boost * 100.0,
        )
        self.glow_depth_row.value_changed.connect(self._emit_settings_changed)
        layout.addLayout(glow_form)

        layout.addWidget(self._create_group_separator())

        self._color_group_title = self._create_group_title("")
        layout.addWidget(self._color_group_title)

        color_form = QFormLayout()
        self._configure_form(color_form)
        self._label_color_intensity, self.color_intensity_row = self._add_slider_row(
            color_form,
            0.0,
            100.0,
            suffix=" %",
            reset_value=_DEFAULT_SETTINGS.stars.color_intensity * 100.0,
        )
        self.color_intensity_row.value_changed.connect(self._emit_settings_changed)
        layout.addLayout(color_form)

        self._sync_glow_depth_controls()

    def _on_glow_changed(self, *_args: object) -> None:
        """sync dependent glow controls before persisting settings."""

        self._sync_glow_depth_controls()
        self._emit_settings_changed()

    def _sync_glow_depth_controls(self) -> None:
        """keep depth glow aligned with the base glow slider."""

        self._sync_dependent_slider(self.glow_row, self.glow_depth_row, self._label_glow_depth)

    def _build_star_animation_section(self, layout: QVBoxLayout) -> None:
        form = QFormLayout()
        self._configure_form(form)

        self.speed_row = SliderSpinBoxRow(0.0, 2.0, decimals=2, step=0.01)
        self.speed_row.value_changed.connect(self._emit_settings_changed)
        self._style_field(self.speed_row)
        self._label_speed = self._create_setting_label()
        self._add_setting_row(
            form,
            self._label_speed,
            self.speed_row,
            lambda: self._reset_slider_value(self.speed_row, _DEFAULT_SETTINGS.stars.speed),
        )

        layout.addLayout(form)

    def _display_image_name(self, source_image: str | None) -> str:
        """
        format source image for display.

        source_image
            stored image path
        """

        if not source_image:
            return self.tr("No image loaded")
        filename = Path(source_image).name
        metrics = QFontMetrics(self.image_label.font())
        return metrics.elidedText(
            filename,
            Qt.TextElideMode.ElideMiddle,
            max(180, self.image_label.width()),
        )

    def retranslate_ui(self) -> None:
        """refresh all translatable texts."""

        self.project_section.set_title(self.tr("Project & Video"))
        self.background_section.set_title(self.tr("Background"))
        self.focus_section.set_title(self.tr("Camera path"))
        self.focus_section.set_hint(
            self.tr(
                "Optional start and target points. Each point is the center of the video "
                "frame. Enable a point to show its marker, then drag it on the preview. "
                "Only a target starts from the image center; only a start ends at the "
                "image center.",
            ),
        )
        self.star_appearance_section.set_title(self.tr("Stars — Count & Size"))
        self.star_effects_section.set_title(self.tr("Stars — Appearance"))
        self.star_animation_section.set_title(self.tr("Stars — Animation"))

        self.load_image_button.setText(self.tr("Load image…"))
        self._label_source_image.set_text(self.tr("Image"))
        self._label_source_image.set_hint(
            self.tr(
                "Photo used as the flying-through background. "
                "Load a PNG or TIFF without embedded stars.",
            ),
        )
        self._label_resolution.set_text(self.tr("Target resolution"))
        self._label_resolution.set_hint(
            self.tr(
                "Output size of the exported video. Higher values need more memory "
                "and take longer to export.",
            ),
        )
        self._label_custom.set_text(self.tr("Custom"))
        self._label_custom.set_hint(
            self.tr("Manual width and height in pixels when no preset fits your target."),
        )
        self._label_width.setText(self.tr("Width"))
        self._label_height.setText(self.tr("Height"))
        self._label_duration.set_text(self.tr("Video length"))
        self._label_duration.set_hint(
            self.tr("Total duration of the exported clip in seconds."),
        )
        self._label_fps.set_text(self.tr("Frame rate"))
        self._label_fps.set_hint(
            self.tr(
                "Frames per second. 24 feels cinematic, 30 is standard, "
                "60 is very smooth but heavier to export.",
            ),
        )

        self.fps_combo.setItemText(0, self.tr("{fps} fps").format(fps=24))
        self.fps_combo.setItemText(1, self.tr("{fps} fps").format(fps=30))
        self.fps_combo.setItemText(2, self.tr("{fps} fps").format(fps=60))

        self._label_scale.set_text(self.tr("Image scale"))
        self._label_scale.set_hint(
            self.tr(
                "Base size of the source image in the video. 100% fills the frame; "
                "smaller values shrink the image, larger values zoom in further.",
            ),
        )
        self._label_zoom.set_text(self.tr("Zoom in"))
        self._label_zoom.set_hint(
            self.tr("How strongly the image slowly enlarges over the full video length."),
        )
        self._label_rotation.set_text(self.tr("Rotation"))
        self._label_rotation.set_hint(
            self.tr(
                "Slow rotation of the image over the full video length. "
                "Positive values rotate clockwise.",
            ),
        )
        self.focus_points.retranslate_ui()
        self._label_fill_frame.set_text(self.tr("Frame edges"))
        self._label_fill_frame.set_hint(
            self.tr(
                "Automatically scales and shifts the image when needed so no black "
                "borders appear during focus and rotation.",
            ),
        )
        self.fill_frame_checkbox.setText(self.tr("Avoid empty areas by\nscaling up"))

        self._label_density.set_text(self.tr("Density"))
        self._label_density.set_hint(
            self.tr(
                "How many stars are generated. Presets set the count automatically; "
                "Custom lets you choose the exact number.",
            ),
        )
        self.density_combo.setItemText(0, self.tr("Low"))
        self.density_combo.setItemText(1, self.tr("Medium"))
        self.density_combo.setItemText(2, self.tr("High"))
        self.density_combo.setItemText(3, self.tr("Custom"))
        self._label_star_count.set_text(self.tr("Star count"))
        self._label_star_count.set_hint(
            self.tr("More stars create a denser field. Very high values can slow export."),
        )
        self._label_min_size.set_text(self.tr("Smallest stars"))
        self._label_min_size.set_hint(
            self.tr(
                "Pixel size of the faintest stars. Keep this below largest stars "
                "for a natural look."
            ),
        )
        self._label_max_size.set_text(self.tr("Largest stars"))
        self._label_max_size.set_hint(
            self.tr(
                "Pixel size of the largest nearby stars. Higher values make bright stars "
                "stand out more clearly.",
            ),
        )
        self._label_size_spread.set_text(self.tr("Size spread"))
        self._label_size_spread.set_hint(
            self.tr(
                "How many mid-sized and large stars appear. 0% keeps the compact default; "
                "higher values fill the field with more clearly larger stars.",
            ),
        )

        self._brightness_group_title.setText(self.tr("Brightness"))
        self._label_brightness.set_text(self.tr("Strength"))
        self._label_brightness.set_hint(
            self.tr("Overall brightness multiplier for all stars. 100% is the default look."),
        )
        self._label_magnitude.set_text(self.tr("Spread"))
        self._label_magnitude.set_hint(
            self.tr("More realistic mix of faint and bright stars."),
        )

        self._glow_group_title.setText(self.tr("Glow"))
        self._label_glow.set_text(self.tr("Strength"))
        self._label_glow.set_hint(
            self.tr("Soft halo around bright stars. Set to 0% to turn glow off completely."),
        )
        self._label_glow_depth.set_text(self.tr("By depth"))
        self._label_glow_depth.set_hint(
            self.tr("Extra glow for nearby stars. Enabled when Strength is above 0%."),
        )

        self._color_group_title.setText(self.tr("Color"))
        self._label_color_intensity.set_text(self.tr("Intensity"))
        self._label_color_intensity.set_hint(
            self.tr(
                "How colorful stars look. 0% = white stars, higher = more spectral color. "
                "Large bright stars lean blue; mid-sized stars often stay yellow or white.",
            ),
        )

        self._label_speed.set_text(self.tr("Flight speed"))
        self._label_speed.set_hint(
            self.tr(
                "Star motion over time, independent of video length. "
                "1.0 matches the previous default feel of a 10s clip."
            ),
        )

        for row in self._setting_field_rows:
            row.retranslate_ui()

        self._populate_resolution_combo(preserve_selection=True)

    def _populate_resolution_combo(self, *, preserve_selection: bool) -> None:
        current_size = (self.width_spin.value(), self.height_spin.value())
        current_custom = self.resolution_combo.currentData() == "custom"

        self.resolution_combo.blockSignals(True)
        self.resolution_combo.clear()
        for key, _size in _RESOLUTION_CHOICES:
            self.resolution_combo.addItem(self._resolution_label(key), key)
        self.resolution_combo.addItem(self.tr("Custom"), "custom")

        if preserve_selection:
            if current_custom:
                self.resolution_combo.setCurrentIndex(self.resolution_combo.count() - 1)
            else:
                matched = False
                for index, (_key, size) in enumerate(_RESOLUTION_CHOICES):
                    if size == current_size:
                        self.resolution_combo.setCurrentIndex(index)
                        matched = True
                        break
                if not matched:
                    self.resolution_combo.setCurrentIndex(self.resolution_combo.count() - 1)
        self.resolution_combo.blockSignals(False)

    def _resolution_label(self, key: str) -> str:
        labels = {
            "portrait_1080": self.tr("1080 × 1920 (Portrait)"),
            "landscape_1080": self.tr("1920 × 1080 (Landscape)"),
            "portrait_4k": self.tr("2160 × 3840 (4K Portrait)"),
        }
        return labels[key]

    def _updates_blocked(self) -> bool:
        return self._update_block_depth > 0

    def _begin_update_block(self) -> None:
        self._update_block_depth += 1

    def _end_update_block(self) -> None:
        self._update_block_depth = max(0, self._update_block_depth - 1)

    def _emit_settings_changed(self, *_args: object) -> None:
        if not self._updates_blocked():
            self.settings_changed.emit()

    def _on_resolution_changed(self) -> None:
        if self._updates_blocked():
            return

        data = self.resolution_combo.currentData()
        if data != "custom":
            for key, size in _RESOLUTION_CHOICES:
                if key == data:
                    self.width_spin.blockSignals(True)
                    self.height_spin.blockSignals(True)
                    self.width_spin.setValue(size[0])
                    self.height_spin.setValue(size[1])
                    self.width_spin.blockSignals(False)
                    self.height_spin.blockSignals(False)
                    break
        self._emit_settings_changed()

    def _on_custom_resolution_changed(self, *_args: object) -> None:
        if self._updates_blocked():
            return

        current_size = (self.width_spin.value(), self.height_spin.value())
        matched = False
        for index, (_key, size) in enumerate(_RESOLUTION_CHOICES):
            if size == current_size:
                self.resolution_combo.blockSignals(True)
                self.resolution_combo.setCurrentIndex(index)
                self.resolution_combo.blockSignals(False)
                matched = True
                break

        if not matched:
            self.resolution_combo.blockSignals(True)
            self.resolution_combo.setCurrentIndex(self.resolution_combo.count() - 1)
            self.resolution_combo.blockSignals(False)

        self._emit_settings_changed()

    def _on_density_changed(self) -> None:
        if self._updates_blocked():
            return

        preset = self.density_combo.currentData()
        if preset != DensityPreset.CUSTOM:
            self.star_count_row.set_value(DENSITY_STAR_COUNTS[preset])
        self._emit_settings_changed()

    def _on_star_count_changed(self, value: float) -> None:
        del value
        if self._updates_blocked():
            return

        preset = density_preset_from_count(int(self.star_count_row.value()))
        self.density_combo.blockSignals(True)
        index = self.density_combo.findData(preset)
        if index >= 0:
            self.density_combo.setCurrentIndex(index)
        self.density_combo.blockSignals(False)
        self._emit_settings_changed()

    def set_project(self, project: Project, *, project_path: Path | None = None) -> None:
        """
        load project values into controls.

        project
            project to display
        project_path
            optional on-disk project path for resolving relative image paths
        """

        self._project_path = project_path
        self._begin_update_block()
        settings = project.settings

        if project.source_image:
            self.image_label.setText(self._display_image_name(project.source_image))
        else:
            self.image_label.setText(self.tr("No image loaded"))

        resolution = settings.resolution
        matched = False
        for index, (_key, size) in enumerate(_RESOLUTION_CHOICES):
            if size == (resolution.width, resolution.height):
                self.resolution_combo.setCurrentIndex(index)
                matched = True
                break
        if not matched:
            self.resolution_combo.setCurrentIndex(self.resolution_combo.count() - 1)
        self.width_spin.setValue(resolution.width)
        self.height_spin.setValue(resolution.height)

        self.duration_row.set_value(settings.duration_seconds)
        fps_index = self.fps_combo.findData(settings.fps)
        if fps_index >= 0:
            self.fps_combo.setCurrentIndex(fps_index)

        background = settings.background
        self.scale_row.set_value(background.scale_percent)
        self.zoom_row.set_value(background.zoom_percent)
        self.rotation_row.set_value(background.rotation_degrees)
        self.fill_frame_checkbox.setChecked(background.fill_frame)
        self._sync_focus_controls(project)

        stars = settings.stars
        density_index = self.density_combo.findData(stars.density_preset)
        if density_index >= 0:
            self.density_combo.setCurrentIndex(density_index)
        self.star_count_row.set_value(stars.star_count)
        self.min_size_row.set_value(stars.min_size)
        self.max_size_row.set_value(stars.max_size)
        self.size_spread_row.set_value(stars.size_spread * 100.0)
        self.brightness_row.set_value(stars.brightness * 100.0)
        self.glow_row.set_value(stars.glow_intensity * 100.0)
        self.glow_depth_row.set_value(stars.glow_depth_boost * 100.0)
        self._sync_glow_depth_controls()
        self.color_intensity_row.set_value(stars.color_intensity * 100.0)
        self.magnitude_realism_row.set_value(stars.magnitude_realism * 100.0)
        self.speed_row.set_value(stars.speed)
        self._apply_ui_state(settings)
        self._end_update_block()

    def apply_to_project(self, project: Project) -> None:
        """
        write control values back to project.

        project
            project to update
        """

        settings = project.settings
        settings.resolution.width = self.width_spin.value()
        settings.resolution.height = self.height_spin.value()
        settings.duration_seconds = float(self.duration_row.value())
        settings.fps = int(self.fps_combo.currentData() or 30)

        background = settings.background
        background.scale_percent = float(self.scale_row.value())
        background.zoom_percent = float(self.zoom_row.value())
        background.rotation_degrees = float(self.rotation_row.value())
        background.fill_frame = self.fill_frame_checkbox.isChecked()
        (
            start_enabled,
            start_x,
            start_y,
            end_enabled,
            end_x,
            end_y,
        ) = self.focus_points.point_values()
        background.start_focus_enabled = start_enabled
        background.start_focus_x = start_x
        background.start_focus_y = start_y
        background.end_focus_enabled = end_enabled
        background.end_focus_x = end_x
        background.end_focus_y = end_y

        stars = settings.stars
        stars.density_preset = coerce_density_preset(self.density_combo.currentData())
        stars.star_count = int(self.star_count_row.value())
        stars.min_size = float(self.min_size_row.value())
        stars.max_size = float(self.max_size_row.value())
        stars.size_spread = float(self.size_spread_row.value()) / 100.0
        stars.brightness = float(self.brightness_row.value()) / 100.0
        stars.glow_intensity = float(self.glow_row.value()) / 100.0
        stars.glow_depth_boost = float(self.glow_depth_row.value()) / 100.0
        stars.color_intensity = float(self.color_intensity_row.value()) / 100.0
        stars.magnitude_realism = float(self.magnitude_realism_row.value()) / 100.0
        stars.speed = float(self.speed_row.value())
        self._write_ui_state(settings)

    def _sync_focus_controls(self, project: Project) -> None:
        """
        sync focus path controls with the current project image and settings.

        project
            current project
        """

        background = project.settings.background
        image_path = resolve_source_image_path(self._project_path, project.source_image)
        has_image = image_path is not None and image_path.is_file()

        self.focus_points.setEnabled(has_image)

        if not has_image:
            self.focus_points.clear_image()
            self.focus_points.set_points(False, 0.5, 0.5, False, 0.5, 0.5)
            return

        try:
            source_bgr = load_image_bgr(str(image_path))
            source_rgb = bgr_to_rgb(source_bgr)
            preview_image = numpy_rgb_to_qimage(source_rgb, screen=self.screen())
            source_h, source_w = source_rgb.shape[:2]
            self.focus_points.set_image(preview_image, source_w, source_h)
        except (OSError, ValueError):
            self.focus_points.clear_image()
            self.focus_points.setEnabled(False)
            return

        self.focus_points.set_points(
            background.start_focus_enabled,
            background.start_focus_x,
            background.start_focus_y,
            background.end_focus_enabled,
            background.end_focus_x,
            background.end_focus_y,
        )


__all__ = ["SettingsPanel"]
