"""
群聊管理模块

负责群组的创建、成员管理、群信息查询等功能
"""
import sqlite3
import logging
from typing import List, Dict, Optional, Any
from .storage import DatabaseManager

logger = logging.getLogger(__name__)

db = DatabaseManager()

class GroupManager:
    """群聊管理器"""
    def __init__(self, db_path: str = "secure_chat.db"):
        self.db_path = db_path
        self.db = DatabaseManager(db_path)

    def create_group(self, group_id: str, group_name: str, creator_id: int, members: List[str] = None) -> Dict[str, Any]:
        """创建群组"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # 首先检查群组是否已存在
                cursor.execute('SELECT group_id FROM groups WHERE group_id = ?', (group_id,))
                if cursor.fetchone():
                    return {
                        "success": False,
                        "error": "群组已存在"
                    }
                
                # 创建群组
                cursor.execute('''
                    INSERT INTO groups (group_id, group_name, creator_id)
                    VALUES (?, ?, ?)
                ''', (group_id, group_name, creator_id))
                
                # 添加创建者为群成员
                cursor.execute('''
                    INSERT INTO group_members (group_id, user_id)
                    VALUES (?, ?)
                ''', (group_id, creator_id))
                
                # 添加其他成员（如果有）
                if members:
                    for member_username in members:
                        if member_username != self._get_username_by_id(creator_id):  # 避免重复添加创建者
                            member_info = self.db.get_user_by_username(member_username)
                            if member_info:
                                cursor.execute('''
                                    INSERT OR IGNORE INTO group_members (group_id, user_id)
                                    VALUES (?, ?)
                                ''', (group_id, member_info['user_id']))
                
                conn.commit()
                logger.info(f"群组创建成功: {group_id} - {group_name}")
                return {
                    "success": True,
                    "message": "群组创建成功"
                }
        except Exception as e:
            logger.error(f"群组创建失败: {e}")
            return {
                "success": False,
                "error": f"群组创建失败: {str(e)}"
            }

    def _get_username_by_id(self, user_id: int) -> Optional[str]:
        """根据用户ID获取用户名（内部方法）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT username FROM users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error(f"根据ID获取用户名失败: {e}")
            return None

    def add_member(self, group_id: str, user_id: int) -> bool:
        """添加群成员"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO group_members (group_id, user_id)
                    VALUES (?, ?)
                ''', (group_id, user_id))
                conn.commit()
                logger.info(f"用户 {user_id} 加入群组 {group_id}")
                return True
        except Exception as e:
            logger.error(f"添加群成员失败: {e}")
            return False

    def remove_member(self, group_id: str, user_id: int) -> bool:
        """移除群成员"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM group_members WHERE group_id = ? AND user_id = ?
                ''', (group_id, user_id))
                conn.commit()
                logger.info(f"用户 {user_id} 移出群组 {group_id}")
                return True
        except Exception as e:
            logger.error(f"移除群成员失败: {e}")
            return False

    def get_group_members(self, group_id: str) -> List[int]:
        """获取群成员ID列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id FROM group_members WHERE group_id = ?
                ''', (group_id,))
                members = [row[0] for row in cursor.fetchall()]
                return members
        except Exception as e:
            logger.error(f"获取群成员失败: {e}")
            return []

    def get_group_info(self, group_id: str) -> Optional[Dict]:
        """获取群组信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM groups WHERE group_id = ?
                ''', (group_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"获取群组信息失败: {e}")
            return None

    def get_user_groups(self, user_id: int) -> List[Dict]:
        """获取用户加入的所有群组"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT g.* FROM groups g
                    JOIN group_members gm ON g.group_id = gm.group_id
                    WHERE gm.user_id = ?
                ''', (user_id,))
                groups = [dict(row) for row in cursor.fetchall()]
                return groups
        except Exception as e:
            logger.error(f"获取用户群组失败: {e}")
            return []

group_manager = GroupManager() 