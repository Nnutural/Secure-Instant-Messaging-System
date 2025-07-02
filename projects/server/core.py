"""
服务端核心模块

提供WebSocket服务器和消息处理功能
"""

import asyncio
import websockets
import json
import logging
import uuid
from typing import Dict, Set, Optional, Any
from datetime import datetime
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from common.config import SERVER_HOST, SERVER_PORT
from common.database import DatabaseManager
from server import auth, directory, history
from server.shema import *

logger = logging.getLogger(__name__)

# 全局状态管理
class ServerState:
    def __init__(self):
        self.connections: Dict[str, WebSocketServerProtocol] = {}  # session_id -> websocket
        self.user_sessions: Dict[str, str] = {}  # username -> session_id
        self.online_users: Set[str] = set()
        self.db = DatabaseManager()

server_state = ServerState()

class MessageHandler:
    """消息处理器"""
    
    def __init__(self, websocket: WebSocketServerProtocol, session_id: str):
        self.websocket = websocket
        self.session_id = session_id
        self.username: Optional[str] = None
        self.db = server_state.db
    
    async def handle_message(self, message: dict):
        """处理客户端消息"""
        try:
            msg_type = message.get('tag')
            
            if msg_type == MsgTag.Login.value:
                await self.handle_login(LoginMsg(**message))
            elif msg_type == MsgTag.Register.value:
                await self.handle_register(RegisterMsg(**message))
            elif msg_type == MsgTag.GetDirectory.value:
                await self.handle_fetch_online_list()
            elif msg_type == MsgTag.Message.value:
                await self.handle_send_message(MessageMsg(**message))
            elif msg_type == MsgTag.GetHistory.value:
                await self.handle_fetch_history(GetHistoryMsg(**message))
            elif msg_type == MsgTag.Logout.value:
                await self.handle_logout()
            else:
                await self.send_error(f"未知消息类型: {msg_type}")
                
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            await self.send_error(f"消息处理错误: {str(e)}")
    
    async def handle_login(self, msg: LoginMsg):
        """处理登录"""
        try:
            # 验证用户凭据
            if not auth.verify_password(msg.username, msg.secret):
                await self.send_response(FailLoginMsg(
                    error_type="用户名或密码错误"
                ))
                return
            
            # 获取用户信息
            user = self.db.get_user_by_username(msg.username)
            if not user:
                await self.send_response(FailLoginMsg(
                    error_type="用户不存在"
                ))
                return
            
            # 更新用户状态
            self.username = msg.username
            server_state.user_sessions[msg.username] = self.session_id
            server_state.online_users.add(msg.username)
            
            # 更新数据库状态
            client_info = getattr(self.websocket, 'remote_address', None)
            ip = client_info[0] if client_info else '127.0.0.1'
            self.db.update_user_login_status(user['user_id'], True, ip, 0)
            
            # 创建会话
            self.db.create_session(self.session_id, user['user_id'], str(id(self.websocket)))
            
            await self.send_response(SuccessLoginMsg(
                username=msg.username,
                user_id=user['user_id']
            ))
            
            # 广播用户上线
            await self.broadcast_user_status_change()
            
            logger.info(f"用户 {msg.username} 登录成功")
            
        except Exception as e:
            logger.error(f"登录处理失败: {e}")
            await self.send_error("登录失败")
    
    async def handle_register(self, msg: RegisterMsg):
        """处理注册"""
        try:
            # 注册用户
            success = auth.register_user(
                username=msg.username,
                password=msg.secret,
                email=msg.email,
                pubkey_pem=""
            )
            
            if success:
                # 获取新用户信息
                user = self.db.get_user_by_username(msg.username)
                await self.send_response(SuccessRegisterMsg(
                    username=msg.username,
                    user_id=user['user_id'] if user else 0
                ))
                logger.info(f"用户 {msg.username} 注册成功")
            else:
                await self.send_response(FailRegisterMsg(
                    error_type="注册失败"
                ))
                
        except ValueError as e:
            await self.send_response(FailRegisterMsg(
                error_type=str(e)
            ))
        except Exception as e:
            logger.error(f"注册处理失败: {e}")
            await self.send_error("注册失败")
    
    async def handle_fetch_online_list(self):
        """处理获取在线用户列表"""
        try:
            if not self.username:
                await self.send_error("未登录")
                return
            
            # 获取用户信息
            user = self.db.get_user_by_username(self.username)
            if not user:
                await self.send_error("用户不存在")
                return
            
            # 获取在线好友
            online_friends = self.db.get_online_friends(user['user_id'])
            
            # 转换为JSON格式
            friends_data = []
            for friend in online_friends:
                friends_data.append({
                    "username": friend['username'],
                    "ip": friend['ip_address'] or '127.0.0.1',
                    "port": friend['port'] or 0
                })
            
            await self.send_response(DirectoryMsg(
                data=json.dumps(friends_data)
            ))
            
        except Exception as e:
            logger.error(f"获取在线列表失败: {e}")
            await self.send_error("获取在线列表失败")
    
    async def handle_send_message(self, msg: MessageMsg):
        """处理发送消息"""
        try:
            if not self.username:
                await self.send_error("未登录")
                return
            
            user = self.db.get_user_by_username(self.username)
            if not user:
                await self.send_error("用户不存在")
                return
            
            # 获取接收者信息
            receiver_user = self.db.get_user_by_username(str(msg.dest_id))
            if not receiver_user:
                await self.send_error("接收者不存在")
                return
                
            # 保存消息到数据库
            message_id = self.db.save_message(
                sender_id=user['user_id'],
                receiver_id=receiver_user['user_id'],
                message_content=msg.content,
                message_type='text'
            )
            
            # 使用历史记录模块保存
            history.append_chatlog(
                sender=self.username,
                receiver=str(msg.dest_id),
                payload_bytes=msg.content.encode('utf-8')
            )
            
            logger.info(f"消息已发送: {self.username} -> {msg.dest_id}")
            
            # 尝试转发给在线的接收者
            await self.forward_message_to_user(str(msg.dest_id), {
                'tag': MsgTag.Message.value,
                'message_id': msg.message_id,
                'source_id': msg.source_id,
                'dest_id': msg.dest_id,
                'content': msg.content,
                'time': msg.time
            })
            
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            await self.send_error("发送消息失败")
    
    async def handle_fetch_history(self, msg: GetHistoryMsg):
        """处理获取聊天历史"""
        try:
            if not self.username:
                await self.send_error("未登录")
                return
            
            # 使用历史记录模块获取聊天记录
            chat_logs = history.read_chatlog(
                user1=self.username,
                user2=str(msg.chat_id),
                limit=50
            )
            
            # 转换为响应格式
            messages_data = []
            for timestamp_iso, sender, receiver, payload_bytes in chat_logs:
                try:
                    content = payload_bytes.decode('utf-8')
                    messages_data.append({
                        "timestamp": timestamp_iso,
                        "sender": sender,
                        "receiver": receiver,
                        "content": content
                    })
                except UnicodeDecodeError:
                    # 跳过无法解码的消息
                    continue
            
            await self.send_response(HistoryMsg(
                data=json.dumps(messages_data)
            ))
            
        except Exception as e:
            logger.error(f"获取聊天历史失败: {e}")
            await self.send_error("获取聊天历史失败")
    
    async def handle_add_contact(self, user1: str, user2: str):
        """处理添加联系人"""
        try:
            # 使用directory模块添加好友
            success = directory.add_friend(user1, user2)
            
            if success:
                await self.send_error(f"添加联系人成功: {user1} <-> {user2}")
            else:
                await self.send_error("添加联系人失败：已经是好友或被拉黑")
            
        except Exception as e:
            logger.error(f"添加联系人失败: {e}")
            await self.send_error("添加联系人失败")
    
    async def handle_logout(self):
        """处理登出"""
        try:
            if self.username:
                # 更新用户状态
                user = self.db.get_user_by_username(self.username)
                if user:
                    self.db.update_user_login_status(user['user_id'], False)
                
                # 关闭会话
                self.db.close_session(self.session_id)
                
                # 从在线列表移除
                server_state.online_users.discard(self.username)
                if self.username in server_state.user_sessions:
                    del server_state.user_sessions[self.username]
                
                # 广播用户下线
                await self.broadcast_user_status_change()
                
                logger.info(f"用户 {self.username} 登出")
                self.username = None
            
        except Exception as e:
            logger.error(f"登出处理失败: {e}")
    
    async def forward_message_to_user(self, target_username: str, message: dict):
        """转发消息给目标用户"""
        try:
            if target_username in server_state.user_sessions:
                session_id = server_state.user_sessions[target_username]
                if session_id in server_state.connections:
                    websocket = server_state.connections[session_id]
                    await websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"转发消息失败: {e}")
    
    async def broadcast_user_status_change(self):
        """广播用户状态变化"""
        try:
            # 这里可以实现更复杂的广播逻辑
            pass
        except Exception as e:
            logger.error(f"广播状态变化失败: {e}")
    
    async def send_response(self, response):
        """发送响应"""
        try:
            if hasattr(response, 'dict'):
                data = response.dict()
            else:
                data = response.__dict__
            await self.websocket.send(json.dumps(data))
        except Exception as e:
            logger.error(f"发送响应失败: {e}")
    
    async def send_error(self, error_msg: str):
        """发送错误消息"""
        try:
            error_response = {
                'tag': MsgTag.Error.value,
                'msg': error_msg,
                'timestamp': datetime.now().isoformat()
            }
            await self.websocket.send(json.dumps(error_response))
        except Exception as e:
            logger.error(f"发送错误消息失败: {e}")

async def handle_client(websocket: WebSocketServerProtocol, path: str):
    """处理客户端连接"""
    session_id = str(uuid.uuid4())
    server_state.connections[session_id] = websocket
    
    handler = MessageHandler(websocket, session_id)
    
    logger.info(f"新客户端连接: {session_id}")
    
    try:
        async for raw_message in websocket:
            try:
                message = json.loads(raw_message)
                await handler.handle_message(message)
            except json.JSONDecodeError:
                await handler.send_error("无效的JSON格式")
            except Exception as e:
                logger.error(f"处理消息失败: {e}")
                await handler.send_error("消息处理失败")
                
    except ConnectionClosed:
        logger.info(f"客户端连接关闭: {session_id}")
    except Exception as e:
        logger.error(f"连接处理失败: {e}")
    finally:
        # 清理连接
        if session_id in server_state.connections:
            del server_state.connections[session_id]
        
        # 处理登出
        await handler.handle_logout()

async def run_server(host: str = "0.0.0.0", port: int = 8765):
    """启动服务器"""
    logger.info(f"启动服务器: {host}:{port}")
    
    # 初始化数据库
    server_state.db.init_database()
    
    # 启动WebSocket服务器
    async with websockets.serve(handle_client, host, port):
        logger.info(f"WebSocket服务器已启动，监听 {host}:{port}")
        await asyncio.Future()  # 保持服务器运行

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server()) 