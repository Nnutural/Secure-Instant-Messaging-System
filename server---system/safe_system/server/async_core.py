"""
异步服务器核心

整合异步消息处理器、连接管理器和协议处理器的主服务器
"""

import asyncio
import websockets
import json
import logging
import signal
import uuid
import sys
from typing import Dict, Any, Optional, Set, List
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent))

from config import Config
from .connection_manager import AsyncConnectionManager
from .async_message_processor import AsyncMessageProcessor
from common.async_protocol import AsyncProtocolProcessor

logger = logging.getLogger(__name__)

class AsyncSecureServer:
    """异步安全即时通讯服务器"""
    
    def __init__(self, config: Config):
        """
        初始化异步安全服务器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.server = None
        self.is_running = False
        self.start_time = None
        
        # 初始化核心组件
        self.connection_manager = AsyncConnectionManager(
            max_connections=config.get('MAX_CONNECTIONS', 10000),
            cleanup_interval=config.get('CLEANUP_INTERVAL', 60)
        )
        
        self.message_processor = AsyncMessageProcessor(
            db_path=config.get('DATABASE_PATH', 'secure_chat.db')
        )
        
        self.protocol_processor = AsyncProtocolProcessor(
            enable_compression=config.get('ENABLE_COMPRESSION', True),
            enable_encryption=config.get('ENABLE_ENCRYPTION', False),
            max_message_size=config.get('MAX_MESSAGE_SIZE', 4 * 1024 * 1024)
        )
        
        # 统计信息
        self.stats = {
            'start_time': None,
            'total_connections': 0,
            'current_connections': 0,
            'messages_processed': 0,
            'bytes_transferred': 0,
            'errors': 0,
            'uptime_seconds': 0
        }
        
        # 设置消息处理器
        self._setup_message_handlers()
        
        # 设置事件处理器
        self._setup_event_handlers()
        
        # 设置信号处理器
        self._setup_signal_handlers()
    
    def _setup_message_handlers(self):
        """设置消息处理器"""
        # 注册消息处理器
        self.connection_manager.register_message_handler(
            'default', self._handle_client_message
        )
    
    def _setup_event_handlers(self):
        """设置事件处理器"""
        # 注册连接事件处理器
        self.connection_manager.register_event_handler(
            'connection_established', self._on_connection_established
        )
        
        self.connection_manager.register_event_handler(
            'connection_closed', self._on_connection_closed
        )
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"接收到信号 {signum}，正在关闭服务器...")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def start(self):
        """启动服务器"""
        try:
            logger.info("🚀 正在启动异步安全即时通讯服务器...")
            
            # 启动核心组件
            await self.connection_manager.start()
            await self.message_processor.start()
            
            # 启动WebSocket服务器
            host = self.config.get('HOST', 'localhost')
            port = self.config.get('PORT', 8765)
            
            # 为新版本websockets库创建兼容的处理器
            async def websocket_handler(websocket):
                # 在新版本websockets中，path信息可以从request_uri获取或使用默认值
                path = getattr(websocket, 'path', '/')
                await self.handle_client_connection(websocket, path)
            
            self.server = await websockets.serve(
                websocket_handler,
                host,
                port,
                max_size=self.config.get('MAX_MESSAGE_SIZE', 4 * 1024 * 1024),
                ping_interval=self.config.get('PING_INTERVAL', 30),
                ping_timeout=self.config.get('PING_TIMEOUT', 60),
                close_timeout=self.config.get('CLOSE_TIMEOUT', 10)
            )
            
            self.is_running = True
            self.start_time = datetime.now()
            self.stats['start_time'] = self.start_time.isoformat()
            
            logger.info(f"✅ 服务器启动成功!")
            logger.info(f"📡 监听地址: {host}:{port}")
            logger.info(f"🔗 最大连接数: {self.config.get('MAX_CONNECTIONS', 10000)}")
            logger.info(f"💾 数据库路径: {self.config.get('DATABASE_PATH', 'secure_chat.db')}")
            logger.info(f"🔄 工作协程数: {self.message_processor.num_workers}")
            
            # 启动统计任务
            asyncio.create_task(self._stats_reporter())
            
            # 等待服务器关闭
            await self.server.wait_closed()
            
        except Exception as e:
            logger.error(f"❌ 服务器启动失败: {e}")
            await self.shutdown()
            raise
    
    async def shutdown(self):
        """关闭服务器"""
        try:
            logger.info("🛑 正在关闭服务器...")
            
            self.is_running = False
            
            # 关闭WebSocket服务器
            if self.server:
                self.server.close()
                await self.server.wait_closed()
            
            # 停止核心组件
            await self.connection_manager.stop()
            await self.message_processor.stop()
            
            logger.info("✅ 服务器已安全关闭")
            
        except Exception as e:
            logger.error(f"❌ 服务器关闭异常: {e}")
    
    async def handle_client_connection(self, websocket, path):
        """处理客户端连接"""
        connection_id = str(uuid.uuid4())
        client_address = websocket.remote_address
        
        logger.info(f"🔗 新客户端连接: {connection_id} from {client_address}")
        
        try:
            # 添加连接到管理器
            if not await self.connection_manager.add_connection(connection_id, websocket):
                await websocket.send(json.dumps({
                    'type': 'error',
                    'message': '服务器连接数已满或连接被拒绝'
                }))
                await websocket.close()
                return
            
            # 发送简化的欢迎消息
            welcome_message = {
                'type': 'system_notification',
                'message': '欢迎连接到安全即时通讯服务器',
                'server_version': '2.0',
                'connection_id': connection_id,
                'timestamp': datetime.now().isoformat()
            }
            
            await websocket.send(json.dumps(welcome_message))
            
            # 处理消息循环
            async for message in websocket:
                try:
                    # 将消息添加到处理队列
                    await self.connection_manager.message_queue.put({
                        'connection_id': connection_id,
                        'message': message,
                        'timestamp': datetime.now().timestamp()
                    })
                    
                except Exception as e:
                    logger.error(f"处理消息异常: {e}")
                    self.stats['errors'] += 1
                    
                    # 发送错误响应
                    try:
                        error_response = {
                            'type': 'error',
                            'message': f'消息处理失败: {str(e)}',
                            'timestamp': datetime.now().isoformat()
                        }
                        await websocket.send(json.dumps(error_response))
                    except:
                        pass  # 忽略发送错误响应的失败
        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🔌 客户端正常断开连接: {connection_id}")
        except websockets.exceptions.ConnectionClosedError:
            logger.info(f"🔌 客户端连接异常关闭: {connection_id}")
        except Exception as e:
            logger.error(f"❌ 连接处理异常: {e}")
            self.stats['errors'] += 1
        finally:
            # 清理连接
            await self.connection_manager.remove_connection(connection_id)
    
    async def _handle_client_message(self, connection_id: str, message_data: Dict[str, Any]):
        """处理客户端消息"""
        try:
            # 获取连接信息
            conn_info = self.connection_manager.connections.get(connection_id)
            if not conn_info:
                logger.warning(f"连接不存在: {connection_id}")
                return
            
            # 构建客户端信息
            client_info = {
                'connection_id': connection_id,
                'ip': conn_info.ip_address,
                'port': conn_info.port,
                'username': conn_info.username,
                'user_id': conn_info.user_id,
                'is_authenticated': conn_info.is_authenticated
            }
            
            # 处理消息
            message_str = json.dumps(message_data)
            result = await self.message_processor.process_message_async(message_str, client_info)
            
            # 解析结果
            result_data = json.loads(result)
            
            # 发送响应
            await conn_info.websocket.send(result)
            
            # 处理特殊响应（如转发、认证等）
            await self._handle_special_responses(result_data, client_info)
            
            # 更新统计
            self.stats['messages_processed'] += 1
            conn_info.update_activity()
            
        except Exception as e:
            logger.error(f"处理客户端消息异常: {e}")
            self.stats['errors'] += 1
    
    async def _handle_special_responses(self, result_data: Dict[str, Any], client_info: Dict[str, Any]):
        """处理特殊响应"""
        try:
            # 处理登录成功
            if result_data.get('type') == 'login_response' and result_data.get('success'):
                user_id = result_data.get('user_id')
                username = result_data.get('username')
                connection_id = client_info['connection_id']
                
                if user_id and username:
                    # 更新连接信息
                    conn_info = self.connection_manager.connections.get(connection_id)
                    if conn_info:
                        conn_info.user_id = user_id
                        conn_info.username = username
                        conn_info.is_authenticated = True
                        
                        # 添加到用户映射
                        self.connection_manager.user_connections[user_id].add(connection_id)
                        self.connection_manager.username_connections[username].add(connection_id)
            
            # 处理消息转发
            forward_to = result_data.get('forward_to')
            if forward_to:
                await self._forward_message(result_data, forward_to)
            
        except Exception as e:
            logger.error(f"处理特殊响应异常: {e}")
    
    async def _forward_message(self, message_data: Dict[str, Any], recipients):
        """转发消息"""
        try:
            # 获取消息类型并转换为web界面期望的格式
            msg_type = message_data.get('type', 'forwarded_message').replace('_response', '')
            
            # 构建转发消息，使其与web界面兼容
            forward_message = {
                'type': msg_type,
                'from_server': True,  # 标记为服务器转发的消息
                'timestamp': datetime.now().isoformat()
            }
            
            # 根据消息类型设置特定字段
            if msg_type in ['text_message', 'stego_message', 'voice_message']:
                # 从原始数据中提取发送者和数据
                original_data = message_data.get('original_data', {})
                forward_message.update({
                    'sender': original_data.get('sender', 'unknown'),
                    'data': original_data.get('data', {}),
                    'recipient': original_data.get('recipient', '')
                })
            elif msg_type == 'group_message':
                # 群聊消息格式
                original_data = message_data.get('original_data', {})
                forward_message.update({
                    'sender': original_data.get('sender', 'unknown'),
                    'data': original_data.get('data', {}),
                    'group_id': original_data.get('group_id', '')
                })
            else:
                # 其他消息类型保持原有格式
                forward_message['data'] = message_data
            
            forward_message_str = json.dumps(forward_message)
            
            # 处理不同类型的接收者
            if isinstance(recipients, str):
                # 单个用户
                connection_ids = self.connection_manager.username_connections.get(recipients, set())
                for connection_id in connection_ids:
                    conn_info = self.connection_manager.connections.get(connection_id)
                    if conn_info and not conn_info.websocket.closed:
                        try:
                            await conn_info.websocket.send(forward_message_str)
                        except Exception as e:
                            logger.error(f"转发消息失败: {e}")
            elif isinstance(recipients, list):
                # 多个用户（群聊）
                for recipient in recipients:
                    connection_ids = self.connection_manager.username_connections.get(recipient, set())
                    for connection_id in connection_ids:
                        conn_info = self.connection_manager.connections.get(connection_id)
                        if conn_info and not conn_info.websocket.closed:
                            try:
                                await conn_info.websocket.send(forward_message_str)
                            except Exception as e:
                                logger.error(f"转发群聊消息失败: {e}")
            
        except Exception as e:
            logger.error(f"转发消息异常: {e}")
    
    # 事件处理器
    
    async def _on_connection_established(self, event_data: Dict[str, Any]):
        """连接建立事件处理器"""
        self.stats['total_connections'] += 1
        self.stats['current_connections'] += 1
        
        logger.info(f"📊 连接统计: 当前 {self.stats['current_connections']}, 总计 {self.stats['total_connections']}")
    
    async def _on_connection_closed(self, event_data: Dict[str, Any]):
        """连接关闭事件处理器"""
        self.stats['current_connections'] -= 1
        
        logger.info(f"📊 连接统计: 当前 {self.stats['current_connections']}, 总计 {self.stats['total_connections']}")
    
    async def _stats_reporter(self):
        """统计信息报告器"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # 每分钟报告一次
                
                if self.start_time:
                    uptime = (datetime.now() - self.start_time).total_seconds()
                    self.stats['uptime_seconds'] = uptime
                
                # 获取各组件统计
                conn_stats = self.connection_manager.get_stats()
                msg_stats = self.message_processor.get_stats()
                proto_stats = self.protocol_processor.get_stats()
                
                logger.info("📊 服务器统计信息:")
                logger.info(f"   运行时间: {uptime:.0f}秒")
                logger.info(f"   当前连接: {conn_stats['current_connections']}")
                logger.info(f"   总连接数: {conn_stats['total_connections']}")
                logger.info(f"   已处理消息: {msg_stats['messages_processed']}")
                logger.info(f"   平均处理时间: {msg_stats.get('avg_processing_time', 0):.3f}秒")
                logger.info(f"   消息队列大小: {conn_stats['message_queue_size']}")
                logger.info(f"   协议处理错误: {proto_stats['errors']}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"统计报告异常: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取服务器统计信息"""
        if self.start_time:
            self.stats['uptime_seconds'] = (datetime.now() - self.start_time).total_seconds()
        
        return {
            'server': self.stats,
            'connections': self.connection_manager.get_stats(),
            'messages': self.message_processor.get_stats(),
            'protocol': self.protocol_processor.get_stats()
        }

async def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='异步安全即时通讯服务器')
    parser.add_argument('--host', default='localhost', help='服务器主机')
    parser.add_argument('--port', type=int, default=8765, help='服务器端口')
    parser.add_argument('--max-connections', type=int, default=10000, help='最大连接数')
    parser.add_argument('--db-path', default='secure_chat.db', help='数据库路径')
    parser.add_argument('--log-level', default='INFO', help='日志级别')
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('async_secure_server.log'),
            logging.StreamHandler()
        ]
    )
    
    # 创建配置
    config = Config()
    config.update({
        'HOST': args.host,
        'PORT': args.port,
        'MAX_CONNECTIONS': args.max_connections,
        'DATABASE_PATH': args.db_path
    })
    
    # 创建并启动服务器
    server = AsyncSecureServer(config)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在关闭服务器...")
    except Exception as e:
        logger.error(f"服务器运行异常: {e}")
        raise
    finally:
        await server.shutdown()

if __name__ == "__main__":
    asyncio.run(main()) 