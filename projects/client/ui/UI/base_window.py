# base_window.py
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QIcon
import os

class BaseWindow(QWidget):
    def __init__(self, *args, **kwargs):
        super(BaseWindow, self).__init__(*args, **kwargs)

        # 设置统一窗口标题
        self.setWindowTitle("安全通信系统")

        # 设置统一图标
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "image.jpg")
        self.setWindowIcon(QIcon(icon_path))
