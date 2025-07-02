#!/usr/bin/env python3
"""
安全即时通讯系统服务器启动脚本
"""

import asyncio
import signal
import sys
import argparse
import logging
from pathlib import Path

from server import SecureChatServer

def setup_signal_handlers(server):
    """设置信号处理器以优雅地关闭服务器"""
    def signal_handler(signum, frame):
        logging.info(f"接收到信号 {signum}，准备关闭服务器...")
        asyncio.create_task(server.stop_server())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='安全即时通讯系统服务器')
    
    parser.add_argument(
        '--host', 
        type=str, 
        default='localhost',
        help='服务器监听地址 (默认: localhost)'
    )
    
    parser.add_argument(
        '--port', 
        type=int, 
        default=8765,
        help='服务器监听端口 (默认: 8765)'
    )
    
    parser.add_argument(
        '--max-connections', 
        type=int, 
        default=100,
        help='最大连接数 (默认: 100)'
    )
    
    parser.add_argument(
        '--db-path', 
        type=str, 
        default='secure_chat.db',
        help='数据库文件路径 (默认: secure_chat.db)'
    )
    
    parser.add_argument(
        '--log-level', 
        type=str, 
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='日志级别 (默认: INFO)'
    )
    
    parser.add_argument(
        '--log-file', 
        type=str, 
        default='secure_chat_server.log',
        help='日志文件路径 (默认: secure_chat_server.log)'
    )
    
    return parser.parse_args()

def setup_logging(log_level, log_file):
    """配置日志系统"""
    # 确保日志目录存在
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 配置日志格式
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # 配置日志处理器
    handlers = [
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
    
    # 配置日志系统
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=handlers,
        force=True
    )

async def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()
    
    # 配置日志
    setup_logging(args.log_level, args.log_file)
    
    # 打印启动信息
    print("=" * 60)
    print("🔐 安全即时通讯系统服务器")
    print("=" * 60)
    print(f"监听地址: {args.host}:{args.port}")
    print(f"最大连接数: {args.max_connections}")
    print(f"数据库路径: {args.db_path}")
    print(f"日志级别: {args.log_level}")
    print(f"日志文件: {args.log_file}")
    print("=" * 60)
    
    # 创建服务器实例
    server = SecureChatServer(
        host=args.host,
        port=args.port,
        max_connections=args.max_connections,
        db_path=args.db_path
    )
    
    # 设置信号处理器
    setup_signal_handlers(server)
    
    try:
        # 启动服务器
        logging.info("正在启动安全即时通讯服务器...")
        await server.start_server()
        
    except KeyboardInterrupt:
        logging.info("接收到中断信号，正在关闭服务器...")
    except Exception as e:
        logging.error(f"服务器运行异常: {e}")
        raise
    finally:
        # 确保服务器正确关闭
        await server.stop_server()
        logging.info("服务器已安全关闭")

def run_server():
    """运行服务器的便捷函数"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n服务器已被用户中断")
    except Exception as e:
        print(f"\n服务器运行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_server() 