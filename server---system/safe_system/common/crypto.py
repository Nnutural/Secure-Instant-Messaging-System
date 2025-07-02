"""
加解密和密钥管理模块

实现RSA+AES混合加密、密钥生成、签名验证等功能
"""

import os
import base64
import hashlib
import hmac
import json
import logging
from typing import Tuple, Optional, Dict, Any
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet

from .utils import generate_uuid
from .schema import CryptoError

logger = logging.getLogger(__name__)

class RSAKeyManager:
    """RSA密钥管理器"""
    
    def __init__(self, key_size: int = 2048):
        """
        初始化RSA密钥管理器
        
        Args:
            key_size: 密钥长度，默认2048位
        """
        self.key_size = key_size
        self.backend = default_backend()
    
    def generate_key_pair(self) -> Tuple[str, str]:
        """
        生成RSA密钥对
        
        Returns:
            (私钥PEM, 公钥PEM)
        """
        try:
            # 生成私钥
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=self.key_size,
                backend=self.backend
            )
            
            # 序列化私钥
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
            
            # 获取公钥
            public_key = private_key.public_key()
            
            # 序列化公钥
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode('utf-8')
            
            return private_pem, public_pem
            
        except Exception as e:
            logger.error(f"生成RSA密钥对失败: {e}")
            raise CryptoError(f"生成RSA密钥对失败: {e}")
    
    def load_private_key(self, private_pem: str, password: Optional[bytes] = None):
        """
        加载私钥
        
        Args:
            private_pem: 私钥PEM字符串
            password: 密钥密码
            
        Returns:
            私钥对象
        """
        try:
            return serialization.load_pem_private_key(
                private_pem.encode('utf-8'),
                password=password,
                backend=self.backend
            )
        except Exception as e:
            logger.error(f"加载私钥失败: {e}")
            raise CryptoError(f"加载私钥失败: {e}")
    
    def load_public_key(self, public_pem: str):
        """
        加载公钥
        
        Args:
            public_pem: 公钥PEM字符串
            
        Returns:
            公钥对象
        """
        try:
            return serialization.load_pem_public_key(
                public_pem.encode('utf-8'),
                backend=self.backend
            )
        except Exception as e:
            logger.error(f"加载公钥失败: {e}")
            raise CryptoError(f"加载公钥失败: {e}")
    
    def encrypt_with_public_key(self, public_pem: str, data: bytes) -> bytes:
        """
        使用公钥加密数据
        
        Args:
            public_pem: 公钥PEM字符串
            data: 要加密的数据
            
        Returns:
            加密后的数据
        """
        try:
            public_key = self.load_public_key(public_pem)
            
            encrypted_data = public_key.encrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return encrypted_data
            
        except Exception as e:
            logger.error(f"RSA公钥加密失败: {e}")
            raise CryptoError(f"RSA公钥加密失败: {e}")
    
    def decrypt_with_private_key(self, private_pem: str, encrypted_data: bytes) -> bytes:
        """
        使用私钥解密数据
        
        Args:
            private_pem: 私钥PEM字符串
            encrypted_data: 加密的数据
            
        Returns:
            解密后的数据
        """
        try:
            private_key = self.load_private_key(private_pem)
            
            decrypted_data = private_key.decrypt(
                encrypted_data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return decrypted_data
            
        except Exception as e:
            logger.error(f"RSA私钥解密失败: {e}")
            raise CryptoError(f"RSA私钥解密失败: {e}")
    
    def sign_data(self, private_pem: str, data: bytes) -> bytes:
        """
        使用私钥签名数据
        
        Args:
            private_pem: 私钥PEM字符串
            data: 要签名的数据
            
        Returns:
            签名
        """
        try:
            private_key = self.load_private_key(private_pem)
            
            signature = private_key.sign(
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return signature
            
        except Exception as e:
            logger.error(f"RSA签名失败: {e}")
            raise CryptoError(f"RSA签名失败: {e}")
    
    def verify_signature(self, public_pem: str, data: bytes, signature: bytes) -> bool:
        """
        使用公钥验证签名
        
        Args:
            public_pem: 公钥PEM字符串
            data: 原始数据
            signature: 签名
            
        Returns:
            验证结果
        """
        try:
            public_key = self.load_public_key(public_pem)
            
            public_key.verify(
                signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True
            
        except Exception as e:
            logger.debug(f"RSA签名验证失败: {e}")
            return False

class AESCipher:
    """AES加密器"""
    
    def __init__(self):
        """初始化AES加密器"""
        self.backend = default_backend()
    
    def generate_key(self) -> bytes:
        """
        生成AES密钥
        
        Returns:
            256位AES密钥
        """
        return os.urandom(32)  # 256位密钥
    
    def generate_iv(self) -> bytes:
        """
        生成初始化向量
        
        Returns:
            128位IV
        """
        return os.urandom(16)  # 128位IV
    
    def encrypt(self, key: bytes, data: bytes) -> Tuple[bytes, bytes]:
        """
        AES-GCM加密
        
        Args:
            key: 加密密钥
            data: 要加密的数据
            
        Returns:
            (加密数据, 认证标签)
        """
        try:
            # 生成随机nonce
            nonce = os.urandom(12)  # GCM推荐12字节nonce
            
            # 创建加密器
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(nonce),
                backend=self.backend
            )
            encryptor = cipher.encryptor()
            
            # 加密数据
            ciphertext = encryptor.update(data) + encryptor.finalize()
            
            # 返回 nonce + ciphertext + tag
            return nonce + ciphertext + encryptor.tag, b''
            
        except Exception as e:
            logger.error(f"AES加密失败: {e}")
            raise CryptoError(f"AES加密失败: {e}")
    
    def decrypt(self, key: bytes, encrypted_data: bytes) -> bytes:
        """
        AES-GCM解密
        
        Args:
            key: 解密密钥
            encrypted_data: 加密的数据（nonce + ciphertext + tag）
            
        Returns:
            解密后的数据
        """
        try:
            # 分离nonce、密文和标签
            nonce = encrypted_data[:12]
            tag = encrypted_data[-16:]
            ciphertext = encrypted_data[12:-16]
            
            # 创建解密器
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(nonce, tag),
                backend=self.backend
            )
            decryptor = cipher.decryptor()
            
            # 解密数据
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            return plaintext
            
        except Exception as e:
            logger.error(f"AES解密失败: {e}")
            raise CryptoError(f"AES解密失败: {e}")

class HybridCrypto:
    """混合加密系统（RSA + AES）"""
    
    def __init__(self):
        """初始化混合加密系统"""
        self.rsa_manager = RSAKeyManager()
        self.aes_cipher = AESCipher()
    
    def encrypt(self, public_pem: str, data: bytes) -> Dict[str, str]:
        """
        混合加密：使用RSA加密AES密钥，使用AES加密数据
        
        Args:
            public_pem: 接收方公钥
            data: 要加密的数据
            
        Returns:
            包含加密信息的字典
        """
        try:
            # 生成AES密钥
            aes_key = self.aes_cipher.generate_key()
            
            # 使用AES加密数据
            encrypted_data, _ = self.aes_cipher.encrypt(aes_key, data)
            
            # 使用RSA加密AES密钥
            encrypted_key = self.rsa_manager.encrypt_with_public_key(public_pem, aes_key)
            
            # 返回加密结果
            return {
                'encrypted_key': base64.b64encode(encrypted_key).decode('utf-8'),
                'encrypted_data': base64.b64encode(encrypted_data).decode('utf-8'),
                'algorithm': 'RSA+AES-GCM'
            }
            
        except Exception as e:
            logger.error(f"混合加密失败: {e}")
            raise CryptoError(f"混合加密失败: {e}")
    
    def decrypt(self, private_pem: str, encrypted_info: Dict[str, str]) -> bytes:
        """
        混合解密：使用RSA解密AES密钥，使用AES解密数据
        
        Args:
            private_pem: 接收方私钥
            encrypted_info: 加密信息字典
            
        Returns:
            解密后的数据
        """
        try:
            # 解码加密的密钥和数据
            encrypted_key = base64.b64decode(encrypted_info['encrypted_key'])
            encrypted_data = base64.b64decode(encrypted_info['encrypted_data'])
            
            # 使用RSA解密AES密钥
            aes_key = self.rsa_manager.decrypt_with_private_key(private_pem, encrypted_key)
            
            # 使用AES解密数据
            plaintext = self.aes_cipher.decrypt(aes_key, encrypted_data)
            
            return plaintext
            
        except Exception as e:
            logger.error(f"混合解密失败: {e}")
            raise CryptoError(f"混合解密失败: {e}")

class PasswordHasher:
    """密码哈希器"""
    
    def __init__(self, iterations: int = 100000):
        """
        初始化密码哈希器
        
        Args:
            iterations: PBKDF2迭代次数
        """
        self.iterations = iterations
        self.backend = default_backend()
    
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
        """
        哈希密码
        
        Args:
            password: 原始密码
            salt: 盐值，为None时自动生成
            
        Returns:
            (哈希值, 盐值) 的Base64编码字符串
        """
        try:
            if salt is None:
                salt = os.urandom(32)
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=self.iterations,
                backend=self.backend
            )
            
            key = kdf.derive(password.encode('utf-8'))
            
            return (
                base64.b64encode(key).decode('utf-8'),
                base64.b64encode(salt).decode('utf-8')
            )
            
        except Exception as e:
            logger.error(f"密码哈希失败: {e}")
            raise CryptoError(f"密码哈希失败: {e}")
    
    def verify_password(self, password: str, hash_b64: str, salt_b64: str) -> bool:
        """
        验证密码
        
        Args:
            password: 要验证的密码
            hash_b64: 存储的哈希值（Base64）
            salt_b64: 存储的盐值（Base64）
            
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
                iterations=self.iterations,
                backend=self.backend
            )
            
            try:
                kdf.verify(password.encode('utf-8'), stored_hash)
                return True
            except:
                return False
                
        except Exception as e:
            logger.error(f"密码验证失败: {e}")
            return False

class SecureRandom:
    """安全随机数生成器"""
    
    @staticmethod
    def generate_bytes(length: int) -> bytes:
        """生成安全随机字节"""
        return os.urandom(length)
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """生成安全随机令牌（Base64编码）"""
        return base64.b64encode(os.urandom(length)).decode('utf-8')
    
    @staticmethod
    def generate_hex(length: int = 16) -> str:
        """生成安全随机十六进制字符串"""
        return os.urandom(length).hex()

# 全局实例
rsa_key_manager = RSAKeyManager()
aes_cipher = AESCipher()
hybrid_crypto = HybridCrypto()
password_hasher = PasswordHasher()

# 便捷函数
def generate_rsa_keypair() -> Tuple[str, str]:
    """生成RSA密钥对的便捷函数"""
    return rsa_key_manager.generate_key_pair()

def encrypt_message(public_key: str, message: bytes) -> Dict[str, str]:
    """加密消息的便捷函数"""
    return hybrid_crypto.encrypt(public_key, message)

def decrypt_message(private_key: str, encrypted_info: Dict[str, str]) -> bytes:
    """解密消息的便捷函数"""
    return hybrid_crypto.decrypt(private_key, encrypted_info)

def hash_password(password: str) -> Tuple[str, str]:
    """哈希密码的便捷函数"""
    return password_hasher.hash_password(password)

def verify_password(password: str, hash_value: str, salt: str) -> bool:
    """验证密码的便捷函数"""
    return password_hasher.verify_password(password, hash_value, salt) 