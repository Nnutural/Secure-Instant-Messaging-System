from PyQt5.QtWidgets import QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox
from register_window import RegisterWindow
from fake_backend import check_login
from base_window import BaseWindow

class LoginWindow(BaseWindow):
    def __init__(self):
        super().__init__()

        self.resize(500, 450)

        self.label_user = QLabel("用户名：")
        self.input_user = QLineEdit()
        self.label_pass = QLabel("密码：")
        self.input_pass = QLineEdit()
        self.input_pass.setEchoMode(QLineEdit.Password)

        self.btn_login = QPushButton("登录")
        self.btn_register = QPushButton("注册")

        layout = QVBoxLayout()
        layout.addWidget(self.label_user)
        layout.addWidget(self.input_user)
        layout.addWidget(self.label_pass)
        layout.addWidget(self.input_pass)
        layout.addWidget(self.btn_login)
        layout.addWidget(self.btn_register)
        self.setLayout(layout)

        self.btn_login.clicked.connect(self.handle_login)
        self.btn_register.clicked.connect(self.open_register)

    def handle_login(self):
        user = self.input_user.text()
        pwd = self.input_pass.text()
        if check_login(user, pwd):
            QMessageBox.information(self, "成功", "登录成功！")
        else:
            QMessageBox.warning(self, "失败", "用户名或密码错误")

    def open_register(self):
        self.register_window = RegisterWindow()
        self.register_window.show()
