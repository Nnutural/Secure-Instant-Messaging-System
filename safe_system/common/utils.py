"""
通用工具模块

提供常用的辅助函数和工具类
"""

import os
import json
import hashlib
import time
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

def generate_uuid() -> str:
    """生成UUID字符串"""
    return str(uuid.uuid4())

def get_timestamp() -> str:
    """获取当前时间戳（ISO格式）"""
    return datetime.now().isoformat()

def calculate_file_hash(file_path: str) -> Optional[str]:
    """
    计算文件的SHA256哈希值
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件哈希值，失败返回None
    """
    try:
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logger.error(f"计算文件哈希失败: {e}")
        return None

def ensure_directory(directory_path: str) -> bool:
    """
    确保目录存在，不存在则创建
    
    Args:
        directory_path: 目录路径
        
    Returns:
        是否成功
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"创建目录失败: {e}")
        return False

def load_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    加载JSON文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        JSON数据，失败返回None
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载JSON文件失败: {e}")
        return None

def save_json_file(file_path: str, data: Dict[str, Any]) -> bool:
    """
    保存JSON文件
    
    Args:
        file_path: 文件路径
        data: 要保存的数据
        
    Returns:
        是否成功
    """
    try:
        # 确保目录存在
        directory = os.path.dirname(file_path)
        if directory:
            ensure_directory(directory)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"保存JSON文件失败: {e}")
        return False

def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 字节数
        
    Returns:
        格式化后的大小字符串
    """
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"

def validate_filename(filename: str) -> bool:
    """
    验证文件名是否合法
    
    Args:
        filename: 文件名
        
    Returns:
        是否合法
    """
    if not filename or len(filename) > 255:
        return False
    
    # 禁止的字符
    forbidden_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
    for char in forbidden_chars:
        if char in filename:
            return False
    
    # 禁止的文件名
    forbidden_names = [
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    ]
    
    name_without_ext = os.path.splitext(filename)[0].upper()
    if name_without_ext in forbidden_names:
        return False
    
    return True

def truncate_string(text: str, max_length: int = 100) -> str:
    """
    截断字符串
    
    Args:
        text: 原始字符串
        max_length: 最大长度
        
    Returns:
        截断后的字符串
    """
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

class PerformanceTimer:
    """性能计时器"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def start(self):
        """开始计时"""
        self.start_time = time.time()
        self.end_time = None
    
    def stop(self):
        """停止计时"""
        if self.start_time is not None:
            self.end_time = time.time()
    
    def elapsed(self) -> float:
        """获取经过的时间（秒）"""
        if self.start_time is None:
            return 0.0
        
        end = self.end_time if self.end_time is not None else time.time()
        return end - self.start_time
    
    def elapsed_ms(self) -> float:
        """获取经过的时间（毫秒）"""
        return self.elapsed() * 1000

class RateLimiter:
    """速率限制器"""
    
    def __init__(self, max_requests: int, time_window: float):
        """
        初始化速率限制器
        
        Args:
            max_requests: 时间窗口内最大请求数
            time_window: 时间窗口（秒）
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def is_allowed(self) -> bool:
        """
        检查是否允许请求
        
        Returns:
            是否允许
        """
        now = time.time()
        
        # 清理过期的请求记录
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < self.time_window]
        
        # 检查是否超过限制
        if len(self.requests) >= self.max_requests:
            return False
        
        # 记录当前请求
        self.requests.append(now)
        return True
    
    def get_remaining_requests(self) -> int:
        """获取剩余请求数"""
        now = time.time()
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < self.time_window]
        return max(0, self.max_requests - len(self.requests))

def sanitize_input(text: str) -> str:
    """
    清理用户输入
    
    Args:
        text: 输入文本
        
    Returns:
        清理后的文本
    """
    if not isinstance(text, str):
        return ""
    
    # 移除控制字符
    cleaned = ''.join(char for char in text if ord(char) >= 32 or char in '\t\n\r')
    
    # 限制长度
    if len(cleaned) > 10000:
        cleaned = cleaned[:10000]
    
    return cleaned.strip()

def is_valid_ip(ip: str) -> bool:
    """
    验证IP地址是否有效
    
    Args:
        ip: IP地址字符串
        
    Returns:
        是否有效
    """
    try:
        import ipaddress
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def is_valid_port(port: int) -> bool:
    """
    验证端口号是否有效
    
    Args:
        port: 端口号
        
    Returns:
        是否有效
    """
    return isinstance(port, int) and 1 <= port <= 65535 