import bcrypt
import hmac
import hashlib
import secrets
import base64
import json
from typing import Optional, Dict, Any, Tuple
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
import logging

from .storage import DatabaseManager

class AuthenticationManager:
    """用户认证管理器"""
    
    def __init__(self, db_manager: DatabaseManager, secret_key: str = None):
        """
        初始化认证管理器
        
        Args:
            db_manager: 数据库管理器实例
            secret_key: 可选的密钥，用于HMAC签名
        """
        if not isinstance(db_manager, DatabaseManager):
            raise TypeError("db_manager必须是DatabaseManager实例")
            
        self.db_manager = db_manager
        self.secret_key = secret_key or secrets.token_hex(32)
        logging.info("认证管理器初始化完成")
        
    def generate_rsa_keypair(self, key_size: int = 2048) -> Tuple[str, str]:
        """生成RSA密钥对"""
        try:
            # 生成私钥
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=default_backend()
            )
            
            # 获取公钥
            public_key = private_key.public_key()
            
            # 序列化私钥（PEM格式）
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
            
            # 序列化公钥（PEM格式）
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode('utf-8')
            
            return public_pem, private_pem
            
        except Exception as e:
            logging.error(f"RSA密钥对生成失败: {e}")
            raise
    
    def hash_password(self, password: str, salt: bytes = None) -> Tuple[str, str]:
        """使用bcrypt对密码进行哈希"""
        try:
            if salt is None:
                salt = bcrypt.gensalt()
            
            password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
            
            return password_hash.decode('utf-8'), salt.decode('utf-8')
            
        except Exception as e:
            logging.error(f"密码哈希失败: {e}")
            raise
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码"""
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'), 
                password_hash.encode('utf-8')
            )
        except Exception as e:
            logging.error(f"密码验证失败: {e}")
            return False
    
    def generate_hmac(self, message: str, key: str = None) -> str:
        """生成HMAC签名"""
        try:
            key = key or self.secret_key
            signature = hmac.new(
                key.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return signature
            
        except Exception as e:
            logging.error(f"HMAC生成失败: {e}")
            raise
    
    def verify_hmac(self, message: str, signature: str, key: str = None) -> bool:
        """验证HMAC签名"""
        try:
            key = key or self.secret_key
            expected_signature = self.generate_hmac(message, key)
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logging.error(f"HMAC验证失败: {e}")
            return False
    
    def generate_session_token(self, user_id: int, username: str) -> str:
        """生成会话令牌"""
        try:
            # 创建会话数据
            session_data = {
                'user_id': user_id,
                'username': username,
                'timestamp': secrets.token_hex(16)
            }
            
            # 序列化并编码
            session_json = json.dumps(session_data)
            session_b64 = base64.b64encode(session_json.encode('utf-8')).decode('utf-8')
            
            # 生成HMAC签名
            signature = self.generate_hmac(session_b64)
            
            # 组合token
            token = f"{session_b64}.{signature}"
            
            return token
            
        except Exception as e:
            logging.error(f"会话令牌生成失败: {e}")
            raise
    
    def verify_session_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证会话令牌"""
        try:
            # 分离数据和签名
            if '.' not in token:
                return None
                
            session_b64, signature = token.rsplit('.', 1)
            
            # 验证HMAC签名
            if not self.verify_hmac(session_b64, signature):
                logging.warning("会话令牌HMAC验证失败")
                return None
            
            # 解码会话数据
            session_json = base64.b64decode(session_b64.encode('utf-8')).decode('utf-8')
            session_data = json.loads(session_json)
            
            return session_data
            
        except Exception as e:
            logging.error(f"会话令牌验证失败: {e}")
            return None
    
    async def register_user(self, username: str, email: str, password: str, 
                           confirm_password: str) -> Dict[str, Any]:
        """用户注册"""
        try:
            # 输入验证
            if not username or not email or not password:
                return {
                    'success': False,
                    'error': '用户名、邮箱和密码不能为空'
                }
            
            if password != confirm_password:
                return {
                    'success': False,
                    'error': '密码确认不匹配'
                }
            
            if len(password) < 8:
                return {
                    'success': False,
                    'error': '密码长度至少8位'
                }
            
            # 检查用户名是否已存在
            existing_user = self.db_manager.get_user_by_username(username)
            if existing_user:
                return {
                    'success': False,
                    'error': '用户名已存在'
                }
            
            # 生成RSA密钥对
            public_key, private_key = self.generate_rsa_keypair()
            
            # 加密私钥（使用用户密码）
            # 这里简化处理，实际应用中应使用更安全的方法
            private_key_encrypted = base64.b64encode(
                private_key.encode('utf-8')
            ).decode('utf-8')
            
            # 哈希密码
            password_hash, salt = self.hash_password(password)
            
            # 创建用户
            user_id = self.db_manager.create_user(
                username=username,
                email=email,
                password_hash=password_hash,
                salt=salt,
                public_key=public_key,
                private_key_encrypted=private_key_encrypted
            )
            
            if user_id is None:
                return {
                    'success': False,
                    'error': '用户创建失败'
                }
            
            # 生成会话令牌
            session_token = self.generate_session_token(user_id, username)
            
            return {
                'success': True,
                'message': '注册成功',
                'user_id': user_id,
                'username': username,
                'session_token': session_token,
                'public_key': public_key
            }
            
        except Exception as e:
            logging.error(f"注册处理异常: {e}")
            return {
                'success': False,
                'error': f'注册处理异常: {str(e)}'
            }
    
    async def authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        """用户登录认证"""
        try:
            # 输入验证
            if not username or not password:
                return {
                    'success': False,
                    'error': '用户名和密码不能为空'
                }
            
            # 获取用户信息
            user = self.db_manager.get_user_by_username(username)
            if not user:
                return {
                    'success': False,
                    'error': '用户不存在'
                }
            
            # 验证密码
            if not self.verify_password(password, user['password_hash']):
                return {
                    'success': False,
                    'error': '密码错误'
                }
            
            # 生成会话令牌
            session_token = self.generate_session_token(user['user_id'], username)
            
            # 创建会话记录
            session_success = self.db_manager.create_session(
                session_id=session_token,
                user_id=user['user_id']
            )
            
            if not session_success:
                return {
                    'success': False,
                    'error': '会话创建失败'
                }
            
            return {
                'success': True,
                'message': '登录成功',
                'user_id': user['user_id'],
                'username': username,
                'session_token': session_token,
                'public_key': user['public_key']
            }
            
        except Exception as e:
            logging.error(f"登录认证异常: {e}")
            return {
                'success': False,
                'error': f'登录认证异常: {str(e)}'
            }
    
    async def logout_user(self, session_token: str) -> Dict[str, Any]:
        """用户登出"""
        try:
            # 验证会话令牌
            session_data = self.verify_session_token(session_token)
            if not session_data:
                return {
                    'success': False,
                    'error': '无效的会话令牌'
                }
            
            # 关闭会话
            session_closed = self.db_manager.close_session(session_token)
            
            # 更新用户在线状态
            status_updated = self.db_manager.update_user_login_status(
                user_id=session_data['user_id'],
                is_online=False
            )
            
            if session_closed and status_updated:
                return {
                    'success': True,
                    'message': '登出成功'
                }
            else:
                return {
                    'success': False,
                    'error': '登出失败'
                }
                
        except Exception as e:
            logging.error(f"用户登出异常: {e}")
            return {
                'success': False,
                'error': '服务器内部错误'
            }
    
    def get_user_public_key(self, username: str) -> Optional[str]:
        """获取用户公钥"""
        try:
            return self.db_manager.get_friend_public_key(username)
        except Exception as e:
            logging.error(f"获取用户公钥失败: {e}")
            return None 