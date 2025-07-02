# 安全即时通讯系统 - Projects 版本

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://python.org)
[![WebSocket](https://img.shields.io/badge/protocol-WebSocket-orange.svg)](https://websockets.readthedocs.io/)

这是一个完全自包含的安全即时通讯系统实现，所有代码都在 `projects` 文件夹内。该系统支持实时消息传输、用户认证、好友管理和聊天历史记录等核心功能。

## 🌟 功能特性

### 核心功能
- ✅ **用户系统**: 注册、登录、密码验证
- ✅ **实时通讯**: WebSocket协议实时消息收发
- ✅ **好友管理**: 添加好友、在线状态显示
- ✅ **聊天历史**: 消息持久化存储和查询
- ✅ **会话管理**: 多用户并发会话支持

### 技术特性
- 🔐 **安全认证**: PBKDF2密码哈希、会话管理
- 📡 **WebSocket通信**: 支持并发连接和实时推送
- 💾 **双重存储**: JSON文件 + SQLite数据库
- 🏗️ **模块化设计**: 清晰的分层架构
- 🔧 **易于部署**: 自包含设计，无外部依赖

## 📁 项目结构

```
projects/
├── 📂 common/              # 公共基础模块
│   ├── 📄 config.py        # 系统配置常量
│   ├── 📄 crypto_tls.py    # 加密和TLS工具
│   └── 📄 database.py      # SQLite数据库管理
├── 📂 server/              # 服务端核心模块
│   ├── 📄 auth.py          # 用户认证和授权
│   ├── 📄 core.py          # WebSocket服务器核心
│   ├── 📄 directory.py     # 好友关系和在线状态
│   ├── 📄 history.py       # 聊天历史记录管理
│   ├── 📄 shema.py         # 数据模型定义
│   └── 📂 data/            # 数据文件存储目录
├── 📂 client/              # 客户端模块
│   ├── 📄 core.py          # 客户端核心逻辑
│   ├── 📄 messenger.py     # 消息处理
│   ├── 📄 contacts.py      # 联系人管理
│   └── 📂 ui/              # 用户界面
├── 📄 requirements.txt     # Python依赖包
├── 📄 start_server.py      # 服务器启动脚本
├── 📄 test_server.py       # 功能测试脚本
└── 📄 README.md           # 项目说明文档
```

## 🚀 快速开始

### 1. 环境准备

**系统要求:**
- Python 3.8+
- Windows/Linux/macOS

**安装依赖:**
```bash
cd projects
pip install -r requirements.txt
```

### 2. 启动服务器

**默认启动:**
```bash
python start_server.py
```

**自定义配置:**
```bash
# 指定主机和端口
python start_server.py --host 0.0.0.0 --port 8765

# 启用调试模式
python start_server.py --debug
```

**成功启动标志:**
```
2024-XX-XX XX:XX:XX - root - INFO - 启动服务器: 0.0.0.0:8765
2024-XX-XX XX:XX:XX - root - INFO - 数据库初始化完成
2024-XX-XX XX:XX:XX - root - INFO - WebSocket服务器已启动，监听 0.0.0.0:8765
```

### 3. 启动客户端

```bash
cd client
python main.py
```

### 4. 功能测试

运行自动化测试脚本：
```bash
python test_server.py
```

预期输出：
```
开始测试 projects 模块...
==================================================
测试配置模块...
服务器配置: localhost:8765
配置模块: 成功

测试数据库模块...
数据库初始化: 成功
创建数据库用户: 成功

测试认证模块...
注册用户: 成功
密码验证: 成功
==================================================
测试完成！
```

## ⚙️ 配置说明

### 服务器配置 (`common/config.py`)

```python
# 网络配置
SERVER_HOST = 'localhost'        # 服务器监听地址
SERVER_PORT = 8765              # 服务器监听端口

# 数据库配置
DATABASE_PATH = "server/data/secure_chat.db"
USERS_JSON_PATH = "server/data/users.json"
CONTACTS_JSON_PATH = "server/data/contacts.json"

# 安全配置
RSA_KEY_SIZE = 2048             # RSA密钥长度
PBKDF2_ITERATIONS = 100000      # 密码哈希迭代次数
SALT_BYTES = 16                 # 盐值长度

# 连接配置
MAX_CONNECTIONS = 1000          # 最大并发连接数
HEARTBEAT_INTERVAL = 30         # 心跳间隔(秒)
CONNECTION_TIMEOUT = 60         # 连接超时(秒)
```

### 日志配置

系统自动生成日志文件 `server.log`，包含以下信息：
- 用户登录/登出事件
- 消息发送记录
- 错误和异常信息
- 服务器状态变化

## 📊 数据存储

### 双重存储架构

1. **JSON文件存储** (兼容性)
   - `server/data/users.json` - 用户账户信息
   - `server/data/contacts.json` - 好友关系数据

2. **SQLite数据库** (性能与一致性)
   - 用户表 (`users`)
   - 联系人表 (`contacts`)
   - 消息表 (`messages`)
   - 会话表 (`sessions`)
   - 群组表 (`groups`)

### 数据库表结构

```sql
-- 用户表
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    public_key TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_online BOOLEAN DEFAULT FALSE,
    last_activity TEXT,
    ip_address TEXT,
    port INTEGER
);

-- 消息表
CREATE TABLE messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL,
    receiver_id INTEGER,
    group_id TEXT,
    message_type TEXT DEFAULT 'text',
    content TEXT NOT NULL,
    is_encrypted BOOLEAN DEFAULT FALSE,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
```

## 🔌 API 接口文档

### WebSocket 消息协议

#### 客户端 → 服务器

| 消息类型 | Tag | 描述 | 参数 |
|---------|-----|------|------|
| Register | 1 | 用户注册 | `username`, `secret`, `email` |
| Login | 2 | 用户登录 | `username`, `secret` |
| Logout | 3 | 用户登出 | `username` |
| GetDirectory | 4 | 获取好友列表 | - |
| GetHistory | 5 | 获取聊天历史 | `chat_id` |
| Message | 11 | 发送消息 | `source_id`, `dest_id`, `content` |

#### 服务器 → 客户端

| 消息类型 | Tag | 描述 | 返回数据 |
|---------|-----|------|----------|
| SuccessRegister | 21 | 注册成功 | `username`, `user_id` |
| SuccessLogin | 22 | 登录成功 | `username`, `user_id` |
| FailRegister | 28 | 注册失败 | `error_type` |
| FailLogin | 29 | 登录失败 | `error_type` |
| Directory | 26 | 好友列表 | `data` (JSON) |
| History | 25 | 聊天历史 | `data` (JSON) |

### 消息示例

**登录请求:**
```json
{
    "tag": 2,
    "username": "alice",
    "secret": "password123",
    "time": 1640995200
}
```

**登录成功响应:**
```json
{
    "tag": 22,
    "username": "alice",
    "user_id": 1,
    "time": 1640995201
}
```

**发送消息:**
```json
{
    "tag": 11,
    "message_id": "msg_123",
    "source_id": "alice",
    "dest_id": "bob",
    "content": "Hello, Bob!",
    "time": 1640995300
}
```

## 🔒 安全特性

### 密码安全
- **PBKDF2算法**: 100,000次迭代，SHA-256哈希
- **随机盐值**: 每个密码使用独立的16字节盐值
- **常量时间比较**: 防止时序攻击

### 会话管理
- **唯一会话ID**: UUID4生成的会话标识
- **自动过期**: 长时间无活动自动断开
- **状态同步**: 实时更新用户在线状态

### 数据保护
- **原子操作**: 防止文件写入过程中的数据损坏
- **输入验证**: 严格的参数验证和类型检查
- **错误隔离**: 异常处理防止系统崩溃

## 🛠️ 开发指南

### 代码结构原则

1. **模块分离**: 按功能划分模块，降低耦合
2. **接口统一**: 标准化的消息格式和错误处理
3. **可扩展性**: 支持新功能的插件式添加

### 添加新功能

1. **定义消息类型**: 在 `shema.py` 中添加新的数据类
2. **实现处理逻辑**: 在 `core.py` 中添加处理函数
3. **更新路由**: 在消息分发器中注册新类型
4. **编写测试**: 在 `test_server.py` 中添加测试用例

### 调试技巧

**启用详细日志:**
```bash
python start_server.py --debug
```

**数据库检查:**
```bash
sqlite3 server/data/secure_chat.db
.tables
.schema users
SELECT * FROM users;
```

**网络连接测试:**
```bash
# 使用 wscat 工具测试WebSocket连接
wscat -c ws://localhost:8765
```

## 🔧 故障排除

### 常见问题

**Q: 服务器启动失败 "Address already in use"**
```bash
# 检查端口占用
netstat -ano | findstr :8765
# 或使用不同端口
python start_server.py --port 8766
```

**Q: 客户端连接被拒绝**
```bash
# 检查防火墙设置
# 确认服务器地址和端口配置
# 查看服务器日志文件
```

**Q: 数据库初始化失败**
```bash
# 检查目录权限
# 删除损坏的数据库文件
rm server/data/secure_chat.db
# 重新启动服务器
```


 