import sys
import os
import json
from PyQt6.QtCore import QObject, pyqtSlot, QUrl
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEngineSettings

class Backend(QObject):
    def __init__(self):
        super().__init__()
        base_dir = os.path.dirname(os.path.abspath(__file__))  # 脚本目录
        self.data_file = os.path.join(base_dir, 'data.json')  # 确保路径正确

    @pyqtSlot(int, str, str, str, str)
    def saveMessage(self, contactId, sender, content, time, date):
        print(f"保存消息: 联系人ID={contactId}, 发送者={sender}, 内容={content}, 时间={time}, 日期={date}")

        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"contacts": [], "messages": {}}

        messages = data.get('messages', {})
        contact_msgs = messages.get(str(contactId), [])

        day_entry = None
        for day in contact_msgs:
            if day['date'] == date:
                day_entry = day
                break
        if not day_entry:
            day_entry = {"date": date, "messages": []}
            contact_msgs.append(day_entry)

        day_entry['messages'].append({
            "sender": sender,
            "content": content,
            "time": time
        })

        messages[str(contactId)] = contact_msgs
        data['messages'] = messages

        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        print("保存路径：", self.data_file)
        print("消息已保存到 data.json")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.resize(900, 600)
        self.setWindowTitle("聊天示例")

        self.webview = QWebEngineView()
        self.setCentralWidget(self.webview)

        # 允许本地文件加载远程资源（如在线图标）
        self.webview.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )

        self.channel = QWebChannel()
        self.backend = Backend()
        self.channel.registerObject("backend", self.backend)
        self.webview.page().setWebChannel(self.channel)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(base_dir, 'index.html')
        self.webview.load(QUrl.fromLocalFile(html_path))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.show()
    sys.exit(app.exec())
