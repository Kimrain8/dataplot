import sys
from PySide6.QtWidgets import QApplication
from dataplot.ui.main_window import MainWindow


def run():
    app = QApplication(sys.argv)
    # 移除全局强制字体设置，恢复系统默认，避免 SpinBox 乱码
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()