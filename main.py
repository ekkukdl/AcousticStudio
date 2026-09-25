# -*- coding: utf-8 -*-
import sys
import os
import subprocess

def check_and_install_requirements():
    import importlib.metadata
    
    packages_info = {
        'PySide6': {'type': '필수', 'size': '~200MB', 'desc': 'GUI 프레임워크'},
        'pyvista': {'type': '필수', 'size': '~40MB', 'desc': '3D 렌더링 엔진'},
        'numpy': {'type': '필수', 'size': '~15MB', 'desc': '수치 연산 배열 처리'},
        'pyserial': {'type': '필수', 'size': '~2MB', 'desc': '하드웨어 USB 통신'},
        'numba': {'type': '필수', 'size': '~10MB', 'desc': 'CPU 병렬 최적화'},
        'taichi': {'type': '선택', 'size': '~30MB', 'desc': '다중/GPU 병렬 가속 연산'},
        'torch': {'type': '선택', 'size': '~2.5GB', 'desc': 'NVIDIA 그래픽카드 초고속 연산'}
    }
    
    installed = {dist.metadata['Name'].lower() for dist in importlib.metadata.distributions()}
    
    missing_required = []
    missing_optional = []
    for pkg, info in packages_info.items():
        if pkg.lower() not in installed:
            if info['type'] == '필수':
                missing_required.append(pkg)
            else:
                missing_optional.append(pkg)
                
    if not missing_required:
        return # 필수 항목이 모두 있으면 검증 통과 (선택 항목만 비어있어도 팝업 띄우지 않음)
        
    try:
        import tkinter as tk
        import threading
        
        root = tk.Tk()
        root.withdraw()
        
        dialog = tk.Toplevel(root)
        dialog.title("AcousticStudio 필수 및 선택 라이브러리 설치")
        
        # Center dialog
        w, h = 600, 480
        sw = dialog.winfo_screenwidth()
        sh = dialog.winfo_screenheight()
        dialog.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        
        tk.Label(dialog, text="AcousticStudio 실행을 위해 아래 라이브러리 설치가 필요합니다.", font=("맑은 고딕", 11, "bold")).pack(pady=10)
        
        frame = tk.Frame(dialog)
        frame.pack(fill="both", expand=True, padx=20)
        
        # Required
        tk.Label(frame, text="[ 필수 설치 항목 ]", font=("맑은 고딕", 10, "bold"), fg="#d32f2f").pack(anchor="w", pady=(0,5))
        for pkg in missing_required:
            info = packages_info[pkg]
            lbl_text = f"✔ {pkg} ({info['size']}) - {info['desc']}"
            tk.Label(frame, text=lbl_text, font=("맑은 고딕", 9)).pack(anchor="w", padx=15)
            
        # Optional
        checkbox_vars = {}
        if missing_optional:
            tk.Label(frame, text="\n[ 선택 설치 항목 ]", font=("맑은 고딕", 10, "bold"), fg="#1976d2").pack(anchor="w", pady=(0,5))
            for pkg in missing_optional:
                # torch는 용량이 너무 커서 기본 체크 해제, taichi는 가벼워서 기본 체크
                var = tk.BooleanVar(value=True if pkg != 'torch' else False)
                checkbox_vars[pkg] = var
                info = packages_info[pkg]
                lbl_text = f"{pkg} ({info['size']}) - {info['desc']}"
                cb = tk.Checkbutton(frame, text=lbl_text, variable=var, font=("맑은 고딕", 9))
                cb.pack(anchor="w", padx=10)
                
        # Buttons
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=15)
        
        user_agreed = [False]
        selected_packages = missing_required.copy()
        
        def on_install():
            for pkg, var in checkbox_vars.items():
                if var.get():
                    selected_packages.append(pkg)
            user_agreed[0] = True
            dialog.destroy()
            
        def on_cancel():
            sys.exit(0)
            
        tk.Button(btn_frame, text="설치 시작", width=15, bg="#4CAF50", fg="white", font=("맑은 고딕", 10, "bold"), command=on_install).pack(side="left", padx=10)
        tk.Button(btn_frame, text="종료", width=15, font=("맑은 고딕", 10), command=on_cancel).pack(side="right", padx=10)
        
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        root.wait_window(dialog)
        
        if not user_agreed[0]:
            sys.exit(0)
            
        # --- 실시간 로그 창 (Live Console) ---
        install_win = tk.Toplevel(root)
        install_win.title("라이브러리 설치 중...")
        install_win.geometry(f"550x350+{(sw - 550) // 2}+{(sh - 350) // 2}")
        
        tk.Label(install_win, text="라이브러리를 다운로드 및 설치 중입니다.\n창을 닫지 말고 잠시만 기다려주세요.", font=("맑은 고딕", 10)).pack(pady=5)
        import tkinter.scrolledtext as scrolledtext
        
        progress_var = tk.DoubleVar()
        
        canvas = tk.Canvas(install_win, height=25, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        canvas.pack(fill="x", padx=10, pady=5)
        
        bar_rect = canvas.create_rectangle(0, 0, 0, 25, fill="#0078D7", width=0)
        pct_text = canvas.create_text(0, 12, text="0%", font=("맑은 고딕", 10))
        
        def update_progress(val):
            canvas.update_idletasks()
            w = canvas.winfo_width()
            if w <= 1: w = 530 # default width if not rendered yet
            canvas.coords(bar_rect, 0, 0, w * (val / 100.0), 25)
            canvas.coords(pct_text, w / 2, 12)
            canvas.itemconfig(pct_text, text=f"{int(val)}%")
        
        text_area = scrolledtext.ScrolledText(install_win, bg="black", fg="lightgreen", font=("Consolas", 9))
        text_area.pack(expand=True, fill="both", padx=10, pady=10)
        install_win.update()
        update_progress(0)
        
        def run_install():
            process = subprocess.Popen(
                [sys.executable, '-m', 'pip', 'install', *selected_packages],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Estimate progress based on log lines (cap at 95%)
            current_progress = 0.0
            
            for line in iter(process.stdout.readline, ''):
                if not line: break
                def append_text(l=line):
                    nonlocal current_progress
                    text_area.insert(tk.END, l)
                    text_area.see(tk.END)
                    # Fake progress increment
                    if current_progress < 95.0:
                        current_progress += (95.0 - current_progress) * 0.05
                        update_progress(current_progress)
                install_win.after(0, append_text)
            process.stdout.close()
            process.wait()
            
            def on_finish():
                update_progress(100.0)
                from tkinter import messagebox
                messagebox.showinfo("설치 완료", "설치가 완료되었습니다! 프로그램을 시작합니다.")
                install_win.destroy()
                root.quit()
            install_win.after(0, on_finish)
            
        threading.Thread(target=run_install, daemon=True).start()
        root.mainloop() 
        root.destroy()
    except Exception as e:
        print("설치 스크립트 실행 중 오류 발생:", e)
        sys.exit(1)

# 가장 먼저 환경 검증 및 설치 실행
check_and_install_requirements()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtGui import QPixmap, QPainter, QFont, QColor
from PySide6.QtCore import Qt

def create_splash_pixmap():
    pixmap = QPixmap(500, 300)
    pixmap.fill(QColor("#2b2b2b"))
    painter = QPainter(pixmap)
    painter.setPen(QColor("#ffffff"))
    font = QFont("Arial", 24, QFont.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "AcousticStudio\nLoading...")
    font.setPointSize(12)
    painter.setFont(font)
    painter.drawText(pixmap.rect().adjusted(0, 0, 0, -20), Qt.AlignBottom | Qt.AlignHCenter, "3D 엔진 및 하드웨어 연산 초기화 중...")
    painter.end()
    return pixmap

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 로딩 창(Splash Screen) 띄우기
    splash_pixmap = create_splash_pixmap()
    splash = QSplashScreen(splash_pixmap, Qt.WindowStaysOnTopHint)
    splash.show()
    app.processEvents() # 로딩 창을 즉시 화면에 그림
    
    # 무거운 메인 창(PyVista 등) 로딩 시작
    from acousticstudio.app import AcousticStudioMain
    window = AcousticStudioMain()
    window.show()
    
    # 로딩이 완료되면 로딩 창 종료
    splash.finish(window)
    sys.exit(app.exec())
