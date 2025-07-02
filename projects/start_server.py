#!/usr/bin/env python3
"""
项目服务器启动脚本
"""

import asyncio
import logging
import argparse
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from server.core import run_server

def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('server.log')
        ]
    )

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='启动安全即时通讯服务器')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=8765, help='监听端口')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        await run_server(args.host, args.port)
    except KeyboardInterrupt:
        logging.info("服务器停止")
    except Exception as e:
        logging.error(f"服务器启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    setup_logging()
    asyncio.run(main()) 