import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("用户登录注册")

        self.browser = QWebEngineView()
        self.setCentralWidget(self.browser)

        # 允许本地文件加载远程资源（如在线图标）
        self.browser.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )

        # 当前脚本目录
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # 修改这里，指向登录注册页面所在文件夹和html文件
        html_path = os.path.join(base_dir,  "index.html")

        # 加载本地文件到 QWebEngineView
        self.browser.load(QUrl.fromLocalFile(html_path))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.resize(900, 600)
    main_win.show()
    sys.exit(app.exec())
