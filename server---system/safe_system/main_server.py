#!/usr/bin/env python3
"""
安全即时通讯服务器 - 多进程版本

提供安全的即时通讯服务，支持多进程处理
"""

import asyncio
import websockets
import json
import logging
import signal
import sys
import argparse
from typing import Dict, Any, Set
from pathlib import Path
from datetime import datetime
# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent))

from config import Config
from server.multi_core import MultiProcessManager
from server.storage import DatabaseManager
from server.group import GroupManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SecureMultiProcessServer:
    """安全多进程服务器"""
    
    def __init__(self, config: Config):
        """
        初始化安全多进程服务器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.clients: Dict[websockets.WebSocketServerProtocol, Dict[str, Any]] = {}
        self.username_to_websocket: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.is_running = False
        self.start_time = None
        self.server = None
        
        # 初始化数据库管理器
        try:
            self.db = DatabaseManager()
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
        
        # 统计信息
        self.stats = {
            'current_connections': 0,
            'total_connections': 0,
            'messages_processed': 0,
            'errors_count': 0
        }
        
        # 初始化多进程管理器
        worker_count = config.get('WORKER_PROCESSES')
        try:
            self.multi_process_manager = MultiProcessManager(worker_count)
        except Exception as e:
            logger.error(f"多进程管理器初始化失败: {e}")
            raise
        
        logger.info(f"多进程服务器初始化完成，工作进程数: {worker_count}")
    
    async def start_server(self):
        """启动服务器"""
        try:
            logger.info("[启动] 正在启动安全多进程服务器...")
            
            # 启动多进程管理器
            self.multi_process_manager.start()
            logger.info("[启动] 多进程管理器已启动")
            
            # 设置信号处理器
            self._setup_signal_handlers()
            logger.info("[启动] 信号处理器已设置")
            
            # 启动WebSocket服务器
            self.server = await websockets.serve(
                self.handle_client,
                self.config.get('HOST', 'localhost'),
                self.config.get('PORT', 8765),
                max_size=4 * 1024 * 1024,
                ping_interval=30,
                ping_timeout=60,
                close_timeout=10
            )
            
            logger.info("[启动] WebSocket服务器已监听")
            self.is_running = True
            self.start_time = datetime.now()
            self.stats['start_time'] = self.start_time.isoformat()
            
            logger.info(f"[启动] 服务器启动成功，监听地址: {self.config.get('HOST', 'localhost')}:{self.config.get('PORT', 8765)}")
            logger.info(f"[启动] 工作进程数量: {self.multi_process_manager.num_workers}")
            
            # 启动统计任务
            asyncio.create_task(self._stats_printer())
            logger.info("[启动] 服务器已进入主循环，等待客户端连接...")
            
            # 等待服务器关闭
            await self.server.wait_closed()
            
        except Exception as e:
            logger.error(f"[启动] 服务器启动失败: {e}")
            await self.shutdown()
            raise
    
    async def handle_client(self, websocket):
        """
        处理客户端连接
        
        Args:
            websocket: WebSocket连接对象
        """
        client_info = {
            'ip': websocket.remote_address[0] if websocket.remote_address else 'unknown',
            'port': websocket.remote_address[1] if websocket.remote_address else 0,
            'connected_at': datetime.now().isoformat(),
            'username': None
        }
        
        # 注册客户端
        self.clients[websocket] = client_info
        self.stats['current_connections'] += 1
        self.stats['total_connections'] += 1
        
        logger.info(f"[连接] 新客户端连接: {client_info['ip']}:{client_info['port']}")
        
        try:
            # 发送欢迎消息
            welcome_message = self._create_system_message('system_notification', {
                'message': '欢迎连接到安全即时通讯服务器',
                'server_version': '1.0',
                'max_message_size': 4 * 1024 * 1024,
                'heartbeat_interval': 30
            })
            await websocket.send(welcome_message)
            
            # 处理客户端消息
            async for message in websocket:
                try:
                    await self.process_client_message(websocket, message, client_info)
                except Exception as e:
                    logger.error(f"[消息处理] 处理消息时出错: {e}")
                    # 发送错误响应但不断开连接
                    try:
                        error_response = self._create_error_response(f"消息处理失败: {str(e)}")
                        await websocket.send(error_response)
                    except:
                        pass  # 如果发送错误响应失败，则忽略
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"[连接] 客户端正常断开连接: {client_info['ip']}:{client_info['port']}")
        except websockets.exceptions.ConnectionClosedError:
            logger.info(f"[连接] 客户端连接异常关闭: {client_info['ip']}:{client_info['port']}")
        except Exception as e:
            logger.error(f"[连接] 客户端连接异常: {e}")
            self.stats['errors_count'] += 1
        finally:
            await self.cleanup_client(websocket, client_info)
    
    async def process_client_message(self, websocket, message: str, client_info: Dict[str, Any]):
        """
        处理客户端消息
        
        Args:
            websocket: WebSocket连接
            message: 消息内容
            client_info: 客户端信息
        """
        try:
            self.stats['messages_processed'] += 1
            
            # 使用多进程管理器处理消息
            result = await self.multi_process_manager.process_message_async(message, client_info)
            
            # 发送响应给客户端
            await websocket.send(result)
            
            # 解析结果进行后续处理
            try:
                result_data = json.loads(result)
                
                # 处理登录成功后的用户映射
                if result_data.get('success') and 'username' in client_info:
                    username = client_info['username']
                    self.username_to_websocket[username] = websocket
                    logger.info(f"用户 {username} WebSocket映射已更新")
                
                # 处理群聊消息转发
                if result_data.get('success') and result_data.get('group_id') and result_data.get('forward_to'):
                    await self._forward_group_message(result_data)
                
                # 处理私聊消息转发
                if result_data.get('success') and result_data.get('recipient_username'):
                    await self._forward_private_message(result_data)
                    
            except json.JSONDecodeError:
                logger.warning("无法解析服务器响应，跳过后续处理")
            
            # 更新用户信息
            try:
                parsed_message = json.loads(message)
                message_type = parsed_message.get('type')
                
                if message_type in ['login', 'register']:
                    if parsed_message.get('metadata') and 'username' in parsed_message['metadata']:
                        username = parsed_message['metadata']['username']
                        client_info['username'] = username
                        self.username_to_websocket[username] = websocket
                        logger.info(f"用户 {username} 已登录，IP: {client_info['ip']}")
                elif message_type == 'logout':
                    if client_info.get('username'):
                        self.cleanup_user(client_info['username'])
            except json.JSONDecodeError:
                logger.warning("无法解析客户端消息格式")
            except Exception as e:
                logger.error(f"更新用户信息时出错: {e}")
            
        except Exception as e:
            logger.error(f"处理客户端消息异常: {e}")
            self.stats['errors_count'] += 1
            # 不要重新抛出异常，以保持连接稳定
            error_response = self._create_error_response(f"服务器内部错误: {str(e)}")
            try:
                await websocket.send(error_response)
            except:
                pass  # 如果发送失败，忽略
    
    async def _forward_group_message(self, result_data: Dict[str, Any]):
        """转发群聊消息"""
        try:
            group_id = result_data['group_id']
            forward_to = result_data['forward_to']
            data = result_data.get('data', {})
            sender = result_data.get('sender', 'unknown')
            
            # 获取所有在线成员的websocket
            for uid in forward_to:
                try:
                    username = self.db.get_username_by_id(uid)
                    if not username or username == sender:  # 不转发给发送者自己
                        continue
                        
                    ws = self.username_to_websocket.get(username)
                    if ws and ws in self.clients:
                        await ws.send(json.dumps({
                            "type": "group_message",
                            "group_id": group_id,
                            "sender": sender,
                            "data": data,
                            "from_server": True,
                            "timestamp": datetime.now().isoformat()
                        }))
                        logger.debug(f"群聊消息已转发给 {username}")
                except Exception as e:
                    logger.warning(f"群聊消息转发给用户ID {uid} 失败: {e}")
        except Exception as e:
            logger.error(f"群聊消息转发失败: {e}")
    
    async def _forward_private_message(self, result_data: Dict[str, Any]):
        """转发私聊消息"""
        try:
            recipient = result_data['recipient_username']
            sender = result_data.get('sender', 'unknown')
            message_type = result_data.get('message_type', 'text_message')
            data = result_data.get('data', {})
            
            ws = self.username_to_websocket.get(recipient)
            if ws and ws in self.clients:
                await ws.send(json.dumps({
                    "type": message_type,
                    "sender": sender,
                    "data": data,
                    "from_server": True,
                    "timestamp": datetime.now().isoformat()
                }))
                logger.debug(f"私聊消息已转发给 {recipient}")
            else:
                logger.info(f"用户 {recipient} 不在线，消息已保存")
        except Exception as e:
            logger.error(f"私聊消息转发失败: {e}")
    
    async def forward_message_to_user(self, username: str, message: str):
        """
        转发消息给指定用户
        
        Args:
            username: 用户名
            message: 消息内容
        """
        try:
            target_websocket = self.username_to_websocket.get(username)
            if target_websocket and target_websocket in self.clients:
                await target_websocket.send(message)
                logger.debug(f"消息已转发给用户 {username}")
            else:
                logger.warning(f"用户 {username} 不在线，无法转发消息")
        except Exception as e:
            logger.error(f"转发消息给用户 {username} 失败: {e}")
    
    async def cleanup_client(self, websocket, client_info: Dict[str, Any]):
        """
        清理客户端连接
        
        Args:
            websocket: WebSocket连接
            client_info: 客户端信息
        """
        try:
            # 从连接列表移除
            if websocket in self.clients:
                del self.clients[websocket]
                self.stats['current_connections'] -= 1
            
            # 清理用户信息
            if client_info.get('username'):
                self.cleanup_user(client_info['username'])
            
            logger.info(f"客户端清理完成: {client_info['ip']}:{client_info['port']}")
            
        except Exception as e:
            logger.error(f"清理客户端连接失败: {e}")
    
    def cleanup_user(self, username: str):
        """
        清理用户信息
        
        Args:
            username: 用户名
        """
        try:
            # 从用户映射中移除
            if username in self.username_to_websocket:
                del self.username_to_websocket[username]
            
            logger.info(f"用户 {username} 已离线")
            
        except Exception as e:
            logger.error(f"清理用户 {username} 失败: {e}")
    
    def _create_system_message(self, message_type: str, data: Dict[str, Any]) -> str:
        """创建系统消息"""
        message = {
            'version': '1.0',
            'type': message_type,
            'timestamp': datetime.now().isoformat(),
            'sender': 'system',
            'recipient': '',
            'metadata': data
        }
        return json.dumps(message, ensure_ascii=False)
    
    def _create_error_response(self, error_message: str) -> str:
        """创建错误响应"""
        return json.dumps({
            'success': False,
            'message': error_message,
            'timestamp': datetime.now().isoformat()
        }, ensure_ascii=False)
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"收到信号 {signum}，准备关闭服务器...")
            if self.is_running:
                asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def _stats_printer(self):
        """定期打印统计信息"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # 每分钟打印一次
                
                if not self.is_running:
                    break
                
                uptime = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
                
                logger.info(f"服务器统计 - "
                          f"运行时间: {uptime:.0f}秒, "
                          f"当前连接: {self.stats['current_connections']}, "
                          f"总连接数: {self.stats['total_connections']}, "
                          f"处理消息: {self.stats['messages_processed']}, "
                          f"错误数: {self.stats['errors_count']}")
                
                # 多进程管理器统计
                try:
                    mp_stats = self.multi_process_manager.get_stats()
                    logger.info(f"多进程统计 - "
                              f"工作进程: {mp_stats['num_workers']}, "
                              f"管理器状态: {'运行中' if mp_stats['is_running'] else '已停止'}")
                except Exception as e:
                    logger.warning(f"获取多进程统计失败: {e}")
                
            except Exception as e:
                logger.error(f"统计信息打印失败: {e}")
    
    async def shutdown(self):
        """关闭服务器"""
        if not self.is_running:
            return
            
        logger.info("正在关闭服务器...")
        self.is_running = False
        
        # 关闭WebSocket服务器
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # 关闭所有客户端连接
        for websocket in list(self.clients.keys()):
            try:
                await websocket.close()
            except Exception as e:
                logger.error(f"关闭客户端连接失败: {e}")
        
        # 停止多进程管理器
        try:
            self.multi_process_manager.stop()
        except Exception as e:
            logger.error(f"停止多进程管理器失败: {e}")
        
        logger.info("服务器已关闭")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='安全即时通讯服务器 - 多进程版本')
    parser.add_argument('--host', default='localhost', help='服务器主机地址')
    parser.add_argument('--port', type=int, default=8765, help='服务器端口')
    parser.add_argument('--workers', type=int, help='工作进程数量')
    parser.add_argument('--config', default='config.py', help='配置文件路径')
    parser.add_argument('--debug', action='store_true', help='开启调试模式')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("调试模式已开启")
    
    try:
        # 加载配置
        config = Config()
        
        # 覆盖配置参数
        if args.host:
            config.set('HOST', args.host)
        if args.port:
            config.set('PORT', args.port)
        if args.workers:
            config.set('WORKER_PROCESSES', args.workers)
        
        logger.info(f"服务器配置: {config.get('HOST')}:{config.get('PORT')}")
        
        # 创建并启动服务器
        server = SecureMultiProcessServer(config)
        
        # 运行服务器
        asyncio.run(server.start_server())
        
    except KeyboardInterrupt:
        logger.info("收到键盘中断，服务器正在关闭...")
    except Exception as e:
        logger.error(f"服务器运行异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

# 为了向后兼容，保留全局对象
group_mgr = GroupManager()
db = DatabaseManager()

 