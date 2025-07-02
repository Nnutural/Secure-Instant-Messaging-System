"""
数据库管理模块

提供SQLite数据库的统一访问接口
"""

import sqlite3
import json
import logging
import os
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = "server/data/secure_chat.db"):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_database_dir()
        self.init_database()
    
    def _ensure_database_dir(self):
        """确保数据库目录存在"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    def init_database(self):
        """初始化数据库表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 用户表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    public_key TEXT,
                    private_key_encrypted TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    is_online BOOLEAN DEFAULT FALSE,
                    last_activity TEXT,
                    ip_address TEXT,
                    port INTEGER
                )
                ''')
                
                # 联系人表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    contact_user_id INTEGER NOT NULL,
                    alias TEXT,
                    group_name TEXT DEFAULT '默认分组',
                    notes TEXT,
                    is_favorite BOOLEAN DEFAULT FALSE,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (contact_user_id) REFERENCES users (user_id),
                    UNIQUE(user_id, contact_user_id)
                )
                ''')
                
                # 消息表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER NOT NULL,
                    receiver_id INTEGER,
                    group_id TEXT,
                    message_type TEXT DEFAULT 'text',
                    content TEXT NOT NULL,
                    is_encrypted BOOLEAN DEFAULT FALSE,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sender_id) REFERENCES users (user_id)
                )
                ''')
                
                # 会话表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
                    websocket_id TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                ''')
                
                # 群组表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS groups (
                    group_id TEXT PRIMARY KEY,
                    group_name TEXT NOT NULL,
                    creator_id INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    description TEXT,
                    FOREIGN KEY (creator_id) REFERENCES users (user_id)
                )
                ''')
                
                # 群组成员表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS group_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    role TEXT DEFAULT 'member',
                    FOREIGN KEY (group_id) REFERENCES groups (group_id),
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    UNIQUE(group_id, user_id)
                )
                ''')
                
                conn.commit()
                logger.info("数据库初始化完成")
                
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
    
    def create_user(self, username: str, email: str, password_hash: str, 
                   salt: str, public_key: str = "", private_key_encrypted: str = "") -> Optional[int]:
        """
        创建用户
        
        Args:
            username: 用户名
            email: 邮箱
            password_hash: 密码哈希
            salt: 盐值
            public_key: 公钥
            private_key_encrypted: 加密的私钥
            
        Returns:
            用户ID，失败返回None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT INTO users (username, email, password_hash, salt, public_key, private_key_encrypted)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (username, email, password_hash, salt, public_key, private_key_encrypted))
                
                user_id = cursor.lastrowid
                conn.commit()
                return user_id
                
        except sqlite3.IntegrityError:
            logger.warning(f"用户 {username} 已存在")
            return None
        except Exception as e:
            logger.error(f"创建用户失败: {e}")
            return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名获取用户信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据用户ID获取用户信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return None
    
    def update_user_login_status(self, user_id: int, is_online: bool, 
                                ip_address: str = None, port: int = None) -> bool:
        """更新用户登录状态"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                UPDATE users 
                SET is_online = ?, last_activity = ?, ip_address = ?, port = ?
                WHERE user_id = ?
                ''', (is_online, datetime.now().isoformat(), ip_address, port, user_id))
                
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"更新用户状态失败: {e}")
            return False
    
    def get_online_friends(self, user_id: int) -> List[Dict[str, Any]]:
        """获取在线好友列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                SELECT u.user_id, u.username, u.ip_address, u.port, u.last_activity
                FROM users u
                INNER JOIN contacts c ON u.user_id = c.contact_user_id
                WHERE c.user_id = ? AND u.is_online = TRUE
                ''', (user_id,))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"获取在线好友失败: {e}")
            return []
    
    def save_message(self, sender_id: int, receiver_id: int = None, group_id: str = None,
                    message_content: str = "", message_type: str = 'text', 
                    is_encrypted: bool = False) -> Optional[int]:
        """保存消息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT INTO messages (sender_id, receiver_id, group_id, message_type, content, is_encrypted)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (sender_id, receiver_id, group_id, message_type, message_content, is_encrypted))
                
                message_id = cursor.lastrowid
                conn.commit()
                return message_id
                
        except Exception as e:
            logger.error(f"保存消息失败: {e}")
            return None
    
    def get_chat_history(self, chat_type: str, target_id: str, user_id: int = None, 
                        limit: int = 50) -> List[Dict[str, Any]]:
        """获取聊天历史"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if chat_type == "single":
                    # 私聊历史
                    cursor.execute('''
                    SELECT m.*, u.username as sender_username
                    FROM messages m
                    INNER JOIN users u ON m.sender_id = u.user_id
                    WHERE (m.sender_id = ? AND m.receiver_id = ?) 
                       OR (m.sender_id = ? AND m.receiver_id = ?)
                    ORDER BY m.timestamp DESC
                    LIMIT ?
                    ''', (user_id, int(target_id), int(target_id), user_id, limit))
                else:
                    # 群聊历史
                    cursor.execute('''
                    SELECT m.*, u.username as sender_username
                    FROM messages m
                    INNER JOIN users u ON m.sender_id = u.user_id
                    WHERE m.group_id = ?
                    ORDER BY m.timestamp DESC
                    LIMIT ?
                    ''', (target_id, limit))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"获取聊天历史失败: {e}")
            return []
    
    def create_session(self, session_id: str, user_id: int, websocket_id: str = None) -> bool:
        """创建会话"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT OR REPLACE INTO sessions (session_id, user_id, websocket_id)
                VALUES (?, ?, ?)
                ''', (session_id, user_id, websocket_id))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"创建会话失败: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM sessions WHERE session_id = ?', (session_id,))
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"获取会话失败: {e}")
            return None
    
    def close_session(self, session_id: str) -> bool:
        """关闭会话"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"关闭会话失败: {e}")
            return False 