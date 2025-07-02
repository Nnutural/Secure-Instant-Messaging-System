import asyncio
import json
import os
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta
import logging

from .storage import DatabaseManager
from .auth import AuthenticationManager

class ContactManager:
    """通讯录管理器，基于JSON文件存储"""
    
    def __init__(self, contacts_dir: str = "data/contacts"):
        """
        初始化通讯录管理器
        
        Args:
            contacts_dir: 通讯录文件存储目录
        """
        self.contacts_dir = contacts_dir
        self._ensure_contacts_dir()
    
    def _ensure_contacts_dir(self):
        """确保通讯录目录存在"""
        if not os.path.exists(self.contacts_dir):
            os.makedirs(self.contacts_dir, exist_ok=True)
    
    def _get_contact_file_path(self, user_id: int) -> str:
        """获取用户通讯录文件路径"""
        return os.path.join(self.contacts_dir, f"user_{user_id}_contacts.json")
    
    def _load_contacts(self, user_id: int) -> Dict[str, Any]:
        """加载用户通讯录"""
        contact_file = self._get_contact_file_path(user_id)
        if not os.path.exists(contact_file):
            return {
                "user_id": user_id,
                "contacts": {},
                "groups": {},
                "blocked_users": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        
        try:
            with open(contact_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"加载通讯录失败 (用户ID: {user_id}): {e}")
            return {
                "user_id": user_id,
                "contacts": {},
                "groups": {},
                "blocked_users": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
    
    def _save_contacts(self, user_id: int, contacts_data: Dict[str, Any]) -> bool:
        """保存用户通讯录"""
        contact_file = self._get_contact_file_path(user_id)
        try:
            contacts_data["updated_at"] = datetime.now().isoformat()
            with open(contact_file, 'w', encoding='utf-8') as f:
                json.dump(contacts_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logging.error(f"保存通讯录失败 (用户ID: {user_id}): {e}")
            return False
    
    def add_contact(self, user_id: int, contact_username: str, contact_user_id: int, 
                   alias: str = None, group: str = "默认分组") -> Dict[str, Any]:
        """添加联系人"""
        try:
            contacts_data = self._load_contacts(user_id)
            
            # 检查是否已存在
            if str(contact_user_id) in contacts_data["contacts"]:
                return {
                    "success": False,
                    "message": "联系人已存在"
                }
            
            # 添加联系人
            contacts_data["contacts"][str(contact_user_id)] = {
                "user_id": contact_user_id,
                "username": contact_username,
                "alias": alias or contact_username,
                "group": group,
                "added_at": datetime.now().isoformat(),
                "notes": "",
                "is_favorite": False
            }
            
            # 更新分组
            if group not in contacts_data["groups"]:
                contacts_data["groups"][group] = {
                    "name": group,
                    "created_at": datetime.now().isoformat(),
                    "member_count": 0
                }
            contacts_data["groups"][group]["member_count"] = contacts_data["groups"][group].get("member_count", 0) + 1
            
            if self._save_contacts(user_id, contacts_data):
                logging.info(f"用户 {user_id} 添加联系人 {contact_username} 成功")
                return {
                    "success": True,
                    "message": "联系人添加成功"
                }
            else:
                return {
                    "success": False,
                    "message": "保存联系人失败"
                }
                
        except Exception as e:
            logging.error(f"添加联系人失败: {e}")
            return {
                "success": False,
                "message": f"添加联系人失败: {str(e)}"
            }
    
    def remove_contact(self, user_id: int, contact_user_id: int) -> Dict[str, Any]:
        """删除联系人"""
        try:
            contacts_data = self._load_contacts(user_id)
            
            contact_key = str(contact_user_id)
            if contact_key not in contacts_data["contacts"]:
                return {
                    "success": False,
                    "message": "联系人不存在"
                }
            
            # 获取分组信息
            contact_info = contacts_data["contacts"][contact_key]
            group_name = contact_info.get("group", "默认分组")
            
            # 删除联系人
            del contacts_data["contacts"][contact_key]
            
            # 更新分组计数
            if group_name in contacts_data["groups"]:
                contacts_data["groups"][group_name]["member_count"] = max(0, 
                    contacts_data["groups"][group_name].get("member_count", 1) - 1)
                
                # 如果分组为空且不是默认分组，删除分组
                if (contacts_data["groups"][group_name]["member_count"] == 0 and 
                    group_name != "默认分组"):
                    del contacts_data["groups"][group_name]
            
            if self._save_contacts(user_id, contacts_data):
                logging.info(f"用户 {user_id} 删除联系人 {contact_user_id} 成功")
                return {
                    "success": True,
                    "message": "联系人删除成功"
                }
            else:
                return {
                    "success": False,
                    "message": "保存更改失败"
                }
                
        except Exception as e:
            logging.error(f"删除联系人失败: {e}")
            return {
                "success": False,
                "message": f"删除联系人失败: {str(e)}"
            }
    
    def get_contacts(self, user_id: int, group: str = None) -> Dict[str, Any]:
        """获取联系人列表"""
        try:
            contacts_data = self._load_contacts(user_id)
            
            if group:
                # 返回指定分组的联系人
                filtered_contacts = {
                    k: v for k, v in contacts_data["contacts"].items()
                    if v.get("group") == group
                }
                return {
                    "success": True,
                    "contacts": filtered_contacts,
                    "group": group,
                    "total": len(filtered_contacts)
                }
            else:
                # 返回所有联系人
                return {
                    "success": True,
                    "contacts": contacts_data["contacts"],
                    "groups": contacts_data["groups"],
                    "total": len(contacts_data["contacts"])
                }
                
        except Exception as e:
            logging.error(f"获取联系人列表失败: {e}")
            return {
                "success": False,
                "message": f"获取联系人列表失败: {str(e)}"
            }
    
    def update_contact(self, user_id: int, contact_user_id: int, 
                      alias: str = None, group: str = None, 
                      notes: str = None, is_favorite: bool = None) -> Dict[str, Any]:
        """更新联系人信息"""
        try:
            contacts_data = self._load_contacts(user_id)
            
            contact_key = str(contact_user_id)
            if contact_key not in contacts_data["contacts"]:
                return {
                    "success": False,
                    "message": "联系人不存在"
                }
            
            contact_info = contacts_data["contacts"][contact_key]
            old_group = contact_info.get("group", "默认分组")
            
            # 更新字段
            if alias is not None:
                contact_info["alias"] = alias
            if notes is not None:
                contact_info["notes"] = notes
            if is_favorite is not None:
                contact_info["is_favorite"] = is_favorite
            if group is not None and group != old_group:
                # 更新分组
                contact_info["group"] = group
                
                # 更新旧分组计数
                if old_group in contacts_data["groups"]:
                    contacts_data["groups"][old_group]["member_count"] = max(0,
                        contacts_data["groups"][old_group].get("member_count", 1) - 1)
                
                # 更新新分组计数
                if group not in contacts_data["groups"]:
                    contacts_data["groups"][group] = {
                        "name": group,
                        "created_at": datetime.now().isoformat(),
                        "member_count": 0
                    }
                contacts_data["groups"][group]["member_count"] = contacts_data["groups"][group].get("member_count", 0) + 1
            
            if self._save_contacts(user_id, contacts_data):
                logging.info(f"用户 {user_id} 更新联系人 {contact_user_id} 成功")
                return {
                    "success": True,
                    "message": "联系人更新成功"
                }
            else:
                return {
                    "success": False,
                    "message": "保存更改失败"
                }
                
        except Exception as e:
            logging.error(f"更新联系人失败: {e}")
            return {
                "success": False,
                "message": f"更新联系人失败: {str(e)}"
            }
    
    def block_user(self, user_id: int, blocked_user_id: int) -> Dict[str, Any]:
        """拉黑用户"""
        try:
            contacts_data = self._load_contacts(user_id)
            
            if blocked_user_id not in contacts_data["blocked_users"]:
                contacts_data["blocked_users"].append(blocked_user_id)
                
                if self._save_contacts(user_id, contacts_data):
                    logging.info(f"用户 {user_id} 拉黑用户 {blocked_user_id} 成功")
                    return {
                        "success": True,
                        "message": "用户已拉黑"
                    }
                else:
                    return {
                        "success": False,
                        "message": "保存更改失败"
                    }
            else:
                return {
                    "success": False,
                    "message": "用户已在黑名单中"
                }
                
        except Exception as e:
            logging.error(f"拉黑用户失败: {e}")
            return {
                "success": False,
                "message": f"拉黑用户失败: {str(e)}"
            }
    
    def unblock_user(self, user_id: int, blocked_user_id: int) -> Dict[str, Any]:
        """解除拉黑"""
        try:
            contacts_data = self._load_contacts(user_id)
            
            if blocked_user_id in contacts_data["blocked_users"]:
                contacts_data["blocked_users"].remove(blocked_user_id)
                
                if self._save_contacts(user_id, contacts_data):
                    logging.info(f"用户 {user_id} 解除拉黑用户 {blocked_user_id} 成功")
                    return {
                        "success": True,
                        "message": "已解除拉黑"
                    }
                else:
                    return {
                        "success": False,
                        "message": "保存更改失败"
                    }
            else:
                return {
                    "success": False,
                    "message": "用户不在黑名单中"
                }
                
        except Exception as e:
            logging.error(f"解除拉黑失败: {e}")
            return {
                "success": False,
                "message": f"解除拉黑失败: {str(e)}"
            }
    
    def is_blocked(self, user_id: int, check_user_id: int) -> bool:
        """检查用户是否被拉黑"""
        try:
            contacts_data = self._load_contacts(user_id)
            return check_user_id in contacts_data["blocked_users"]
        except Exception as e:
            logging.error(f"检查拉黑状态失败: {e}")
            return False

class DirectoryManager:
    """目录管理器，负责好友列表和在线状态管理"""
    
    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager
        self.online_users: Dict[int, Dict[str, Any]] = {}  # 在线用户缓存
        self.user_connections: Dict[int, Set[str]] = {}  # 用户连接映射
        
    async def set_online(self, user_id: int, username: str, ip_address: str, 
                        port: int, websocket_id: str = None) -> Dict[str, Any]:
        """设置用户在线状态"""
        try:
            # 更新数据库中的在线状态
            status_updated = self.db_manager.update_user_login_status(
                user_id=user_id,
                is_online=True,
                ip_address=ip_address,
                port=port
            )
            
            if not status_updated:
                return {
                    'success': False,
                    'error': '更新在线状态失败'
                }
            
            # 更新内存缓存
            self.online_users[user_id] = {
                'user_id': user_id,
                'username': username,
                'ip_address': ip_address,
                'port': port,
                'websocket_id': websocket_id,
                'last_activity': datetime.now(),
                'status': 'online'
            }
            
            # 添加连接映射
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            if websocket_id:
                self.user_connections[user_id].add(websocket_id)
            
            logging.info(f"用户 {username} (ID: {user_id}) 已上线")
            
            # 通知好友用户上线
            await self._notify_friends_status_change(user_id, 'online')
            
            return {
                'success': True,
                'message': '用户已上线',
                'online_friends': await self.get_online_friends_list(user_id)
            }
            
        except Exception as e:
            logging.error(f"设置在线状态失败: {e}")
            return {
                'success': False,
                'error': '服务器内部错误'
            }
    
    async def set_offline(self, user_id: int, websocket_id: str = None) -> Dict[str, Any]:
        """设置用户离线状态"""
        try:
            # 从连接映射中移除
            if user_id in self.user_connections and websocket_id:
                self.user_connections[user_id].discard(websocket_id)
                
                # 如果还有其他连接，不设置为离线
                if self.user_connections[user_id]:
                    return {
                        'success': True,
                        'message': '连接已断开，但用户仍在线'
                    }
            
            # 更新数据库中的离线状态
            status_updated = self.db_manager.update_user_login_status(
                user_id=user_id,
                is_online=False
            )
            
            # 从内存缓存中移除
            user_info = self.online_users.pop(user_id, {})
            username = user_info.get('username', 'Unknown')
            
            # 清理连接映射
            self.user_connections.pop(user_id, None)
            
            logging.info(f"用户 {username} (ID: {user_id}) 已下线")
            
            # 通知好友用户下线
            await self._notify_friends_status_change(user_id, 'offline')
            
            return {
                'success': True,
                'message': '用户已下线'
            }
            
        except Exception as e:
            logging.error(f"设置离线状态失败: {e}")
            return {
                'success': False,
                'error': '服务器内部错误'
            }
    
    async def get_online_friends_list(self, user_id: int) -> List[Dict[str, Any]]:
        """获取用户的在线好友列表"""
        try:
            # 从数据库获取好友列表
            friends = self.db_manager.get_online_friends(user_id)
            
            # 补充实时状态信息
            online_friends = []
            for friend in friends:
                friend_id = friend['user_id']
                if friend_id in self.online_users:
                    friend_info = {
                        'user_id': friend_id,
                        'username': friend['username'],
                        'public_key': friend['public_key'],
                        'ip_address': friend['ip_address'],
                        'port': friend['port'],
                        'status': 'online',
                        'last_activity': self.online_users[friend_id]['last_activity'].isoformat()
                    }
                    online_friends.append(friend_info)
            
            return online_friends
            
        except Exception as e:
            logging.error(f"获取在线好友列表失败: {e}")
            return []
    
    async def get_friend_public_key(self, friend_username: str) -> Optional[str]:
        """获取好友的RSA公钥"""
        try:
            public_key = self.db_manager.get_friend_public_key(friend_username)
            
            if public_key:
                logging.info(f"获取好友 {friend_username} 的公钥成功")
                return public_key
            else:
                logging.warning(f"未找到好友 {friend_username} 的公钥")
                return None
                
        except Exception as e:
            logging.error(f"获取好友公钥失败: {e}")
            return None
    
    async def _notify_friends_status_change(self, user_id: int, status: str):
        """通知好友用户状态变化"""
        try:
            # 获取该用户的所有好友
            friends = self.db_manager.get_online_friends(user_id)
            
            # 获取状态变化的用户信息
            user_info = self.online_users.get(user_id)
            if not user_info and status == 'online':
                return  # 无法获取用户信息
            
            # 构建通知消息
            notification = {
                'type': 'friend_status_change',
                'user_id': user_id,
                'username': user_info.get('username') if user_info else 'Unknown',
                'status': status,
                'timestamp': datetime.now().isoformat()
            }
            
            # 发送通知给在线好友
            for friend in friends:
                friend_id = friend['user_id']
                if friend_id in self.online_users:
                    # 这里应该通过WebSocket发送通知
                    # 具体实现在core.py中
                    pass
                    
        except Exception as e:
            logging.error(f"通知好友状态变化失败: {e}")
    
    def get_user_endpoint(self, username: str) -> Optional[Dict[str, Any]]:
        """获取用户的网络端点信息（用于P2P连接）"""
        try:
            user = self.db_manager.get_user_by_username(username)
            if not user or not user['is_online']:
                return None
            
            return {
                'username': user['username'],
                'ip_address': user['ip_address'],
                'port': user['port'],
                'public_key': user['public_key']
            }
            
        except Exception as e:
            logging.error(f"获取用户端点信息失败: {e}")
            return None
    
    def is_user_online(self, user_id: int) -> bool:
        """检查用户是否在线"""
        return user_id in self.online_users
    
    def get_online_users_count(self) -> int:
        """获取在线用户数量"""
        return len(self.online_users)
    
    def get_all_online_users(self) -> List[Dict[str, Any]]:
        """获取所有在线用户信息（管理员功能）"""
        try:
            online_list = []
            for user_id, user_info in self.online_users.items():
                online_list.append({
                    'user_id': user_id,
                    'username': user_info['username'],
                    'ip_address': user_info['ip_address'],
                    'port': user_info['port'],
                    'last_activity': user_info['last_activity'].isoformat(),
                    'connection_count': len(self.user_connections.get(user_id, set()))
                })
            
            return online_list
            
        except Exception as e:
            logging.error(f"获取在线用户列表失败: {e}")
            return []
    
    async def cleanup_inactive_users(self, timeout_minutes: int = 30):
        """清理非活跃用户"""
        try:
            current_time = datetime.now()
            timeout_delta = timedelta(minutes=timeout_minutes)
            
            inactive_users = []
            for user_id, user_info in list(self.online_users.items()):
                last_activity = user_info['last_activity']
                if current_time - last_activity > timeout_delta:
                    inactive_users.append(user_id)
            
            # 设置非活跃用户为离线
            for user_id in inactive_users:
                await self.set_offline(user_id)
                logging.info(f"用户 {user_id} 因非活跃被设置为离线")
            
            return len(inactive_users)
            
        except Exception as e:
            logging.error(f"清理非活跃用户失败: {e}")
            return 0
    
    def update_user_activity(self, user_id: int):
        """更新用户活动时间"""
        if user_id in self.online_users:
            self.online_users[user_id]['last_activity'] = datetime.now()
    
    async def handle_friend_request(self, requester_id: int, target_username: str) -> Dict[str, Any]:
        """处理好友请求"""
        try:
            # 获取目标用户信息
            target_user = self.db_manager.get_user_by_username(target_username)
            if not target_user:
                return {
                    'success': False,
                    'error': '用户不存在'
                }
            
            target_id = target_user['user_id']
            
            # 检查是否已经是好友
            # 这里需要在数据库中添加检查好友关系的方法
            # 简化处理，假设可以直接添加
            
            # 这里应该添加好友请求的逻辑
            # 实际实现中需要创建好友请求记录，等待对方确认
            
            return {
                'success': True,
                'message': f'已向 {target_username} 发送好友请求'
            }
            
        except Exception as e:
            logging.error(f"处理好友请求失败: {e}")
            return {
                'success': False,
                'error': '服务器内部错误'
            } 