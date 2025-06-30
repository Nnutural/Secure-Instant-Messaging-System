# server/main.py
import argparse, asyncio
from server import core           # 需要你补 core.run_server()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=443)
    args = ap.parse_args()

    asyncio.run(core.run_server(args.host, args.port))
