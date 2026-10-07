# -*- coding: utf-8 -*-
import sys
import os
import subprocess
from threading import Event, Lock
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit, QHBoxLayout, QMessageBox, QApplication
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont, QColor
from acousticstudio.dependencies import PACKAGE_INFO, installed_package_names
from acousticstudio.compute_devices import probe_compute_devices
from acousticstudio.cuda_runtime import install_cuda_runtime

class InstallWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, packages, parent=None, cuda=False):
        super().__init__(parent)
        self.packages = packages
        self.cuda = cuda
        self.success = False
        self.error = ''
        self.cancelled = Event()
        self._process = None
        self._process_lock = Lock()

    def _set_process(self, process):
        with self._process_lock:
            self._process = process
        if self.cancelled.is_set() and process is not None:
            try:
                process.terminate()
            except OSError:
                pass

    def cancel(self):
        self.cancelled.set()
        with self._process_lock:
            process = self._process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

    def run(self):
        try:
            if self.cuda:
                install_cuda_runtime(self.log_signal.emit, self.cancelled, self._set_process)
                self.success = True
                return
            process = subprocess.Popen(
                [sys.executable, '-m', 'pip', 'install', *self.packages],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            self._set_process(process)
            for line in iter(process.stdout.readline, ''):
                if not line: break
                self.log_signal.emit(line)
            process.stdout.close()
            code = process.wait()
            if self.cancelled.is_set():
                raise RuntimeError('설치를 취소했습니다.')
            if code:
                raise RuntimeError(f'라이브러리 설치 실패 (pip 종료 코드 {code}).')
            self.success = True
        except Exception as e:
            self.error = str(e)
            self.log_signal.emit(f"Error: {e}")
        finally:
            self._set_process(None)
            self.finished_signal.emit()

class LiveInstallerDialog(QDialog):
    def __init__(self, packages, parent=None, cuda=False):
        super().__init__(parent)
        self.setWindowTitle("PyTorch CUDA 준비" if cuda else "라이브러리 자동 설치")
        self.resize(600, 400)
        self._close_when_finished = False

        layout = QVBoxLayout(self)
        text = ("PyTorch CUDA를 다운로드하고 사용 가능 상태를 확인합니다.\n"
                "다운로드에는 수 GB의 공간이 필요합니다. 완료하면 선택한 계산 모드가 적용됩니다."
                if cuda else f"라이브러리를 설치 중입니다:\n{', '.join(packages)}\n잠시만 기다려주세요...")
        self.info_label = QLabel(text)
        self.info_label.setWordWrap(True)
        self.info_label.setFont(QFont("맑은 고딕", 10))
        layout.addWidget(self.info_label)

        from PySide6.QtWidgets import QProgressBar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("background-color: black; color: lightgreen; font-family: Consolas; font-size: 13px;")
        layout.addWidget(self.text_edit)

        self.close_btn = QPushButton("설치 취소")
        self.close_btn.clicked.connect(self.reject)
        layout.addWidget(self.close_btn, alignment=Qt.AlignCenter)

        self.worker = InstallWorker(packages, self, cuda=cuda)
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def append_log(self, text):
        self.text_edit.insertPlainText(text)
        self.text_edit.ensureCursorVisible()

    def on_finished(self):
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1 if self.worker.success else 0)
        self.close_btn.setText("닫기")
        self.close_btn.setEnabled(True)
        if self._close_when_finished:
            super().reject()
            return
        if self.worker.success:
            self.info_label.setText("설치가 완료되었습니다.")
            self.accept()
        else:
            self.info_label.setText(f"설치가 완료되지 않았습니다.\n{self.worker.error}")

    def reject(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self._close_when_finished = True
            self.info_label.setText("설치를 취소하는 중입니다…")
            self.close_btn.setEnabled(False)
            self.worker.cancel()
        else:
            super().reject()

    def closeEvent(self, event):
        if self.worker.isRunning():
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)

class LibraryManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("라이브러리 관리자")
        self.resize(600, 480)

        installed = installed_package_names()
        packages_info = PACKAGE_INFO

        layout = QVBoxLayout(self)

        title = QLabel("AcousticStudio 라이브러리 환경 점검")
        title.setFont(QFont("맑은 고딕", 12, QFont.Bold))
        layout.addWidget(title)

        self.checkbox_vars = {}
        self.missing_selected = []
        self.requested_compute_mode = None
        devices = getattr(parent, 'compute_devices', None) or probe_compute_devices()

        from PySide6.QtWidgets import QFrame, QCheckBox

        layout.addWidget(QLabel("[ 필수 설치 항목 ]"))
        for pkg, info in packages_info.items():
            if info['type'] == '필수':
                is_inst = pkg.lower() in installed
                status = "✔ 설치됨" if is_inst else "❌ 미설치"
                lbl = QLabel(f"{status} | {pkg} ({info['size']}) - {info['desc']}")
                lbl.setStyleSheet("color: green;" if is_inst else "color: red;")
                layout.addWidget(lbl)
                if not is_inst:
                    cb = QCheckBox(f"{pkg} 설치", self)
                    cb.setChecked(True)
                    layout.addWidget(cb)
                    self.checkbox_vars[pkg] = cb
                    self.missing_selected.append(pkg)

        layout.addWidget(QLabel("\n[ 선택 설치 항목 ]"))
        for pkg, info in packages_info.items():
            if info['type'] != '필수':
                if pkg == 'torch':
                    if devices.cuda_available:
                        layout.addWidget(QLabel(f"✔ CUDA 사용 가능 | PyTorch - {devices.cuda_device}"))
                    elif devices.torch_cuda_build is not None:
                        status = QLabel(f"PyTorch CUDA 장치 사용 불가: {devices.cuda_error}")
                        status.setWordWrap(True)
                        layout.addWidget(status)
                    else:
                        status = 'CPU 전용 설치본' if devices.torch_installed else '미설치'
                        cb = QCheckBox(f"PyTorch/CUDA 사용 ({status}, {info['size']})")
                        cb.setChecked(False)
                        layout.addWidget(cb)
                        self.checkbox_vars[pkg] = cb
                    continue
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
        for pkg, checkbox in self.checkbox_vars.items():
            if checkbox.isChecked():
                to_install.append(pkg)

        if not to_install:
            QMessageBox.information(self, "안내", "설치할 항목이 없습니다.")
            return

        general = [pkg for pkg in to_install if pkg != 'torch']
        if general:
            dlg = LiveInstallerDialog(general, self)
            if dlg.exec() != QDialog.Accepted:
                return
        if 'torch' in to_install:
            if self.parent() is not None and hasattr(self.parent(), 'prepare_compute_install'):
                self.parent().prepare_compute_install()
            dlg = LiveInstallerDialog(['torch'], self, cuda=True)
            if dlg.exec() != QDialog.Accepted:
                return
            self.requested_compute_mode = 3
        self.accept()
