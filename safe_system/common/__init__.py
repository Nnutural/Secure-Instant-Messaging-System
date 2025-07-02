"""
安全即时通讯系统共同模块

包含客户端和服务器端共用的功能：
- 数据包处理和格式化 (packet.py)
- 加解密和密钥管理 (crypto.py)
- 信息隐藏功能 (stego.py)
- 协议定义和数据结构 (schema.py)
- 工具函数 (utils.py)
"""

from .packet import *
from .crypto import *
from .schema import *
from .utils import *

__version__ = "1.0.0"
__author__ = "安全即时通讯系统开发团队" 