#!/usr/bin/env python3
"""
简单的服务器功能测试脚本
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_auth():
    """测试认证模块"""
    print("测试认证模块...")
    
    from server import auth
    
    # 测试注册
    try:
        success = auth.register_user(
            username="test_user",
            password="test_password",
            email="test@example.com",
            pubkey_pem=""
        )
        print(f"注册用户: {'成功' if success else '失败'}")
    except Exception as e:
        print(f"注册失败: {e}")
    
    # 测试验证
    try:
        verified = auth.verify_password("test_user", "test_password")
        print(f"密码验证: {'成功' if verified else '失败'}")
    except Exception as e:
        print(f"验证失败: {e}")

def test_database():
    """测试数据库模块"""
    print("测试数据库模块...")
    
    try:
        from common.database import DatabaseManager
        
        db = DatabaseManager()
        print("数据库初始化: 成功")
        
        # 测试创建用户
        user_id = db.create_user(
            username="db_test_user",
            email="dbtest@example.com",
            password_hash="test_hash",
            salt="test_salt"
        )
        print(f"创建数据库用户: {'成功' if user_id else '失败'}")
        
    except Exception as e:
        print(f"数据库测试失败: {e}")

def test_config():
    """测试配置模块"""
    print("测试配置模块...")
    
    try:
        from common.config import SERVER_HOST, SERVER_PORT
        print(f"服务器配置: {SERVER_HOST}:{SERVER_PORT}")
        print("配置模块: 成功")
    except Exception as e:
        print(f"配置模块失败: {e}")

def main():
    """主测试函数"""
    print("开始测试 projects 模块...")
    print("=" * 50)
    
    test_config()
    print()
    
    test_database()
    print()
    
    test_auth()
    print()
    
    print("=" * 50)
    print("测试完成！")

if __name__ == "__main__":
    main() 