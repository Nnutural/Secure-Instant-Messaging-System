# ──────────────────────────────────────────────────────────────
# server/history.py — 聊天日志持久化与查询（接口骨架 + 步骤）
#
# 日志文件路径约定：
#   server/history/<min(user1,user2)>__<max(user1,user2)>.log
#   — 每行一条 TSV：<timestamp_iso>\t<sender>\t<receiver>\t<base64_payload>\n
# 依赖：标准库 only（datetime, pathlib, base64, json, typing）
# ──────────────────────────────────────────────────────────────

from __future__ import annotations

import base64
import datetime as _dt
import json
import pathlib
from typing import List, Tuple, Optional

HISTORY_DIR = pathlib.Path("server/history")

# ======================================================================
# 1. 工具：生成文件路径 & 时间戳
# ======================================================================

def _pair_key(u1: str, u2: str) -> str:
    """返回排序后的会话键："alice__bob"。"""
    pass


def _log_path(u1: str, u2: str) -> pathlib.Path:
    """拼接完整日志文件路径。"""
    pass


def _utc_iso(ts: float | None = None) -> str:
    """float 秒 → ISO-8601 字符串 (UTC)。"""
    pass

# ======================================================================
# 2. 写入 API
# ======================================================================

def append_chatlog(sender: str,
                   receiver: str,
                   payload_bytes: bytes,
                   timestamp: float | None = None) -> None:
    """追加一条聊天记录。支持密文 / 明文均可。

    步骤
    -----
    1. `ts_iso = _utc_iso(timestamp)`
    2. `b64 = base64.b64encode(payload_bytes).decode()`
    3. `line = f"{ts_iso}\t{sender}\t{receiver}\t{b64}\n"`
    4. `path = _log_path(sender, receiver)`
       • 确保目录存在：`path.parent.mkdir(parents=True, exist_ok=True)`
    5. 以 *append, utf-8* 打开文件并写入；不锁也可，行追加原子性在 POSIX 足够。
    """
    pass

# ======================================================================
# 3. 读取 / 查询 API
# ======================================================================

def read_chatlog(user1: str,
                 user2: str,
                 since_iso: str | None = None,
                 limit: int | None = 100) -> List[Tuple[str, str, str, bytes]]:
    """读取两人聊天记录，按时间倒序返回。

    Parameters
    ----------
    since_iso : str, optional
        仅返回时间戳晚于此值的条目（ISO-8601）。
    limit : int, optional
        返回条数上限，None = 不限制。

    Returns
    -------
    List[(timestamp_iso, sender, receiver, payload_bytes)]
    """
    pass


def list_conversation_pairs() -> List[str]:
    """列出服务器现有的所有 `<user1>__<user2>.log` 文件名。"""
    pass

# ======================================================================
# 4. 导出 / 归档
# ======================================================================

def export_chatlog(user1: str, user2: str, out_path: pathlib.Path) -> None:
    """将指定会话日志复制到外部路径（例如供管理员归档）。"""
    pass


def rotate_daily(retention_days: int = 30) -> None:
    """日志轮替：保留最近 `retention_days` 天文件，其余压缩或删除。

    步骤建议
    ---------
    1. 遍历 HISTORY_DIR.glob('*.log')
    2. 解析文件的 *最后一行* 时间戳；若早于 `today - retention_days` → 压缩 `.gz` 或删除。
    """
    pass

# ───────── End of server/history.py skeleton ─────────