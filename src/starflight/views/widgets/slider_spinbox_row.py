"""Keep a slider and numeric input on the same value."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from starflight.views.widgets.no_wheel_widgets import NoWheelDoubleSpinBox, NoWheelSlider

_SPINBOX_WIDTH = 76


class SliderSpinBoxRow(QWidget):
    """slider and spinbox row for numeric settings."""

    value_changed = Signal(float)

    def __init__(
        self,
        minimum: float,
        maximum: float,
        decimals: int = 1,
        step: float = 0.1,
        suffix: str = "",
        parent: QWidget | None = None,
    ) -> None:
        """
        create linked slider and spinbox.

        minimum
            minimum value
        maximum
            maximum value
        decimals
            decimal places in spinbox
        step
            spinbox step size
        suffix
            optional suffix for spinbox
        parent
            optional parent widget
        """

        super().__init__(parent)
        self._decimals = decimals
        self._scale = 10**decimals

        self.slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(int(minimum * self._scale))
        self.slider.setMaximum(int(maximum * self._scale))

        self.spinbox = NoWheelDoubleSpinBox()
        self.spinbox.setDecimals(decimals)
        self.spinbox.setRange(minimum, maximum)
        self.spinbox.setSingleStep(step)
        self.spinbox.setFixedWidth(_SPINBOX_WIDTH)
        if suffix:
            self.spinbox.setSuffix(suffix)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slider, stretch=1)
        layout.addWidget(self.spinbox)

        self.slider.valueChanged.connect(self._on_slider_changed)
        self.spinbox.valueChanged.connect(self._on_spinbox_changed)

    def _on_slider_changed(self, value: int) -> None:
        """sync spinbox from slider."""

        self.spinbox.blockSignals(True)
        self.spinbox.setValue(value / self._scale)
        self.spinbox.blockSignals(False)
        self.value_changed.emit(self.spinbox.value())

    def _on_spinbox_changed(self, value: float) -> None:
        """sync slider from spinbox."""

        self.slider.blockSignals(True)
        self.slider.setValue(round(value * self._scale))
        self.slider.blockSignals(False)
        self.value_changed.emit(value)

    def set_value(self, value: float) -> None:
        """
        set current value without duplicate signals.

        value
            new value
        """

        self.slider.blockSignals(True)
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(value)
        self.slider.setValue(round(value * self._scale))
        self.spinbox.blockSignals(False)
        self.slider.blockSignals(False)

    def value(self) -> float:
        """return current value."""

        return float(self.spinbox.value())


__all__ = ["SliderSpinBoxRow"]
