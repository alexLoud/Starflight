"""Define and apply the shared Qt color palette and style sheet."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from starflight.app.constants import package_dir

APP_BG = "#0C0F14"
PANEL_BG = "#141A22"
SURFACE_BG = "#1A222C"
SURFACE_ALT_BG = "#10151C"
BORDER = "#2B3544"
BORDER_FOCUS = "#3D5168"
TEXT_PRIMARY = "#E4EBF4"
TEXT_FORM_LABEL = "#F5F8FC"
TEXT_FORM_LABEL_DISABLED = "#A3B0C0"
TEXT_GROUP_TITLE = "#FFFFFF"
TEXT_MUTED = "#8A97A8"
TEXT_DISABLED = "#5C6775"
ACCENT = "#3A6EA5"
ACCENT_HOVER = "#4A82BE"
ACCENT_PRESSED = "#2F5A8C"
ACCENT_SELECTION = "#2E4A66"
TIMELINE_TRACK = "#151C26"
TIMELINE_PLAYHEAD = "#E86A5A"
TIMELINE_RULER = "#6B7A8F"
CHECKER_A = "#2A3038"
CHECKER_B = "#1E242C"
COMBO_ARROW_ICON = (package_dir() / "assets" / "icons" / "combo-arrow.svg").as_posix()


def apply_dark_theme(app: QApplication) -> None:
    """apply consistent dark theme to the entire ui."""

    app.setStyle("Fusion")
    app.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont))
    app.setPalette(_build_palette())
    app.setStyleSheet(_build_stylesheet())


def _build_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(APP_BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(SURFACE_ALT_BG))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(SURFACE_BG))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(PANEL_BG))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(PANEL_BG))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT_SELECTION))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_MUTED))
    return palette


def _build_stylesheet() -> str:
    return f"""
* {{
    font-size: 13px;
}}

QMainWindow#main_window {{
    background-color: {APP_BG};
    color: {TEXT_PRIMARY};
}}

QWidget#central_workspace {{
    background-color: {APP_BG};
}}

QMenuBar {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER};
    padding: 2px 0;
    spacing: 2px;
}}

QMenuBar::item {{
    padding: 5px 12px;
    background: transparent;
    border-radius: 4px;
}}

QMenuBar::item:selected {{
    background-color: {ACCENT_SELECTION};
}}

QMenu {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 28px 6px 16px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {ACCENT_SELECTION};
}}

QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
}}

QToolBar#toolbar_main {{
    background-color: {PANEL_BG};
    border-bottom: 1px solid {BORDER};
    spacing: 4px;
    padding: 4px 10px;
}}

QToolBar#toolbar_main::separator {{
    width: 1px;
    background: {BORDER_FOCUS};
    margin: 6px 10px;
}}

QToolBar#toolbar_main QToolButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 4px 10px;
    margin: 0 2px;
    min-width: 0;
    min-height: 28px;
    color: {TEXT_PRIMARY};
    font-size: 12px;
}}

QToolBar#toolbar_main QToolButton:hover {{
    background-color: {SURFACE_BG};
    border-color: {BORDER};
}}

QToolBar#toolbar_main QToolButton:pressed {{
    background-color: {ACCENT_PRESSED};
    border-color: {ACCENT};
}}

QToolBar#toolbar_main QToolButton:disabled {{
    color: {TEXT_DISABLED};
}}

QToolBar#toolbar_zoom {{
    background-color: transparent;
    border: none;
    spacing: 2px;
    padding: 0;
}}

QToolBar#toolbar_zoom QToolButton {{
    background-color: {SURFACE_BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 3px 8px;
    min-height: 24px;
    color: {TEXT_PRIMARY};
}}

QToolBar#toolbar_zoom QToolButton:hover {{
    border-color: {BORDER_FOCUS};
    background-color: #222C38;
}}

QToolBar#toolbar_zoom QToolButton:pressed {{
    background-color: {ACCENT_PRESSED};
}}

QWidget#timeline_transport,
QWidget#timeline_zoom {{
    background-color: {PANEL_BG};
}}

QWidget#timeline_transport {{
    border-right: 1px solid {BORDER};
}}

QWidget#timeline_zoom {{
    border-left: 1px solid {BORDER};
}}

QLabel#zoom_level_label {{
    color: {TEXT_MUTED};
    font-size: 11px;
    padding: 0 4px;
    min-width: 44px;
    max-width: 44px;
}}

QStatusBar {{
    background-color: {PANEL_BG};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
}}

QStatusBar::item {{
    border: none;
}}

QScrollArea#settings_scroll {{
    background-color: {PANEL_BG};
    border: none;
    border-left: 1px solid {BORDER};
}}

QScrollArea#settings_scroll > QWidget > QWidget {{
    background-color: {PANEL_BG};
}}

QScrollBar:vertical {{
    background: {SURFACE_ALT_BG};
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 24px;
    border-radius: 5px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background: {BORDER_FOCUS};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {SURFACE_ALT_BG};
    height: 10px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER};
    min-width: 24px;
    border-radius: 5px;
    margin: 2px;
}}

QWidget#collapsible_section {{
    background-color: {PANEL_BG};
}}

QWidget#collapsible_section_header {{
    background-color: #243040;
    border: none;
    border-top: 1px solid #334155;
    border-bottom: 1px solid {BORDER};
    min-height: 36px;
}}

QWidget#collapsible_section_header:hover {{
    background-color: #2B3A4D;
}}

QLabel#collapsible_section_arrow {{
    color: {TEXT_MUTED};
    font-size: 20px;
    padding: 0;
}}

QLabel#collapsible_section_icon {{
    background: transparent;
}}

QLabel#collapsible_section_title {{
    color: {TEXT_PRIMARY};
    font-weight: 600;
    font-size: 12px;
}}

QLabel#focus_points_summary {{
    color: {TEXT_MUTED};
    font-size: 11px;
    padding: 0;
}}

QWidget#focus_points_control {{
    background: transparent;
}}

QWidget#focus_points_canvas {{
    background: transparent;
}}

QPushButton#focus_point_toggle {{
    min-width: 72px;
}}

QPushButton#focus_point_toggle:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    color: #FFFFFF;
    font-weight: 600;
}}

QPushButton#focus_point_toggle:checked:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}

QWidget#collapsible_section_content {{
    background-color: {PANEL_BG};
}}

QWidget#collapsible_section_nested {{
    background-color: transparent;
}}

QWidget#collapsible_section_header_nested {{
    background-color: #1A222C;
    border: 1px solid {BORDER};
    border-radius: 5px;
    min-height: 30px;
}}

QWidget#collapsible_section_header_nested:hover {{
    background-color: #222C38;
    border-color: {BORDER_FOCUS};
}}

QLabel#collapsible_section_title_nested {{
    color: {TEXT_PRIMARY};
    font-weight: 600;
    font-size: 12px;
}}

QWidget#preview_workspace {{
    background-color: {SURFACE_ALT_BG};
}}

QWidget#preview_container {{
    background-color: {SURFACE_ALT_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}

QWidget#zoom_toolbar_row {{
    background-color: transparent;
}}

QGraphicsView#preview_viewport {{
    background-color: {SURFACE_ALT_BG};
    border: none;
}}

QStackedWidget#root_stack {{
    background-color: {APP_BG};
    border: none;
}}

QWidget#welcome_splash {{
    background-color: {APP_BG};
}}

QWidget#welcome_splash_frame,
QLabel#welcome_splash_logo,
QWidget#welcome_actions_host,
QWidget#welcome_recent_list,
QWidget#welcome_recent_section {{
    background-color: transparent;
}}

QWidget#welcome_splash_meta_bar {{
    background-color: rgba(20, 26, 34, 170);
}}

QFrame#welcome_action_button {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 0;
}}

QFrame#welcome_action_button:hover {{
    background-color: {SURFACE_BG};
    border-color: {BORDER_FOCUS};
}}

QFrame#welcome_action_button:focus {{
    background-color: {SURFACE_BG};
    border-color: {ACCENT_HOVER};
}}

QLabel#welcome_action_icon {{
    background-color: rgba(58, 110, 165, 70);
    border: 1px solid rgba(122, 186, 232, 70);
    border-radius: 10px;
}}

QLabel#welcome_action_title {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
    font-size: 15px;
    font-weight: 600;
    padding: 0;
}}

QLabel#welcome_action_subtitle {{
    color: {TEXT_MUTED};
    background-color: transparent;
    font-size: 12px;
    padding: 0;
}}

QFrame#welcome_recent_panel {{
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QLabel#welcome_recent_heading {{
    color: {TEXT_MUTED};
    background-color: transparent;
    font-size: 12px;
    font-weight: 600;
    padding: 0 2px;
}}

QPushButton#welcome_recent_row {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 0;
    min-height: 58px;
    text-align: left;
}}

QPushButton#welcome_recent_row:hover,
QPushButton#welcome_recent_row:focus {{
    background-color: {SURFACE_BG};
    border-color: {BORDER};
}}

QPushButton#welcome_recent_row:pressed {{
    background-color: {ACCENT_SELECTION};
}}

QLabel#welcome_recent_icon {{
    background-color: {SURFACE_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QLabel#welcome_recent_name {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
    font-size: 14px;
    font-weight: 600;
    padding: 0;
}}

QLabel#welcome_recent_location {{
    color: {TEXT_MUTED};
    background-color: transparent;
    font-size: 12px;
    padding: 0;
}}

QLabel#welcome_recent_date {{
    color: {TEXT_MUTED};
    background-color: transparent;
    font-size: 12px;
    padding: 0;
}}

QLabel#welcome_splash_meta {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
    font-size: 12px;
    padding: 0;
}}

QLabel#welcome_splash_update {{
    color: {ACCENT};
    background-color: transparent;
    font-size: 12px;
    padding: 0;
}}

QLabel#welcome_splash_update a {{
    color: {ACCENT};
    text-decoration: none;
}}

QLabel#welcome_splash_update a:hover {{
    text-decoration: underline;
}}

QLabel#about_dialog_title {{
    color: {TEXT_PRIMARY};
    font-size: 18px;
}}

QLabel#about_dialog_version,
QLabel#about_dialog_author {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}

QLabel#about_dialog_description {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}

QLabel#about_dialog_link {{
    color: {ACCENT};
    font-size: 12px;
}}

QLabel#about_dialog_link a {{
    color: {ACCENT};
    text-decoration: none;
}}

QLabel#about_dialog_link a:hover {{
    text-decoration: underline;
}}

QWidget#timeline_widget {{
    background-color: {PANEL_BG};
    border-top: 1px solid {BORDER};
}}

QToolButton#setting_reset_button {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 0;
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
}}

QToolButton#setting_reset_button:hover {{
    background-color: {SURFACE_BG};
    border-color: {BORDER};
}}

QToolButton#setting_reset_button:pressed {{
    background-color: {ACCENT_PRESSED};
    border-color: {BORDER_FOCUS};
}}

QToolButton#setting_reset_button:disabled {{
    opacity: 0.35;
}}

QPushButton {{
    background-color: {SURFACE_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 5px 12px;
    min-height: 24px;
}}

QPushButton:hover {{
    border-color: {BORDER_FOCUS};
    background-color: #222C38;
}}

QPushButton:pressed {{
    background-color: {ACCENT_PRESSED};
}}

QPushButton:disabled {{
    color: {TEXT_DISABLED};
    border-color: {BORDER};
}}

QPushButton#primary_button {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    color: #FFFFFF;
    font-weight: 600;
}}

QPushButton#primary_button:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}

QPushButton#primary_button:disabled {{
    background-color: {SURFACE_BG};
    border-color: {BORDER};
    color: {TEXT_DISABLED};
}}

QToolButton#transport_button {{
    background-color: {SURFACE_BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 0;
    min-width: 32px;
    min-height: 32px;
    max-width: 32px;
    max-height: 32px;
}}

QToolButton#transport_button:hover {{
    border-color: {BORDER_FOCUS};
}}

QToolButton#transport_button:pressed {{
    background-color: {ACCENT_PRESSED};
}}

QToolButton#transport_button:checked {{
    border-color: {BORDER_FOCUS};
    background-color: {ACCENT_PRESSED};
}}

QToolButton#stars_toggle_button {{
    background-color: {SURFACE_BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 0 10px 0 6px;
    min-height: 32px;
    max-height: 32px;
    color: {TEXT_PRIMARY};
    font-size: 12px;
}}

QToolButton#stars_toggle_button:hover {{
    border-color: {BORDER_FOCUS};
}}

QToolButton#stars_toggle_button:pressed {{
    background-color: {ACCENT_PRESSED};
}}

QToolButton#stars_toggle_button:checked {{
    border-color: {BORDER_FOCUS};
    background-color: {ACCENT_PRESSED};
}}

QLabel#timeline_time_label {{
    color: {TEXT_MUTED};
    font-size: 11px;
    padding: 0 4px;
}}

QLabel#image_filename_label {{
    color: {TEXT_MUTED};
    font-size: 11px;
    padding: 2px 0 0 0;
}}

QComboBox {{
    background-color: {SURFACE_ALT_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 4px 34px 4px 10px;
    min-height: 24px;
    selection-background-color: {ACCENT_SELECTION};
}}

QComboBox:hover {{
    border-color: {BORDER_FOCUS};
    background-color: #131A23;
}}

QComboBox:focus {{
    border-color: {BORDER_FOCUS};
}}

QComboBox::drop-down {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 28px;
    border-left: 1px solid {BORDER};
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
    background-color: {SURFACE_BG};
}}

QComboBox::down-arrow {{
    image: url("{COMBO_ARROW_ICON}");
    width: 10px;
    height: 10px;
}}

QComboBox::down-arrow:on {{
    top: 1px;
}}

QComboBox::drop-down:hover {{
    background-color: #222C38;
    border-left-color: {BORDER_FOCUS};
}}

QComboBox:disabled {{
    color: {TEXT_DISABLED};
    border-color: {BORDER};
    background-color: {SURFACE_ALT_BG};
}}

QComboBox::drop-down:disabled {{
    background-color: {SURFACE_ALT_BG};
}}

QComboBox QAbstractItemView {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_SELECTION};
    selection-color: {TEXT_PRIMARY};
    outline: none;
    padding: 4px 0;
}}

QComboBox#resolution_combo {{
    icon-size: 16px;
}}

QComboBox#resolution_combo QAbstractItemView::item {{
    min-height: 22px;
    padding: 4px 10px 4px 6px;
}}

QSpinBox, QDoubleSpinBox {{
    background-color: {SURFACE_ALT_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 3px 6px;
    min-height: 24px;
}}

QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {BORDER_FOCUS};
}}

QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: {TEXT_DISABLED};
    background-color: {SURFACE_ALT_BG};
    border-color: {BORDER};
}}

QSlider::groove:horizontal:disabled {{
    background: #1E2630;
}}

QSlider::handle:horizontal:disabled {{
    background: #3A4554;
    border-color: #3A4554;
}}

QSlider::sub-page:horizontal:disabled {{
    background: #2A3542;
}}

QWidget#setting_label:disabled QLabel#form_label {{
    color: {TEXT_FORM_LABEL_DISABLED};
}}

QWidget#setting_label:disabled QLabel#setting_hint_icon {{
    opacity: 0.28;
}}

QLineEdit {{
    background-color: {SURFACE_ALT_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 5px 8px;
    min-height: 24px;
    selection-background-color: {ACCENT_SELECTION};
}}

QLineEdit:hover {{
    border-color: {BORDER_FOCUS};
}}

QLineEdit:focus {{
    border-color: {ACCENT};
}}

QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDER};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    margin: -5px 0;
    background: {TEXT_PRIMARY};
    border: 2px solid {ACCENT};
    border-radius: 7px;
}}

QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}

QCheckBox {{
    spacing: 8px;
    color: {TEXT_PRIMARY};
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {SURFACE_ALT_BG};
}}

QCheckBox::indicator:hover {{
    border-color: {BORDER_FOCUS};
}}

QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

QLabel {{
    color: {TEXT_PRIMARY};
}}

QLabel#settings_group_title {{
    color: {TEXT_GROUP_TITLE};
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.4px;
    padding: 4px 0 2px 0;
}}

QFrame#settings_group_separator {{
    color: {BORDER};
    background-color: {BORDER};
    border: none;
    max-height: 1px;
    margin: 10px 0 6px 0;
}}

QLabel#setting_hint_icon {{
    background: transparent;
    opacity: 0.38;
}}

QLabel#setting_hint_icon:hover {{
    opacity: 0.62;
}}

QToolTip {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 8px 10px;
}}

QLabel#section_hint {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}

QProgressBar {{
    background-color: {SURFACE_ALT_BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    text-align: center;
    color: {TEXT_PRIMARY};
    min-height: 18px;
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 4px;
}}

QDialog {{
    background-color: {APP_BG};
    color: {TEXT_PRIMARY};
}}

QFileDialog {{
    background-color: {APP_BG};
    color: {TEXT_PRIMARY};
}}

QSplitter::handle {{
    background-color: {BORDER};
    width: 1px;
}}

QWidget#setting_label QLabel#form_label,
QLabel#form_label {{
    color: {TEXT_FORM_LABEL};
    font-weight: 500;
}}
""".strip()


__all__ = [
    "ACCENT",
    "ACCENT_HOVER",
    "ACCENT_PRESSED",
    "ACCENT_SELECTION",
    "APP_BG",
    "BORDER",
    "BORDER_FOCUS",
    "CHECKER_A",
    "CHECKER_B",
    "PANEL_BG",
    "SURFACE_ALT_BG",
    "SURFACE_BG",
    "TEXT_DISABLED",
    "TEXT_FORM_LABEL",
    "TEXT_FORM_LABEL_DISABLED",
    "TEXT_GROUP_TITLE",
    "TEXT_MUTED",
    "TEXT_PRIMARY",
    "TIMELINE_PLAYHEAD",
    "TIMELINE_RULER",
    "TIMELINE_TRACK",
    "apply_dark_theme",
]
