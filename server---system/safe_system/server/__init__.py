"""
安全即时通讯系统服务器端模块

这个包含了完整的服务器端实现，包括：
- 数据库存储管理 (storage.py)
- 用户认证系统 (auth.py) 
- 在线目录管理 (directory.py)
- 核心服务器逻辑 (core.py)
"""

from .storage import DatabaseManager
from .auth import AuthenticationManager
from .directory import DirectoryManager
from .core import SecureChatServer

__version__ = "1.0.0"
__author__ = "安全即时通讯系统开发团队"

__all__ = [
    'DatabaseManager',
    'AuthenticationManager', 
    'DirectoryManager',
    'SecureChatServer'
] 