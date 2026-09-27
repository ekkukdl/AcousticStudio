# -*- coding: utf-8 -*-
import sys
import os
import subprocess
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit, QHBoxLayout, QMessageBox, QApplication
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont, QColor

class InstallWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, packages, parent=None):
        super().__init__(parent)
        self.packages = packages

    def run(self):
        try:
            process = subprocess.Popen(
                [sys.executable, '-m', 'pip', 'install', *self.packages],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            for line in iter(process.stdout.readline, ''):
                if not line: break
                self.log_signal.emit(line)
            process.stdout.close()
            process.wait()
        except Exception as e:
            self.log_signal.emit(f"Error: {e}")
        finally:
            self.finished_signal.emit()

class LiveInstallerDialog(QDialog):
    def __init__(self, packages, parent=None):
        super().__init__(parent)
        self.setWindowTitle("라이브러리 자동 설치")
        self.resize(600, 400)

        layout = QVBoxLayout(self)
        self.info_label = QLabel(f"라이브러리를 설치 중입니다:\n{', '.join(packages)}\n잠시만 기다려주세요...")
        self.info_label.setFont(QFont("맑은 고딕", 10))
        layout.addWidget(self.info_label)

        from PySide6.QtWidgets import QProgressBar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("background-color: black; color: lightgreen; font-family: Consolas; font-size: 13px;")
        layout.addWidget(self.text_edit)

        self.close_btn = QPushButton("닫기")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(self.close_btn, alignment=Qt.AlignCenter)

        self.worker = InstallWorker(packages, self)
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def append_log(self, text):
        self.text_edit.insertPlainText(text)
        self.text_edit.ensureCursorVisible()
        current = self.progress_bar.value()
        if current < 95:
            # Fake progress increment
            step = max(1, int((95 - current) * 0.05))
            self.progress_bar.setValue(current + step)

    def on_finished(self):
        self.progress_bar.setValue(100)

        self.info_label.setText("설치가 완료되었습니다! 이제 기능을 사용할 수 있습니다.")
        self.info_label.setStyleSheet("color: blue; font-weight: bold;")
        self.close_btn.setEnabled(True)
        QMessageBox.information(self, "설치 완료", "라이브러리 설치가 성공적으로 완료되었습니다.")
        self.accept()

class LibraryManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("라이브러리 관리자")
        self.resize(600, 480)

        import importlib.metadata
        installed = {dist.metadata['Name'].lower() for dist in importlib.metadata.distributions()}

        packages_info = {
            'PySide6': {'type': '필수', 'size': '~200MB', 'desc': 'GUI 프레임워크'},
            'pyvista': {'type': '필수', 'size': '~40MB', 'desc': '3D 렌더링 엔진'},
            'numpy': {'type': '필수', 'size': '~15MB', 'desc': '수치 연산 배열 처리'},
            'pyserial': {'type': '필수', 'size': '~2MB', 'desc': '하드웨어 USB 통신'},
            'numba': {'type': '필수', 'size': '~10MB', 'desc': 'CPU 병렬 최적화'},
            'taichi': {'type': '선택', 'size': '~30MB', 'desc': '다중/GPU 병렬 가속 연산'},
            'torch': {'type': '선택', 'size': '~2.5GB', 'desc': 'NVIDIA 그래픽카드 초고속 연산'},
            'psutil': {'type': '선택', 'size': '~1MB', 'desc': 'CPU 리소스 실시간 모니터링'},
            'GPUtil': {'type': '선택', 'size': '~1MB', 'desc': 'GPU 리소스 실시간 모니터링'}
        }

        layout = QVBoxLayout(self)

        title = QLabel("AcousticStudio 라이브러리 환경 점검")
        title.setFont(QFont("맑은 고딕", 12, QFont.Bold))
        layout.addWidget(title)

        self.checkbox_vars = {}
        self.missing_selected = []

        from PySide6.QtWidgets import QFrame, QCheckBox

        layout.addWidget(QLabel("[ 필수 설치 항목 ]"))
        for pkg, info in packages_info.items():
            if info['type'] == '필수':
                is_inst = pkg.lower() in installed
                status = "✔ 설치됨" if is_inst else "❌ 미설치"
                lbl = QLabel(f"{status} | {pkg} ({info['size']}) - {info['desc']}")
                lbl.setStyleSheet("color: green;" if is_inst else "color: red;")
                layout.addWidget(lbl)

        layout.addWidget(QLabel("\n[ 선택 설치 항목 ]"))
        for pkg, info in packages_info.items():
            if info['type'] != '필수':
                is_inst = pkg.lower() in installed
                if is_inst:
                    lbl = QLabel(f"✔ 설치됨 | {pkg} ({info['size']}) - {info['desc']}")
                    lbl.setStyleSheet("color: green;")
                    layout.addWidget(lbl)
                else:
                    cb = QCheckBox(f"미설치 | {pkg} ({info['size']}) - {info['desc']}")
                    cb.setStyleSheet("color: blue;")
                    cb.setChecked(pkg == 'taichi')
                    layout.addWidget(cb)
                    self.checkbox_vars[pkg] = cb
                    self.missing_selected.append(pkg)

        btn_layout = QHBoxLayout()
        self.install_btn = QPushButton("선택 항목 설치")
        self.install_btn.clicked.connect(self.on_install)

        self.close_btn = QPushButton("닫기")
        self.close_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.install_btn)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

    def on_install(self):
        to_install = []
        for pkg in self.missing_selected:
            if self.checkbox_vars[pkg].isChecked():
                to_install.append(pkg)

        if not to_install:
            QMessageBox.information(self, "안내", "설치할 항목이 없습니다.")
            return

        self.accept()
        dlg = LiveInstallerDialog(to_install, self.parent())
        dlg.exec()
