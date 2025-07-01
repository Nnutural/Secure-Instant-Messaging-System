import json
import os
import hashlib


# 相对路径：存到项目下的 data/users.json
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
USER_FILE = os.path.join(DATA_DIR, "users.json")

# 如果 data 目录不存在，先创建
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# 加载所有用户信息
def load_users():
    if not os.path.exists(USER_FILE):
        with open(USER_FILE, "w") as f:
            json.dump({}, f)
    with open(USER_FILE, "r") as f:
        return json.load(f)

# 保存用户信息
def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f, indent=4)

# 密码哈希函数（使用 SHA-256）
def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

# 登录验证
def check_login(username, password):
    users = load_users()
    hashed = hash_password(password)
    return users.get(username) == hashed

# 注册用户
def register_user(username, password):
    users = load_users()
    if username in users:
        return False
    users[username] = hash_password(password)
    save_users(users)
    return True
