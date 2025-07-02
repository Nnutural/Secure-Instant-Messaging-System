"""
连接管理器

实现基于asyncio的高效IO复用和连接池管理
"""

import asyncio
import weakref
import time
import logging
from typing import Dict, Set, Optional, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import websockets
import json

logger = logging.getLogger(__name__)

@dataclass
class ConnectionInfo:
    """连接信息"""
    websocket: websockets.WebSocketServerProtocol
    user_id: Optional[int] = None
    username: Optional[str] = None
    ip_address: str = ""
    port: int = 0
    connected_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    is_authenticated: bool = False
    user_agent: str = ""
    session_id: str = ""
    
    def update_activity(self):
        """更新活动时间"""
        self.last_activity = datetime.now()
    
    def is_expired(self, timeout_seconds: int = 300) -> bool:
        """检查连接是否过期"""
        return (datetime.now() - self.last_activity).total_seconds() > timeout_seconds

class ConnectionPool:
    """连接池"""
    
    def __init__(self, max_connections: int = 10000):
        """
        初始化连接池
        
        Args:
            max_connections: 最大连接数
        """
        self.max_connections = max_connections
        self.connections: Dict[str, ConnectionInfo] = {}
        self.user_connections: Dict[int, Set[str]] = defaultdict(set)
        self.username_connections: Dict[str, Set[str]] = defaultdict(set)
        self.ip_connections: Dict[str, Set[str]] = defaultdict(set)
        
        # 统计信息
        self.stats = {
            'total_connections': 0,
            'current_connections': 0,
            'max_concurrent_connections': 0,
            'messages_processed': 0,
            'bytes_transferred': 0,
            'connection_errors': 0,
            'timeouts': 0
        }
        
        # 连接限制
        self.max_connections_per_ip = 100
        self.max_connections_per_user = 10
        
    def add_connection(self, connection_id: str, websocket: websockets.WebSocketServerProtocol,
                      ip_address: str = "", port: int = 0) -> bool:
        """
        添加连接
        
        Args:
            connection_id: 连接ID
            websocket: WebSocket连接
            ip_address: IP地址
            port: 端口
            
        Returns:
            是否成功添加
        """
        try:
            # 检查连接数限制
            if len(self.connections) >= self.max_connections:
                logger.warning(f"连接数已达上限: {self.max_connections}")
                return False
            
            # 检查IP连接数限制
            if len(self.ip_connections[ip_address]) >= self.max_connections_per_ip:
                logger.warning(f"IP {ip_address} 连接数已达上限: {self.max_connections_per_ip}")
                return False
            
            # 创建连接信息
            conn_info = ConnectionInfo(
                websocket=websocket,
                ip_address=ip_address,
                port=port
            )
            
            # 添加到池中
            self.connections[connection_id] = conn_info
            self.ip_connections[ip_address].add(connection_id)
            
            # 更新统计
            self.stats['total_connections'] += 1
            self.stats['current_connections'] += 1
            self.stats['max_concurrent_connections'] = max(
                self.stats['max_concurrent_connections'],
                self.stats['current_connections']
            )
            
            logger.info(f"连接已添加: {connection_id} from {ip_address}:{port}")
            return True
            
        except Exception as e:
            logger.error(f"添加连接失败: {e}")
            self.stats['connection_errors'] += 1
            return False
    
    def remove_connection(self, connection_id: str) -> bool:
        """
        移除连接
        
        Args:
            connection_id: 连接ID
            
        Returns:
            是否成功移除
        """
        try:
            conn_info = self.connections.get(connection_id)
            if not conn_info:
                return False
            
            # 从各种映射中移除
            if conn_info.user_id:
                self.user_connections[conn_info.user_id].discard(connection_id)
                if not self.user_connections[conn_info.user_id]:
                    del self.user_connections[conn_info.user_id]
            
            if conn_info.username:
                self.username_connections[conn_info.username].discard(connection_id)
                if not self.username_connections[conn_info.username]:
                    del self.username_connections[conn_info.username]
            
            if conn_info.ip_address:
                self.ip_connections[conn_info.ip_address].discard(connection_id)
                if not self.ip_connections[conn_info.ip_address]:
                    del self.ip_connections[conn_info.ip_address]
            
            # 从主连接池移除
            del self.connections[connection_id]
            
            # 更新统计
            self.stats['current_connections'] -= 1
            
            logger.info(f"连接已移除: {connection_id}")
            return True
            
        except Exception as e:
            logger.error(f"移除连接失败: {e}")
            return False
    
    def authenticate_connection(self, connection_id: str, user_id: int, username: str) -> bool:
        """
        认证连接
        
        Args:
            connection_id: 连接ID
            user_id: 用户ID
            username: 用户名
            
        Returns:
            是否成功认证
        """
        try:
            conn_info = self.connections.get(connection_id)
            if not conn_info:
                return False
            
            # 检查用户连接数限制
            if len(self.user_connections[user_id]) >= self.max_connections_per_user:
                logger.warning(f"用户 {username} 连接数已达上限: {self.max_connections_per_user}")
                return False
            
            # 更新连接信息
            conn_info.user_id = user_id
            conn_info.username = username
            conn_info.is_authenticated = True
            conn_info.update_activity()
            
            # 添加到用户映射
            self.user_connections[user_id].add(connection_id)
            self.username_connections[username].add(connection_id)
            
            logger.info(f"连接已认证: {connection_id} -> {username} (ID: {user_id})")
            return True
            
        except Exception as e:
            logger.error(f"认证连接失败: {e}")
            return False
    
    def get_connection(self, connection_id: str) -> Optional[ConnectionInfo]:
        """获取连接信息"""
        return self.connections.get(connection_id)
    
    def get_user_connections(self, user_id: int) -> List[ConnectionInfo]:
        """获取用户的所有连接"""
        connection_ids = self.user_connections.get(user_id, set())
        return [self.connections[cid] for cid in connection_ids if cid in self.connections]
    
    def get_username_connections(self, username: str) -> List[ConnectionInfo]:
        """获取用户名的所有连接"""
        connection_ids = self.username_connections.get(username, set())
        return [self.connections[cid] for cid in connection_ids if cid in self.connections]
    
    def update_connection_activity(self, connection_id: str):
        """更新连接活动时间"""
        conn_info = self.connections.get(connection_id)
        if conn_info:
            conn_info.update_activity()
    
    def cleanup_expired_connections(self, timeout_seconds: int = 300) -> int:
        """清理过期连接"""
        expired_connections = []
        
        for connection_id, conn_info in self.connections.items():
            if conn_info.is_expired(timeout_seconds):
                expired_connections.append(connection_id)
        
        # 移除过期连接
        for connection_id in expired_connections:
            self.remove_connection(connection_id)
            self.stats['timeouts'] += 1
        
        if expired_connections:
            logger.info(f"清理了 {len(expired_connections)} 个过期连接")
        
        return len(expired_connections)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            'connections_by_ip': {ip: len(conn_ids) for ip, conn_ids in self.ip_connections.items()},
            'connections_by_user': {user_id: len(conn_ids) for user_id, conn_ids in self.user_connections.items()},
            'authenticated_connections': sum(1 for conn in self.connections.values() if conn.is_authenticated)
        }

class AsyncConnectionManager:
    """异步连接管理器"""
    
    def __init__(self, max_connections: int = 10000, cleanup_interval: int = 60):
        """
        初始化异步连接管理器
        
        Args:
            max_connections: 最大连接数
            cleanup_interval: 清理间隔（秒）
        """
        self.max_connections = max_connections
        self.cleanup_interval = cleanup_interval
        self.connections: Dict[str, ConnectionInfo] = {}
        self.user_connections: Dict[int, Set[str]] = defaultdict(set)
        self.username_connections: Dict[str, Set[str]] = defaultdict(set)
        
        # 消息队列和工作协程
        self.message_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self.worker_tasks: List[asyncio.Task] = []
        self.num_workers = 4
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # 统计信息
        self.stats = {
            'total_connections': 0,
            'current_connections': 0,
            'messages_processed': 0,
            'bytes_transferred': 0,
            'connection_errors': 0,
            'timeouts': 0
        }
        
        # 消息处理器
        self.message_handlers: Dict[str, Callable] = {}
        self.event_handlers: Dict[str, List[Callable]] = defaultdict(list)
    
    async def start(self):
        """启动连接管理器"""
        try:
            # 启动清理任务
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            # 启动工作协程
            for i in range(self.num_workers):
                task = asyncio.create_task(self._message_worker(f"worker-{i}"))
                self.worker_tasks.append(task)
            
            logger.info(f"异步连接管理器已启动，工作协程数: {self.num_workers}")
            
        except Exception as e:
            logger.error(f"启动连接管理器失败: {e}")
            raise
    
    async def stop(self):
        """停止连接管理器"""
        try:
            # 停止清理任务
            if self.cleanup_task:
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # 停止工作协程
            for task in self.worker_tasks:
                task.cancel()
            
            if self.worker_tasks:
                await asyncio.gather(*self.worker_tasks, return_exceptions=True)
            
            # 关闭所有连接
            await self._close_all_connections()
            
            logger.info("异步连接管理器已停止")
            
        except Exception as e:
            logger.error(f"停止连接管理器失败: {e}")
    
    async def add_connection(self, connection_id: str, websocket: websockets.WebSocketServerProtocol) -> bool:
        """添加连接"""
        try:
            # 检查连接数限制
            if len(self.connections) >= self.max_connections:
                logger.warning(f"连接数已达上限: {self.max_connections}")
                return False
            
            ip_address = websocket.remote_address[0] if websocket.remote_address else ""
            port = websocket.remote_address[1] if websocket.remote_address else 0
            
            # 创建连接信息
            conn_info = ConnectionInfo(
                websocket=websocket,
                ip_address=ip_address,
                port=port
            )
            
            # 添加到池中
            self.connections[connection_id] = conn_info
            
            # 更新统计
            self.stats['total_connections'] += 1
            self.stats['current_connections'] += 1
            
            logger.info(f"连接已添加: {connection_id} from {ip_address}:{port}")
            return True
            
        except Exception as e:
            logger.error(f"添加连接失败: {e}")
            self.stats['connection_errors'] += 1
            return False
    
    async def remove_connection(self, connection_id: str) -> bool:
        """移除连接"""
        try:
            conn_info = self.connections.get(connection_id)
            if not conn_info:
                return False
            
            # 从各种映射中移除
            if conn_info.user_id:
                self.user_connections[conn_info.user_id].discard(connection_id)
                if not self.user_connections[conn_info.user_id]:
                    del self.user_connections[conn_info.user_id]
            
            if conn_info.username:
                self.username_connections[conn_info.username].discard(connection_id)
                if not self.username_connections[conn_info.username]:
                    del self.username_connections[conn_info.username]
            
            # 从主连接池移除
            del self.connections[connection_id]
            
            # 更新统计
            self.stats['current_connections'] -= 1
            
            logger.info(f"连接已移除: {connection_id}")
            return True
            
        except Exception as e:
            logger.error(f"移除连接失败: {e}")
            return False
    
    def register_message_handler(self, message_type: str, handler: Callable):
        """注册消息处理器"""
        self.message_handlers[message_type] = handler
    
    def register_event_handler(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        self.event_handlers[event_type].append(handler)
    
    async def _cleanup_loop(self):
        """清理循环"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                # 清理过期连接的逻辑
                expired_connections = []
                for connection_id, conn_info in self.connections.items():
                    if conn_info.is_expired():
                        expired_connections.append(connection_id)
                
                for connection_id in expired_connections:
                    await self.remove_connection(connection_id)
                    self.stats['timeouts'] += 1
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理循环异常: {e}")
    
    async def _message_worker(self, worker_name: str):
        """消息工作协程"""
        logger.info(f"消息工作协程 {worker_name} 已启动")
        
        while True:
            try:
                # 获取消息
                message_data = await self.message_queue.get()
                
                # 处理消息
                await self._handle_message(message_data)
                
                # 标记任务完成
                self.message_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"消息工作协程 {worker_name} 异常: {e}")
    
    async def _handle_message(self, message_data: Dict[str, Any]):
        """处理单个消息"""
        try:
            connection_id = message_data['connection_id']
            message = message_data['message']
            
            # 解析消息
            try:
                data = json.loads(message)
                message_type = data.get('type', 'unknown')
            except json.JSONDecodeError:
                logger.error(f"无效的JSON消息: {message[:100]}")
                return
            
            # 查找处理器
            handler = self.message_handlers.get(message_type) or self.message_handlers.get('default')
            if handler:
                await handler(connection_id, data)
            else:
                logger.warning(f"未找到消息类型 {message_type} 的处理器")
            
            # 更新统计
            self.stats['messages_processed'] += 1
            
        except Exception as e:
            logger.error(f"处理消息异常: {e}")
    
    async def _close_all_connections(self):
        """关闭所有连接"""
        tasks = []
        for conn_info in self.connections.values():
            if not conn_info.websocket.closed:
                tasks.append(conn_info.websocket.close())
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            'message_queue_size': self.message_queue.qsize(),
            'worker_count': len(self.worker_tasks)
        } 