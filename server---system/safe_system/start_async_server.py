#!/usr/bin/env python3
"""
启动异步安全即时通讯服务器

使用新的异步架构，支持高并发连接和IO复用
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent))

from config import Config
from server.async_core import AsyncSecureServer

def setup_logging(log_level: str = "INFO", log_file: str = "async_server.log"):
    """设置日志系统"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def print_banner():
    """打印启动横幅"""
    print("=" * 70)
    print("🚀 异步安全即时通讯服务器 v2.0")
    print("=" * 70)
    print("✨ 特性:")
    print("   🔄 基于asyncio的异步架构")
    print("   🌐 高效IO复用和连接池管理")
    print("   📦 统一消息结构体和协议处理")
    print("   ⚡ 支持10,000+并发连接")
    print("   🛡️ 完整的安全认证和加密")
    print("   📊 实时性能监控和统计")
    print("=" * 70)

async def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='异步安全即时通讯服务器')
    parser.add_argument('--host', default='localhost', help='服务器主机地址')
    parser.add_argument('--port', type=int, default=8765, help='服务器端口')
    parser.add_argument('--max-connections', type=int, default=10000, help='最大连接数')
    parser.add_argument('--db-path', default='secure_chat.db', help='数据库文件路径')
    parser.add_argument('--log-level', default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='日志级别')
    parser.add_argument('--log-file', default='async_server.log', help='日志文件路径')
    parser.add_argument('--enable-compression', action='store_true', 
                       default=True, help='启用消息压缩')
    parser.add_argument('--workers', type=int, default=8, help='消息处理工作协程数')
    parser.add_argument('--cleanup-interval', type=int, default=60, 
                       help='连接清理间隔（秒）')
    
    args = parser.parse_args()
    
    # 打印启动横幅
    print_banner()
    
    # 设置日志
    setup_logging(args.log_level, args.log_file)
    logger = logging.getLogger(__name__)
    
    # 打印配置信息
    print(f"🔧 服务器配置:")
    print(f"   监听地址: {args.host}:{args.port}")
    print(f"   最大连接数: {args.max_connections}")
    print(f"   数据库路径: {args.db_path}")
    print(f"   日志级别: {args.log_level}")
    print(f"   日志文件: {args.log_file}")
    print(f"   消息压缩: {'启用' if args.enable_compression else '禁用'}")
    print(f"   工作协程数: {args.workers}")
    print(f"   清理间隔: {args.cleanup_interval}秒")
    print("=" * 70)
    
    # 创建配置对象
    config = Config()
    config.set('HOST', args.host)
    config.set('PORT', args.port)
    config.set('MAX_CONNECTIONS', args.max_connections)
    config.set('DATABASE_PATH', args.db_path)
    config.set('ENABLE_COMPRESSION', args.enable_compression)
    config.set('ENABLE_ENCRYPTION', False)  # 暂时禁用加密
    config.set('MAX_MESSAGE_SIZE', 4 * 1024 * 1024)  # 4MB
    config.set('PING_INTERVAL', 30)
    config.set('PING_TIMEOUT', 60)
    config.set('CLOSE_TIMEOUT', 10)
    config.set('CLEANUP_INTERVAL', args.cleanup_interval)
    config.set('NUM_WORKERS', args.workers)
    
    # 创建并启动服务器
    server = AsyncSecureServer(config)
    
    try:
        logger.info("正在启动异步安全即时通讯服务器...")
        await server.start()
        
    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在关闭服务器...")
        print("\n🛑 服务器正在关闭...")
        
    except Exception as e:
        logger.error(f"服务器运行异常: {e}")
        print(f"\n❌ 服务器异常: {e}")
        sys.exit(1)
        
    finally:
        try:
            await server.shutdown()
            print("✅ 服务器已安全关闭")
        except Exception as e:
            logger.error(f"服务器关闭异常: {e}")
            print(f"❌ 关闭异常: {e}")

def run_server():
    """运行服务器的便捷函数"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 再见！")
    except Exception as e:
        print(f"\n💥 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_server() 