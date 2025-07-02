"""
统一消息结构体定义

整合dataclass和ctypes两种消息格式，提供类型安全的消息处理
"""

import time
import ctypes
from enum import Enum
from dataclasses import dataclass, field
from typing import Union, List, Dict, Any, Optional

def get_timestamp() -> int:
    """获取当前的Unix时间戳"""
    return int(time.time())

# =================================================================
#                    消息类型标识枚举
# =================================================================

class MsgTag(Enum):
    """消息类型标识枚举 - 统一版本"""
    # Client to Server
    REGISTER = 1        # 注册
    LOGIN = 2           # 登录
    LOGOUT = 3          # 注销
    GET_DIRECTORY = 4   # 获取通信录
    GET_HISTORY = 5     # 获取聊天记录
    GET_PUBLIC_KEY = 6  # 获取公钥
    ALIVE = 7           # 心跳/在线状态
    BACKUP = 8          # 备份聊天记录

    # Peer to Peer
    MESSAGE = 11        # 普通消息
    VOICE = 12          # 语音消息
    FILE = 13           # 文件消息
    PICTURE = 14        # 图片消息

    # Server to Client
    SUCCESS_REGISTER = 21   # 注册成功
    SUCCESS_LOGIN = 22      # 登录成功
    SUCCESS_LOGOUT = 23     # 注销成功
    SUCCESS_BACKUP = 24     # 备份成功
    HISTORY = 25           # 聊天记录响应
    DIRECTORY = 26         # 通信录响应
    PUBLIC_KEY = 27        # 公钥响应
    FAIL_REGISTER = 28     # 注册失败
    FAIL_LOGIN = 29        # 登录失败

    # 扩展消息类型（兼容现有系统）
    TEXT_MESSAGE = 101      # 文本消息
    GROUP_MESSAGE = 102     # 群聊消息
    STEGO_MESSAGE = 103     # 隐写消息
    VOICE_MESSAGE = 104     # 语音消息（扩展）
    CREATE_GROUP = 105      # 创建群组
    HEARTBEAT = 106         # 心跳检测
    PERFORMANCE_TEST = 107  # 性能测试
    
    # 联系人管理
    ADD_CONTACT = 108       # 添加联系人
    GET_CONTACTS = 109      # 获取联系人列表
    UPDATE_CONTACT = 110    # 更新联系人
    REMOVE_CONTACT = 111    # 删除联系人
    
    # 群组管理
    GET_GROUPS = 112        # 获取群组列表
    JOIN_GROUP = 113        # 加入群组

# =================================================================
#                      DataClass 消息结构
# =================================================================

@dataclass
class BaseMessage:
    """基础消息类 - 不包含默认参数"""
    pass

# --- Client to Server Messages ---

@dataclass
class RegisterMsg(BaseMessage):
    """注册请求消息"""
    username: str
    secret: str
    email: str
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.REGISTER, init=False)

@dataclass
class LoginMsg(BaseMessage):
    """登录请求消息"""
    username: str
    secret: str
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.LOGIN, init=False)

@dataclass
class LogoutMsg(BaseMessage):
    """注销请求消息"""
    username: str
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.LOGOUT, init=False)

@dataclass
class GetDirectoryMsg(BaseMessage):
    """获取通信录请求"""
    username: str
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.GET_DIRECTORY, init=False)

@dataclass
class GetHistoryMsg(BaseMessage):
    """获取聊天记录请求"""
    chat_id: Union[str, int]
    chat_type: str = "single"  # single, group
    limit: int = 50
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.GET_HISTORY, init=False)

@dataclass
class GetPublicKeyMsg(BaseMessage):
    """获取公钥请求"""
    user_id: Union[str, int]
    dest_id: Union[str, int]
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.GET_PUBLIC_KEY, init=False)

@dataclass
class AliveMsg(BaseMessage):
    """心跳消息"""
    user_id: Union[str, int]
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.ALIVE, init=False)

@dataclass
class BackupMsg(BaseMessage):
    """备份请求消息"""
    user_id: Union[str, int]
    dest_id: Union[str, int]
    data: Union[str, bytes]
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.BACKUP, init=False)

# --- Peer to Peer Messages ---

@dataclass
class MessageMsg(BaseMessage):
    """普通消息"""
    message_id: str
    source_id: Union[str, int]
    dest_id: Union[str, int]
    content: str
    content_type: str = "text"
    encryption: str = "none"
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.MESSAGE, init=False)

@dataclass
class VoiceMsg(BaseMessage):
    """语音消息"""
    voice_id: str
    source_id: Union[str, int]
    dest_id: Union[str, int]
    data: bytes
    duration: float = 0.0
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.VOICE, init=False)

@dataclass
class FileMsg(BaseMessage):
    """文件消息"""
    file_id: str
    source_id: Union[str, int]
    dest_id: Union[str, int]
    file_name: str
    data: bytes
    file_size: int = 0
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.FILE, init=False)

@dataclass
class PictureMsg(BaseMessage):
    """图片消息"""
    picture_id: str
    source_id: Union[str, int]
    dest_id: Union[str, int]
    data: bytes
    image_format: str = "jpeg"
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.PICTURE, init=False)

# --- Server to Client Messages ---

@dataclass
class SuccessRegisterMsg(BaseMessage):
    """注册成功响应"""
    username: str
    user_id: Union[str, int]
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.SUCCESS_REGISTER, init=False)

@dataclass
class SuccessLoginMsg(BaseMessage):
    """登录成功响应"""
    username: str
    user_id: Union[str, int]
    session_token: Optional[str] = None
    public_key: Optional[str] = None
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.SUCCESS_LOGIN, init=False)

@dataclass
class SuccessLogoutMsg(BaseMessage):
    """注销成功响应"""
    username: str
    user_id: Union[str, int]
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.SUCCESS_LOGOUT, init=False)

@dataclass
class HistoryMsg(BaseMessage):
    """聊天记录响应"""
    records: List[Dict[str, Any]]
    total: int = 0
    chat_type: str = "single"
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.HISTORY, init=False)

@dataclass
class DirectoryMsg(BaseMessage):
    """通信录响应"""
    contacts: Dict[str, Any]
    total: int = 0
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.DIRECTORY, init=False)

@dataclass
class PublicKeyMsg(BaseMessage):
    """公钥响应"""
    user_id: Union[str, int]
    dest_id: Union[str, int]
    public_key: str
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.PUBLIC_KEY, init=False)

@dataclass
class FailRegisterMsg(BaseMessage):
    """注册失败响应"""
    error_type: str
    message: str = ""
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.FAIL_REGISTER, init=False)

@dataclass
class FailLoginMsg(BaseMessage):
    """登录失败响应"""
    error_type: str
    message: str = ""
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.FAIL_LOGIN, init=False)

# --- 扩展消息类型（兼容现有系统）---

@dataclass
class TextMessageMsg(BaseMessage):
    """文本消息（扩展）"""
    recipient: str
    data: Dict[str, Any]
    sender: Optional[str] = None
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.TEXT_MESSAGE, init=False)

@dataclass
class GroupMessageMsg(BaseMessage):
    """群聊消息"""
    group_id: str
    data: Dict[str, Any]
    sender: Optional[str] = None
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.GROUP_MESSAGE, init=False)

@dataclass
class StegoMessageMsg(BaseMessage):
    """隐写消息"""
    recipient: str
    data: Dict[str, Any]
    sender: Optional[str] = None
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.STEGO_MESSAGE, init=False)

@dataclass
class CreateGroupMsg(BaseMessage):
    """创建群组消息"""
    group_id: str
    group_name: str
    members: List[str]
    sender: Optional[str] = None
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.CREATE_GROUP, init=False)

@dataclass
class HeartbeatMsg(BaseMessage):
    """心跳检测消息"""
    sender: Optional[str] = None
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.HEARTBEAT, init=False)

@dataclass
class AddContactMsg(BaseMessage):
    """添加联系人消息"""
    contact_username: str
    alias: Optional[str] = None
    group: str = "默认分组"
    sender: Optional[str] = None
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.ADD_CONTACT, init=False)

@dataclass
class GetContactsMsg(BaseMessage):
    """获取联系人列表消息"""
    sender: Optional[str] = None
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.GET_CONTACTS, init=False)

@dataclass
class UpdateContactMsg(BaseMessage):
    """更新联系人消息"""
    contact_user_id: int
    alias: Optional[str] = None
    group: Optional[str] = None
    notes: Optional[str] = None
    is_favorite: Optional[bool] = None
    sender: Optional[str] = None
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.UPDATE_CONTACT, init=False)

@dataclass
class RemoveContactMsg(BaseMessage):
    """删除联系人消息"""
    contact_user_id: int
    sender: Optional[str] = None
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.REMOVE_CONTACT, init=False)

@dataclass
class GetGroupsMsg(BaseMessage):
    """获取群组列表消息"""
    sender: Optional[str] = None
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.GET_GROUPS, init=False)

@dataclass
class JoinGroupMsg(BaseMessage):
    """加入群组消息"""
    group_id: str
    sender: Optional[str] = None
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.JOIN_GROUP, init=False)

# =================================================================
#                      CTypes 消息结构
# =================================================================

# 常量定义
MAX_PAYLOAD_SIZE = 2044  # 2048 - 4 (msgID)

class Msg_Info(ctypes.Structure):
    """基础消息信息结构"""
    _pack_ = 1
    _fields_ = [
        ("username", ctypes.c_char * 32),
        ("secret", ctypes.c_char * 32),
        ("email", ctypes.c_char * 32),
        ("userID", ctypes.c_char * 8),
        ("source", ctypes.c_char * 8),
        ("dest", ctypes.c_char * 8),
        ("MessageID", ctypes.c_char * 16),
        ("content", ctypes.c_char * 1024),
        ("ChatID", ctypes.c_char * 8),
        ("time", ctypes.c_char * 16),
        ("errortype", ctypes.c_char * 16)
    ]

class Msg_Voice_Data(ctypes.Structure):
    """语音数据结构"""
    _pack_ = 1
    _fields_ = [
        ("VoiceID", ctypes.c_char * 16),
        ("source", ctypes.c_char * 8),
        ("dest", ctypes.c_char * 8),
        ("time", ctypes.c_char * 16),
        ("data", ctypes.c_char * (MAX_PAYLOAD_SIZE - 48))
    ]

class Msg_File_Data(ctypes.Structure):
    """文件数据结构"""
    _pack_ = 1
    _fields_ = [
        ("FileID", ctypes.c_char * 16),
        ("source", ctypes.c_char * 8),
        ("dest", ctypes.c_char * 8),
        ("time", ctypes.c_char * 16),
        ("data", ctypes.c_char * (MAX_PAYLOAD_SIZE - 48))
    ]

class Msg_Picture_Data(ctypes.Structure):
    """图片数据结构"""
    _pack_ = 1
    _fields_ = [
        ("PictureID", ctypes.c_char * 16),
        ("source", ctypes.c_char * 8),
        ("dest", ctypes.c_char * 8),
        ("time", ctypes.c_char * 16),
        ("data", ctypes.c_char * (MAX_PAYLOAD_SIZE - 48))
    ]

class Msg_History_Data(ctypes.Structure):
    """历史记录数据结构"""
    _pack_ = 1
    _fields_ = [
        ("flag", ctypes.c_char * 1),  # 0: 获取历史消息 1: 备份历史消息
        ("userID", ctypes.c_char * 8),
        ("dest", ctypes.c_char * 8),
        ("data", ctypes.c_char * (MAX_PAYLOAD_SIZE - 33)),
        ("time", ctypes.c_char * 16)
    ]

class Msg_Payload(ctypes.Union):
    """消息载荷联合体"""
    _pack_ = 1
    _fields_ = [
        ("Msg_Info", Msg_Info),
        ("Msg_Voice_Data", Msg_Voice_Data),
        ("Msg_File_Data", Msg_File_Data),
        ("Msg_Picture_Data", Msg_Picture_Data),
        ("Msg_History_Data", Msg_History_Data)
    ]

class MsgHeader(ctypes.Structure):
    """消息头结构"""
    _pack_ = 1
    _fields_ = [
        ("msgID", ctypes.c_int),  # 4 Bytes - 消息类型ID
        ("Msg_Payload", Msg_Payload)  # 2044 Bytes - 消息载荷
    ]

# =================================================================
#                      消息类型映射
# =================================================================

# 消息类型到字符串的映射
MSG_TYPE_TO_STRING = {
    MsgTag.REGISTER: "register",
    MsgTag.LOGIN: "login",
    MsgTag.LOGOUT: "logout",
    MsgTag.GET_DIRECTORY: "get_directory",
    MsgTag.GET_HISTORY: "get_history",
    MsgTag.GET_PUBLIC_KEY: "get_public_key",
    MsgTag.ALIVE: "alive",
    MsgTag.BACKUP: "backup",
    MsgTag.MESSAGE: "message",
    MsgTag.VOICE: "voice",
    MsgTag.FILE: "file",
    MsgTag.PICTURE: "picture",
    MsgTag.SUCCESS_REGISTER: "success_register",
    MsgTag.SUCCESS_LOGIN: "success_login",
    MsgTag.SUCCESS_LOGOUT: "success_logout",
    MsgTag.SUCCESS_BACKUP: "success_backup",
    MsgTag.HISTORY: "history",
    MsgTag.DIRECTORY: "directory",
    MsgTag.PUBLIC_KEY: "public_key",
    MsgTag.FAIL_REGISTER: "fail_register",
    MsgTag.FAIL_LOGIN: "fail_login",
    # 扩展类型
    MsgTag.TEXT_MESSAGE: "text_message",
    MsgTag.GROUP_MESSAGE: "group_message",
    MsgTag.STEGO_MESSAGE: "stego_message",
    MsgTag.VOICE_MESSAGE: "voice_message",
    MsgTag.CREATE_GROUP: "create_group",
    MsgTag.HEARTBEAT: "heartbeat",
    MsgTag.PERFORMANCE_TEST: "performance_test",
    MsgTag.ADD_CONTACT: "add_contact",
    MsgTag.GET_CONTACTS: "get_contacts",
    MsgTag.UPDATE_CONTACT: "update_contact",
    MsgTag.REMOVE_CONTACT: "remove_contact",
    MsgTag.GET_GROUPS: "get_groups",
    MsgTag.JOIN_GROUP: "join_group"
}

# 字符串到消息类型的映射
STRING_TO_MSG_TYPE = {v: k for k, v in MSG_TYPE_TO_STRING.items()}

# DataClass类型映射
DATACLASS_TYPE_MAP = {
    MsgTag.REGISTER: RegisterMsg,
    MsgTag.LOGIN: LoginMsg,
    MsgTag.LOGOUT: LogoutMsg,
    MsgTag.GET_DIRECTORY: GetDirectoryMsg,
    MsgTag.GET_HISTORY: GetHistoryMsg,
    MsgTag.GET_PUBLIC_KEY: GetPublicKeyMsg,
    MsgTag.ALIVE: AliveMsg,
    MsgTag.BACKUP: BackupMsg,
    MsgTag.MESSAGE: MessageMsg,
    MsgTag.VOICE: VoiceMsg,
    MsgTag.FILE: FileMsg,
    MsgTag.PICTURE: PictureMsg,
    MsgTag.SUCCESS_REGISTER: SuccessRegisterMsg,
    MsgTag.SUCCESS_LOGIN: SuccessLoginMsg,
    MsgTag.SUCCESS_LOGOUT: SuccessLogoutMsg,
    MsgTag.HISTORY: HistoryMsg,
    MsgTag.DIRECTORY: DirectoryMsg,
    MsgTag.PUBLIC_KEY: PublicKeyMsg,
    MsgTag.FAIL_REGISTER: FailRegisterMsg,
    MsgTag.FAIL_LOGIN: FailLoginMsg,
    # 扩展类型
    MsgTag.TEXT_MESSAGE: TextMessageMsg,
    MsgTag.GROUP_MESSAGE: GroupMessageMsg,
    MsgTag.STEGO_MESSAGE: StegoMessageMsg,
    MsgTag.CREATE_GROUP: CreateGroupMsg,
    MsgTag.HEARTBEAT: HeartbeatMsg,
    MsgTag.ADD_CONTACT: AddContactMsg,
    MsgTag.GET_CONTACTS: GetContactsMsg,
    MsgTag.UPDATE_CONTACT: UpdateContactMsg,
    MsgTag.REMOVE_CONTACT: RemoveContactMsg,
    MsgTag.GET_GROUPS: GetGroupsMsg,
    MsgTag.JOIN_GROUP: JoinGroupMsg
} 