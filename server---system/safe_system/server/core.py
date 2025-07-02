import asyncio
import websockets
import json
import logging
import uuid
from typing import Dict, Any, Optional, Set
from datetime import datetime
import traceback

from .storage import DatabaseManager
from .auth import AuthenticationManager
from .directory import DirectoryManager

class SecureChatServer:
    """安全即时通讯服务器核心"""
    
    def __init__(self, host: str = 'localhost', port: int = 8765, 
                 max_connections: int = 100, db_path: str = "secure_chat.db"):
        self.host = host
        self.port = port
        self.max_connections = max_connections
        
        # 初始化组件
        self.db_manager = DatabaseManager(db_path)
        self.auth_manager = AuthenticationManager(self.db_manager)
        self.directory_manager = DirectoryManager(self.db_manager, self.auth_manager)
        
        # 连接管理
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.user_sessions: Dict[int, Set[str]] = {}  # 用户ID -> WebSocket连接ID集合
        self.connection_users: Dict[str, int] = {}  # WebSocket连接ID -> 用户ID
        
        # 服务器状态
        self.running = False
        self.server = None
        
        # 配置日志
        self._setup_logging()
    
    def _setup_logging(self):
        """配置日志系统"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('secure_chat_server.log'),
                logging.StreamHandler()
            ]
        )
    
    async def start_server(self):
        """启动服务器"""
        try:
            self.running = True
            
            # 启动WebSocket服务器
            self.server = await websockets.serve(
                self.handle_connection,
                self.host,
                self.port,
                max_size=1024*1024,  # 1MB消息限制
                timeout=60,  # 60秒超时
                ping_interval=30,  # 30秒ping间隔
                ping_timeout=10   # 10秒ping超时
            )
            
            logging.info(f"安全即时通讯服务器启动成功，监听 {self.host}:{self.port}")
            logging.info(f"最大连接数: {self.max_connections}")
            
            # 启动后台任务
            asyncio.create_task(self._cleanup_task())
            
            # 保持服务器运行
            await self.server.wait_closed()
            
        except Exception as e:
            logging.error(f"服务器启动失败: {e}")
            raise
    
    async def stop_server(self):
        """停止服务器"""
        try:
            self.running = False
            
            # 关闭所有连接
            if self.connections:
                await asyncio.gather(
                    *[conn.close() for conn in self.connections.values()],
                    return_exceptions=True
                )
            
            # 停止WebSocket服务器
            if self.server:
                self.server.close()
                await self.server.wait_closed()
            
            logging.info("服务器已停止")
            
        except Exception as e:
            logging.error(f"服务器停止异常: {e}")
    
    async def handle_connection(self, websocket, path):
        """处理WebSocket连接"""
        connection_id = str(uuid.uuid4())
        client_address = websocket.remote_address
        
        try:
            # 检查连接数限制
            if len(self.connections) >= self.max_connections:
                await websocket.send(json.dumps({
                    'type': 'error',
                    'message': '服务器连接数已满'
                }))
                await websocket.close()
                return
            
            # 添加连接
            self.connections[connection_id] = websocket
            logging.info(f"新连接建立: {connection_id} from {client_address}")
            
            # 发送连接确认
            await websocket.send(json.dumps({
                'type': 'connection_established',
                'connection_id': connection_id,
                'message': '连接建立成功'
            }))
            
            # 处理消息循环
            async for message in websocket:
                try:
                    await self.handle_message(connection_id, message)
                except json.JSONDecodeError as e:
                    await self.send_error(connection_id, '无效的JSON格式')
                except Exception as e:
                    logging.error(f"处理消息异常: {e}")
                    await self.send_error(connection_id, '服务器内部错误')
        
        except websockets.exceptions.ConnectionClosed:
            logging.info(f"连接断开: {connection_id}")
        except Exception as e:
            logging.error(f"连接处理异常: {e}")
        finally:
            await self.cleanup_connection(connection_id)
    
    async def handle_message(self, connection_id: str, message: str):
        """处理客户端消息"""
        try:
            # 解析JSON消息
            data = json.loads(message)
            
            # 验证消息格式
            if not isinstance(data, dict) or 'type' not in data:
                await self.send_error(connection_id, '消息格式错误')
                return
            
            message_type = data['type']
            
            # 更新用户活动时间
            user_id = self.connection_users.get(connection_id)
            if user_id:
                self.directory_manager.update_user_activity(user_id)
            
            # 路由消息到相应处理器
            if message_type == 'register':
                await self.handle_register(connection_id, data)
            elif message_type == 'login':
                await self.handle_login(connection_id, data)
            elif message_type == 'logout':
                await self.handle_logout(connection_id, data)
            elif message_type == 'get_online_friends':
                await self.handle_get_online_friends(connection_id, data)
            elif message_type == 'get_public_key':
                await self.handle_get_public_key(connection_id, data)
            elif message_type == 'send_message':
                await self.handle_send_message(connection_id, data)
            elif message_type == 'heartbeat':
                await self.handle_heartbeat(connection_id, data)
            else:
                await self.send_error(connection_id, f'未知的消息类型: {message_type}')
                
        except Exception as e:
            logging.error(f"消息处理异常: {e}")
            logging.error(traceback.format_exc())
            await self.send_error(connection_id, '消息处理失败')
    
    async def handle_register(self, connection_id: str, data: Dict[str, Any]):
        """处理用户注册"""
        try:
            required_fields = ['username', 'email', 'password', 'confirm_password']
            if not all(field in data for field in required_fields):
                await self.send_error(connection_id, '注册信息不完整')
                return
            
            result = await self.auth_manager.register_user(
                username=data['username'],
                email=data['email'],
                password=data['password'],
                confirm_password=data['confirm_password']
            )
            
            await self.send_message(connection_id, {
                'type': 'register_response',
                'success': result['success'],
                'message': result.get('message', result.get('error')),
                'user_id': result.get('user_id')
            })
            
        except Exception as e:
            logging.error(f"注册处理异常: {e}")
            await self.send_error(connection_id, '注册处理失败')
    
    async def handle_login(self, connection_id: str, data: Dict[str, Any]):
        """处理用户登录"""
        try:
            if 'username' not in data or 'password' not in data:
                await self.send_error(connection_id, '用户名或密码缺失')
                return
            
            # 获取客户端IP和端口（用于P2P连接）
            client_ip = data.get('client_ip', 'unknown')
            client_port = data.get('client_port', 0)
            
            # 认证用户
            auth_result = await self.auth_manager.authenticate_user(
                username=data['username'],
                password=data['password']
            )
            
            if auth_result['success']:
                user_id = auth_result['user_id']
                username = auth_result['username']
                
                # 建立用户会话映射
                if user_id not in self.user_sessions:
                    self.user_sessions[user_id] = set()
                self.user_sessions[user_id].add(connection_id)
                self.connection_users[connection_id] = user_id
                
                # 设置用户在线状态
                online_result = await self.directory_manager.set_online(
                    user_id=user_id,
                    username=username,
                    ip_address=client_ip,
                    port=client_port,
                    websocket_id=connection_id
                )
                
                # 发送登录成功响应
                await self.send_message(connection_id, {
                    'type': 'login_response',
                    'success': True,
                    'message': '登录成功',
                    'user_id': user_id,
                    'username': username,
                    'session_token': auth_result['session_token'],
                    'public_key': auth_result['public_key'],
                    'online_friends': online_result.get('online_friends', [])
                })
                
                logging.info(f"用户 {username} 登录成功")
            else:
                await self.send_message(connection_id, {
                    'type': 'login_response',
                    'success': False,
                    'message': auth_result['error']
                })
                
        except Exception as e:
            logging.error(f"登录处理异常: {e}")
            await self.send_error(connection_id, '登录处理失败')
    
    async def handle_logout(self, connection_id: str, data: Dict[str, Any]):
        """处理用户登出"""
        try:
            user_id = self.connection_users.get(connection_id)
            if not user_id:
                await self.send_error(connection_id, '用户未登录')
                return
            
            # 登出用户
            session_token = data.get('session_token')
            if session_token:
                logout_result = await self.auth_manager.logout_user(session_token)
            
            # 设置用户离线状态
            await self.directory_manager.set_offline(user_id, connection_id)
            
            # 清理会话映射
            self._remove_user_connection(user_id, connection_id)
            
            await self.send_message(connection_id, {
                'type': 'logout_response',
                'success': True,
                'message': '登出成功'
            })
            
        except Exception as e:
            logging.error(f"登出处理异常: {e}")
            await self.send_error(connection_id, '登出处理失败')
    
    async def handle_get_online_friends(self, connection_id: str, data: Dict[str, Any]):
        """处理获取在线好友列表请求"""
        try:
            user_id = self.connection_users.get(connection_id)
            if not user_id:
                await self.send_error(connection_id, '用户未登录')
                return
            
            online_friends = await self.directory_manager.get_online_friends_list(user_id)
            
            await self.send_message(connection_id, {
                'type': 'online_friends_response',
                'success': True,
                'friends': online_friends
            })
            
        except Exception as e:
            logging.error(f"获取在线好友异常: {e}")
            await self.send_error(connection_id, '获取在线好友失败')
    
    async def handle_get_public_key(self, connection_id: str, data: Dict[str, Any]):
        """处理获取公钥请求"""
        try:
            if 'username' not in data:
                await self.send_error(connection_id, '用户名缺失')
                return
            
            public_key = await self.directory_manager.get_friend_public_key(data['username'])
            
            if public_key:
                await self.send_message(connection_id, {
                    'type': 'public_key_response',
                    'success': True,
                    'username': data['username'],
                    'public_key': public_key
                })
            else:
                await self.send_message(connection_id, {
                    'type': 'public_key_response',
                    'success': False,
                    'message': '未找到用户公钥'
                })
                
        except Exception as e:
            logging.error(f"获取公钥异常: {e}")
            await self.send_error(connection_id, '获取公钥失败')
    
    async def handle_send_message(self, connection_id: str, data: Dict[str, Any]):
        """处理发送消息请求"""
        try:
            user_id = self.connection_users.get(connection_id)
            if not user_id:
                await self.send_error(connection_id, '用户未登录')
                return
            
            required_fields = ['recipient', 'message', 'message_type']
            if not all(field in data for field in required_fields):
                await self.send_error(connection_id, '消息信息不完整')
                return
            
            # 获取接收者信息
            recipient_user = self.db_manager.get_user_by_username(data['recipient'])
            if not recipient_user:
                await self.send_error(connection_id, '接收者不存在')
                return
            
            recipient_id = recipient_user['user_id']
            
            # 保存消息到数据库
            message_id = self.db_manager.save_message(
                sender_id=user_id,
                receiver_id=recipient_id,
                message_content=data['message'],
                message_type=data['message_type'],
                is_encrypted=data.get('is_encrypted', True)
            )
            
            if message_id:
                # 转发消息给在线的接收者
                if recipient_id in self.user_sessions:
                    forward_message = {
                        'type': 'new_message',
                        'message_id': message_id,
                        'sender': self.db_manager.get_user_by_username(
                            next(user['username'] for user in [self.db_manager.get_user_by_username('username')] 
                                 if user and user['user_id'] == user_id)
                        )['username'],
                        'message': data['message'],
                        'message_type': data['message_type'],
                        'is_encrypted': data.get('is_encrypted', True),
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # 发送给接收者的所有连接
                    for recipient_conn_id in self.user_sessions[recipient_id]:
                        await self.send_message(recipient_conn_id, forward_message)
                
                # 发送确认给发送者
                await self.send_message(connection_id, {
                    'type': 'send_message_response',
                    'success': True,
                    'message_id': message_id,
                    'message': '消息发送成功'
                })
            else:
                await self.send_error(connection_id, '消息发送失败')
                
        except Exception as e:
            logging.error(f"发送消息异常: {e}")
            await self.send_error(connection_id, '消息发送失败')
    
    async def handle_heartbeat(self, connection_id: str, data: Dict[str, Any]):
        """处理心跳消息"""
        try:
            await self.send_message(connection_id, {
                'type': 'heartbeat_response',
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logging.error(f"心跳处理异常: {e}")
    
    async def send_message(self, connection_id: str, message: Dict[str, Any]):
        """发送消息到指定连接"""
        try:
            if connection_id in self.connections:
                websocket = self.connections[connection_id]
                await websocket.send(json.dumps(message))
        except Exception as e:
            logging.error(f"发送消息失败: {e}")
            await self.cleanup_connection(connection_id)
    
    async def send_error(self, connection_id: str, error_message: str):
        """发送错误消息"""
        await self.send_message(connection_id, {
            'type': 'error',
            'message': error_message,
            'timestamp': datetime.now().isoformat()
        })
    
    async def cleanup_connection(self, connection_id: str):
        """清理连接"""
        try:
            # 移除连接
            if connection_id in self.connections:
                del self.connections[connection_id]
            
            # 清理用户会话映射
            user_id = self.connection_users.get(connection_id)
            if user_id:
                self._remove_user_connection(user_id, connection_id)
                
                # 如果用户没有其他连接，设置为离线
                if user_id not in self.user_sessions or not self.user_sessions[user_id]:
                    await self.directory_manager.set_offline(user_id, connection_id)
            
            logging.info(f"连接清理完成: {connection_id}")
            
        except Exception as e:
            logging.error(f"连接清理异常: {e}")
    
    def _remove_user_connection(self, user_id: int, connection_id: str):
        """移除用户连接映射"""
        if user_id in self.user_sessions:
            self.user_sessions[user_id].discard(connection_id)
            if not self.user_sessions[user_id]:
                del self.user_sessions[user_id]
        
        if connection_id in self.connection_users:
            del self.connection_users[connection_id]
    
    async def _cleanup_task(self):
        """后台清理任务"""
        while self.running:
            try:
                # 清理非活跃用户
                cleaned_count = await self.directory_manager.cleanup_inactive_users(30)
                if cleaned_count > 0:
                    logging.info(f"清理了 {cleaned_count} 个非活跃用户")
                
                # 每5分钟执行一次清理
                await asyncio.sleep(300)
                
            except Exception as e:
                logging.error(f"后台清理任务异常: {e}")
                await asyncio.sleep(60)  # 出错时等待1分钟再重试
    
    def get_server_stats(self) -> Dict[str, Any]:
        """获取服务器统计信息"""
        return {
            'active_connections': len(self.connections),
            'online_users': len(self.user_sessions),
            'max_connections': self.max_connections,
            'server_running': self.running,
            'server_address': f"{self.host}:{self.port}"
        } 