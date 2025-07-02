import argparse, asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = str(Path(__file__).resolve().parents[1])
sys.path.append(project_root)

from server import core  # 绝对导入

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=443)
    args = ap.parse_args()

    asyncio.run(core.run_server(args.host, args.port))