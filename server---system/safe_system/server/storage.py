import sqlite3
import os
import json
import datetime
from typing import Optional, List, Dict, Any
import logging

class DatabaseManager:
    """数据库管理器，负责所有数据的持久化存储"""
    
    def __init__(self, db_path: str = "secure_chat.db"):
        self.db_path = db_path
        self.init_database()
        
    def init_database(self):
        """初始化数据库，创建必要的表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建用户表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        salt TEXT NOT NULL,
                        public_key TEXT NOT NULL,
                        private_key_encrypted TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP,
                        is_online BOOLEAN DEFAULT FALSE,
                        ip_address TEXT,
                        port INTEGER
                    )
                ''')
                
                # 创建好友关系表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS friendships (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        friend_id INTEGER NOT NULL,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id),
                        FOREIGN KEY (friend_id) REFERENCES users (user_id),
                        UNIQUE(user_id, friend_id)
                    )
                ''')
                
                # 创建消息表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS messages (
                        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sender_id INTEGER NOT NULL,
                        receiver_id INTEGER NOT NULL,
                        message_content TEXT NOT NULL,
                        message_type TEXT DEFAULT 'text',
                        is_encrypted BOOLEAN DEFAULT TRUE,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_delivered BOOLEAN DEFAULT FALSE,
                        FOREIGN KEY (sender_id) REFERENCES users (user_id),
                        FOREIGN KEY (receiver_id) REFERENCES users (user_id)
                    )
                ''')
                
                # 创建文件传输记录表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS file_transfers (
                        transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sender_id INTEGER NOT NULL,
                        receiver_id INTEGER NOT NULL,
                        filename TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        file_hash TEXT NOT NULL,
                        is_encrypted BOOLEAN DEFAULT TRUE,
                        transfer_status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        FOREIGN KEY (sender_id) REFERENCES users (user_id),
                        FOREIGN KEY (receiver_id) REFERENCES users (user_id)
                    )
                ''')
                
                # 创建会话表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        websocket_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT TRUE,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                
                # 创建群组表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS groups (
                        group_id TEXT PRIMARY KEY,
                        group_name TEXT NOT NULL,
                        creator_id INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 创建群组成员表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS group_members (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id TEXT NOT NULL,
                        user_id INTEGER NOT NULL,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (group_id) REFERENCES groups (group_id),
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                
                # 创建群聊消息表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS group_messages (
                        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id TEXT NOT NULL,
                        sender_id INTEGER NOT NULL,
                        message_content TEXT NOT NULL,
                        message_type TEXT DEFAULT 'text',
                        is_encrypted BOOLEAN DEFAULT TRUE,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (group_id) REFERENCES groups (group_id),
                        FOREIGN KEY (sender_id) REFERENCES users (user_id)
                    )
                ''')
                
                # 创建联系人表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS contacts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        contact_user_id INTEGER NOT NULL,
                        alias TEXT,
                        group_name TEXT DEFAULT '默认分组',
                        notes TEXT,
                        is_favorite BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id),
                        FOREIGN KEY (contact_user_id) REFERENCES users (user_id),
                        UNIQUE(user_id, contact_user_id)
                    )
                ''')
                
                conn.commit()
                logging.info("数据库初始化完成")
                
        except Exception as e:
            logging.error(f"数据库初始化失败: {e}")
            raise
    
    def create_user(self, username: str, email: str, password_hash: str, 
                   salt: str, public_key: str, private_key_encrypted: str) -> Optional[int]:
        """创建新用户"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (username, email, password_hash, salt, 
                                     public_key, private_key_encrypted)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (username, email, password_hash, salt, public_key, private_key_encrypted))
                
                user_id = cursor.lastrowid
                conn.commit()
                logging.info(f"用户 {username} 创建成功，ID: {user_id}")
                return user_id
                
        except sqlite3.IntegrityError as e:
            logging.error(f"用户创建失败，用户名或邮箱已存在: {e}")
            return None
        except Exception as e:
            logging.error(f"用户创建失败: {e}")
            return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名获取用户信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM users WHERE username = ?
                ''', (username,))
                
                row = cursor.fetchone()
                return dict(row) if row else None
                
        except Exception as e:
            logging.error(f"获取用户信息失败: {e}")
            return None
    
    def update_user_login_status(self, user_id: int, is_online: bool, 
                                ip_address: str = None, port: int = None) -> bool:
        """更新用户登录状态"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if is_online:
                    cursor.execute('''
                        UPDATE users 
                        SET is_online = ?, last_login = CURRENT_TIMESTAMP,
                            ip_address = ?, port = ?
                        WHERE user_id = ?
                    ''', (is_online, ip_address, port, user_id))
                else:
                    cursor.execute('''
                        UPDATE users 
                        SET is_online = ?, ip_address = NULL, port = NULL
                        WHERE user_id = ?
                    ''', (is_online, user_id))
                
                conn.commit()
                return True
                
        except Exception as e:
            logging.error(f"更新用户状态失败: {e}")
            return False
    
    def get_online_friends(self, user_id: int) -> List[Dict[str, Any]]:
        """获取用户的在线好友列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT u.user_id, u.username, u.public_key, u.ip_address, u.port
                    FROM users u
                    INNER JOIN friendships f ON (u.user_id = f.friend_id OR u.user_id = f.user_id)
                    WHERE (f.user_id = ? OR f.friend_id = ?) 
                    AND u.user_id != ? 
                    AND u.is_online = TRUE
                    AND f.status = 'accepted'
                ''', (user_id, user_id, user_id))
                
                friends = [dict(row) for row in cursor.fetchall()]
                return friends
                
        except Exception as e:
            logging.error(f"获取在线好友失败: {e}")
            return []
    
    def get_friend_public_key(self, friend_username: str) -> Optional[str]:
        """获取好友的公钥"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT public_key FROM users WHERE username = ?
                ''', (friend_username,))
                
                result = cursor.fetchone()
                return result[0] if result else None
                
        except Exception as e:
            logging.error(f"获取好友公钥失败: {e}")
            return None
    
    def save_message(self, sender_id: int, receiver_id: int, message_content: str,
                    message_type: str = 'text', is_encrypted: bool = True) -> Optional[int]:
        """保存消息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO messages (sender_id, receiver_id, message_content,
                                        message_type, is_encrypted)
                    VALUES (?, ?, ?, ?, ?)
                ''', (sender_id, receiver_id, message_content, message_type, is_encrypted))
                
                message_id = cursor.lastrowid
                conn.commit()
                return message_id
                
        except Exception as e:
            logging.error(f"保存消息失败: {e}")
            return None
    
    def create_session(self, session_id: str, user_id: int, websocket_id: str = None) -> bool:
        """创建用户会话"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO sessions 
                    (session_id, user_id, websocket_id, created_at, last_activity)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (session_id, user_id, websocket_id))
                
                conn.commit()
                return True
                
        except Exception as e:
            logging.error(f"创建会话失败: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM sessions WHERE session_id = ? AND is_active = TRUE
                ''', (session_id,))
                
                row = cursor.fetchone()
                return dict(row) if row else None
                
        except Exception as e:
            logging.error(f"获取会话失败: {e}")
            return None
    
    def close_session(self, session_id: str) -> bool:
        """关闭会话"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE sessions SET is_active = FALSE WHERE session_id = ?
                ''', (session_id,))
                
                conn.commit()
                return True
                
        except Exception as e:
            logging.error(f"关闭会话失败: {e}")
            return False
    
    def save_group_message(self, group_id: str, sender_id: int, message_content: str, message_type: str = 'text', is_encrypted: bool = True) -> Optional[int]:
        """保存群聊消息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO group_messages (group_id, sender_id, message_content, message_type, is_encrypted)
                    VALUES (?, ?, ?, ?, ?)
                ''', (group_id, sender_id, message_content, message_type, is_encrypted))
                message_id = cursor.lastrowid
                conn.commit()
                return message_id
        except Exception as e:
            logging.error(f"保存群聊消息失败: {e}")
            return None
    
    def get_history(self, chat_type: str, target_id: str, user_id: int = None, start_time: str = None, end_time: str = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """查询历史消息（单聊/群聊）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                if chat_type == 'single' and user_id:
                    # 单聊历史 - 需要将target_id（用户名）转换为用户ID
                    target_user_id = None
                    if target_id.isdigit():
                        # 如果target_id是数字，直接使用
                        target_user_id = int(target_id)
                    else:
                        # 如果target_id是用户名，先查询用户ID
                        cursor.execute('SELECT user_id FROM users WHERE username = ?', (target_id,))
                        target_row = cursor.fetchone()
                        if target_row:
                            target_user_id = target_row[0]
                        else:
                            logging.warning(f"未找到用户: {target_id}")
                            return []
                    
                    sql = '''
                        SELECT m.*, u1.username as sender_name, u2.username as receiver_name
                        FROM messages m
                        JOIN users u1 ON m.sender_id = u1.user_id
                        JOIN users u2 ON m.receiver_id = u2.user_id
                        WHERE (m.sender_id = ? AND m.receiver_id = ?)
                           OR (m.sender_id = ? AND m.receiver_id = ?)
                    '''
                    params = [user_id, target_user_id, target_user_id, user_id]
                    if start_time:
                        sql += ' AND m.timestamp >= ?'
                        params.append(start_time)
                    if end_time:
                        sql += ' AND m.timestamp <= ?'
                        params.append(end_time)
                    sql += ' ORDER BY m.timestamp DESC LIMIT ? OFFSET ?'
                    params += [limit, offset]
                    cursor.execute(sql, params)
                elif chat_type == 'group':
                    # 群聊历史
                    sql = '''
                        SELECT gm.*, u.username as sender_name
                        FROM group_messages gm
                        JOIN users u ON gm.sender_id = u.user_id
                        WHERE gm.group_id = ?
                    '''
                    params = [target_id]
                    if start_time:
                        sql += ' AND gm.timestamp >= ?'
                        params.append(start_time)
                    if end_time:
                        sql += ' AND gm.timestamp <= ?'
                        params.append(end_time)
                    sql += ' ORDER BY gm.timestamp DESC LIMIT ? OFFSET ?'
                    params += [limit, offset]
                    cursor.execute(sql, params)
                else:
                    return []
                records = [dict(row) for row in cursor.fetchall()]
                return records
        except Exception as e:
            logging.error(f"查询历史消息失败: {e}")
            return []
    
    def get_username_by_id(self, user_id: int) -> str:
        """根据用户ID获取用户名"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT username FROM users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            logging.error(f"根据ID获取用户名失败: {e}")
            return None
    
    def update_user_last_activity(self, user_id: int) -> bool:
        """更新用户最后活动时间"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = ?
                ''', (user_id,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"更新用户最后活动时间失败: {e}")
            return False
    
    def get_chat_history(self, chat_type: str, target_id: str, user_id: int = None, limit: int = 50) -> List[Dict[str, Any]]:
        """获取聊天历史记录（兼容方法）"""
        return self.get_history(chat_type, target_id, user_id, limit=limit)
    
    def get_user_id_by_username(self, username: str) -> Optional[int]:
        """根据用户名获取用户ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_id FROM users WHERE username = ?', (username,))
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            logging.error(f"根据用户名获取ID失败: {e}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据用户ID获取用户信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logging.error(f"根据ID获取用户信息失败: {e}")
            return None
    
    def add_contact(self, user_id: int, contact_username: str, alias: str = None, group: str = "默认分组") -> bool:
        """添加联系人"""
        try:
            # 先获取联系人的用户ID
            contact_user_id = self.get_user_id_by_username(contact_username)
            if not contact_user_id:
                logging.error(f"联系人用户名不存在: {contact_username}")
                return False
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO contacts 
                    (user_id, contact_user_id, alias, group_name, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (user_id, contact_user_id, alias or contact_username, group))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"添加联系人失败: {e}")
            return False
    
    def get_contacts(self, user_id: int) -> Dict[str, Any]:
        """获取用户的联系人列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT c.*, u.username, u.is_online
                    FROM contacts c
                    JOIN users u ON c.contact_user_id = u.user_id
                    WHERE c.user_id = ?
                    ORDER BY c.group_name, c.alias
                ''', (user_id,))
                
                contacts = {}
                total = 0
                for row in cursor.fetchall():
                    contact_info = dict(row)
                    contacts[str(contact_info['contact_user_id'])] = {
                        'username': contact_info['username'],
                        'alias': contact_info['alias'],
                        'group': contact_info['group_name'],
                        'notes': contact_info['notes'],
                        'is_favorite': bool(contact_info['is_favorite']),
                        'is_online': bool(contact_info['is_online']),
                        'created_at': contact_info['created_at']
                    }
                    total += 1
                
                return {'contacts': contacts, 'total': total}
        except Exception as e:
            logging.error(f"获取联系人列表失败: {e}")
            return {'contacts': {}, 'total': 0}
    
    def update_contact(self, user_id: int, contact_user_id: int, alias: str = None, 
                      group: str = None, notes: str = None, is_favorite: bool = None) -> bool:
        """更新联系人信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 构建动态更新语句
                update_fields = []
                params = []
                
                if alias is not None:
                    update_fields.append("alias = ?")
                    params.append(alias)
                if group is not None:
                    update_fields.append("group_name = ?")
                    params.append(group)
                if notes is not None:
                    update_fields.append("notes = ?")
                    params.append(notes)
                if is_favorite is not None:
                    update_fields.append("is_favorite = ?")
                    params.append(is_favorite)
                
                if not update_fields:
                    return True  # 没有要更新的字段
                
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                params.extend([user_id, contact_user_id])
                
                sql = f'''
                    UPDATE contacts 
                    SET {", ".join(update_fields)}
                    WHERE user_id = ? AND contact_user_id = ?
                '''
                
                cursor.execute(sql, params)
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"更新联系人失败: {e}")
            return False
    
    def remove_contact(self, user_id: int, contact_user_id: int) -> bool:
        """删除联系人"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM contacts 
                    WHERE user_id = ? AND contact_user_id = ?
                ''', (user_id, contact_user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"删除联系人失败: {e}")
            return False
    
    def create_group(self, group_id: str, group_name: str, creator_id: int, members: List[str] = None) -> bool:
        """创建群组"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建群组
                cursor.execute('''
                    INSERT OR REPLACE INTO groups (group_id, group_name, creator_id)
                    VALUES (?, ?, ?)
                ''', (group_id, group_name, creator_id))
                
                # 添加创建者为成员
                cursor.execute('''
                    INSERT OR REPLACE INTO group_members (group_id, user_id)
                    VALUES (?, ?)
                ''', (group_id, creator_id))
                
                # 添加其他成员
                if members:
                    for member_username in members:
                        member_id = self.get_user_id_by_username(member_username)
                        if member_id and member_id != creator_id:
                            cursor.execute('''
                                INSERT OR REPLACE INTO group_members (group_id, user_id)
                                VALUES (?, ?)
                            ''', (group_id, member_id))
                
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"创建群组失败: {e}")
            return False
    
    def get_group_info(self, group_id: str) -> Optional[Dict[str, Any]]:
        """获取群组信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 获取群组基本信息
                cursor.execute('''
                    SELECT g.*, u.username as creator_name
                    FROM groups g
                    JOIN users u ON g.creator_id = u.user_id
                    WHERE g.group_id = ?
                ''', (group_id,))
                
                group_row = cursor.fetchone()
                if not group_row:
                    return None
                
                group_info = dict(group_row)
                
                # 获取群组成员
                cursor.execute('''
                    SELECT gm.user_id, u.username, gm.joined_at
                    FROM group_members gm
                    JOIN users u ON gm.user_id = u.user_id
                    WHERE gm.group_id = ?
                ''', (group_id,))
                
                members = [dict(row) for row in cursor.fetchall()]
                group_info['members'] = members
                group_info['member_count'] = len(members)
                
                return group_info
        except Exception as e:
            logging.error(f"获取群组信息失败: {e}")
            return None
    
    def add_group_member(self, group_id: str, user_id: int) -> bool:
        """添加群组成员"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO group_members (group_id, user_id)
                    VALUES (?, ?)
                ''', (group_id, user_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"添加群组成员失败: {e}")
            return False
    
    def remove_group_member(self, group_id: str, user_id: int) -> bool:
        """移除群组成员"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM group_members 
                    WHERE group_id = ? AND user_id = ?
                ''', (group_id, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"移除群组成员失败: {e}")
            return False
    
    def get_user_groups(self, user_id: int) -> List[Dict[str, Any]]:
        """获取用户参与的群组列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT g.group_id, g.group_name, g.creator_id, g.created_at,
                           u.username as creator_name, gm.joined_at
                    FROM groups g
                    JOIN group_members gm ON g.group_id = gm.group_id
                    JOIN users u ON g.creator_id = u.user_id
                    WHERE gm.user_id = ?
                    ORDER BY gm.joined_at DESC
                ''', (user_id,))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"获取用户群组列表失败: {e}")
            return [] 