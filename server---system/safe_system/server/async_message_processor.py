"""
异步消息处理器

基于统一消息结构体实现完全异步的消息分发和处理机制
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, Callable, List
from dataclasses import asdict
from datetime import datetime

from common.message_structures import (
    MsgTag, BaseMessage, MSG_TYPE_TO_STRING, STRING_TO_MSG_TYPE,
    DATACLASS_TYPE_MAP
)
from common.async_protocol import AsyncProtocolProcessor, create_response
from .storage import DatabaseManager
from .auth import AuthenticationManager
from .group import GroupManager
from .directory import ContactManager

logger = logging.getLogger(__name__)

class AsyncMessageProcessor:
    """异步消息处理器"""
    
    def __init__(self, db_path: str = "secure_chat.db"):
        """
        初始化异步消息处理器
        
        Args:
            db_path: 数据库路径
        """
        # 初始化组件
        self.db = DatabaseManager(db_path)
        self.auth_mgr = AuthenticationManager(self.db)
        self.group_mgr = GroupManager(db_path)
        self.contact_mgr = ContactManager()
        self.protocol = AsyncProtocolProcessor()
        
        # 消息处理器映射
        self.handlers: Dict[MsgTag, Callable] = {
            # 客户端到服务器
            MsgTag.REGISTER: self._handle_register,
            MsgTag.LOGIN: self._handle_login,
            MsgTag.LOGOUT: self._handle_logout,
            MsgTag.GET_DIRECTORY: self._handle_get_directory,
            MsgTag.GET_HISTORY: self._handle_get_history,
            MsgTag.GET_PUBLIC_KEY: self._handle_get_public_key,
            MsgTag.ALIVE: self._handle_alive,
            MsgTag.BACKUP: self._handle_backup,
            
            # 点对点消息
            MsgTag.MESSAGE: self._handle_message,
            MsgTag.VOICE: self._handle_voice,
            MsgTag.FILE: self._handle_file,
            MsgTag.PICTURE: self._handle_picture,
            
            # 扩展消息类型
            MsgTag.TEXT_MESSAGE: self._handle_text_message,
            MsgTag.GROUP_MESSAGE: self._handle_group_message,
            MsgTag.STEGO_MESSAGE: self._handle_stego_message,
            MsgTag.VOICE_MESSAGE: self._handle_voice_message,
            MsgTag.CREATE_GROUP: self._handle_create_group,
            MsgTag.HEARTBEAT: self._handle_heartbeat,
            MsgTag.PERFORMANCE_TEST: self._handle_performance_test,
            
            # 联系人管理
            MsgTag.ADD_CONTACT: self._handle_add_contact,
            MsgTag.GET_CONTACTS: self._handle_get_contacts,
            MsgTag.UPDATE_CONTACT: self._handle_update_contact,
            MsgTag.REMOVE_CONTACT: self._handle_remove_contact,
            
            # 群组管理
            MsgTag.GET_GROUPS: self._handle_get_groups,
            MsgTag.JOIN_GROUP: self._handle_join_group
        }
        
        # 统计信息
        self.stats = {
            'messages_processed': 0,
            'processing_time_total': 0.0,
            'processing_errors': 0,
            'handler_stats': {}
        }
        
        # 消息队列和协程池
        self.message_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self.worker_tasks: List[asyncio.Task] = []
        self.num_workers = 8
        self.running = False
    
    async def start(self):
        """启动消息处理器"""
        try:
            self.running = True
            
            # 启动工作协程
            for i in range(self.num_workers):
                task = asyncio.create_task(self._message_worker(f"processor-{i}"))
                self.worker_tasks.append(task)
            
            logger.info(f"异步消息处理器已启动，工作协程数: {self.num_workers}")
            
        except Exception as e:
            logger.error(f"启动消息处理器失败: {e}")
            raise
    
    async def stop(self):
        """停止消息处理器"""
        try:
            self.running = False
            
            # 停止工作协程
            for task in self.worker_tasks:
                task.cancel()
            
            if self.worker_tasks:
                await asyncio.gather(*self.worker_tasks, return_exceptions=True)
            
            logger.info("异步消息处理器已停止")
            
        except Exception as e:
            logger.error(f"停止消息处理器失败: {e}")
    
    async def process_message_async(self, message_data: str, client_info: Dict[str, Any]) -> str:
        """
        异步处理消息
        
        Args:
            message_data: 消息数据
            client_info: 客户端信息
            
        Returns:
            处理结果
        """
        try:
            # 解析消息
            data = json.loads(message_data)
            
            # 验证消息格式
            if not await self.protocol.validate_message(data):
                return json.dumps(await create_response(
                    data, False, "无效的消息格式"
                ))
            
            # 获取消息类型
            message_type_str = data.get('type', 'unknown')
            message_type = self.protocol.get_message_type_from_string(message_type_str)
            
            if not message_type:
                return json.dumps(await create_response(
                    data, False, f"不支持的消息类型: {message_type_str}"
                ))
            
            # 记录开始时间
            start_time = time.time()
            
            # 查找处理器
            handler = self.handlers.get(message_type)
            if not handler:
                return json.dumps(await create_response(
                    data, False, f"未找到消息类型 {message_type_str} 的处理器"
                ))
            
            # 处理消息
            result = await handler(data, client_info)
            
            # 更新统计
            processing_time = time.time() - start_time
            self.stats['messages_processed'] += 1
            self.stats['processing_time_total'] += processing_time
            
            # 更新处理器统计
            handler_name = handler.__name__
            if handler_name not in self.stats['handler_stats']:
                self.stats['handler_stats'][handler_name] = {
                    'count': 0,
                    'total_time': 0.0,
                    'avg_time': 0.0
                }
            
            handler_stats = self.stats['handler_stats'][handler_name]
            handler_stats['count'] += 1
            handler_stats['total_time'] += processing_time
            handler_stats['avg_time'] = handler_stats['total_time'] / handler_stats['count']
            
            return result
            
        except json.JSONDecodeError as e:
            self.stats['processing_errors'] += 1
            logger.error(f"JSON解析失败: {e}")
            return json.dumps({
                'success': False,
                'message': 'JSON格式错误',
                'error': str(e)
            })
        except Exception as e:
            self.stats['processing_errors'] += 1
            logger.error(f"消息处理异常: {e}")
            return json.dumps({
                'success': False,
                'message': '服务器内部错误',
                'error': str(e)
            })
    
    async def _message_worker(self, worker_name: str):
        """消息工作协程"""
        logger.info(f"消息工作协程 {worker_name} 已启动")
        
        while self.running:
            try:
                # 获取消息（带超时）
                try:
                    message_item = await asyncio.wait_for(
                        self.message_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # 处理消息
                result = await self.process_message_async(
                    message_item['message_data'],
                    message_item['client_info']
                )
                
                # 设置结果
                if 'result_future' in message_item:
                    message_item['result_future'].set_result(result)
                
                # 标记任务完成
                self.message_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"消息工作协程 {worker_name} 异常: {e}")
    
    # =================================================================
    #                      消息处理器实现
    # =================================================================
    
    async def _handle_register(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理注册请求"""
        try:
            metadata = data.get('metadata', {})
            username = metadata.get('username')
            password = metadata.get('password')
            email = metadata.get('email', f"{username}@demo.com")
            
            if not username or not password:
                return json.dumps(await create_response(
                    data, False, "用户名和密码不能为空"
                ))
            
            # 调用认证管理器注册用户
            result = await self.auth_mgr.register_user(
                username=username,
                email=email,
                password=password,
                confirm_password=password
            )
            
            return json.dumps({
                'success': result['success'],
                'message': result.get('message', result.get('error')),
                'user_id': result.get('user_id'),
                'type': 'register_response'
            })
            
        except Exception as e:
            logger.error(f"注册处理异常: {e}")
            return json.dumps(await create_response(
                data, False, f"注册处理异常: {str(e)}"
            ))
    
    async def _handle_login(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理登录请求"""
        try:
            metadata = data.get('metadata', {})
            username = metadata.get('username')
            password = metadata.get('password')
            
            if not username or not password:
                return json.dumps(await create_response(
                    data, False, "用户名和密码不能为空"
                ))
            
            # 调用认证管理器认证用户
            result = await self.auth_mgr.authenticate_user(username, password)
            
            # 如果登录成功，更新用户在线状态
            if result['success']:
                user_id = result['user_id']
                self.db.update_user_login_status(
                    user_id=user_id,
                    is_online=True,
                    ip_address=client_info.get('ip', 'unknown'),
                    port=client_info.get('port', 0)
                )
                
                # 更新客户端信息
                client_info['username'] = username
                client_info['user_id'] = user_id
            
            return json.dumps({
                'success': result['success'],
                'message': result.get('message', result.get('error')),
                'user_id': result.get('user_id'),
                'username': result.get('username'),
                'session_token': result.get('session_token'),
                'public_key': result.get('public_key'),
                'type': 'login_response'
            })
            
        except Exception as e:
            logger.error(f"登录处理异常: {e}")
            return json.dumps(await create_response(
                data, False, f"登录处理异常: {str(e)}"
            ))
    
    async def _handle_logout(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理注销请求"""
        try:
            username = data.get('username') or client_info.get('username')
            if not username:
                return json.dumps(await create_response(
                    data, False, "用户名不能为空"
                ))
            
            # 更新用户离线状态
            user_info = self.db.get_user_by_username(username)
            if user_info:
                self.db.update_user_login_status(
                    user_id=user_info['user_id'],
                    is_online=False
                )
            
            return json.dumps(await create_response(
                data, True, "注销成功", type='logout_response'
            ))
            
        except Exception as e:
            logger.error(f"注销处理异常: {e}")
            return json.dumps(await create_response(
                data, False, f"注销处理异常: {str(e)}"
            ))
    
    async def _handle_get_directory(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理获取通讯录请求"""
        try:
            username = data.get('username') or client_info.get('username')
            if not username:
                return json.dumps(await create_response(
                    data, False, "用户名不能为空"
                ))
            
            # 获取用户信息
            user_info = self.db.get_user_by_username(username)
            if not user_info:
                return json.dumps(await create_response(
                    data, False, "用户不存在"
                ))
            
            # 获取联系人列表
            contacts = self.contact_mgr.get_user_contacts(user_info['user_id'])
            
            return json.dumps({
                'success': True,
                'contacts': contacts,
                'total': len(contacts),
                'type': 'directory_response'
            })
            
        except Exception as e:
            logger.error(f"获取通讯录异常: {e}")
            return json.dumps(await create_response(
                data, False, f"获取通讯录异常: {str(e)}"
            ))
    
    async def _handle_get_history(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理获取历史记录请求"""
        try:
            chat_type = data.get('chat_type', 'single')
            target_id = data.get('target_id')
            limit = data.get('limit', 50)
            username = client_info.get('username')
            
            if not username:
                return json.dumps(await create_response(
                    data, False, "用户未登录"
                ))
            
            if not target_id:
                return json.dumps(await create_response(
                    data, False, "目标ID不能为空"
                ))
            
            # 获取用户信息
            user_info = self.db.get_user_by_username(username)
            if not user_info:
                return json.dumps(await create_response(
                    data, False, "用户不存在"
                ))
            
            user_id = user_info['user_id']
            
            # 获取历史记录
            records = self.db.get_history(chat_type, target_id, user_id, limit=limit)
            
            return json.dumps({
                'success': True,
                'records': records,
                'total': len(records),
                'chat_type': chat_type,
                'type': 'history_response'
            })
            
        except Exception as e:
            logger.error(f"获取历史记录异常: {e}")
            return json.dumps(await create_response(
                data, False, f"获取历史记录异常: {str(e)}"
            ))
    
    async def _handle_get_public_key(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理获取公钥请求"""
        try:
            user_id = data.get('user_id')
            dest_id = data.get('dest_id')
            
            if not user_id or not dest_id:
                return json.dumps(await create_response(
                    data, False, "用户ID和目标ID不能为空"
                ))
            
            # 获取目标用户的公钥
            dest_user_info = self.db.get_user_by_id(dest_id)
            if not dest_user_info:
                return json.dumps(await create_response(
                    data, False, "目标用户不存在"
                ))
            
            public_key = dest_user_info.get('public_key', '')
            
            return json.dumps({
                'success': True,
                'user_id': user_id,
                'dest_id': dest_id,
                'public_key': public_key,
                'type': 'public_key_response'
            })
            
        except Exception as e:
            logger.error(f"获取公钥异常: {e}")
            return json.dumps(await create_response(
                data, False, f"获取公钥异常: {str(e)}"
            ))
    
    async def _handle_alive(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理心跳请求"""
        try:
            user_id = data.get('user_id') or client_info.get('user_id')
            
            if user_id:
                # 更新用户活动时间
                self.db.update_user_last_activity(user_id)
            
            return json.dumps({
                'success': True,
                'message': '心跳正常',
                'timestamp': datetime.now().isoformat(),
                'type': 'alive_response'
            })
            
        except Exception as e:
            logger.error(f"心跳处理异常: {e}")
            return json.dumps(await create_response(
                data, False, f"心跳处理异常: {str(e)}"
            ))
    
    async def _handle_backup(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理备份请求"""
        try:
            user_id = data.get('user_id')
            dest_id = data.get('dest_id')
            backup_data = data.get('data')
            
            if not user_id or not dest_id or not backup_data:
                return json.dumps(await create_response(
                    data, False, "备份参数不完整"
                ))
            
            # TODO: 实现备份逻辑
            
            return json.dumps({
                'success': True,
                'message': '备份成功',
                'type': 'backup_response'
            })
            
        except Exception as e:
            logger.error(f"备份处理异常: {e}")
            return json.dumps(await create_response(
                data, False, f"备份处理异常: {str(e)}"
            ))
    
    async def _handle_message(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理普通消息"""
        try:
            message_id = data.get('message_id')
            source_id = data.get('source_id')
            dest_id = data.get('dest_id')
            content = data.get('content')
            
            if not all([message_id, source_id, dest_id, content]):
                return json.dumps(await create_response(
                    data, False, "消息参数不完整"
                ))
            
            # 保存消息到数据库
            saved_message_id = self.db.save_message(
                sender_id=source_id,
                receiver_id=dest_id,
                message_content=content,
                message_type='text'
            )
            
            return json.dumps({
                'success': True,
                'message_id': saved_message_id,
                'type': 'message_response',
                'forward_to': dest_id
            })
            
        except Exception as e:
            logger.error(f"消息处理异常: {e}")
            return json.dumps(await create_response(
                data, False, f"消息处理异常: {str(e)}"
            ))
    
    async def _handle_voice(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理语音消息"""
        try:
            voice_id = data.get('voice_id')
            source_id = data.get('source_id')
            dest_id = data.get('dest_id')
            voice_data = data.get('data')
            duration = data.get('duration', 0.0)
            
            if not all([voice_id, source_id, dest_id, voice_data]):
                return json.dumps(await create_response(
                    data, False, "语音消息参数不完整"
                ))
            
            # 保存语音消息到数据库
            saved_message_id = self.db.save_message(
                sender_id=source_id,
                receiver_id=dest_id,
                message_content=voice_data,
                message_type='voice'
            )
            
            return json.dumps({
                'success': True,
                'message_id': saved_message_id,
                'voice_id': voice_id,
                'type': 'voice_response',
                'forward_to': dest_id
            })
            
        except Exception as e:
            logger.error(f"语音消息处理异常: {e}")
            return json.dumps(await create_response(
                data, False, f"语音消息处理异常: {str(e)}"
            ))
    
    async def _handle_file(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理文件消息"""
        try:
            file_id = data.get('file_id')
            source_id = data.get('source_id')
            dest_id = data.get('dest_id')
            file_name = data.get('file_name')
            file_data = data.get('data')
            file_size = data.get('file_size', 0)
            
            if not all([file_id, source_id, dest_id, file_name, file_data]):
                return json.dumps(await create_response(
                    data, False, "文件消息参数不完整"
                ))
            
            # 保存文件消息到数据库
            saved_message_id = self.db.save_message(
                sender_id=source_id,
                receiver_id=dest_id,
                message_content=file_data,
                message_type='file'
            )
            
            return json.dumps({
                'success': True,
                'message_id': saved_message_id,
                'file_id': file_id,
                'type': 'file_response',
                'forward_to': dest_id
            })
            
        except Exception as e:
            logger.error(f"文件消息处理异常: {e}")
            return json.dumps(await create_response(
                data, False, f"文件消息处理异常: {str(e)}"
            ))
    
    async def _handle_picture(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理图片消息"""
        try:
            picture_id = data.get('picture_id')
            source_id = data.get('source_id')
            dest_id = data.get('dest_id')
            image_data = data.get('data')
            image_format = data.get('image_format', 'jpeg')
            
            if not all([picture_id, source_id, dest_id, image_data]):
                return json.dumps(await create_response(
                    data, False, "图片消息参数不完整"
                ))
            
            # 保存图片消息到数据库
            saved_message_id = self.db.save_message(
                sender_id=source_id,
                receiver_id=dest_id,
                message_content=image_data,
                message_type='picture'
            )
            
            return json.dumps({
                'success': True,
                'message_id': saved_message_id,
                'picture_id': picture_id,
                'type': 'picture_response',
                'forward_to': dest_id
            })
            
        except Exception as e:
            logger.error(f"图片消息处理异常: {e}")
            return json.dumps(await create_response(
                data, False, f"图片消息处理异常: {str(e)}"
            ))
    
    # 扩展消息类型处理器
    
    async def _handle_text_message(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理文本消息（扩展）"""
        try:
            recipient = data.get('recipient')
            message_data = data.get('data', {})
            sender = data.get('sender') or client_info.get('username')
            
            if not recipient or not message_data:
                return json.dumps(await create_response(
                    data, False, "消息参数不完整"
                ))
            
            # 获取发送者信息
            sender_info = self.db.get_user_by_username(sender)
            if not sender_info:
                return json.dumps(await create_response(
                    data, False, "发送者不存在"
                ))
            
            # 获取接收者信息
            recipient_info = self.db.get_user_by_username(recipient)
            if not recipient_info:
                return json.dumps(await create_response(
                    data, False, "接收者不存在"
                ))
            
            # 保存消息
            message_id = self.db.save_message(
                sender_id=sender_info['user_id'],
                receiver_id=recipient_info['user_id'],
                message_content=message_data.get('content', ''),
                message_type=message_data.get('content_type', 'text')
            )
            
            return json.dumps({
                'success': True,
                'message_id': message_id,
                'type': 'text_message_response',
                'forward_to': recipient,
                'original_data': {
                    'sender': sender,
                    'recipient': recipient,
                    'data': message_data
                }
            })
            
        except Exception as e:
            logger.error(f"文本消息处理异常: {e}")
            return json.dumps(await create_response(
                data, False, f"文本消息处理异常: {str(e)}"
            ))
    
    async def _handle_group_message(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理群聊消息"""
        try:
            group_id = data.get('group_id')
            message_data = data.get('data', {})
            sender = data.get('sender') or client_info.get('username')
            
            if not group_id or not message_data:
                return json.dumps(await create_response(
                    data, False, "群聊消息参数不完整"
                ))
            
            # 获取发送者信息
            sender_info = self.db.get_user_by_username(sender)
            if not sender_info:
                return json.dumps(await create_response(
                    data, False, "发送者不存在"
                ))
            
            sender_id = sender_info['user_id']
            
            # 检查群组是否存在，如果不存在则创建
            group_info = self.group_mgr.get_group_info(group_id)
            if not group_info:
                # 群组不存在，尝试创建
                create_result = self.group_mgr.create_group(group_id, group_id, sender_id, [])
                if not create_result.get('success'):
                    return json.dumps(await create_response(
                        data, False, f"群组创建失败: {create_result.get('error', '未知错误')}"
                    ))
            
            # 检查用户是否是群组成员，如果不是则添加
            members = self.group_mgr.get_group_members(group_id)
            if sender_id not in members:
                # 添加用户为群组成员
                add_result = self.group_mgr.add_member(group_id, sender_id)
                if not add_result:
                    return json.dumps(await create_response(
                        data, False, "无法加入群组"
                    ))
                members.append(sender_id)
            
            # 保存群聊消息
            message_id = self.db.save_group_message(
                group_id=group_id,
                sender_id=sender_id,
                message_content=message_data.get('content', ''),
                message_type=message_data.get('content_type', 'text')
            )
            
            # 获取群组成员列表（用于转发）
            member_usernames = []
            for member_id in members:
                if member_id != sender_id:  # 不包括发送者自己
                    member_info = self.db.get_user_by_id(member_id)
                    if member_info:
                        member_usernames.append(member_info['username'])
            
            return json.dumps({
                'success': True,
                'message_id': message_id,
                'group_id': group_id,
                'type': 'group_message_response',
                'forward_to': member_usernames,
                'original_data': {
                    'sender': sender,
                    'group_id': group_id,
                    'data': message_data
                }
            })
            
        except Exception as e:
            logger.error(f"群聊消息处理异常: {e}")
            return json.dumps(await create_response(
                data, False, f"群聊消息处理异常: {str(e)}"
            ))
    
    async def _handle_stego_message(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理隐写消息"""
        try:
            recipient = data.get('recipient')
            message_data = data.get('data', {})
            sender = data.get('sender') or client_info.get('username')
            
            if not recipient or not message_data:
                return json.dumps(await create_response(
                    data, False, "隐写消息参数不完整"
                ))
            
            # 获取发送者和接收者信息
            sender_info = self.db.get_user_by_username(sender)
            recipient_info = self.db.get_user_by_username(recipient)
            
            if not sender_info or not recipient_info:
                return json.dumps(await create_response(
                    data, False, "发送者或接收者不存在"
                ))
            
            # 保存隐写消息
            message_id = self.db.save_message(
                sender_id=sender_info['user_id'],
                receiver_id=recipient_info['user_id'],
                message_content=message_data.get('content', ''),
                message_type='steganography'
            )
            
            return json.dumps({
                'success': True,
                'message_id': message_id,
                'type': 'stego_message_response',
                'forward_to': recipient,
                'original_data': {
                    'sender': sender,
                    'recipient': recipient,
                    'data': message_data
                }
            })
            
        except Exception as e:
            logger.error(f"隐写消息处理异常: {e}")
            return json.dumps(await create_response(
                data, False, f"隐写消息处理异常: {str(e)}"
            ))
    
    async def _handle_voice_message(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理语音消息（扩展）"""
        try:
            recipient = data.get('recipient')
            message_data = data.get('data', {})
            sender = data.get('sender') or client_info.get('username')
            
            if not recipient or not message_data:
                return json.dumps(await create_response(
                    data, False, "语音消息参数不完整"
                ))
            
            # 获取发送者和接收者信息
            sender_info = self.db.get_user_by_username(sender)
            recipient_info = self.db.get_user_by_username(recipient)
            
            if not sender_info or not recipient_info:
                return json.dumps(await create_response(
                    data, False, "发送者或接收者不存在"
                ))
            
            # 保存语音消息
            message_id = self.db.save_message(
                sender_id=sender_info['user_id'],
                receiver_id=recipient_info['user_id'],
                message_content=message_data.get('content', ''),
                message_type='voice'
            )
            
            return json.dumps({
                'success': True,
                'message_id': message_id,
                'type': 'voice_message_response',
                'forward_to': recipient,
                'original_data': {
                    'sender': sender,
                    'recipient': recipient,
                    'data': message_data
                }
            })
            
        except Exception as e:
            logger.error(f"语音消息处理异常: {e}")
            return json.dumps(await create_response(
                data, False, f"语音消息处理异常: {str(e)}"
            ))
    
    async def _handle_create_group(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理创建群组请求"""
        try:
            group_id = data.get('group_id')
            group_name = data.get('group_name', group_id)
            members = data.get('members', [])
            sender = data.get('sender') or client_info.get('username')
            
            if not group_id:
                return json.dumps(await create_response(
                    data, False, "群组ID不能为空"
                ))
            
            # 获取发送者信息
            sender_info = self.db.get_user_by_username(sender)
            if not sender_info:
                return json.dumps(await create_response(
                    data, False, "发送者不存在"
                ))
            
            sender_id = sender_info['user_id']
            
            # 创建群组
            result = self.group_mgr.create_group(group_id, group_name, sender_id, members)
            
            if result.get('success'):
                return json.dumps({
                    'success': True,
                    'group_id': group_id,
                    'group_name': group_name,
                    'message': result.get('message', '群组创建成功'),
                    'type': 'create_group_response'
                })
            else:
                return json.dumps(await create_response(
                    data, False, result.get('error', '群组创建失败')
                ))
            
        except Exception as e:
            logger.error(f"创建群组异常: {e}")
            return json.dumps(await create_response(
                data, False, f"创建群组异常: {str(e)}"
            ))
    
    async def _handle_join_group(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理加入群组请求"""
        try:
            group_id = data.get('group_id')
            sender = data.get('sender') or client_info.get('username')
            
            if not group_id:
                return json.dumps(await create_response(
                    data, False, "群组ID不能为空"
                ))
            
            if not sender:
                return json.dumps(await create_response(
                    data, False, "发送者不能为空"
                ))
            
            # 获取发送者信息
            sender_info = self.db.get_user_by_username(sender)
            if not sender_info:
                return json.dumps(await create_response(
                    data, False, "发送者不存在"
                ))
            
            sender_id = sender_info['user_id']
            
            # 检查群组是否存在
            group_info = self.db.get_group_info(group_id)
            if not group_info:
                return json.dumps(await create_response(
                    data, False, "群组不存在"
                ))
            
            # 检查用户是否已经是群组成员
            if self.db.is_group_member(group_id, sender_id):
                return json.dumps(await create_response(
                    data, False, "您已经是该群组的成员"
                ))
            
            # 加入群组
            result = self.db.add_group_member(group_id, sender_id)
            
            if result:
                return json.dumps({
                    'success': True,
                    'group_id': group_id,
                    'group_name': group_info['group_name'],
                    'message': f'成功加入群组 "{group_info["group_name"]}"',
                    'type': 'join_group_response'
                })
            else:
                return json.dumps(await create_response(
                    data, False, "加入群组失败"
                ))
            
        except Exception as e:
            logger.error(f"加入群组异常: {e}")
            return json.dumps(await create_response(
                data, False, f"加入群组异常: {str(e)}"
            ))
    
    async def _handle_heartbeat(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理心跳检测"""
        try:
            sender = data.get('sender') or client_info.get('username')
            
            # 更新用户活动时间
            if sender:
                user_info = self.db.get_user_by_username(sender)
                if user_info:
                    self.db.update_user_last_activity(user_info['user_id'])
            
            return json.dumps({
                'success': True,
                'message': '心跳正常',
                'timestamp': datetime.now().isoformat(),
                'type': 'heartbeat_response'
            })
            
        except Exception as e:
            logger.error(f"心跳处理异常: {e}")
            return json.dumps(await create_response(
                data, False, f"心跳处理异常: {str(e)}"
            ))
    
    async def _handle_performance_test(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理性能测试"""
        try:
            content = data.get('content', '')
            message_id = data.get('message_id', 0)
            
            return json.dumps({
                'success': True,
                'message': f'性能测试消息处理成功: {content}',
                'message_id': message_id,
                'processing_time': time.time(),
                'type': 'performance_test_response'
            })
            
        except Exception as e:
            logger.error(f"性能测试处理异常: {e}")
            return json.dumps(await create_response(
                data, False, f"性能测试处理异常: {str(e)}"
            ))
    
    async def _handle_add_contact(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理添加联系人请求"""
        try:
            contact_username = data.get('contact_username')
            alias = data.get('alias')
            group = data.get('group', '默认分组')
            sender = data.get('sender') or client_info.get('username')
            
            if not contact_username or not sender:
                return json.dumps(await create_response(
                    data, False, "联系人用户名和发送者不能为空"
                ))
            
            # 获取发送者信息
            sender_info = self.db.get_user_by_username(sender)
            if not sender_info:
                return json.dumps(await create_response(
                    data, False, "发送者不存在"
                ))
            
            # 添加联系人
            result = self.db.add_contact(
                user_id=sender_info['user_id'],
                contact_username=contact_username,
                alias=alias,
                group=group
            )
            
            if result:
                return json.dumps({
                    'success': True,
                    'message': '联系人添加成功',
                    'type': 'add_contact_response'
                })
            else:
                return json.dumps(await create_response(
                    data, False, "联系人添加失败，可能是用户名不存在"
                ))
            
        except Exception as e:
            logger.error(f"添加联系人异常: {e}")
            return json.dumps(await create_response(
                data, False, f"添加联系人异常: {str(e)}"
            ))
    
    async def _handle_get_contacts(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理获取联系人列表请求"""
        try:
            sender = data.get('sender') or client_info.get('username')
            
            if not sender:
                return json.dumps(await create_response(
                    data, False, "发送者不能为空"
                ))
            
            # 获取发送者信息
            sender_info = self.db.get_user_by_username(sender)
            if not sender_info:
                return json.dumps(await create_response(
                    data, False, "发送者不存在"
                ))
            
            # 获取联系人列表
            contacts_data = self.db.get_contacts(sender_info['user_id'])
            
            return json.dumps({
                'success': True,
                'message': '获取联系人列表成功',
                'contacts': contacts_data['contacts'],
                'total': contacts_data['total'],
                'type': 'get_contacts_response',
                'response_to': 'get_contacts'
            })
            
        except Exception as e:
            logger.error(f"获取联系人列表异常: {e}")
            return json.dumps(await create_response(
                data, False, f"获取联系人列表异常: {str(e)}"
            ))
    
    async def _handle_update_contact(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理更新联系人请求"""
        try:
            contact_user_id = data.get('contact_user_id')
            alias = data.get('alias')
            group = data.get('group')
            notes = data.get('notes')
            is_favorite = data.get('is_favorite')
            sender = data.get('sender') or client_info.get('username')
            
            if not contact_user_id or not sender:
                return json.dumps(await create_response(
                    data, False, "联系人ID和发送者不能为空"
                ))
            
            # 获取发送者信息
            sender_info = self.db.get_user_by_username(sender)
            if not sender_info:
                return json.dumps(await create_response(
                    data, False, "发送者不存在"
                ))
            
            # 更新联系人
            result = self.db.update_contact(
                user_id=sender_info['user_id'],
                contact_user_id=contact_user_id,
                alias=alias,
                group=group,
                notes=notes,
                is_favorite=is_favorite
            )
            
            if result:
                return json.dumps({
                    'success': True,
                    'message': '联系人更新成功',
                    'type': 'update_contact_response'
                })
            else:
                return json.dumps(await create_response(
                    data, False, "联系人更新失败"
                ))
            
        except Exception as e:
            logger.error(f"更新联系人异常: {e}")
            return json.dumps(await create_response(
                data, False, f"更新联系人异常: {str(e)}"
            ))
    
    async def _handle_remove_contact(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理删除联系人请求"""
        try:
            contact_user_id = data.get('contact_user_id')
            sender = data.get('sender') or client_info.get('username')
            
            if not contact_user_id or not sender:
                return json.dumps(await create_response(
                    data, False, "联系人ID和发送者不能为空"
                ))
            
            # 获取发送者信息
            sender_info = self.db.get_user_by_username(sender)
            if not sender_info:
                return json.dumps(await create_response(
                    data, False, "发送者不存在"
                ))
            
            # 删除联系人
            result = self.db.remove_contact(
                user_id=sender_info['user_id'],
                contact_user_id=contact_user_id
            )
            
            if result:
                return json.dumps({
                    'success': True,
                    'message': '联系人删除成功',
                    'type': 'remove_contact_response'
                })
            else:
                return json.dumps(await create_response(
                    data, False, "联系人删除失败"
                ))
            
        except Exception as e:
            logger.error(f"删除联系人异常: {e}")
            return json.dumps(await create_response(
                data, False, f"删除联系人异常: {str(e)}"
            ))

    async def _handle_get_groups(self, data: Dict[str, Any], client_info: Dict[str, Any]) -> str:
        """处理获取群组列表请求"""
        try:
            # 获取用户信息
            sender = data.get('sender')
            if not sender:
                return json.dumps(await create_response(
                    data, False, "缺少发送者信息"
                ))
            
            # 获取用户ID
            user_id = self.db.get_user_id_by_username(sender)
            if not user_id:
                return json.dumps(await create_response(
                    data, False, "用户不存在"
                ))
            
            # 获取用户参与的群组列表
            groups_list = self.db.get_user_groups(user_id)
            
            # 转换为前端期望的格式
            groups = {}
            for group in groups_list:
                groups[group['group_id']] = {
                    'group_id': group['group_id'],
                    'group_name': group['group_name'],
                    'creator_id': group['creator_id'],
                    'creator_name': group['creator_name'],
                    'created_at': group['created_at'],
                    'joined_at': group['joined_at']
                }
                
                # 获取群组成员数量
                group_info = self.db.get_group_info(group['group_id'])
                if group_info:
                    groups[group['group_id']]['member_count'] = group_info['member_count']
                else:
                    groups[group['group_id']]['member_count'] = 1
            
            # 返回成功响应
            return json.dumps({
                'success': True,
                'message': '获取群组列表成功',
                'groups': groups,
                'total': len(groups),
                'type': 'get_groups_response',
                'response_to': 'get_groups'
            })
            
        except Exception as e:
            logger.error(f"获取群组列表失败: {e}")
            return json.dumps(await create_response(
                data, False, f"获取群组列表失败: {str(e)}"
            ))

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        avg_processing_time = 0.0
        if self.stats['messages_processed'] > 0:
            avg_processing_time = self.stats['processing_time_total'] / self.stats['messages_processed']
        
        return {
            **self.stats,
            'avg_processing_time': avg_processing_time,
            'queue_size': self.message_queue.qsize() if hasattr(self, 'message_queue') else 0,
            'worker_count': len(self.worker_tasks)
        } 