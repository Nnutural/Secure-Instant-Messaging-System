"""
多进程管理器

实现主进程+工作进程池的架构，优化服务器并发性能
"""

import asyncio
import multiprocessing as mp
import signal
import time
import json
import logging
from typing import Dict, List, Optional, Any, Callable
from queue import Queue, Empty
from threading import Thread, Event
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from server.storage import DatabaseManager
from server.group import GroupManager
from common.packet import PacketProcessor
from common.schema import MessageType
from server.auth import AuthenticationManager
from server.directory import ContactManager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局数据库和认证管理器实例（在工作进程中使用）
db = None
group_mgr = None
auth_mgr = None
contact_mgr = None

def init_worker_globals():
    """初始化工作进程的全局变量"""
    global db, group_mgr, auth_mgr, contact_mgr
    
    try:
        from .storage import DatabaseManager
        from .group import GroupManager
        from .auth import AuthenticationManager
        from .directory import ContactManager
        
        db = DatabaseManager()
        group_mgr = GroupManager("secure_chat.db")
        auth_mgr = AuthenticationManager(db)
        contact_mgr = ContactManager()
        
        logger.info("工作进程全局变量初始化成功")
    except Exception as e:
        logger.error(f"工作进程全局变量初始化失败: {e}")
        raise

class WorkerProcess:
    """工作进程类"""
    
    def __init__(self, process_id: int):
        """
        初始化工作进程
        
        Args:
            process_id: 进程ID
        """
        self.process_id = process_id
        self.is_running = False
        # 初始化全局变量
        init_worker_globals()
        logger.info(f"工作进程 {process_id} 初始化完成")
    
    async def process_message(self, message_data: str, client_info: Dict[str, Any]) -> str:
        global db, group_mgr, auth_mgr
        try:
            import json
            message_obj = json.loads(message_data)
            message_type = message_obj.get('type', 'unknown')
            sender = message_obj.get('sender', 'unknown')
            logger.info(f"工作进程 {self.process_id} 处理消息类型: {message_type}, 发送者: {sender}")
            logger.info(f"消息内容: {message_obj}")  # 添加详细消息内容日志

            # 注册处理
            if message_type == MessageType.REGISTER.value:
                logger.info(f"进入注册处理逻辑, 消息类型: {message_type}")
                metadata = message_obj.get('metadata', {})
                username = metadata.get('username')
                password = metadata.get('password')
                email = metadata.get('email', f"{username}@demo.com")  # 默认邮箱
                logger.info(f"注册参数: username={username}, email={email}")
                if not username or not password:
                    logger.warning("注册失败: 用户名或密码为空")
                    return json.dumps({
                        "success": False, 
                        "message": "用户名和密码不能为空", 
                        "worker_id": self.process_id
                    })
                try:
                    # 调用认证管理器注册用户
                    logger.info("开始调用认证管理器注册用户...")
                    result = await auth_mgr.register_user(
                        username=username,
                        email=email,
                        password=password,
                        confirm_password=password
                    )
                    logger.info(f"注册结果: {result}")
                    return json.dumps({
                        "success": result['success'],
                        "message": result.get('message', result.get('error')),
                        "worker_id": self.process_id,
                        "user_id": result.get('user_id')
                    })
                except Exception as e:
                    logger.error(f"注册处理异常: {e}")
                    return json.dumps({
                        "success": False,
                        "message": f"注册处理异常: {str(e)}",
                        "worker_id": self.process_id
                    })

            # 登录处理
            if message_type == MessageType.LOGIN.value:
                logger.info(f"进入登录处理逻辑, 消息类型: {message_type}")
                metadata = message_obj.get('metadata', {})
                username = metadata.get('username')
                password = metadata.get('password')
                logger.info(f"登录参数: username={username}")
                if not username or not password:
                    logger.warning("登录失败: 用户名或密码为空")
                    return json.dumps({
                        "success": False, 
                        "message": "用户名和密码不能为空", 
                        "worker_id": self.process_id
                    })
                try:
                    # 调用认证管理器认证用户
                    logger.info("开始调用认证管理器认证用户...")
                    result = await auth_mgr.authenticate_user(username, password)
                    logger.info(f"登录结果: {result}")
                    # 如果登录成功，更新用户在线状态
                    if result['success']:
                        user_id = result['user_id']
                        db.update_user_login_status(
                            user_id=user_id,
                            is_online=True,
                            ip_address=client_info.get('ip', 'unknown'),
                            port=client_info.get('port', 0)
                        )
                        logger.info(f"用户 {username} 在线状态已更新")
                    return json.dumps({
                        "success": result['success'],
                        "message": result.get('message', result.get('error')),
                        "worker_id": self.process_id,
                        "user_id": result.get('user_id'),
                        "username": result.get('username'),
                        "session_token": result.get('session_token'),
                        "public_key": result.get('public_key')
                    })
                except Exception as e:
                    logger.error(f"登录处理异常: {e}")
                    return json.dumps({
                        "success": False,
                        "message": f"登录处理异常: {str(e)}",
                        "worker_id": self.process_id
                    })

            # 创建群组
            if message_type == "create_group":
                logger.info(f"进入群组创建逻辑")
                if group_mgr is None:
                    logger.error("group_mgr未初始化，无法创建群组")
                    return json.dumps({
                        "success": False,
                        "message": "处理失败: group_mgr未初始化",
                        "error_code": "PROCESSING_ERROR",
                        "worker_id": self.process_id
                    })
                group_id = message_obj.get('group_id')
                group_name = message_obj.get('group_name', group_id)
                members = message_obj.get('members', [])
                # 查找发送者ID
                sender_info = db.get_user_by_username(sender)
                sender_id = sender_info['user_id'] if sender_info else None
                logger.info(f"群组创建: 发送者ID={sender_id}, 群组ID={group_id}")
                if not sender_id:
                    return json.dumps({
                        "success": False, 
                        "message": "用户未登录", 
                        "worker_id": self.process_id
                    })
                try:
                    # 检查群组是否存在
                    existing_group = group_mgr.get_group_info(group_id)
                    if existing_group:
                        # 群组已存在，检查用户是否已是成员
                        current_members = group_mgr.get_group_members(group_id)
                        if sender_id not in current_members:
                            # 用户不是成员，自动加入
                            if group_mgr.add_member(group_id, sender_id):
                                logger.info(f"用户 {sender} 自动加入已存在的群组 {group_id}")
                                return json.dumps({
                                    "success": True,
                                    "message": f"已加入群组 {group_name}",
                                    "worker_id": self.process_id
                                })
                            else:
                                return json.dumps({
                                    "success": False,
                                    "message": "加入群组失败",
                                    "worker_id": self.process_id
                                })
                        else:
                            return json.dumps({
                                "success": True,
                                "message": "您已经是群组成员",
                                "worker_id": self.process_id
                            })
                    else:
                        # 创建新群组
                        result = group_mgr.create_group(group_id, group_name, sender_id, members)
                        logger.info(f"群组创建结果: {result}")
                        return json.dumps({
                            "success": result['success'],
                            "message": result.get('message', result.get('error')),
                            "worker_id": self.process_id
                        })
                except Exception as e:
                    logger.error(f"群组创建异常: {e}")
                    return json.dumps({
                        "success": False,
                        "message": f"群组创建异常: {str(e)}",
                        "worker_id": self.process_id
                    })

            # 群聊消息
            if message_type == "group_message":
                logger.info(f"进入群聊消息处理逻辑")
                if group_mgr is None:
                    logger.error("group_mgr未初始化，无法处理群聊消息")
                    return json.dumps({
                        "success": False,
                        "message": "处理失败: group_mgr未初始化",
                        "error_code": "PROCESSING_ERROR",
                        "worker_id": self.process_id
                    })
                group_id = message_obj.get('group_id')
                data = message_obj.get('data', {})
                sender_info = db.get_user_by_username(sender)
                sender_id = sender_info['user_id'] if sender_info else None
                logger.info(f"群聊消息: 发送者ID={sender_id}, 群组ID={group_id}")
                if not sender_id:
                    return json.dumps({
                        "success": False,
                        "message": "用户未登录",
                        "worker_id": self.process_id
                    })
                try:
                    # 获取群组成员
                    members = group_mgr.get_group_members(group_id)
                    logger.info(f"群组成员: {members}")
                    
                    # 检查发送者是否是群成员
                    if sender_id not in members:
                        return json.dumps({
                            "success": False,
                            "message": "您不是该群组成员",
                            "worker_id": self.process_id
                        })
                    
                    # 保存群聊消息到数据库
                    message_content = data.get('content', '')
                    message_type_db = data.get('content_type', 'text')
                    is_encrypted = data.get('encryption', 'none') != 'none'
                    
                    message_id = db.save_group_message(
                        group_id=group_id,
                        sender_id=sender_id,
                        message_content=message_content,
                        message_type=message_type_db,
                        is_encrypted=is_encrypted
                    )
                    
                    if message_id:
                        logger.info(f"群聊消息已保存，消息ID: {message_id}")
                        # 返回成功结果，包含转发信息
                        return json.dumps({
                        "success": True,
                        "message": "群聊消息已处理",
                            "worker_id": self.process_id,
                            "group_id": group_id,
                            "forward_to": members,  # 需要转发给的成员ID列表
                            "data": data,
                            "message_id": message_id
                        })
                    else:
                        return json.dumps({
                            "success": False,
                            "message": "消息保存失败",
                        "worker_id": self.process_id
                    })
                except Exception as e:
                    logger.error(f"群聊消息处理异常: {e}")
                    return json.dumps({
                        "success": False,
                        "message": f"群聊消息处理异常: {str(e)}",
                        "worker_id": self.process_id
                    })

            # 语音消息
            if message_type == "voice_message":
                logger.info(f"进入语音消息处理逻辑")
                recipient = message_obj.get('recipient')
                data = message_obj.get('data', {})
                
                sender_info = db.get_user_by_username(sender)
                sender_id = sender_info['user_id'] if sender_info else None
                if not sender_id:
                    return json.dumps({
                        "success": False,
                        "message": "用户未登录",
                        "worker_id": self.process_id
                    })
                
                # 检查接收者是否存在
                recipient_info = db.get_user_by_username(recipient)
                if not recipient_info:
                    return json.dumps({
                        "success": False,
                        "message": "接收者不存在",
                        "worker_id": self.process_id
                    })
                
                recipient_id = recipient_info['user_id']
                
                # 检查是否被拉黑
                if contact_mgr.is_blocked(recipient_id, sender_id):
                    return json.dumps({
                        "success": False,
                        "message": "消息发送失败：您已被对方拉黑",
                        "worker_id": self.process_id
                    })
                
                # 保存语音消息到数据库
                message_content = data.get('content', '')
                duration = data.get('duration', 0)
                is_encrypted = data.get('encryption', 'none') != 'none'
                
                # 将语音信息包含在消息内容中
                voice_info = {
                    'content': message_content,
                    'duration': duration,
                    'content_type': data.get('content_type', 'audio/wav')
                }
                
                message_id = db.save_message(
                    sender_id=sender_id,
                    receiver_id=recipient_id,
                    message_content=json.dumps(voice_info),
                    message_type='voice',
                    is_encrypted=is_encrypted
                )
                
                if message_id:
                    return json.dumps({
                        "success": True,
                        "message": "语音消息已发送",
                        "worker_id": self.process_id,
                        "recipient": recipient,
                        "recipient_username": recipient,  # 添加转发所需的字段
                        "sender": sender,
                        "message_type": "voice_message",
                        "data": data,
                        "message_id": message_id
                    })
                else:
                    return json.dumps({
                        "success": False,
                        "message": "语音消息保存失败",
                        "worker_id": self.process_id
                    })

            # 聊天历史查询
            if message_type == MessageType.GET_HISTORY.value or message_type == "get_history":
                logger.info(f"进入历史记录查询逻辑")
                chat_type = message_obj.get('chat_type')
                target_id = message_obj.get('target_id')
                start_time = message_obj.get('start_time')
                end_time = message_obj.get('end_time')
                limit = int(message_obj.get('limit', 50))
                offset = int(message_obj.get('offset', 0))
                
                sender_info = db.get_user_by_username(sender)
                user_id = sender_info['user_id'] if sender_info else None
                if not user_id:
                    return json.dumps({
                        "success": False,
                        "message": "用户未登录或不存在",
                        "worker_id": self.process_id
                    })
                
                try:
                    # 查询历史记录
                    records = db.get_history(chat_type, target_id, user_id, start_time, end_time, limit, offset)
                    logger.info(f"历史记录查询结果: 查询到{len(records)}条记录")
                    
                    # 返回历史记录响应，使用特殊的响应类型
                    return json.dumps({
                        "type": "history_response",
                        "success": True,
                        "message": "历史记录查询成功",
                        "worker_id": self.process_id,
                        "records": records,
                        "total": len(records),
                        "chat_type": chat_type,
                        "target_id": target_id
                    })
                except Exception as e:
                    logger.error(f"历史记录查询异常: {e}")
                    return json.dumps({
                        "success": False,
                        "message": f"历史记录查询异常: {str(e)}",
                        "worker_id": self.process_id
                    })

            # 通讯录管理
            if message_type == "add_contact":
                contact_username = message_obj.get('contact_username')
                alias = message_obj.get('alias')
                group = message_obj.get('group', '默认分组')
                
                sender_info = db.get_user_by_username(sender)
                user_id = sender_info['user_id'] if sender_info else None
                if not user_id:
                    return json.dumps({
                        "success": False,
                        "message": "用户未登录",
                        "worker_id": self.process_id
                    })
                
                # 查找联系人用户ID
                contact_info = db.get_user_by_username(contact_username)
                if not contact_info:
                    return json.dumps({
                        "success": False,
                        "message": "联系人用户不存在",
                        "worker_id": self.process_id
                    })
                
                contact_user_id = contact_info['user_id']
                result = contact_mgr.add_contact(user_id, contact_username, contact_user_id, alias, group)
                
                return json.dumps({
                    "success": result['success'],
                    "message": result['message'],
                    "worker_id": self.process_id
                })

            if message_type == "remove_contact":
                contact_user_id = message_obj.get('contact_user_id')
                
                sender_info = db.get_user_by_username(sender)
                user_id = sender_info['user_id'] if sender_info else None
                if not user_id:
                    return json.dumps({
                        "success": False,
                        "message": "用户未登录",
                        "worker_id": self.process_id
                    })
                
                result = contact_mgr.remove_contact(user_id, contact_user_id)
                
                return json.dumps({
                    "success": result['success'],
                    "message": result['message'],
                    "worker_id": self.process_id
                })

            if message_type == "get_contacts":
                group = message_obj.get('group')
                
                sender_info = db.get_user_by_username(sender)
                user_id = sender_info['user_id'] if sender_info else None
                if not user_id:
                    return json.dumps({
                        "success": False,
                        "message": "用户未登录",
                        "worker_id": self.process_id
                    })
                
                result = contact_mgr.get_contacts(user_id, group)
                
                return json.dumps({
                    "success": result['success'],
                    "message": result.get('message', '获取成功'),
                    "contacts": result.get('contacts', {}),
                    "groups": result.get('groups', {}),
                    "total": result.get('total', 0),
                    "worker_id": self.process_id
                })

            if message_type == "update_contact":
                contact_user_id = message_obj.get('contact_user_id')
                alias = message_obj.get('alias')
                group = message_obj.get('group')
                notes = message_obj.get('notes')
                is_favorite = message_obj.get('is_favorite')
                
                sender_info = db.get_user_by_username(sender)
                user_id = sender_info['user_id'] if sender_info else None
                if not user_id:
                    return json.dumps({
                        "success": False,
                        "message": "用户未登录",
                        "worker_id": self.process_id
                    })
                
                result = contact_mgr.update_contact(user_id, contact_user_id, alias, group, notes, is_favorite)
                
                return json.dumps({
                    "success": result['success'],
                    "message": result['message'],
                    "worker_id": self.process_id
                })

            # 文本消息处理
            if message_type == "text_message":
                recipient = message_obj.get('recipient')
                data = message_obj.get('data', {})
                
                sender_info = db.get_user_by_username(sender)
                sender_id = sender_info['user_id'] if sender_info else None
                if not sender_id:
                    return json.dumps({
                        "success": False,
                        "message": "用户未登录",
                        "worker_id": self.process_id
                    })
                
                # 检查接收者是否存在
                recipient_info = db.get_user_by_username(recipient)
                if not recipient_info:
                    return json.dumps({
                        "success": False,
                        "message": "接收者不存在",
                        "worker_id": self.process_id
                    })
                
                recipient_id = recipient_info['user_id']
                
                # 检查是否被拉黑
                if contact_mgr.is_blocked(recipient_id, sender_id):
                    return json.dumps({
                        "success": False,
                        "message": "消息发送失败：您已被对方拉黑",
                        "worker_id": self.process_id
                    })
                
                # 保存消息到数据库
                message_content = data.get('content', '')
                message_type_db = data.get('content_type', 'text')
                is_encrypted = data.get('encryption', 'none') != 'none'
                
                message_id = db.save_message(
                    sender_id=sender_id,
                    receiver_id=recipient_id,
                    message_content=message_content,
                    message_type=message_type_db,
                    is_encrypted=is_encrypted
                )
                
                if message_id:
                    return json.dumps({
                        "success": True,
                        "message": "消息已发送",
                        "worker_id": self.process_id,
                        "recipient": recipient,
                        "recipient_username": recipient,  # 添加转发所需的字段
                        "sender": sender,
                        "message_type": "text_message",
                        "data": data,
                        "message_id": message_id
                    })
                else:
                    return json.dumps({
                        "success": False,
                        "message": "消息保存失败",
                        "worker_id": self.process_id
                    })

            # 隐写消息处理
            if message_type == "stego_message":
                recipient = message_obj.get('recipient')
                data = message_obj.get('data', {})
                
                sender_info = db.get_user_by_username(sender)
                sender_id = sender_info['user_id'] if sender_info else None
                if not sender_id:
                    return json.dumps({
                        "success": False,
                        "message": "用户未登录",
                        "worker_id": self.process_id
                    })
                
                # 检查接收者是否存在
                recipient_info = db.get_user_by_username(recipient)
                if not recipient_info:
                    return json.dumps({
                        "success": False,
                        "message": "接收者不存在",
                        "worker_id": self.process_id
                    })
                
                recipient_id = recipient_info['user_id']
                
                # 检查是否被拉黑
                if contact_mgr.is_blocked(recipient_id, sender_id):
                    return json.dumps({
                        "success": False,
                        "message": "消息发送失败：您已被对方拉黑",
                        "worker_id": self.process_id
                    })
                
                # 保存隐写消息到数据库
                message_content = data.get('content', '')
                stego_method = data.get('stego_method', 'lsb')
                is_encrypted = data.get('encryption', 'none') != 'none'
                
                # 将元数据信息包含在消息内容中
                stego_info = {
                    'content': message_content,
                    'stego_method': stego_method,
                    'cover_image': data.get('cover_image', '')
                }
                
                message_id = db.save_message(
                    sender_id=sender_id,
                    receiver_id=recipient_id,
                    message_content=json.dumps(stego_info),
                    message_type='steganography',
                    is_encrypted=is_encrypted
                )
                
                if message_id:
                    return json.dumps({
                        "success": True,
                        "message": "隐写消息已发送",
                        "worker_id": self.process_id,
                        "recipient": recipient,
                        "recipient_username": recipient,  # 添加转发所需的字段
                        "sender": sender,
                        "message_type": "stego_message",
                        "data": data,
                        "message_id": message_id
                    })
                else:
                    return json.dumps({
                        "success": False,
                        "message": "隐写消息保存失败",
                        "worker_id": self.process_id
                    })

            # 构造响应
            response = {
                "success": True,
                "message": f"消息已由工作进程 {self.process_id} 处理",
                "worker_id": self.process_id,
                "processed_type": message_type,
                "timestamp": time.time()
            }
            return json.dumps(response)
        except Exception as e:
            logger.error(f"进程{self.process_id}处理消息失败: {e}")
            return json.dumps({
                "success": False,
                "message": f"处理失败: {str(e)}",
                "error_code": "PROCESSING_ERROR",
                "worker_id": self.process_id
            })

class MultiProcessManager:
    """多进程管理器"""
    
    def __init__(self, num_workers: Optional[int] = None):
        """
        初始化多进程管理器
        
        Args:
            num_workers: 工作进程数量，默认为CPU核心数
        """
        self.num_workers = num_workers or mp.cpu_count()
        self.workers = []
        self.is_running = False
        self.executor = None
        
        logger.info(f"初始化多进程管理器，工作进程数量: {self.num_workers}")
    
    def start(self):
        """启动多进程管理器"""
        logger.info("启动多进程管理器...")
        
        self.is_running = True
        
        # 使用ProcessPoolExecutor管理工作进程
        self.executor = ProcessPoolExecutor(
            max_workers=self.num_workers,
            initializer=self._init_worker
        )
        
        logger.info("多进程管理器启动完成")
    
    def stop(self):
        """停止多进程管理器"""
        logger.info("停止多进程管理器...")
        
        self.is_running = False
        
        if self.executor:
            self.executor.shutdown(wait=True)
            self.executor = None
        
        logger.info("多进程管理器已停止")
    
    @staticmethod
    def _init_worker():
        """工作进程初始化函数"""
        # 设置进程标题
        try:
            import setproctitle
            setproctitle.setproctitle(f"secure-chat-worker-{mp.current_process().pid}")
        except ImportError:
            pass
        
        # 忽略信号（由主进程处理）
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        
        # 初始化工作进程全局变量
        try:
            init_worker_globals()
            logger.info(f"工作进程 {mp.current_process().pid} 全局变量初始化完成")
        except Exception as e:
            logger.error(f"工作进程 {mp.current_process().pid} 全局变量初始化失败: {e}")
        
        logger.info(f"工作进程 {mp.current_process().pid} 初始化完成")
    
    async def process_message_async(self, message_data: str, client_info: Dict[str, Any]) -> str:
        """
        异步处理消息
        
        Args:
            message_data: 消息数据
            client_info: 客户端信息
            
        Returns:
            处理结果的JSON字符串
        """
        try:
            if not self.executor:
                return json.dumps({
                    "success": False,
                    "message": "服务器未启动",
                    "error_code": "SERVER_NOT_READY"
                })
            
            # 在工作进程中处理消息
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._process_message_sync,
                message_data, client_info
            )
            
            return result
            
        except Exception as e:
            logger.error(f"异步消息处理失败: {e}")
            return json.dumps({
                "success": False,
                "message": f"处理失败: {str(e)}",
                "error_code": "ASYNC_ERROR"
            })
    
    @staticmethod
    def _process_message_sync(message_data: str, client_info: Dict[str, Any]) -> str:
        """
        同步处理消息（在工作进程中执行）
        
        Args:
            message_data: 消息数据
            client_info: 客户端信息
            
        Returns:
            处理结果的JSON字符串
        """
        try:
            global db, group_mgr, auth_mgr, contact_mgr
            
            # 确保全局变量已初始化
            if db is None or group_mgr is None or auth_mgr is None or contact_mgr is None:
                init_worker_globals()
            
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                import json
                import time
                from common.schema import MessageType
                
                message_obj = json.loads(message_data)
                message_type = message_obj.get('type', 'unknown')
                sender = message_obj.get('sender', 'unknown')
                process_id = mp.current_process().pid
                
                logger.info(f"工作进程 {process_id} 处理消息类型: {message_type}, 发送者: {sender}")
                logger.info(f"消息内容: {message_obj}")

                # 注册处理
                if message_type == MessageType.REGISTER.value:
                    logger.info(f"进入注册处理逻辑, 消息类型: {message_type}")
                    metadata = message_obj.get('metadata', {})
                    username = metadata.get('username')
                    password = metadata.get('password')
                    email = metadata.get('email', f"{username}@demo.com")
                    logger.info(f"注册参数: username={username}, email={email}")
                    if not username or not password:
                        logger.warning("注册失败: 用户名或密码为空")
                        return json.dumps({
                            "success": False, 
                            "message": "用户名和密码不能为空", 
                            "worker_id": process_id
                        })
                    try:
                        logger.info("开始调用认证管理器注册用户...")
                        result = loop.run_until_complete(auth_mgr.register_user(
                            username=username,
                            email=email,
                            password=password,
                            confirm_password=password
                        ))
                        logger.info(f"注册结果: {result}")
                        return json.dumps({
                            "success": result['success'],
                            "message": result.get('message', result.get('error')),
                            "worker_id": process_id,
                            "user_id": result.get('user_id')
                        })
                    except Exception as e:
                        logger.error(f"注册处理异常: {e}")
                        return json.dumps({
                            "success": False,
                            "message": f"注册处理异常: {str(e)}",
                            "worker_id": process_id
                        })

                # 登录处理
                if message_type == MessageType.LOGIN.value:
                    logger.info(f"进入登录处理逻辑, 消息类型: {message_type}")
                    metadata = message_obj.get('metadata', {})
                    username = metadata.get('username')
                    password = metadata.get('password')
                    logger.info(f"登录参数: username={username}")
                    if not username or not password:
                        logger.warning("登录失败: 用户名或密码为空")
                        return json.dumps({
                            "success": False, 
                            "message": "用户名和密码不能为空", 
                            "worker_id": process_id
                        })
                    try:
                        logger.info("开始调用认证管理器认证用户...")
                        result = loop.run_until_complete(auth_mgr.authenticate_user(username, password))
                        logger.info(f"登录结果: {result}")
                        if result['success']:
                            user_id = result['user_id']
                            db.update_user_login_status(
                                user_id=user_id,
                                is_online=True,
                                ip_address=client_info.get('ip', 'unknown'),
                                port=client_info.get('port', 0)
                            )
                            logger.info(f"用户 {username} 在线状态已更新")
                        return json.dumps({
                            "success": result['success'],
                            "message": result.get('message', result.get('error')),
                            "worker_id": process_id,
                            "user_id": result.get('user_id'),
                            "username": result.get('username'),
                            "session_token": result.get('session_token'),
                            "public_key": result.get('public_key')
                        })
                    except Exception as e:
                        logger.error(f"登录处理异常: {e}")
                        return json.dumps({
                            "success": False,
                            "message": f"登录处理异常: {str(e)}",
                            "worker_id": process_id
                        })

                # 创建群组
                if message_type == "create_group":
                    logger.info(f"进入群组创建逻辑")
                    if group_mgr is None:
                        logger.error("group_mgr未初始化，无法创建群组")
                        return json.dumps({
                            "success": False,
                            "message": "处理失败: group_mgr未初始化",
                            "error_code": "PROCESSING_ERROR",
                            "worker_id": process_id
                        })
                    group_id = message_obj.get('group_id')
                    group_name = message_obj.get('group_name', group_id)
                    members = message_obj.get('members', [])
                    sender_info = db.get_user_by_username(sender)
                    sender_id = sender_info['user_id'] if sender_info else None
                    logger.info(f"群组创建: 发送者ID={sender_id}, 群组ID={group_id}")
                    if not sender_id:
                        return json.dumps({
                            "success": False, 
                            "message": "用户未登录", 
                            "worker_id": process_id
                        })
                    try:
                        # 检查群组是否存在
                        existing_group = group_mgr.get_group_info(group_id)
                        if existing_group:
                            # 群组已存在，检查用户是否已是成员
                            current_members = group_mgr.get_group_members(group_id)
                            if sender_id not in current_members:
                                # 用户不是成员，自动加入
                                if group_mgr.add_member(group_id, sender_id):
                                    logger.info(f"用户 {sender} 自动加入已存在的群组 {group_id}")
                                    return json.dumps({
                                        "success": True,
                                        "message": f"已加入群组 {group_name}",
                                        "worker_id": process_id
                                    })
                                else:
                                    return json.dumps({
                                        "success": False,
                                        "message": "加入群组失败",
                                        "worker_id": process_id
                                    })
                            else:
                                return json.dumps({
                                    "success": True,
                                    "message": "您已经是群组成员",
                                    "worker_id": process_id
                                })
                        else:
                            # 创建新群组
                            result = group_mgr.create_group(group_id, group_name, sender_id, members)
                            logger.info(f"群组创建结果: {result}")
                            return json.dumps({
                                "success": result['success'],
                                "message": result.get('message', result.get('error')),
                                "worker_id": process_id
                            })
                    except Exception as e:
                        logger.error(f"群组创建异常: {e}")
                        return json.dumps({
                            "success": False,
                            "message": f"群组创建异常: {str(e)}",
                            "worker_id": process_id
                        })

                # 群聊消息
                if message_type == "group_message":
                    logger.info(f"进入群聊消息处理逻辑")
                    if group_mgr is None:
                        logger.error("group_mgr未初始化，无法处理群聊消息")
                        return json.dumps({
                            "success": False,
                            "message": "处理失败: group_mgr未初始化",
                            "error_code": "PROCESSING_ERROR",
                            "worker_id": process_id
                        })
                    group_id = message_obj.get('group_id')
                    data = message_obj.get('data', {})
                    sender_info = db.get_user_by_username(sender)
                    sender_id = sender_info['user_id'] if sender_info else None
                    logger.info(f"群聊消息: 发送者ID={sender_id}, 群组ID={group_id}")
                    if not sender_id:
                        return json.dumps({
                            "success": False,
                            "message": "用户未登录",
                            "worker_id": process_id
                        })
                    try:
                        members = group_mgr.get_group_members(group_id)
                        logger.info(f"群组成员: {members}")
                        
                        if sender_id not in members:
                            return json.dumps({
                                "success": False,
                                "message": "您不是该群组成员",
                                "worker_id": process_id
                            })
                        
                        message_content = data.get('content', '')
                        message_type_db = data.get('content_type', 'text')
                        is_encrypted = data.get('encryption', 'none') != 'none'
                        
                        message_id = db.save_group_message(
                            group_id=group_id,
                            sender_id=sender_id,
                            message_content=message_content,
                            message_type=message_type_db,
                            is_encrypted=is_encrypted
                        )
                        
                        if message_id:
                            logger.info(f"群聊消息已保存，消息ID: {message_id}")
                            return json.dumps({
                                "success": True,
                                "message": "群聊消息已处理",
                                "worker_id": process_id,
                                "group_id": group_id,
                                "forward_to": members,
                                "data": data,
                                "message_id": message_id
                            })
                        else:
                            return json.dumps({
                                "success": False,
                                "message": "消息保存失败",
                                "worker_id": process_id
                            })
                    except Exception as e:
                        logger.error(f"群聊消息处理异常: {e}")
                        return json.dumps({
                            "success": False,
                            "message": f"群聊消息处理异常: {str(e)}",
                            "worker_id": process_id
                        })

                # 语音消息
                if message_type == "voice_message":
                    logger.info(f"进入语音消息处理逻辑")
                    recipient = message_obj.get('recipient')
                    data = message_obj.get('data', {})
                    
                    sender_info = db.get_user_by_username(sender)
                    sender_id = sender_info['user_id'] if sender_info else None
                    if not sender_id:
                        return json.dumps({
                            "success": False,
                            "message": "用户未登录",
                            "worker_id": process_id
                        })
                    
                    # 检查接收者是否存在
                    recipient_info = db.get_user_by_username(recipient)
                    if not recipient_info:
                        return json.dumps({
                            "success": False,
                            "message": "接收者不存在",
                            "worker_id": process_id
                        })
                    
                    recipient_id = recipient_info['user_id']
                    
                    # 检查是否被拉黑
                    if contact_mgr.is_blocked(recipient_id, sender_id):
                        return json.dumps({
                            "success": False,
                            "message": "消息发送失败：您已被对方拉黑",
                            "worker_id": process_id
                        })
                    
                    # 保存语音消息到数据库
                    message_content = data.get('content', '')
                    duration = data.get('duration', 0)
                    is_encrypted = data.get('encryption', 'none') != 'none'
                    
                    # 将语音信息包含在消息内容中
                    voice_info = {
                        'content': message_content,
                        'duration': duration,
                        'content_type': data.get('content_type', 'audio/wav')
                    }
                    
                    message_id = db.save_message(
                        sender_id=sender_id,
                        receiver_id=recipient_id,
                        message_content=json.dumps(voice_info),
                        message_type='voice',
                        is_encrypted=is_encrypted
                    )
                    
                    if message_id:
                        return json.dumps({
                            "success": True,
                            "message": "语音消息已发送",
                            "worker_id": process_id,
                            "recipient": recipient,
                            "recipient_username": recipient,  # 添加转发所需的字段
                            "sender": sender,
                            "message_type": "voice_message",
                            "data": data,
                            "message_id": message_id
                        })
                    else:
                        return json.dumps({
                            "success": False,
                            "message": "语音消息保存失败",
                            "worker_id": process_id
                        })

                # 聊天历史查询
                if message_type == MessageType.GET_HISTORY.value or message_type == "get_history":
                    logger.info(f"进入历史记录查询逻辑")
                    chat_type = message_obj.get('chat_type')
                    target_id = message_obj.get('target_id')
                    start_time = message_obj.get('start_time')
                    end_time = message_obj.get('end_time')
                    limit = int(message_obj.get('limit', 50))
                    offset = int(message_obj.get('offset', 0))
                    
                    sender_info = db.get_user_by_username(sender)
                    user_id = sender_info['user_id'] if sender_info else None
                    if not user_id:
                        return json.dumps({
                            "success": False,
                            "message": "用户未登录或不存在",
                            "worker_id": process_id
                        })
                    
                    try:
                        # 查询历史记录
                        records = db.get_history(chat_type, target_id, user_id, start_time, end_time, limit, offset)
                        logger.info(f"历史记录查询结果: 查询到{len(records)}条记录")
                        
                        # 返回历史记录响应，使用特殊的响应类型
                        return json.dumps({
                            "type": "history_response",
                            "success": True,
                            "message": "历史记录查询成功",
                            "worker_id": process_id,
                            "records": records,
                            "total": len(records),
                            "chat_type": chat_type,
                            "target_id": target_id
                        })
                    except Exception as e:
                        logger.error(f"历史记录查询异常: {e}")
                        return json.dumps({
                            "success": False,
                            "message": f"历史记录查询异常: {str(e)}",
                            "worker_id": process_id
                        })

                # 通讯录管理
                if message_type == "add_contact":
                    contact_username = message_obj.get('contact_username')
                    alias = message_obj.get('alias')
                    group = message_obj.get('group', '默认分组')
                    
                    sender_info = db.get_user_by_username(sender)
                    user_id = sender_info['user_id'] if sender_info else None
                    if not user_id:
                        return json.dumps({
                            "success": False,
                            "message": "用户未登录",
                            "worker_id": process_id
                        })
                    
                    # 查找联系人用户ID
                    contact_info = db.get_user_by_username(contact_username)
                    if not contact_info:
                        return json.dumps({
                            "success": False,
                            "message": "联系人用户不存在",
                            "worker_id": process_id
                        })
                    
                    contact_user_id = contact_info['user_id']
                    result = contact_mgr.add_contact(user_id, contact_username, contact_user_id, alias, group)
                    
                    return json.dumps({
                        "success": result['success'],
                        "message": result['message'],
                        "worker_id": process_id
                    })

                if message_type == "remove_contact":
                    contact_user_id = message_obj.get('contact_user_id')
                    
                    sender_info = db.get_user_by_username(sender)
                    user_id = sender_info['user_id'] if sender_info else None
                    if not user_id:
                        return json.dumps({
                            "success": False,
                            "message": "用户未登录",
                            "worker_id": process_id
                        })
                    
                    result = contact_mgr.remove_contact(user_id, contact_user_id)
                    
                    return json.dumps({
                        "success": result['success'],
                        "message": result['message'],
                        "worker_id": process_id
                    })

                if message_type == "get_contacts":
                    group = message_obj.get('group')
                    
                    sender_info = db.get_user_by_username(sender)
                    user_id = sender_info['user_id'] if sender_info else None
                    if not user_id:
                        return json.dumps({
                            "success": False,
                            "message": "用户未登录",
                            "worker_id": process_id
                        })
                    
                    result = contact_mgr.get_contacts(user_id, group)
                    
                    return json.dumps({
                        "success": result['success'],
                        "message": result.get('message', '获取成功'),
                        "contacts": result.get('contacts', {}),
                        "groups": result.get('groups', {}),
                        "total": result.get('total', 0),
                        "worker_id": process_id
                    })

                if message_type == "update_contact":
                    contact_user_id = message_obj.get('contact_user_id')
                    alias = message_obj.get('alias')
                    group = message_obj.get('group')
                    notes = message_obj.get('notes')
                    is_favorite = message_obj.get('is_favorite')
                    
                    sender_info = db.get_user_by_username(sender)
                    user_id = sender_info['user_id'] if sender_info else None
                    if not user_id:
                        return json.dumps({
                            "success": False,
                            "message": "用户未登录",
                            "worker_id": process_id
                        })
                    
                    result = contact_mgr.update_contact(user_id, contact_user_id, alias, group, notes, is_favorite)
                    
                    return json.dumps({
                        "success": result['success'],
                        "message": result['message'],
                        "worker_id": process_id
                    })

                # 文本消息处理
                if message_type == "text_message":
                    recipient = message_obj.get('recipient')
                    data = message_obj.get('data', {})
                    
                    sender_info = db.get_user_by_username(sender)
                    sender_id = sender_info['user_id'] if sender_info else None
                    if not sender_id:
                        return json.dumps({
                            "success": False,
                            "message": "用户未登录",
                            "worker_id": process_id
                        })
                    
                    # 检查接收者是否存在
                    recipient_info = db.get_user_by_username(recipient)
                    if not recipient_info:
                        return json.dumps({
                            "success": False,
                            "message": "接收者不存在",
                            "worker_id": process_id
                        })
                    
                    recipient_id = recipient_info['user_id']
                    
                    # 检查是否被拉黑
                    if contact_mgr.is_blocked(recipient_id, sender_id):
                        return json.dumps({
                            "success": False,
                            "message": "消息发送失败：您已被对方拉黑",
                            "worker_id": process_id
                        })
                    
                    # 保存消息到数据库
                    message_content = data.get('content', '')
                    message_type_db = data.get('content_type', 'text')
                    is_encrypted = data.get('encryption', 'none') != 'none'
                    
                    message_id = db.save_message(
                        sender_id=sender_id,
                        receiver_id=recipient_id,
                        message_content=message_content,
                        message_type=message_type_db,
                        is_encrypted=is_encrypted
                    )
                    
                    if message_id:
                        return json.dumps({
                            "success": True,
                            "message": "消息已发送",
                            "worker_id": process_id,
                            "recipient": recipient,
                            "recipient_username": recipient,  # 添加转发所需的字段
                            "sender": sender,
                            "message_type": "text_message",
                            "data": data,
                            "message_id": message_id
                        })
                    else:
                        return json.dumps({
                            "success": False,
                            "message": "消息保存失败",
                            "worker_id": process_id
                        })

                # 隐写消息处理
                if message_type == "stego_message":
                    recipient = message_obj.get('recipient')
                    data = message_obj.get('data', {})
                    
                    sender_info = db.get_user_by_username(sender)
                    sender_id = sender_info['user_id'] if sender_info else None
                    if not sender_id:
                        return json.dumps({
                            "success": False,
                            "message": "用户未登录",
                            "worker_id": process_id
                        })
                    
                    # 检查接收者是否存在
                    recipient_info = db.get_user_by_username(recipient)
                    if not recipient_info:
                        return json.dumps({
                            "success": False,
                            "message": "接收者不存在",
                            "worker_id": process_id
                        })
                    
                    recipient_id = recipient_info['user_id']
                    
                    # 检查是否被拉黑
                    if contact_mgr.is_blocked(recipient_id, sender_id):
                        return json.dumps({
                            "success": False,
                            "message": "消息发送失败：您已被对方拉黑",
                            "worker_id": process_id
                        })
                    
                    # 保存隐写消息到数据库
                    message_content = data.get('content', '')
                    stego_method = data.get('stego_method', 'lsb')
                    is_encrypted = data.get('encryption', 'none') != 'none'
                    
                    # 将元数据信息包含在消息内容中
                    stego_info = {
                        'content': message_content,
                        'stego_method': stego_method,
                        'cover_image': data.get('cover_image', '')
                    }
                    
                    message_id = db.save_message(
                        sender_id=sender_id,
                        receiver_id=recipient_id,
                        message_content=json.dumps(stego_info),
                        message_type='steganography',
                        is_encrypted=is_encrypted
                    )
                    
                    if message_id:
                        return json.dumps({
                            "success": True,
                            "message": "隐写消息已发送",
                            "worker_id": process_id,
                            "recipient": recipient,
                            "recipient_username": recipient,  # 添加转发所需的字段
                            "sender": sender,
                            "message_type": "stego_message",
                            "data": data,
                            "message_id": message_id
                        })
                    else:
                        return json.dumps({
                            "success": False,
                            "message": "隐写消息保存失败",
                            "worker_id": process_id
                        })

                # 构造响应
                response = {
                    "success": True,
                    "message": f"消息已由工作进程 {process_id} 处理",
                    "worker_id": process_id,
                    "processed_type": message_type,
                    "timestamp": time.time()
                }
                return json.dumps(response)
                
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"同步消息处理失败: {e}")
            import json
            return json.dumps({
                "success": False,
                "message": f"处理失败: {str(e)}",
                "error_code": "WORKER_ERROR"
            })
    
    def get_stats(self) -> Dict[str, Any]:
        """获取管理器统计信息"""
        return {
            'num_workers': self.num_workers,
            'is_running': self.is_running,
            'executor_available': self.executor is not None
        } 