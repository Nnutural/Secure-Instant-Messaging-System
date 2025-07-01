from PyQt5.QtWidgets import QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox
from fake_backend import register_user
from base_window import BaseWindow

class RegisterWindow(BaseWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("注册")
        self.resize(400, 350)

        self.label_user = QLabel("新用户名：")
        self.input_user = QLineEdit()
        self.label_pass = QLabel("新密码：")
        self.input_pass = QLineEdit()
        self.input_pass.setEchoMode(QLineEdit.Password)

        self.btn_register = QPushButton("提交注册")

        layout = QVBoxLayout()
        layout.addWidget(self.label_user)
        layout.addWidget(self.input_user)
        layout.addWidget(self.label_pass)
        layout.addWidget(self.input_pass)
        layout.addWidget(self.btn_register)
        self.setLayout(layout)

        self.btn_register.clicked.connect(self.handle_register)

    def handle_register(self):
        user = self.input_user.text()
        pwd = self.input_pass.text()
        if register_user(user, pwd):
            QMessageBox.information(self, "成功", "注册成功，请返回登录")
            self.close()
        else:
            QMessageBox.warning(self, "失败", "用户名已存在")
