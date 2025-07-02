"""
项目配置模块

提供服务器和客户端的配置常量
"""

import os

# 服务器配置
SERVER_HOST = os.getenv('SERVER_HOST', 'localhost')
SERVER_PORT = int(os.getenv('SERVER_PORT', 8765))
VERIFY_PEER = os.getenv('VERIFY_PEER', 'false').lower() == 'true'

# 数据库配置
DATABASE_PATH = "server/data/secure_chat.db"
USERS_JSON_PATH = "server/data/users.json"
CONTACTS_JSON_PATH = "server/data/contacts.json"

# 安全配置
SECRET_KEY = os.getenv('SECRET_KEY', 'default-secret-key-change-in-production')
RSA_KEY_SIZE = 2048
HASH_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 100000
SALT_BYTES = 16

# 协议配置
MAX_MESSAGE_SIZE = 4 * 1024 * 1024  # 4MB
MAX_CONNECTIONS = 1000
HEARTBEAT_INTERVAL = 30
CONNECTION_TIMEOUT = 60

# 日志配置
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'server.log')
