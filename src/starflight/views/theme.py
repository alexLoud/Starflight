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
TEXT_DISABLED = "#718095"
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

QFrame#toolbar_main {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #18212D, stop:1 {PANEL_BG});
    border-bottom: 1px solid {BORDER};
}}

QToolButton#toolbar_button {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    color: {TEXT_FORM_LABEL_DISABLED};
    font-weight: 400;
    padding: 6px 10px;
}}

QToolButton#toolbar_button:hover {{
    background-color: {SURFACE_BG};
    border-color: {BORDER};
}}

QToolButton#toolbar_button:pressed {{
    background-color: {ACCENT_PRESSED};
    border-color: {ACCENT};
}}

QToolButton#toolbar_button:disabled {{
    color: {TEXT_DISABLED};
}}

QToolButton#toolbar_export_button {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {ACCENT_HOVER}, stop:1 {ACCENT});
    border: 1px solid {ACCENT};
    border-radius: 8px;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 600;
    padding: 7px 16px;
}}

QToolButton#toolbar_export_button:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #5790CF, stop:1 #4376AE);
    border-color: {ACCENT_HOVER};
}}

QToolButton#toolbar_export_button:pressed {{
    background: {ACCENT_PRESSED};
    border-color: {ACCENT_PRESSED};
}}

QToolButton#toolbar_export_button:disabled {{
    background: {SURFACE_BG};
    border-color: {BORDER};
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

QWidget#preview_footer {{
    background-color: {PANEL_BG};
    border-top: 1px solid {BORDER};
}}

QLabel#zoom_level_label {{
    color: {TEXT_MUTED};
    font-size: 12px;
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
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #273444, stop:1 #212C3B);
    border: none;
    border-top: 1px solid #334155;
    border-bottom: 1px solid {BORDER};
    min-height: 36px;
}}

QWidget#collapsible_section_header:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2D3D52, stop:1 #263344);
}}

QWidget#collapsible_section[available="false"] QWidget#collapsible_section_header {{
    background-color: #1A222C;
}}

QWidget#collapsible_section[available="false"] QWidget#collapsible_section_header:hover {{
    background-color: #1A222C;
}}

QWidget#collapsible_section[available="false"] QLabel#collapsible_section_title,
QWidget#collapsible_section[available="false"] QLabel#collapsible_section_arrow {{
    color: {TEXT_DISABLED};
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

QLabel#focus_points_summary,
QLabel#crop_summary {{
    color: {TEXT_MUTED};
    font-size: 11px;
    padding: 0;
}}

QWidget#focus_points_control,
QWidget#crop_control {{
    background: transparent;
}}

QWidget#focus_points_canvas,
QWidget#crop_canvas {{
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

QWidget#preview_footer {{
    background-color: {PANEL_BG};
    border-top: 1px solid {BORDER};
}}

QWidget#preview_container {{
    background-color: {SURFACE_ALT_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}

QWidget#preview_empty_state {{
    background-color: {SURFACE_ALT_BG};
    border: 1px dashed {BORDER_FOCUS};
    border-radius: 5px;
}}

QWidget#preview_empty_state[dragActive="true"] {{
    background-color: {ACCENT_SELECTION};
    border: 1px solid {ACCENT_HOVER};
}}

QLabel#preview_empty_title {{
    color: {TEXT_PRIMARY};
    font-size: 16px;
    font-weight: 600;
}}

QLabel#preview_empty_message {{
    color: {TEXT_MUTED};
    max-width: 360px;
}}

QLabel#preview_empty_hint {{
    color: {TEXT_MUTED};
}}

QPushButton#preview_empty_load_button {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT_HOVER};
    border-radius: 6px;
    color: #FFFFFF;
    font-weight: 600;
    padding: 8px 14px;
}}

QPushButton#preview_empty_load_button:hover {{
    background-color: {ACCENT_HOVER};
}}

QLabel#preview_empty_edge_warning {{
    background-color: {PANEL_BG};
    border: 1px solid #70572F;
    border-radius: 4px;
    color: #E5B56A;
    font-size: 11px;
    margin: 10px;
    padding: 4px 7px;
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
QWidget#welcome_hero_host,
QWidget#welcome_content_host,
QWidget#welcome_actions_host,
QWidget#welcome_recent_list,
QWidget#welcome_recent_section {{
    background-color: transparent;
}}

QWidget#welcome_splash_meta_bar {{
    background-color: transparent;
}}

QFrame#welcome_action_button {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1C2534, stop:1 #131A24);
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 0;
}}

QFrame#welcome_action_button:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #222E40, stop:1 #17202C);
    border-color: {BORDER_FOCUS};
}}

QFrame#welcome_action_button:focus {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #222E40, stop:1 #17202C);
    border-color: {ACCENT_HOVER};
}}

QLabel#welcome_action_icon {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(74, 130, 190, 95), stop:1 rgba(58, 110, 165, 55));
    border: 1px solid rgba(122, 186, 232, 85);
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
    background-color: rgba(20, 26, 34, 190);
    border: 1px solid rgba(122, 186, 232, 45);
    border-radius: 8px;
    font-size: 12px;
    padding: 0 8px;
}}

QLabel#welcome_splash_update {{
    color: {ACCENT};
    background-color: rgba(20, 26, 34, 190);
    border: 1px solid rgba(122, 186, 232, 45);
    border-radius: 8px;
    font-size: 12px;
    padding: 0 8px;
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

QLabel#licenses_dialog_intro {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}

QPlainTextEdit#licenses_dialog_text {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px;
}}

QWidget#timeline_widget {{
    background-color: {PANEL_BG};
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
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {ACCENT_HOVER}, stop:1 {ACCENT});
    border-color: {ACCENT};
    color: #FFFFFF;
    font-weight: 600;
}}

QPushButton#primary_button:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #5790CF, stop:1 #4376AE);
    border-color: {ACCENT_HOVER};
}}

QPushButton#primary_button:pressed {{
    background: {ACCENT_PRESSED};
    border-color: {ACCENT_PRESSED};
}}

QPushButton#primary_button:disabled {{
    background-color: {SURFACE_BG};
    border-color: {BORDER};
    color: {TEXT_DISABLED};
}}

QFrame#reset_confirm_popover {{
    background-color: {SURFACE_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_FOCUS};
    border-radius: 12px;
}}

QLabel#reset_confirm_title {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
    font-size: 13px;
    font-weight: 600;
}}

QLabel#reset_confirm_message {{
    color: {TEXT_MUTED};
    background-color: transparent;
    font-size: 12px;
}}

QFrame#reset_confirm_popover QPushButton {{
    min-height: 26px;
    padding: 5px 12px;
    border-radius: 7px;
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

QToolButton#transport_button:focus {{
    border-color: {BORDER_FOCUS};
}}

QToolButton#transport_button:pressed {{
    background-color: {ACCENT_PRESSED};
}}

QToolButton#transport_button:checked {{
    border-color: {BORDER_FOCUS};
    background-color: {ACCENT_PRESSED};
}}

QToolButton#stars_toggle_button,
QToolButton#parallax_preview_toggle_button {{
    background-color: {SURFACE_BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 0 10px 0 6px;
    min-height: 32px;
    max-height: 32px;
    color: {TEXT_PRIMARY};
    font-size: 12px;
}}

QToolButton#stars_toggle_button:hover,
QToolButton#parallax_preview_toggle_button:hover {{
    border-color: {BORDER_FOCUS};
}}

QToolButton#stars_toggle_button:focus,
QToolButton#parallax_preview_toggle_button:focus {{
    border-color: {BORDER_FOCUS};
}}

QToolButton#stars_toggle_button:pressed,
QToolButton#parallax_preview_toggle_button:pressed {{
    background-color: {ACCENT_PRESSED};
}}

QToolButton#stars_toggle_button:checked,
QToolButton#parallax_preview_toggle_button:checked {{
    border-color: {BORDER_FOCUS};
    background-color: {ACCENT_PRESSED};
}}

QToolButton#parallax_preview_toggle_button:disabled {{
    background-color: {PANEL_BG};
    border-color: {SURFACE_ALT_BG};
    color: {TEXT_DISABLED};
}}

QLabel#timeline_time_label,
QLabel#timeline_preview_heading {{
    color: #AAB7C8;
    font-size: 12px;
    padding: 0 4px;
}}

QLabel#timeline_preview_status {{
    color: #AAB7C8;
    font-size: 12px;
    padding: 0 4px;
}}

QLabel#timeline_preview_status[previewStatus="generating"] {{
    color: {ACCENT_HOVER};
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

QScrollArea#presets_scroll {{
    background-color: {APP_BG};
    border: none;
}}

QWidget#presets_content {{
    background-color: {APP_BG};
}}

QFrame#presets_header,
QFrame#export_header,
QFrame#settings_header,
QFrame#welcome_header {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1B2635, stop:0.5 #131B27, stop:1 {APP_BG});
    border-bottom: 1px solid {BORDER};
}}

QLabel#presets_header_icon,
QLabel#export_header_icon,
QLabel#settings_header_icon,
QLabel#welcome_header_icon {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(74, 130, 190, 95), stop:1 rgba(58, 110, 165, 55));
    border: 1px solid rgba(122, 186, 232, 85);
    border-radius: 11px;
}}

QLabel#presets_title,
QLabel#export_title,
QLabel#settings_title,
QLabel#welcome_title {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
    font-size: 17px;
    font-weight: 600;
}}

QLabel#presets_subtitle,
QLabel#export_subtitle,
QLabel#welcome_subtitle {{
    color: {TEXT_MUTED};
    background-color: transparent;
    font-size: 12px;
}}

QLabel#export_percent_label {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
    font-size: 12px;
    font-weight: 600;
    min-width: 34px;
}}

QFrame#export_summary_card {{
    background-color: {SURFACE_ALT_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QLabel#export_summary_primary {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
    font-size: 13px;
    font-weight: 600;
}}

QLabel#export_summary_secondary {{
    color: {TEXT_MUTED};
    background-color: transparent;
    font-size: 12px;
}}

QLabel#preset_section_title {{
    color: {TEXT_MUTED};
    background-color: transparent;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.6px;
    padding: 8px 2px 2px 2px;
}}

QLabel#preset_empty_label {{
    color: {TEXT_MUTED};
    font-size: 12px;
    padding: 14px 16px;
    background-color: {PANEL_BG};
    border: 1px dashed {BORDER};
    border-radius: 10px;
}}

QFrame#preset_card {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1C2534, stop:1 #131A24);
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QFrame#preset_card:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #222E40, stop:1 #17202C);
    border-color: {BORDER_FOCUS};
}}

QFrame#preset_card:focus {{
    border-color: {ACCENT_HOVER};
}}

QFrame#preset_card[selected="true"] {{
    border: 1px solid {ACCENT_HOVER};
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #22385A, stop:1 #162031);
}}

QLabel#preset_card_title {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
    font-size: 13px;
    font-weight: 600;
}}

QLabel#preset_card_description {{
    color: {TEXT_MUTED};
    background-color: transparent;
    font-size: 11px;
}}

QToolButton#preset_card_delete {{
    background-color: transparent;
    border: none;
    border-radius: 11px;
    color: {TEXT_MUTED};
    font-size: 12px;
    font-weight: 600;
    padding: 0;
}}

QToolButton#preset_card_delete:hover {{
    background-color: rgba(232, 106, 90, 55);
    color: #FF9B8B;
}}

QToolButton#preset_card_delete:pressed {{
    background-color: {TIMELINE_PLAYHEAD};
    color: #FFFFFF;
}}

QFrame#presets_footer {{
    background-color: {PANEL_BG};
    border-top: 1px solid {BORDER};
}}

QWidget#settings_content {{
    background-color: {APP_BG};
}}

QTabWidget#settings_tabs::pane {{
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    top: -1px;
}}

QTabWidget#settings_tabs QTabBar::tab {{
    color: {TEXT_MUTED};
    background-color: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 9px 18px;
    margin-right: 2px;
}}

QTabWidget#settings_tabs QTabBar::tab:hover {{
    color: {TEXT_PRIMARY};
    background-color: rgba(61, 81, 104, 45);
}}

QTabWidget#settings_tabs QTabBar::tab:selected {{
    color: {TEXT_PRIMARY};
    background-color: {PANEL_BG};
    border-bottom-color: {ACCENT_HOVER};
}}

QLabel#settings_section_title {{
    color: #A9BCD2;
    background-color: transparent;
    font-size: 15px;
    font-weight: 600;
}}

QFrame#settings_footer,
QFrame#welcome_footer {{
    background-color: {PANEL_BG};
    border-top: 1px solid {BORDER};
}}

QFrame#welcome_content {{
    background-color: {APP_BG};
}}

QFrame#welcome_icon_card {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1C2736, stop:1 #121923);
    border: 1px solid {BORDER};
    border-radius: 24px;
}}

QLabel#welcome_step_number {{
    color: {ACCENT_HOVER};
    background-color: transparent;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
}}

QLabel#welcome_step_title {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
    font-size: 24px;
    font-weight: 600;
}}

QLabel#welcome_step_body {{
    color: #A9B6C7;
    background-color: transparent;
    font-size: 14px;
}}

QFrame#welcome_progress_dot {{
    background-color: #4B5666;
    border: none;
    border-radius: 3px;
}}

QFrame#welcome_progress_dot[active="true"] {{
    background-color: {ACCENT_HOVER};
}}

QFrame#preset_create_action {{
    background-color: {SURFACE_BG};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QFrame#preset_create_action:hover {{
    background-color: #1E2836;
    border-color: {BORDER_FOCUS};
}}

QFrame#preset_create_action:focus {{
    border-color: {ACCENT_HOVER};
}}

QLabel#preset_create_icon {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(74, 130, 190, 95), stop:1 rgba(58, 110, 165, 55));
    border: 1px solid rgba(122, 186, 232, 85);
    border-radius: 11px;
}}

QLabel#preset_create_title {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
    font-size: 13px;
    font-weight: 600;
}}

QLabel#preset_create_hint {{
    color: {TEXT_MUTED};
    background-color: transparent;
    font-size: 11px;
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
