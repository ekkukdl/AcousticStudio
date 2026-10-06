"""Switch presentation without rebuilding the viewer or hardware controls."""
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QStyle, QVBoxLayout, QWidget


LEGACY_STYLES = {
    'run_btn': 'background-color: #4CAF50; color: white; height: 30px; font-weight: bold;',
    'show_field_btn': 'background-color: #2196F3; color: white; height: 30px; font-weight: bold;',
    'btn_kwave_sim': 'background-color: #00796B; color: white; height: 30px; font-weight: bold; border-radius: 3px;',
    'lbl_traj_preview_inline': 'color: #E65100; font-weight: bold; font-size: 11px; margin-top: 4px; margin-bottom: 2px;',
    'btn_gen_traj': 'background-color: #9C27B0; color: white; font-weight: bold; height: 32px; border-radius: 4px; margin-bottom: 5px;',
    'btn_clear_sel_traj': 'height: 28px; border-radius: 4px; background-color: #f44336; color: white;',
    'btn_clear_all_traj': 'height: 28px; border-radius: 4px; background-color: #d32f2f; color: white;',
    'btn_export_traj': 'height: 28px; border-radius: 4px; background-color: #1976D2; color: white; font-weight: bold; margin-top: 2px;',
    'lbl_traj_time': 'color: #E65100; font-weight: bold; margin-top: 10px;',
}
LEGACY_SCROLL_STYLE = """
    QScrollBar:vertical { border: none; background: transparent; width: 8px; margin: 0px; }
    QScrollBar::handle:vertical { background: rgba(128, 128, 128, 150); border-radius: 4px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""


class UIAppearance:
    SETTINGS_KEY = 'ui/ver2/use_legacy_ui'

    def __init__(self, window, main_layout, hardware_bar, scrolls):
        self.window = window
        self.main_layout = main_layout
        self.hardware_bar = hardware_bar
        self.scrolls = scrolls
        self.legacy = False
        self.modern_style = window.styleSheet()
        self.modern_minimum = window.minimumSize()
        margins = main_layout.contentsMargins()
        self.modern_margins = (margins.left(), margins.top(), margins.right(), margins.bottom())
        self.modern_spacing = main_layout.spacing()
        self.modern_bar_style = hardware_bar.styleSheet()
        self.modern_scroll_styles = [s.styleSheet() for s in scrolls]
        self.modern_widget_styles = {name: getattr(window, name).styleSheet() for name in LEGACY_STYLES}
        # Read the native layout defaults used by the original UI.
        defaults = QWidget()
        layout = QVBoxLayout(defaults)
        margins = layout.contentsMargins()
        self.legacy_margins = (margins.left(), margins.top(), margins.right(), margins.bottom())
        self.legacy_spacing = layout.spacing()
        defaults.deleteLater()
        self.splitter_sizes = {False: None, True: None}

    def apply(self, legacy, persist=True):
        legacy = bool(legacy)
        window = self.window
        if legacy != self.legacy:
            sizes = window.splitter.sizes()
            if sizes and all(size > 0 for size in sizes):
                self.splitter_sizes[self.legacy] = sizes
        window.setUpdatesEnabled(False)
        try:
            window.setStyleSheet('' if legacy else self.modern_style)
            window.setMinimumSize(0, 0) if legacy else window.setMinimumSize(self.modern_minimum)
            self.main_layout.setContentsMargins(*(self.legacy_margins if legacy else self.modern_margins))
            self.main_layout.setSpacing(self.legacy_spacing if legacy else self.modern_spacing)
            self.hardware_bar.setStyleSheet('' if legacy else self.modern_bar_style)
            self.hardware_bar.setFixedHeight(50 if legacy else 54)
            for name, style in (LEGACY_STYLES if legacy else self.modern_widget_styles).items():
                getattr(window, name).setStyleSheet(style)
            for scroll, modern_style in zip(self.scrolls, self.modern_scroll_styles):
                scroll.setStyleSheet(LEGACY_SCROLL_STYLE if legacy else modern_style)
            refresh = window.btn_refresh_ports
            refresh.setText('새로고침' if legacy else '')
            refresh.setIcon(QIcon() if legacy else window.style().standardIcon(QStyle.SP_BrowserReload))
            refresh.setFixedWidth(60 if legacy else 32)
            refresh.setMinimumHeight(0 if legacy else 30)
            refresh.setMaximumHeight(16777215 if legacy else 30)
            if legacy != self.legacy:
                sizes = self.splitter_sizes[legacy]
                window.splitter.setSizes(sizes or ([1020, 480] if legacy else [1180, 520]))
            self.legacy = legacy
            if persist:
                window.settings.setValue(self.SETTINGS_KEY, legacy)
        finally:
            window.setUpdatesEnabled(True)
        window.update()
