import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Union, List, Dict # Import necessary types

def get_timestamp() -> int:
    """获取当前的Unix时间戳"""
    return int(time.time())

# --- ENUM: Based on the complete list from Message.py ---
# Note: Typos like 'Registser' and 'PbulicKey' have been corrected for clarity.
class MsgTag(Enum):
    """消息类型标识枚举"""
    # --- Client to Server ---
    Register = 1
    Login = 2
    Logout = 3
    GetDirectory = 4
    GetHistory = 5
    GetPublicKey = 6
    Alive = 7
    BackUp = 8

    # --- Peer to Peer ---
    Message = 11
    Voice = 12
    File = 13
    Picture = 14

    # --- Server to Client ---
    SuccessRegister = 21
    SuccessLogin = 22
    SuccessLogout = 23
    SuccessBackUp = 24
    History = 25
    Directory = 26
    PublicKey = 27
    FailRegister = 28
    FailLogin = 29

# =================================================================
#               DATACLASSES BASED ON Message.py
# =================================================================

# --- Client to Server Messages ---

@dataclass
class RegisterMsg:
    """C->S 注册请求 (Tag: 1)"""
    username: str
    secret: str
    email: str
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.Register, init=False)

@dataclass
class LoginMsg:
    """C->S 登录请求 (Tag: 2)"""
    username: str
    secret: str
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.Login, init=False)

@dataclass
class LogoutMsg:
    """C->S 注销请求 (Tag: 3)"""
    username: str
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.Logout, init=False)

@dataclass
class GetDirectoryMsg:
    """C->S 获取通信录请求 (Tag: 4)"""
    username: str
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.GetDirectory, init=False)

@dataclass
class GetHistoryMsg:
    """C->S 获取聊天记录请求 (Tag: 5)"""
    chat_id: Union[str, int]
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.GetHistory, init=False)

@dataclass
class GetPublicKeyMsg:
    """C->S 获取好友公钥请求 (Tag: 6)"""
    user_id: Union[str, int]
    dest_id: Union[str, int]
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.GetPublicKey, init=False)

@dataclass
class AliveMsg:
    """C->S 在线心跳包 (Tag: 7)"""
    user_id: Union[str, int]
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.Alive, init=False)

@dataclass
class BackupMsg:
    """C->S 备份聊天记录请求 (Tag: 8)"""
    user_id: Union[str, int]
    dest_id: Union[str, int]
    # 'data' represents the history content, could be a JSON string or bytes
    data: Union[str, bytes] 
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.BackUp, init=False)


# --- Peer to Peer Messages ---

@dataclass
class MessageMsg:
    """P2P 普通消息 (Tag: 11)"""
    message_id: str
    source_id: Union[str, int]
    dest_id: Union[str, int]
    content: str
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.Message, init=False)

@dataclass
class VoiceMsg: # 后面需要加入分包功能
    """P2P 语音消息 (Tag: 12)"""
    voice_id: str
    source_id: Union[str, int]
    dest_id: Union[str, int]
    data: bytes  # Voice data is binary
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.Voice, init=False)

@dataclass
class FileMsg:
    """P2P 文件消息 (Tag: 13)"""
    file_id: str
    source_id: Union[str, int]
    dest_id: Union[str, int]
    file_name: str # It's good practice to include the file name
    data: bytes  # File data is binary
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.File, init=False)
    
@dataclass
class PictureMsg:
    """P2P 图片消息 (Tag: 14)"""
    picture_id: str
    source_id: Union[str, int]
    dest_id: Union[str, int]
    data: bytes  # Picture data is binary
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.Picture, init=False)


# --- Server to Client Messages ---

@dataclass
class SuccessRegisterMsg:
    """S->C 注册成功 (Tag: 21)"""
    username: str
    user_id: Union[str, int]
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.SuccessRegister, init=False)

@dataclass
class SuccessLoginMsg:
    """S->C 登录成功 (Tag: 22)"""
    username: str
    user_id: Union[str, int]
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.SuccessLogin, init=False)

@dataclass
class SuccessLogoutMsg:
    """S->C 注销成功 (Tag: 23)"""
    username: str
    user_id: Union[str, int]
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.SuccessLogout, init=False)

@dataclass
class SuccessBackUpMsg:
    """S->C 备份成功 (Tag: 24)"""
    user_id: Union[str, int]
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.SuccessBackUp, init=False)
    
@dataclass
class HistoryMsg:
    """S->C 返回聊天记录 (Tag: 25)"""
    # 'data' would typically be a JSON string of a list of messages
    data: str
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.History, init=False)

@dataclass
class DirectoryMsg:
    """S->C 返回通信录 (Tag: 26)"""
    # 'data' would typically be a JSON string of a list of contacts
    data: str
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.Directory, init=False)

@dataclass
class PublicKeyMsg:
    """S->C 返回公钥 (Tag: 27)"""
    user_id: Union[str, int]
    dest_id: Union[str, int]
    public_key: str # The public key itself
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.PublicKey, init=False)

@dataclass
class FailRegisterMsg:
    """S->C 注册失败 (Tag: 28)"""
    error_type: str
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.FailRegister, init=False)

@dataclass
class FailLoginMsg:
    """S->C 登录失败 (Tag: 29)"""
    error_type: str
    time: int = field(default_factory=get_timestamp)
    tag: MsgTag = field(default=MsgTag.FailLogin, init=False)