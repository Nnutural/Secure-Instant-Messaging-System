# ──────────────────────────────────────────────────────────────
# server/auth.py — 账户注册 / 认证模块（接口骨架 + 详细实现步骤）
#
# ⚠️ 说明：本文件仍不包含具体业务代码，仅提供最完整的
#       “Todo‑List 级” 步骤注释，确保实现者清楚每一步该干什么。
#       每个函数体仍保留 `pass`，请按注释顺序补充逻辑。
#
# 数据落盘：server/data/users.json
# 依赖建议：标准库 (hashlib, hmac, secrets, json, base64, datetime, pathlib)
# 安全原则：不留明文口令；所有时间为 UTC ISO‑8601("Z")；所有写操作文件锁同程。
# ──────────────────────────────────────────────────────────────

from __future__ import annotations

import pathlib
from typing import List, Dict, Optional

# ----------------------------------------------------------------------
# 常量（仅供演示，实现阶段可改用 settings.ini 覆盖）
# ----------------------------------------------------------------------
USERS_FILE = pathlib.Path("server/data/users.json")
HASH_ALG = "sha256"        # PBKDF2 内部摘要算法
PBKDF2_ITER = 100_000       # PBKDF2 迭代次数（≥10^5 建议）
SALT_BYTES = 16             # 盐长度：16B = 128bit

# ======================================================================
# 内部辅助函数（仅声明 + 实现步骤）
# ======================================================================

def _hash_password(password: str, salt: bytes) -> str:  # noqa: D401
    """返回 Base64 编码的 PBKDF2-HMAC 派生值。

    步骤
    -----
    1. 使用 `hashlib.pbkdf2_hmac`，参数：
       • hash_name = HASH_ALG
       • password  = UTF‑8 编码后的字节串
       • salt      = 调用方传入
       • iterations= PBKDF2_ITER
       • dklen     = 摘要长度（`hashlib.new(HASH_ALG).digest_size`）
    2. 将返回字节用 `base64.b64encode()` → 字符串返回。
    """
    import hashlib
    import base64
    
    # 使用PBKDF2进行密码哈希
    key = hashlib.pbkdf2_hmac(
        hash_name=HASH_ALG,
        password=password.encode('utf-8'),
        salt=salt,
        iterations=PBKDF2_ITER,
        dklen=hashlib.new(HASH_ALG).digest_size
    )
    
    return base64.b64encode(key).decode('utf-8')


def _load_users() -> List[Dict]:
    """读取并解析 *users.json*；若文件为空则返回空列表。

    步骤
    -----
    1. `USERS_FILE.parent.mkdir(parents=True, exist_ok=True)` — 确保目录存在。
    2. `USERS_FILE.touch(exist_ok=True)` — 确保文件存在。
    3. 以只读模式打开文件；若内容为空置为 "[]"。
    4. `json.loads()` 解析并返回列表。
    """
    import json
    
    # 确保目录存在
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # 确保文件存在
    USERS_FILE.touch(exist_ok=True)
    
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save_users(users: List[Dict]) -> None:
    """原子写回 *users.json*。

    步骤
    -----
    1. 将 `users` 用 `json.dumps(indent=2, ensure_ascii=False)` 转为文本。
    2. 写入临时文件 `USERS_FILE.with_suffix('.tmp')`。
    3. `os.replace()` 或 `Path.replace()` 原子覆盖旧文件。
    4. *可选*：调用文件锁，防并发写。（见项目文件锁实现方案）
    """
    import json
    import os
    
    # 转换为JSON文本
    json_text = json.dumps(users, indent=2, ensure_ascii=False)
    
    # 写入临时文件
    temp_file = USERS_FILE.with_suffix('.tmp')
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write(json_text)
    
    # 原子替换
    temp_file.replace(USERS_FILE)


def _find_user(users: List[Dict], username: str) -> Optional[Dict]:
    """在列表中按用户名查找用户条目，若找不到返回 `None`."""
    for user in users:
        if user.get('username') == username:
            return user
    return None


# ======================================================================
# 公共 API — 仅文档，无实现，步骤列表详尽
# ======================================================================

def register_user(
    username: str,
    password: str,
    email: str,
    pubkey_pem: str,
    cert_sha256: str | None = None,
) -> bool:
    """注册账号 — **详细步骤清单**

    预期流程
    ============
    ▸ 参数校验
        1. 检查 `username` 非空、无空格、长度 <= 项目配置上限。
        2. 检查 `password` 长度和复杂度（如需）。
        3. 若 `pubkey_pem` 不符合 PEM 头/尾格式，抛 `ValueError`。

    ▸ 检测账号冲突
        4. 调用 `_load_users()` → 列表。
        5. 使用 `_find_user()`；若已存在同名用户 → `ValueError('username exists')`。

    ▸ 生成口令哈希
        6. `salt = secrets.token_bytes(SALT_BYTES)`。
        7. `pass_hash = _hash_password(password, salt)`。

    ▸ 写入用户条目
        8. 构造 dict：
           ``{
             'username': username,
             'email': email,
             'salt': base64.b64encode(salt).decode(),
             'pass_hash': pass_hash,
             'pubkey_pem': pubkey_pem,
             'cert_sha256': cert_sha256 or '',
             'created_at': utc_now_iso(),
             'revoked': False
           }``
        9. 追加到列表，调用 `_save_users()`。

    ▸ 返回
       10. 返回 `True`。
    """
    import secrets
    import base64
    from datetime import datetime
    
    # 1. 参数校验
    if not username or ' ' in username or len(username) > 50:
        raise ValueError("用户名无效")
    
    if not password or len(password) < 6:
        raise ValueError("密码长度不足")
    
    if pubkey_pem and not (pubkey_pem.startswith('-----BEGIN') and pubkey_pem.endswith('-----')):
        raise ValueError("公钥格式无效")
    
    # 2. 检测账号冲突
    users = _load_users()
    if _find_user(users, username):
        raise ValueError("username exists")
    
    # 3. 生成口令哈希
    salt = secrets.token_bytes(SALT_BYTES)
    pass_hash = _hash_password(password, salt)
    
    # 4. 写入用户条目
    user_entry = {
        'username': username,
        'email': email,
        'salt': base64.b64encode(salt).decode(),
        'pass_hash': pass_hash,
        'pubkey_pem': pubkey_pem,
        'cert_sha256': cert_sha256 or '',
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'revoked': False
    }
    
    users.append(user_entry)
    _save_users(users)
    
    # 同时写入数据库
    try:
        from common.database import DatabaseManager
        db = DatabaseManager()
        db.create_user(
            username=username,
            email=email,
            password_hash=pass_hash,
            salt=base64.b64encode(salt).decode(),
            public_key=pubkey_pem
        )
    except Exception:
        pass  # 忽略数据库错误，以JSON为准
    
    return True


def verify_password(username: str, password: str) -> bool:
    """登录口令验证 — **详细步骤**

    1. `users = _load_users()`
    2. `user = _find_user(users, username)`；若 None → 返回 False
    3. 若 `user['revoked']` 为 True → 返回 False
    4. 解码 `salt = base64.b64decode(user['salt'])`
    5. 计算 `calc_hash = _hash_password(password, salt)`
    6. `hmac.compare_digest(calc_hash, user['pass_hash'])` → bool
    7. 返回比较结果
    """
    import base64
    import hmac
    
    # 1. 加载用户
    users = _load_users()
    
    # 2. 查找用户
    user = _find_user(users, username)
    if not user:
        return False
    
    # 3. 检查是否已封禁
    if user.get('revoked', False):
        return False
    
    # 4. 解码盐值
    try:
        salt = base64.b64decode(user['salt'])
    except (KeyError, ValueError):
        return False
    
    # 5. 计算哈希
    calc_hash = _hash_password(password, salt)
    
    # 6. 常量时间比较
    stored_hash = user.get('pass_hash', '')
    return hmac.compare_digest(calc_hash, stored_hash)


def get_user_pubkey(username: str) -> str | None:
    """取用户公钥 — 步骤

    1. `_load_users()`
    2. `_find_user()`
    3. 若找到且未封禁 → 返回 `'pubkey_pem'`
       否则返回 `None`。
    """
    users = _load_users()
    user = _find_user(users, username)
    
    if user and not user.get('revoked', False):
        return user.get('pubkey_pem')
    
    return None


def validate_client_cert(username: str, fingerprint_hex: str) -> bool:
    """验证 / 首绑客户端证书指纹 — 步骤

    1. 加载 & 查找用户；不存在或封禁 → False
    2. `stored = user['cert_sha256']`；
    3. 如果 `stored` 为空：
        • 将 `fingerprint_hex.lower()` 写回 user 条目 → `_save_users()`
        • 返回 True
    4. 否则比较：`hmac.compare_digest(stored.lower(), fingerprint_hex.lower())`。
    5. 返回比较结果。
    """
    pass


def update_password(username: str, old_password: str, new_password: str) -> bool:
    """修改口令 — 步骤

    1. 校验旧密码：调用 `verify_password()`；失败直接 False。
    2. 重新生成 `salt` & `pass_hash`（调用 `_hash_password`）。
    3. 更新条目字段：`salt`, `pass_hash`, `pw_changed_at`。
    4. `_save_users()`；成功返回 True。
    """
    pass


def revoke_user(username: str, reason: str = "") -> None:
    """封禁账户 — 步骤

    1. 读取 users → 找到条目；找不到直接返回。
    2. 设置：`revoked = True`, `revoke_reason = reason`, `revoked_at = utc_now_iso()`
    3. 持久化。
    """
    pass


def list_all_users() -> List[str]:
    """列出所有用户 — 步骤

    1. `_load_users()`
    2. `return [u['username'] for u in users]`
    """
    users = _load_users()
    return [u['username'] for u in users]

# ───────── End of detailed auth.py skeleton ─────────
