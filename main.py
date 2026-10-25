import sys
import ctypes
from PySide6.QtWidgets import QApplication
from dataplot.ui.main_window import MainWindow

def run():
    # 修复 Windows 任务栏图标显示延迟问题
    if sys.platform == 'win32':
        myappid = 'mycompany.dataplot.visualization.1' 
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    win = MainWindow()
    win.showMaximized()  # 直接最大化
    sys.exit(app.exec())

if __name__ == "__main__":
    run()