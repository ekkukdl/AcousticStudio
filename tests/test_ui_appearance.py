"""Real Qt widgets: switching UI must preserve input and hardware selections."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QComboBox, QMainWindow, QPushButton, QScrollArea,
    QSplitter, QTabWidget, QVBoxLayout, QWidget,
)
from acousticstudio.ui_appearance import LEGACY_STYLES, UIAppearance


def test_switch_preserves_widgets_values_and_board_menu(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    central = QWidget(); window.setCentralWidget(central)
    layout = QVBoxLayout(central); layout.setContentsMargins(16, 10, 16, 12); layout.setSpacing(10)
    hardware_bar = QWidget(); hardware_bar.setStyleSheet('background: white;')
    layout.addWidget(hardware_bar)
    window.setStyleSheet('QMainWindow {background: #f3f5f8;}')
    window.setMinimumSize(1120, 720)
    for name in LEGACY_STYLES:
        widget = QPushButton(name, central); widget.setStyleSheet('color: #5e7f9d;')
        setattr(window, name, widget)
    window.btn_refresh_ports = QPushButton('', hardware_bar)
    window.board_profile_cb = QComboBox(hardware_bar)
    window.board_profile_cb.addItems(['Legacy', 'SonicSurface']); window.board_profile_cb.setCurrentIndex(1)
    board_menu = window.menuBar().addMenu('보드')
    selected_action = QAction('SonicSurface', window); selected_action.setCheckable(True); selected_action.setChecked(True)
    board_menu.addAction(selected_action)
    tabs = QTabWidget(); scrolls = tuple(QScrollArea() for _ in range(3))
    for scroll, label in zip(scrolls, ['구성', '음장', '궤적']):
        scroll.setWidget(QWidget()); tabs.addTab(scroll, label)
    tabs.setCurrentIndex(2)
    window.splitter = QSplitter(); window.splitter.addWidget(QWidget()); window.splitter.addWidget(tabs)
    layout.addWidget(window.splitter)
    window.settings = QSettings(str(tmp_path / 'ui.ini'), QSettings.IniFormat)
    changes = []; window.board_profile_cb.currentIndexChanged.connect(changes.append)
    appearance = UIAppearance(window, layout, hardware_bar, scrolls)
    identities = [id(window.board_profile_cb), id(tabs), *[id(s) for s in scrolls]]
    for _ in range(5):
        appearance.apply(True); assert '#4CAF50' in window.run_btn.styleSheet()
        appearance.apply(False); assert window.run_btn.styleSheet() == 'color: #5e7f9d;'
    appearance.apply(True)
    assert window.settings.value(UIAppearance.SETTINGS_KEY, type=bool) is True
    window.settings.sync()
    reopened = QSettings(str(tmp_path / 'ui.ini'), QSettings.IniFormat)
    assert reopened.value(UIAppearance.SETTINGS_KEY, type=bool) is True
    assert identities == [id(window.board_profile_cb), id(tabs), *[id(s) for s in scrolls]]
    assert tabs.currentIndex() == 2 and window.board_profile_cb.currentIndex() == 1
    assert selected_action.isChecked() and not changes
    appearance.apply(False)
    assert layout.contentsMargins().left() == 16 and layout.spacing() == 10
    window.close(); app.processEvents()
