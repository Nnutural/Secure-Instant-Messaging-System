from PyQt5.QtWidgets import QApplication
from login_window import LoginWindow
import sys

if __name__ == "__main__":
    app = QApplication(sys.argv)
    login = LoginWindow()
    login.show()
    sys.exit(app.exec_())
#只实现登录界面