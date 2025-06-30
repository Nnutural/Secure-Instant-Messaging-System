# ──────────────────────────────────────────────────────────────
# server/directory.py — 在线目录 / 好友图管理（接口骨架 + 步骤）
#
# ⚠️ 仅包含函数签名和实现步骤注释；逻辑留空。
#
# 数据文件：
#   • server/data/contacts.json   — 好友关系、版本号、拉黑列表
#   • 在线状态放内存 `ONLINE_MAP`，服务重启清零，由客户端重新心跳汇报。
#
# 依赖：auth.get_user_pubkey 用于查询公钥
# ──────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import os
import pathlib
import time
from typing import Dict, List, Tuple, Optional

CONTACTS_FILE = pathlib.Path("server/data/contacts.json")

# 在线状态表：username -> (ip, port, last_heartbeat)
ONLINE_MAP: Dict[str, Tuple[str, int, float]] = {}

# ----------------------------------------------------------------------
# 内部工具：载入 & 保存 contacts.json
# ----------------------------------------------------------------------

def _load_contacts() -> Dict:
    """读 contacts.json；若空则返回默认结构。"""
    pass


def _save_contacts(data: Dict) -> None:
    """原子写回 contacts.json。"""
    pass

# ======================================================================
# 1. 在线状态维护
# ======================================================================

def set_online(username: str, ip: str, port: int) -> None:
    """标记用户上线 / 更新心跳。

    步骤
    -----
    1. `ONLINE_MAP[username] = (ip, port, time.time())`
    2. *可选*：广播给该用户好友（遍历 ONLINE_MAP）在线通知。
    """
    pass


def set_offline(username: str) -> None:
    """用户下线：从 ONLINE_MAP 删除并通知好友。"""
    pass


def prune_stale(timeout_sec: int = 90) -> None:
    """定期调用：移除超过 `timeout_sec` 未心跳的条目。"""
    pass

# ======================================================================
# 2. 好友关系操作（持久化）
# ======================================================================

def add_friend(u: str, v: str) -> bool:
    """建立好友关系（双向）。

    1. `_load_contacts()`
    2. 检查是否已互为好友 / 是否被拉黑 → 决定允许或拒绝
    3. 在 `graph[u]` 和 `graph[v]` 列表追加对方
    4. `version += 1`，`_save_contacts()`
    5. 返回 True 表示已成功添加
    """
    pass


def remove_friend(u: str, v: str) -> None:
    """解除好友关系（双向移除）。"""
    pass


def add_friend_request(src: str, dest: str) -> bool:
    """写入待审批请求 `pending[dest]`。

    返回 True 表示已写入；如果冲突或已在好友列表，返回 False。
    """
    pass


def list_pending(dest: str) -> List[str]:
    """返回 dest 收到的所有待处理加好友请求。"""
    pass


def block_user(user: str, target: str) -> None:
    """将 *target* 加入 *user* 的拉黑列表。"""
    pass

# ======================================================================
# 3. 数据查询 API
# ======================================================================

def get_online_friends(username: str) -> List[Tuple[str, str, int]]:
    """返回 *username* 好友中当前在线的端点列表。

    Returns
    -------
    List[(friend_name, ip, port)]
    """
    pass


def get_friend_pubkey(friend_name: str) -> Optional[str]:
    """代理调用 auth.get_user_pubkey，提供统一出口。"""
    pass


def get_contacts_version() -> int:
    """获取 contacts.json 顶层 version 字段。"""
    pass

# ======================================================================
# 4. 向客户端推送格式（示例生成）
# ======================================================================

def make_online_list_packet(username: str) -> Dict:
    """构造服务器 → 客户端 的在线好友列表 JSON 包。"""
    pass

# ───────── End of server/directory.py skeleton ─────────
