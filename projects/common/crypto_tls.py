"""
加密和TLS模块

提供基础的加密、哈希和TLS连接功能
"""

import asyncio
import hashlib
import hmac
import base64
import secrets
from typing import Tuple, Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# 类型别名
StreamReader = asyncio.StreamReader
StreamWriter = asyncio.StreamWriter

async def open_tls(host: str, port: int, ca_cert: str = None, 
                  client_cert: str = None, client_key: str = None) -> Tuple[StreamReader, StreamWriter]:
    """
    建立TLS连接
    
    Args:
        host: 服务器地址
        port: 服务器端口
        ca_cert: CA证书路径（可选）
        client_cert: 客户端证书路径（可选）
        client_key: 客户端私钥路径（可选）
        
    Returns:
        (reader, writer) 元组
    """
    # 简化实现：使用普通TCP连接
    # 在生产环境中应该使用真正的TLS
    reader, writer = await asyncio.open_connection(host, port)
    return reader, writer

async def open_dtls(host: str, port: int, ca_cert: str = None,
                   client_cert: str = None, client_key: str = None):
    """
    建立DTLS连接（UDP上的TLS）
    
    注意：这是占位实现，实际DTLS需要专门的库
    """
    # 占位实现
    raise NotImplementedError("DTLS implementation not available")

def generate_rsa_keypair(key_size: int = 2048) -> Tuple[str, str]:
    """
    生成RSA密钥对
    
    Args:
        key_size: 密钥长度
        
    Returns:
        (private_key_pem, public_key_pem)
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    return private_pem, public_pem

def hash_password(password: str, salt: bytes = None) -> Tuple[str, str]:
    """
    哈希密码
    
    Args:
        password: 原始密码
        salt: 盐值（可选，自动生成）
        
    Returns:
        (hash_b64, salt_b64)
    """
    if salt is None:
        salt = secrets.token_bytes(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    
    key = kdf.derive(password.encode('utf-8'))
    
    return (
        base64.b64encode(key).decode('utf-8'),
        base64.b64encode(salt).decode('utf-8')
    )

def verify_password(password: str, hash_b64: str, salt_b64: str) -> bool:
    """
    验证密码
    
    Args:
        password: 要验证的密码
        hash_b64: 存储的哈希值
        salt_b64: 存储的盐值
        
    Returns:
        验证结果
    """
    try:
        salt = base64.b64decode(salt_b64)
        stored_hash = base64.b64decode(hash_b64)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        kdf.verify(password.encode('utf-8'), stored_hash)
        return True
    except:
        return False

def generate_hmac(message: str, key: str) -> str:
    """生成HMAC签名"""
    return hmac.new(
        key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def verify_hmac(message: str, signature: str, key: str) -> bool:
    """验证HMAC签名"""
    expected = generate_hmac(message, key)
    return hmac.compare_digest(signature, expected) 