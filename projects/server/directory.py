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
    # 确保目录存在
    CONTACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    if not CONTACTS_FILE.exists():
        # 创建默认结构
        default_data = {
            "version": 1,
            "graph": {},
            "pending": {},
            "blocked": {}
        }
        _save_contacts(default_data)
        return default_data
    
    try:
        with open(CONTACTS_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return {
                    "version": 1,
                    "graph": {},
                    "pending": {},
                    "blocked": {}
                }
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return {
            "version": 1,
            "graph": {},
            "pending": {},
            "blocked": {}
        }


def _save_contacts(data: Dict) -> None:
    """原子写回 contacts.json。"""
    # 转换为JSON文本
    json_text = json.dumps(data, indent=2, ensure_ascii=False)
    
    # 写入临时文件
    temp_file = CONTACTS_FILE.with_suffix('.tmp')
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write(json_text)
    
    # 原子替换
    temp_file.replace(CONTACTS_FILE)

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
    ONLINE_MAP[username] = (ip, port, time.time())


def set_offline(username: str) -> None:
    """用户下线：从 ONLINE_MAP 删除并通知好友。"""
    if username in ONLINE_MAP:
        del ONLINE_MAP[username]


def prune_stale(timeout_sec: int = 90) -> None:
    """定期调用：移除超过 `timeout_sec` 未心跳的条目。"""
    current_time = time.time()
    stale_users = []
    
    for username, (ip, port, last_heartbeat) in ONLINE_MAP.items():
        if current_time - last_heartbeat > timeout_sec:
            stale_users.append(username)
    
    for username in stale_users:
        del ONLINE_MAP[username]

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
    data = _load_contacts()
    
    # 初始化用户的好友列表
    if u not in data["graph"]:
        data["graph"][u] = []
    if v not in data["graph"]:
        data["graph"][v] = []
    
    # 检查是否已经是好友
    if v in data["graph"][u] or u in data["graph"][v]:
        return False
    
    # 检查是否被拉黑
    if u in data["blocked"].get(v, []) or v in data["blocked"].get(u, []):
        return False
    
    # 添加好友关系（双向）
    data["graph"][u].append(v)
    data["graph"][v].append(u)
    
    # 更新版本号
    data["version"] += 1
    
    # 保存数据
    _save_contacts(data)
    
    return True


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
    data = _load_contacts()
    
    # 获取用户的好友列表
    friends = data["graph"].get(username, [])
    
    # 筛选在线好友
    online_friends = []
    for friend in friends:
        if friend in ONLINE_MAP:
            ip, port, _ = ONLINE_MAP[friend]
            online_friends.append((friend, ip, port))
    
    return online_friends


def get_friend_pubkey(friend_name: str) -> Optional[str]:
    """代理调用 auth.get_user_pubkey，提供统一出口。"""
    from server import auth
    return auth.get_user_pubkey(friend_name)


def get_contacts_version() -> int:
    """获取 contacts.json 顶层 version 字段。"""
    data = _load_contacts()
    return data.get("version", 1)

# ======================================================================
# 4. 向客户端推送格式（示例生成）
# ======================================================================

def make_online_list_packet(username: str) -> Dict:
    """构造服务器 → 客户端 的在线好友列表 JSON 包。"""
    online_friends = get_online_friends(username)
    
    friends_list = []
    for friend_name, ip, port in online_friends:
        friends_list.append({
            "username": friend_name,
            "ip": ip,
            "port": port
        })
    
    return {
        "type": "online_list",
        "friends": friends_list,
        "version": get_contacts_version()
    }

# ───────── End of server/directory.py skeleton ─────────
