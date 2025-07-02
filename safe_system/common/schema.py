"""
安全即时通讯系统协议定义和数据结构

定义统一的消息格式、状态枚举和数据结构
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Union
from enum import Enum
import json
from datetime import datetime

class MessageType(Enum):
    """消息类型枚举"""
    # 认证相关
    REGISTER = "register"
    LOGIN = "login"
    LOGOUT = "logout"
    AUTH_RESPONSE = "auth_response"
    
    # 用户管理
    GET_ONLINE_FRIENDS = "get_online_friends"
    GET_PUBLIC_KEY = "get_public_key"
    ADD_FRIEND = "add_friend"
    REMOVE_FRIEND = "remove_friend"
    
    # 消息传输
    TEXT_MESSAGE = "text_message"
    FILE_MESSAGE = "file_message"
    VOICE_MESSAGE = "voice_message"  # 语音消息
    IMAGE_MESSAGE = "image_message"
    STEGO_MESSAGE = "stego_message"  # 隐写消息
    GROUP_MESSAGE = "group_message"  # 群聊消息
    
    # 系统通知
    USER_STATUS_CHANGE = "user_status_change"
    FRIEND_REQUEST = "friend_request"
    HEARTBEAT = "heartbeat"
    SYSTEM_NOTIFICATION = "system_notification"
    
    # 聊天历史
    GET_HISTORY = "get_history"  # 查询历史
    HISTORY_RESPONSE = "history_response"

class ContentType(Enum):
    """内容类型枚举"""
    TEXT = "text"
    FILE = "file"
    VOICE = "voice"
    IMAGE = "image"
    JSON = "json"
    BINARY = "binary"

class EncryptionType(Enum):
    """加密类型枚举"""
    NONE = "none"
    AES_GCM = "aes_gcm"
    RSA = "rsa"
    HYBRID = "hybrid"  # RSA + AES

class UserStatus(Enum):
    """用户状态枚举"""
    OFFLINE = "offline"
    ONLINE = "online"
    BUSY = "busy"
    AWAY = "away"

@dataclass
class FileInfo:
    """文件信息数据结构"""
    filename: str
    size: int
    mime_type: str
    checksum: str
    chunk_count: Optional[int] = None
    chunk_index: Optional[int] = None

@dataclass
class VoiceParams:
    """语音参数数据结构"""
    sample_rate: int
    channels: int
    duration: float
    codec: str
    bitrate: Optional[int] = None

@dataclass
class UserEndpoint:
    """用户端点信息"""
    username: str
    ip_address: str
    port: int
    public_key: str
    status: UserStatus = UserStatus.ONLINE

@dataclass
class MessageData:
    """消息数据结构"""
    content: str  # Base64编码的内容
    content_type: ContentType
    encryption: EncryptionType
    signature: Optional[str] = None
    file_info: Optional[FileInfo] = None
    voice_params: Optional[VoiceParams] = None

@dataclass
class SecureMessage:
    """安全消息格式"""
    version: str = "1.0"
    type: MessageType = MessageType.TEXT_MESSAGE
    timestamp: str = ""
    sender: str = ""
    recipient: str = ""
    data: Optional[MessageData] = None
    metadata: Optional[Dict[str, Any]] = None
    message_id: Optional[str] = None
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        
        if not self.message_id:
            import uuid
            self.message_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        
        # 处理枚举类型
        if isinstance(self.type, MessageType):
            result['type'] = self.type.value
        
        if self.data:
            if isinstance(self.data.content_type, ContentType):
                result['data']['content_type'] = self.data.content_type.value
            if isinstance(self.data.encryption, EncryptionType):
                result['data']['encryption'] = self.data.encryption.value
        
        return result
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=None)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SecureMessage':
        """从字典创建对象"""
        # 处理枚举类型
        if 'type' in data:
            data['type'] = MessageType(data['type'])
        
        if 'data' in data and data['data']:
            data_obj = data['data']
            if 'content_type' in data_obj:
                data_obj['content_type'] = ContentType(data_obj['content_type'])
            if 'encryption' in data_obj:
                data_obj['encryption'] = EncryptionType(data_obj['encryption'])
            
            # 处理文件信息
            if 'file_info' in data_obj and data_obj['file_info']:
                data_obj['file_info'] = FileInfo(**data_obj['file_info'])
            
            # 处理语音参数
            if 'voice_params' in data_obj and data_obj['voice_params']:
                data_obj['voice_params'] = VoiceParams(**data_obj['voice_params'])
            
            data['data'] = MessageData(**data_obj)
        
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'SecureMessage':
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)

@dataclass
class ServerResponse:
    """服务器响应格式"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

class ProtocolError(Exception):
    """协议错误基类"""
    def __init__(self, message: str, error_code: str = "PROTOCOL_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)

class AuthError(ProtocolError):
    """认证错误"""
    def __init__(self, message: str):
        super().__init__(message, "AUTH_ERROR")

class CryptoError(ProtocolError):
    """加密错误"""
    def __init__(self, message: str):
        super().__init__(message, "CRYPTO_ERROR")

class NetworkError(ProtocolError):
    """网络错误"""
    def __init__(self, message: str):
        super().__init__(message, "NETWORK_ERROR")

class ValidationError(ProtocolError):
    """验证错误"""
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")

# 协议常量
class ProtocolConstants:
    """协议常量"""
    VERSION = "1.0"
    MAX_MESSAGE_SIZE = 4 * 1024 * 1024  # 4MB
    MAX_FILE_SIZE = 100 * 1024 * 1024   # 100MB
    DEFAULT_PORT = 8765
    HEARTBEAT_INTERVAL = 30  # 秒
    CONNECTION_TIMEOUT = 60  # 秒
    CHUNK_SIZE = 64 * 1024   # 64KB分块大小

@dataclass
class VoiceMessageData:
    """语音消息数据结构"""
    content: str  # Base64编码音频
    content_type: str = "audio"  # 如audio/wav, audio/opus
    encryption: str = "none"  # 加密方式
    duration: float = 0.0  # 音频时长（秒）
    extra: Optional[Dict[str, Any]] = None

@dataclass
class GroupMessageData:
    """群聊消息数据结构"""
    group_id: str
    sender: str
    content: str  # Base64编码内容
    content_type: str = "text"  # text/file/voice/image
    encryption: str = "none"
    timestamp: str = ""
    extra: Optional[Dict[str, Any]] = None

@dataclass
class HistoryQuery:
    """历史记录查询结构"""
    chat_type: str  # "single" or "group"
    target_id: str  # 用户名或群ID
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    limit: int = 50
    offset: int = 0

@dataclass
class HistoryRecord:
    """历史消息记录结构"""
    message_id: str
    message_type: str
    sender: str
    recipient: str
    group_id: Optional[str] = None
    content: str = ""
    content_type: str = "text"
    encryption: str = "none"
    timestamp: str = ""
    extra: Optional[Dict[str, Any]] = None 