"""
异步协议处理器

提供统一的消息协议处理，支持JSON和二进制两种格式
"""

import asyncio
import json
import struct
import zlib
import base64
import logging
from typing import Dict, Any, Optional, Union, Type
from dataclasses import asdict, is_dataclass
from datetime import datetime

from .message_structures import (
    MsgTag, BaseMessage, MSG_TYPE_TO_STRING, STRING_TO_MSG_TYPE,
    DATACLASS_TYPE_MAP, MsgHeader
)

logger = logging.getLogger(__name__)

class ProtocolError(Exception):
    """协议处理异常"""
    pass

class AsyncProtocolProcessor:
    """异步协议处理器"""
    
    def __init__(self, 
                 enable_compression: bool = True,
                 enable_encryption: bool = False,
                 max_message_size: int = 4 * 1024 * 1024):
        """
        初始化异步协议处理器
        
        Args:
            enable_compression: 是否启用压缩
            enable_encryption: 是否启用加密
            max_message_size: 最大消息大小
        """
        self.enable_compression = enable_compression
        self.enable_encryption = enable_encryption
        self.max_message_size = max_message_size
        
        # 统计信息
        self.stats = {
            'messages_processed': 0,
            'bytes_sent': 0,
            'bytes_received': 0,
            'compression_ratio': 0.0,
            'errors': 0
        }
    
    async def serialize_message(self, message: Union[BaseMessage, Dict[str, Any]], 
                               format_type: str = "json") -> bytes:
        """
        异步序列化消息
        
        Args:
            message: 要序列化的消息
            format_type: 格式类型 ("json" 或 "binary")
            
        Returns:
            序列化后的字节数据
        """
        try:
            if format_type == "json":
                return await self._serialize_json(message)
            elif format_type == "binary":
                return await self._serialize_binary(message)
            else:
                raise ProtocolError(f"不支持的格式类型: {format_type}")
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"消息序列化失败: {e}")
            raise ProtocolError(f"序列化失败: {e}")
    
    async def deserialize_message(self, data: bytes, 
                                 format_type: str = "json") -> Dict[str, Any]:
        """
        异步反序列化消息
        
        Args:
            data: 要反序列化的字节数据
            format_type: 格式类型 ("json" 或 "binary")
            
        Returns:
            反序列化后的消息字典
        """
        try:
            if format_type == "json":
                return await self._deserialize_json(data)
            elif format_type == "binary":
                return await self._deserialize_binary(data)
            else:
                raise ProtocolError(f"不支持的格式类型: {format_type}")
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"消息反序列化失败: {e}")
            raise ProtocolError(f"反序列化失败: {e}")
    
    async def _serialize_json(self, message: Union[BaseMessage, Dict[str, Any]]) -> bytes:
        """JSON格式序列化"""
        # 转换为字典
        if is_dataclass(message):
            data = asdict(message)
            # 处理枚举类型
            if 'tag' in data and isinstance(data['tag'], MsgTag):
                data['tag'] = data['tag'].value
        elif isinstance(message, dict):
            data = message.copy()
        else:
            raise ProtocolError(f"不支持的消息类型: {type(message)}")
        
        # 添加元数据
        data['_protocol_version'] = '1.0'
        data['_timestamp'] = datetime.now().isoformat()
        
        # JSON序列化
        json_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        json_bytes = json_str.encode('utf-8')
        
        # 压缩（如果启用）
        if self.enable_compression and len(json_bytes) > 1024:
            compressed = zlib.compress(json_bytes, level=6)
            if len(compressed) < len(json_bytes):
                # 压缩有效果
                header = struct.pack('!I', len(json_bytes)) + b'COMP'
                result = header + compressed
                self.stats['compression_ratio'] = len(compressed) / len(json_bytes)
            else:
                # 压缩无效果，使用原始数据
                header = struct.pack('!I', len(json_bytes)) + b'NONE'
                result = header + json_bytes
        else:
            header = struct.pack('!I', len(json_bytes)) + b'NONE'
            result = header + json_bytes
        
        self.stats['bytes_sent'] += len(result)
        return result
    
    async def _deserialize_json(self, data: bytes) -> Dict[str, Any]:
        """JSON格式反序列化"""
        if len(data) < 8:
            raise ProtocolError("数据长度不足")
        
        # 解析头部
        original_size = struct.unpack('!I', data[:4])[0]
        compression_flag = data[4:8]
        payload = data[8:]
        
        # 检查大小限制
        if original_size > self.max_message_size:
            raise ProtocolError(f"消息过大: {original_size} > {self.max_message_size}")
        
        # 解压缩（如果需要）
        if compression_flag == b'COMP':
            try:
                json_bytes = zlib.decompress(payload)
            except zlib.error as e:
                raise ProtocolError(f"解压缩失败: {e}")
        elif compression_flag == b'NONE':
            json_bytes = payload
        else:
            raise ProtocolError(f"未知的压缩标志: {compression_flag}")
        
        # 验证大小
        if len(json_bytes) != original_size:
            raise ProtocolError("解压缩后大小不匹配")
        
        # JSON反序列化
        try:
            json_str = json_bytes.decode('utf-8')
            data_dict = json.loads(json_str)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ProtocolError(f"JSON解析失败: {e}")
        
        self.stats['bytes_received'] += len(data)
        self.stats['messages_processed'] += 1
        
        return data_dict
    
    async def _serialize_binary(self, message: Union[BaseMessage, Dict[str, Any]]) -> bytes:
        """二进制格式序列化"""
        # TODO: 实现二进制序列化
        # 这里可以使用protobuf、msgpack或自定义二进制格式
        raise NotImplementedError("二进制序列化尚未实现")
    
    async def _deserialize_binary(self, data: bytes) -> Dict[str, Any]:
        """二进制格式反序列化"""
        # TODO: 实现二进制反序列化
        raise NotImplementedError("二进制反序列化尚未实现")
    
    def create_message_from_dict(self, data: Dict[str, Any]) -> Optional[BaseMessage]:
        """
        从字典创建消息对象
        
        Args:
            data: 消息字典
            
        Returns:
            消息对象或None
        """
        try:
            # 获取消息类型
            msg_type_str = data.get('type')
            if not msg_type_str:
                return None
            
            # 查找消息类型
            msg_type = STRING_TO_MSG_TYPE.get(msg_type_str)
            if not msg_type:
                return None
            
            # 获取对应的dataclass
            dataclass_type = DATACLASS_TYPE_MAP.get(msg_type)
            if not dataclass_type:
                return None
            
            # 过滤参数
            init_fields = dataclass_type.__dataclass_fields__.keys()
            filtered_data = {k: v for k, v in data.items() 
                           if k in init_fields and k != 'tag'}
            
            # 创建消息对象
            return dataclass_type(**filtered_data)
            
        except Exception as e:
            logger.error(f"创建消息对象失败: {e}")
            return None
    
    def get_message_type_from_string(self, type_str: str) -> Optional[MsgTag]:
        """从字符串获取消息类型"""
        return STRING_TO_MSG_TYPE.get(type_str)
    
    def get_string_from_message_type(self, msg_type: MsgTag) -> Optional[str]:
        """从消息类型获取字符串"""
        return MSG_TYPE_TO_STRING.get(msg_type)
    
    async def create_response_message(self, request_data: Dict[str, Any], 
                                    success: bool, 
                                    message: str = "",
                                    **kwargs) -> Dict[str, Any]:
        """
        创建响应消息
        
        Args:
            request_data: 请求消息数据
            success: 是否成功
            message: 响应消息
            **kwargs: 额外的响应数据
            
        Returns:
            响应消息字典
        """
        response = {
            'success': success,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            **kwargs
        }
        
        # 根据请求类型设置响应类型
        request_type = request_data.get('type')
        if request_type:
            response['response_to'] = request_type
        
        return response
    
    async def validate_message(self, data: Dict[str, Any]) -> bool:
        """
        验证消息格式
        
        Args:
            data: 消息数据
            
        Returns:
            是否有效
        """
        try:
            # 基本字段检查
            if not isinstance(data, dict):
                return False
            
            # 检查必需字段
            if 'type' not in data:
                return False
            
            # 检查消息类型是否支持
            msg_type = self.get_message_type_from_string(data['type'])
            if not msg_type:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"消息验证失败: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'messages_processed': 0,
            'bytes_sent': 0,
            'bytes_received': 0,
            'compression_ratio': 0.0,
            'errors': 0
        }

# 全局协议处理器实例
default_protocol_processor = AsyncProtocolProcessor()

# 便捷函数
async def serialize_message(message: Union[BaseMessage, Dict[str, Any]], 
                           format_type: str = "json") -> bytes:
    """序列化消息的便捷函数"""
    return await default_protocol_processor.serialize_message(message, format_type)

async def deserialize_message(data: bytes, format_type: str = "json") -> Dict[str, Any]:
    """反序列化消息的便捷函数"""
    return await default_protocol_processor.deserialize_message(data, format_type)

async def create_response(request_data: Dict[str, Any], success: bool, 
                         message: str = "", **kwargs) -> Dict[str, Any]:
    """创建响应消息的便捷函数"""
    return await default_protocol_processor.create_response_message(
        request_data, success, message, **kwargs)

async def validate_message(data: Dict[str, Any]) -> bool:
    """验证消息的便捷函数"""
    return await default_protocol_processor.validate_message(data) 