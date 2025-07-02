"""
统一数据包处理模块

实现JSON + Base64格式的消息封包、拆包、签名和验证功能
"""

import json
import base64
import hashlib
import hmac
import logging
from typing import Dict, Any, Optional, Union, Tuple
from datetime import datetime
import uuid

from .schema import (
    SecureMessage, MessageData, MessageType, ContentType, 
    EncryptionType, ProtocolError, ValidationError, 
    ProtocolConstants, ServerResponse,
    VoiceMessageData, GroupMessageData, HistoryQuery, HistoryRecord
)

logger = logging.getLogger(__name__)

class PacketProcessor:
    """数据包处理器"""
    
    def __init__(self, secret_key: Optional[str] = None):
        """
        初始化数据包处理器
        
        Args:
            secret_key: 用于HMAC签名的密钥
        """
        self.secret_key = secret_key or "default-secret-key"
    
    def encode_binary_content(self, binary_data: bytes) -> str:
        """
        将二进制数据编码为Base64字符串
        
        Args:
            binary_data: 二进制数据
            
        Returns:
            Base64编码的字符串
        """
        try:
            return base64.b64encode(binary_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Base64编码失败: {e}")
            raise ValidationError(f"Base64编码失败: {e}")
    
    def decode_binary_content(self, encoded_data: str) -> bytes:
        """
        将Base64字符串解码为二进制数据
        
        Args:
            encoded_data: Base64编码的字符串
            
        Returns:
            解码后的二进制数据
        """
        try:
            return base64.b64decode(encoded_data.encode('utf-8'))
        except Exception as e:
            logger.error(f"Base64解码失败: {e}")
            raise ValidationError(f"Base64解码失败: {e}")
    
    def generate_signature(self, content: str) -> str:
        """
        生成HMAC签名
        
        Args:
            content: 要签名的内容
            
        Returns:
            HMAC签名字符串
        """
        try:
            signature = hmac.new(
                self.secret_key.encode('utf-8'),
                content.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            return signature
        except Exception as e:
            logger.error(f"生成签名失败: {e}")
            raise ValidationError(f"生成签名失败: {e}")
    
    def verify_signature(self, content: str, signature: str) -> bool:
        """
        验证HMAC签名
        
        Args:
            content: 要验证的内容
            signature: 签名字符串
            
        Returns:
            验证是否成功
        """
        try:
            expected_signature = self.generate_signature(content)
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"验证签名失败: {e}")
            return False
    
    def calculate_checksum(self, data: bytes) -> str:
        """
        计算数据的SHA256校验和
        
        Args:
            data: 二进制数据
            
        Returns:
            SHA256校验和
        """
        return hashlib.sha256(data).hexdigest()
    
    def create_text_message(self, 
                           sender: str, 
                           recipient: str, 
                           text_content: str,
                           encryption: EncryptionType = EncryptionType.NONE) -> SecureMessage:
        """
        创建文本消息
        
        Args:
            sender: 发送者用户名
            recipient: 接收者用户名
            text_content: 文本内容
            encryption: 加密类型
            
        Returns:
            安全消息对象
        """
        try:
            # 将文本内容编码为Base64
            encoded_content = self.encode_binary_content(text_content.encode('utf-8'))
            
            # 创建消息数据
            message_data = MessageData(
                content=encoded_content,
                content_type=ContentType.TEXT,
                encryption=encryption
            )
            
            # 创建安全消息
            secure_message = SecureMessage(
                type=MessageType.TEXT_MESSAGE,
                sender=sender,
                recipient=recipient,
                data=message_data
            )
            
            # 生成签名
            if self.secret_key:
                content_for_signature = f"{sender}{recipient}{text_content}"
                signature = self.generate_signature(content_for_signature)
                secure_message.data.signature = signature
            
            return secure_message
            
        except Exception as e:
            logger.error(f"创建文本消息失败: {e}")
            raise ValidationError(f"创建文本消息失败: {e}")
    
    def create_file_message(self,
                           sender: str,
                           recipient: str,
                           file_data: bytes,
                           filename: str,
                           mime_type: str = "application/octet-stream",
                           encryption: EncryptionType = EncryptionType.NONE) -> SecureMessage:
        """
        创建文件消息
        
        Args:
            sender: 发送者用户名
            recipient: 接收者用户名
            file_data: 文件二进制数据
            filename: 文件名
            mime_type: MIME类型
            encryption: 加密类型
            
        Returns:
            安全消息对象
        """
        try:
            # 检查文件大小
            if len(file_data) > ProtocolConstants.MAX_FILE_SIZE:
                raise ValidationError(f"文件过大，最大支持{ProtocolConstants.MAX_FILE_SIZE}字节")
            
            # 编码文件数据
            encoded_content = self.encode_binary_content(file_data)
            
            # 计算校验和
            checksum = self.calculate_checksum(file_data)
            
            # 创建文件信息
            from .schema import FileInfo
            file_info = FileInfo(
                filename=filename,
                size=len(file_data),
                mime_type=mime_type,
                checksum=checksum
            )
            
            # 创建消息数据
            message_data = MessageData(
                content=encoded_content,
                content_type=ContentType.FILE,
                encryption=encryption,
                file_info=file_info
            )
            
            # 创建安全消息
            secure_message = SecureMessage(
                type=MessageType.FILE_MESSAGE,
                sender=sender,
                recipient=recipient,
                data=message_data
            )
            
            # 生成签名
            if self.secret_key:
                content_for_signature = f"{sender}{recipient}{filename}{checksum}"
                signature = self.generate_signature(content_for_signature)
                secure_message.data.signature = signature
            
            return secure_message
            
        except Exception as e:
            logger.error(f"创建文件消息失败: {e}")
            raise ValidationError(f"创建文件消息失败: {e}")
    
    def create_voice_message(self,
                            sender: str,
                            recipient: str,
                            voice_data: bytes,
                            sample_rate: int = 44100,
                            channels: int = 1,
                            duration: float = 0.0,
                            codec: str = "wav",
                            encryption: EncryptionType = EncryptionType.NONE) -> SecureMessage:
        """
        创建语音消息
        
        Args:
            sender: 发送者用户名
            recipient: 接收者用户名
            voice_data: 语音二进制数据
            sample_rate: 采样率
            channels: 声道数
            duration: 时长(秒)
            codec: 编码格式
            encryption: 加密类型
            
        Returns:
            安全消息对象
        """
        try:
            # 编码语音数据
            encoded_content = self.encode_binary_content(voice_data)
            
            # 创建语音参数
            from .schema import VoiceParams
            voice_params = VoiceParams(
                sample_rate=sample_rate,
                channels=channels,
                duration=duration,
                codec=codec
            )
            
            # 创建消息数据
            message_data = MessageData(
                content=encoded_content,
                content_type=ContentType.VOICE,
                encryption=encryption,
                voice_params=voice_params
            )
            
            # 创建安全消息
            secure_message = SecureMessage(
                type=MessageType.VOICE_MESSAGE,
                sender=sender,
                recipient=recipient,
                data=message_data
            )
            
            # 生成签名
            if self.secret_key:
                checksum = self.calculate_checksum(voice_data)
                content_for_signature = f"{sender}{recipient}{codec}{checksum}"
                signature = self.generate_signature(content_for_signature)
                secure_message.data.signature = signature
            
            return secure_message
            
        except Exception as e:
            logger.error(f"创建语音消息失败: {e}")
            raise ValidationError(f"创建语音消息失败: {e}")
    
    def create_system_message(self,
                             message_type: MessageType,
                             data: Optional[Dict[str, Any]] = None,
                             sender: str = "system",
                             recipient: str = "") -> SecureMessage:
        """
        创建系统消息
        
        Args:
            message_type: 消息类型
            data: 消息数据
            sender: 发送者
            recipient: 接收者
            
        Returns:
            安全消息对象
        """
        try:
            secure_message = SecureMessage(
                type=message_type,
                sender=sender,
                recipient=recipient,
                metadata=data
            )
            
            return secure_message
            
        except Exception as e:
            logger.error(f"创建系统消息失败: {e}")
            raise ValidationError(f"创建系统消息失败: {e}")
    
    def pack_message(self, message: SecureMessage) -> str:
        """
        将安全消息打包为JSON字符串
        
        Args:
            message: 安全消息对象
            
        Returns:
            JSON字符串
        """
        try:
            return message.to_json()
        except Exception as e:
            logger.error(f"消息打包失败: {e}")
            raise ValidationError(f"消息打包失败: {e}")
    
    def unpack_message(self, json_data: str) -> SecureMessage:
        """
        从JSON字符串解包安全消息
        
        Args:
            json_data: JSON字符串
            
        Returns:
            安全消息对象
        """
        try:
            # 检查消息大小
            if len(json_data.encode('utf-8')) > ProtocolConstants.MAX_MESSAGE_SIZE:
                raise ValidationError(f"消息过大，最大支持{ProtocolConstants.MAX_MESSAGE_SIZE}字节")
            
            return SecureMessage.from_json(json_data)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            raise ValidationError(f"JSON解析失败: {e}")
        except Exception as e:
            logger.error(f"消息解包失败: {e}")
            raise ValidationError(f"消息解包失败: {e}")
    
    def validate_message(self, message: SecureMessage) -> Tuple[bool, str]:
        """
        验证消息的完整性和有效性
        
        Args:
            message: 安全消息对象
            
        Returns:
            (是否有效, 错误信息)
        """
        try:
            # 检查必要字段
            if not message.sender or not message.type:
                return False, "缺少必要字段"
            
            # 检查版本
            if message.version != ProtocolConstants.VERSION:
                return False, f"协议版本不匹配: {message.version}"
            
            # 验证签名
            if message.data and message.data.signature and self.secret_key:
                if message.data.content_type == ContentType.TEXT:
                    # 解码文本内容进行签名验证
                    try:
                        text_content = self.decode_binary_content(message.data.content).decode('utf-8')
                        content_for_signature = f"{message.sender}{message.recipient}{text_content}"
                        if not self.verify_signature(content_for_signature, message.data.signature):
                            return False, "签名验证失败"
                    except Exception as e:
                        return False, f"签名验证异常: {e}"
            
            # 验证文件校验和
            if (message.data and 
                message.data.content_type == ContentType.FILE and 
                message.data.file_info):
                
                try:
                    file_data = self.decode_binary_content(message.data.content)
                    calculated_checksum = self.calculate_checksum(file_data)
                    if calculated_checksum != message.data.file_info.checksum:
                        return False, "文件校验和不匹配"
                except Exception as e:
                    return False, f"文件校验失败: {e}"
            
            return True, "消息有效"
            
        except Exception as e:
            logger.error(f"消息验证异常: {e}")
            return False, f"验证异常: {e}"
    
    def extract_text_content(self, message: SecureMessage) -> str:
        """
        从消息中提取文本内容
        
        Args:
            message: 安全消息对象
            
        Returns:
            文本内容
        """
        try:
            if not message.data or message.data.content_type != ContentType.TEXT:
                raise ValidationError("不是文本消息")
            
            text_bytes = self.decode_binary_content(message.data.content)
            return text_bytes.decode('utf-8')
            
        except Exception as e:
            logger.error(f"提取文本内容失败: {e}")
            raise ValidationError(f"提取文本内容失败: {e}")
    
    def extract_file_content(self, message: SecureMessage) -> Tuple[bytes, str, str]:
        """
        从消息中提取文件内容
        
        Args:
            message: 安全消息对象
            
        Returns:
            (文件数据, 文件名, MIME类型)
        """
        try:
            if not message.data or message.data.content_type != ContentType.FILE:
                raise ValidationError("不是文件消息")
            
            if not message.data.file_info:
                raise ValidationError("缺少文件信息")
            
            file_data = self.decode_binary_content(message.data.content)
            filename = message.data.file_info.filename
            mime_type = message.data.file_info.mime_type
            
            return file_data, filename, mime_type
            
        except Exception as e:
            logger.error(f"提取文件内容失败: {e}")
            raise ValidationError(f"提取文件内容失败: {e}")
    
    def extract_voice_content(self, message: SecureMessage) -> Tuple[bytes, dict]:
        """
        从消息中提取语音内容
        
        Args:
            message: 安全消息对象
            
        Returns:
            (语音数据, 语音参数字典)
        """
        try:
            if not message.data or message.data.content_type != ContentType.VOICE:
                raise ValidationError("不是语音消息")
            
            if not message.data.voice_params:
                raise ValidationError("缺少语音参数")
            
            voice_data = self.decode_binary_content(message.data.content)
            voice_params = {
                'sample_rate': message.data.voice_params.sample_rate,
                'channels': message.data.voice_params.channels,
                'duration': message.data.voice_params.duration,
                'codec': message.data.voice_params.codec,
                'bitrate': message.data.voice_params.bitrate
            }
            
            return voice_data, voice_params
            
        except Exception as e:
            logger.error(f"提取语音内容失败: {e}")
            raise ValidationError(f"提取语音内容失败: {e}")

    def pack_voice_message(self, sender: str, recipient: str, audio_b64: str, duration: float, encryption: str = "none", content_type: str = "audio/wav", extra: Optional[dict] = None) -> str:
        """封装语音消息"""
        msg = {
            "type": MessageType.VOICE_MESSAGE.value,
            "sender": sender,
            "recipient": recipient,
            "data": {
                "content": audio_b64,
                "content_type": content_type,
                "encryption": encryption,
                "duration": duration,
                "extra": extra or {}
            },
            "timestamp": self._now(),
        }
        return json.dumps(msg, ensure_ascii=False)

    def pack_group_message(self, group_id: str, sender: str, content: str, content_type: str = "text", encryption: str = "none", extra: Optional[dict] = None) -> str:
        """封装群聊消息"""
        msg = {
            "type": MessageType.GROUP_MESSAGE.value,
            "group_id": group_id,
            "sender": sender,
            "data": {
                "content": content,
                "content_type": content_type,
                "encryption": encryption,
                "extra": extra or {}
            },
            "timestamp": self._now(),
        }
        return json.dumps(msg, ensure_ascii=False)

    def pack_history_query(self, chat_type: str, target_id: str, start_time: Optional[str] = None, end_time: Optional[str] = None, limit: int = 50, offset: int = 0) -> str:
        """封装历史记录查询请求"""
        msg = {
            "type": MessageType.GET_HISTORY.value,
            "chat_type": chat_type,
            "target_id": target_id,
            "start_time": start_time,
            "end_time": end_time,
            "limit": limit,
            "offset": offset,
            "timestamp": self._now(),
        }
        return json.dumps(msg, ensure_ascii=False)

    def pack_history_response(self, records: list, total: int) -> str:
        """封装历史记录响应"""
        msg = {
            "type": MessageType.HISTORY_RESPONSE.value,
            "records": records,
            "total": total,
            "timestamp": self._now(),
        }
        return json.dumps(msg, ensure_ascii=False)

# 全局数据包处理器实例
default_packet_processor = PacketProcessor()

# 便捷函数
def create_text_message(sender: str, recipient: str, text: str) -> str:
    """创建文本消息的便捷函数"""
    message = default_packet_processor.create_text_message(sender, recipient, text)
    return default_packet_processor.pack_message(message)

def create_file_message(sender: str, recipient: str, file_data: bytes, filename: str) -> str:
    """创建文件消息的便捷函数"""
    message = default_packet_processor.create_file_message(sender, recipient, file_data, filename)
    return default_packet_processor.pack_message(message)

def parse_message(json_data: str) -> SecureMessage:
    """解析消息的便捷函数"""
    return default_packet_processor.unpack_message(json_data)

def validate_message(message: SecureMessage) -> bool:
    """验证消息的便捷函数"""
    is_valid, _ = default_packet_processor.validate_message(message)
    return is_valid 