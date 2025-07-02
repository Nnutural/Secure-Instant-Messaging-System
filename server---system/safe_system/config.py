"""
安全即时通讯系统配置模块

提供Config类，支持主服务器和各模块统一读取/设置配置
"""

import os
from pathlib import Path

class ServerConfig:
    """服务器配置类"""
    
    # 网络配置
    HOST = os.getenv('SERVER_HOST', 'localhost')
    PORT = int(os.getenv('SERVER_PORT', 8765))
    MAX_CONNECTIONS = int(os.getenv('MAX_CONNECTIONS', 100))
    
    # 数据库配置
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'secure_chat.db')
    
    # 日志配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'secure_chat_server.log')
    LOG_MAX_SIZE = int(os.getenv('LOG_MAX_SIZE', 10485760))  # 10MB
    LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', 5))
    
    # 安全配置
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here-change-in-production')
    SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', 3600))  # 1小时
    PASSWORD_MIN_LENGTH = int(os.getenv('PASSWORD_MIN_LENGTH', 8))
    
    # WebSocket配置
    WEBSOCKET_MAX_SIZE = int(os.getenv('WEBSOCKET_MAX_SIZE', 1048576))  # 1MB
    WEBSOCKET_TIMEOUT = int(os.getenv('WEBSOCKET_TIMEOUT', 60))  # 60秒
    PING_INTERVAL = int(os.getenv('PING_INTERVAL', 30))  # 30秒
    PING_TIMEOUT = int(os.getenv('PING_TIMEOUT', 10))  # 10秒
    
    # 用户限制
    MAX_USERS = int(os.getenv('MAX_USERS', 1000))
    MAX_FRIENDS_PER_USER = int(os.getenv('MAX_FRIENDS_PER_USER', 100))
    
    # 消息限制
    MAX_MESSAGE_LENGTH = int(os.getenv('MAX_MESSAGE_LENGTH', 4096))
    MESSAGE_HISTORY_DAYS = int(os.getenv('MESSAGE_HISTORY_DAYS', 30))
    
    # 文件传输配置
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 104857600))  # 100MB
    UPLOAD_DIRECTORY = Path(os.getenv('UPLOAD_DIRECTORY', 'uploads'))
    ALLOWED_FILE_TYPES = os.getenv('ALLOWED_FILE_TYPES', 'txt,pdf,doc,docx,jpg,jpeg,png,gif').split(',')
    
    # 加密配置
    RSA_KEY_SIZE = int(os.getenv('RSA_KEY_SIZE', 2048))
    ENCRYPTION_ALGORITHM = os.getenv('ENCRYPTION_ALGORITHM', 'AES-256-GCM')
    
    # 清理配置
    INACTIVE_USER_TIMEOUT = int(os.getenv('INACTIVE_USER_TIMEOUT', 30))  # 30分钟
    CLEANUP_INTERVAL = int(os.getenv('CLEANUP_INTERVAL', 300))  # 5分钟
    
    # 性能配置
    CONNECTION_POOL_SIZE = int(os.getenv('CONNECTION_POOL_SIZE', 20))
    WORKER_THREADS = int(os.getenv('WORKER_THREADS', 4))
    
    @classmethod
    def validate_config(cls):
        """验证配置参数的有效性"""
        errors = []
        
        # 验证端口范围
        if not (1 <= cls.PORT <= 65535):
            errors.append(f"无效的端口号: {cls.PORT}")
        
        # 验证最大连接数
        if cls.MAX_CONNECTIONS <= 0:
            errors.append(f"最大连接数必须大于0: {cls.MAX_CONNECTIONS}")
        
        # 验证密码最小长度
        if cls.PASSWORD_MIN_LENGTH < 6:
            errors.append(f"密码最小长度不能小于6: {cls.PASSWORD_MIN_LENGTH}")
        
        # 验证上传目录
        try:
            cls.UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"无法创建上传目录 {cls.UPLOAD_DIRECTORY}: {e}")
        
        # 验证RSA密钥大小
        if cls.RSA_KEY_SIZE < 1024:
            errors.append(f"RSA密钥大小过小，建议至少2048位: {cls.RSA_KEY_SIZE}")
        
        return errors
    
    @classmethod
    def get_config_dict(cls):
        """获取配置字典"""
        return {
            'host': cls.HOST,
            'port': cls.PORT,
            'max_connections': cls.MAX_CONNECTIONS,
            'database_path': cls.DATABASE_PATH,
            'log_level': cls.LOG_LEVEL,
            'log_file': cls.LOG_FILE,
            'secret_key': cls.SECRET_KEY[:10] + '...',  # 只显示前10个字符
            'session_timeout': cls.SESSION_TIMEOUT,
            'max_users': cls.MAX_USERS,
            'max_file_size': cls.MAX_FILE_SIZE,
            'rsa_key_size': cls.RSA_KEY_SIZE,
            'inactive_user_timeout': cls.INACTIVE_USER_TIMEOUT,
        }

# 开发环境配置
class DevelopmentConfig(ServerConfig):
    """开发环境配置"""
    HOST = 'localhost'
    PORT = 8765
    LOG_LEVEL = 'DEBUG'
    MAX_CONNECTIONS = 50

# 生产环境配置
class ProductionConfig(ServerConfig):
    """生产环境配置"""
    HOST = '0.0.0.0'
    PORT = 443
    LOG_LEVEL = 'WARNING'
    MAX_CONNECTIONS = 1000
    SESSION_TIMEOUT = 7200  # 2小时

# 测试环境配置
class TestingConfig(ServerConfig):
    """测试环境配置"""
    HOST = 'localhost'
    PORT = 8766
    DATABASE_PATH = 'test_secure_chat.db'
    LOG_LEVEL = 'DEBUG'
    MAX_CONNECTIONS = 10

# 根据环境变量选择配置
def get_config():
    """根据环境变量获取配置类"""
    env = os.getenv('FLASK_ENV', 'development').lower()
    
    if env == 'production':
        return ProductionConfig
    elif env == 'testing':
        return TestingConfig
    else:
        return DevelopmentConfig

# 默认配置
class Config:
    def __init__(self):
        # 默认配置
        self._config = {
            "HOST": "localhost",
            "PORT": 8765,
            "WORKER_PROCESSES": None,
            "MAX_MESSAGE_SIZE": 4 * 1024 * 1024,
            "HEARTBEAT_INTERVAL": 30,
            "CONNECTION_TIMEOUT": 60,
            "ENCRYPTION_ENABLED": True,
            "KEY_SIZE": 2048,
            "SESSION_TIMEOUT": 3600,
            # 可扩展更多配置项
        }

    def get(self, key, default=None):
        return self._config.get(key, default)

    def set(self, key, value):
        self._config[key] = value

# 可选：全局默认配置实例
config = Config()
 