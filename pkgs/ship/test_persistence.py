#!/usr/bin/env python3
"""
Test script to verify persistence and recovery functionality.
"""

import asyncio
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_persistence():
    """测试持久化和恢复功能"""
    from app.components.user_manager import (
        UserManager,
        save_session_users,
        load_session_users,
        save_user_info,
        load_users_info,
        session_users,
    )
    
    logger.info("=== Testing Persistence Functionality ===")
    
    # Test 1: 创建用户
    logger.info("\n1. Creating test users...")
    session_id_1 = "test_session_001"
    session_id_2 = "test_session_002"
    
    username_1 = await UserManager.create_session_user(session_id_1)
    logger.info(f"Created user for session {session_id_1}: {username_1}")
    
    username_2 = await UserManager.create_session_user(session_id_2)
    logger.info(f"Created user for session {session_id_2}: {username_2}")
    
    # Test 2: 验证数据已保存
    logger.info("\n2. Verifying metadata files...")
    from app.components.user_manager import SESSION_USERS_FILE, USERS_INFO_FILE
    
    if SESSION_USERS_FILE.exists():
        logger.info(f"✓ Session users file exists: {SESSION_USERS_FILE}")
        with open(SESSION_USERS_FILE, 'r') as f:
            import json
            data = json.load(f)
            logger.info(f"  Content: {data}")
    else:
        logger.error(f"✗ Session users file not found")
    
    if USERS_INFO_FILE.exists():
        logger.info(f"✓ Users info file exists: {USERS_INFO_FILE}")
        with open(USERS_INFO_FILE, 'r') as f:
            import json
            data = json.load(f)
            logger.info(f"  Content: {json.dumps(data, indent=2)}")
    else:
        logger.error(f"✗ Users info file not found")
    
    # Test 3: 模拟容器重启 - 清空内存数据
    logger.info("\n3. Simulating container restart (clearing in-memory data)...")
    session_users.clear()
    logger.info(f"  In-memory session_users cleared: {session_users}")
    
    # Test 4: 恢复用户
    logger.info("\n4. Restoring users from metadata...")
    restored_count = await UserManager.restore_all_users()
    logger.info(f"  Restored {restored_count} users")
    logger.info(f"  Current session_users: {session_users}")
    
    # Test 5: 验证用户可用
    logger.info("\n5. Verifying restored users...")
    user_1_restored = UserManager.get_session_user(session_id_1)
    user_2_restored = UserManager.get_session_user(session_id_2)
    
    if user_1_restored == username_1:
        logger.info(f"✓ Session {session_id_1} -> {user_1_restored} (restored correctly)")
    else:
        logger.error(f"✗ Session {session_id_1} restoration failed")
    
    if user_2_restored == username_2:
        logger.info(f"✓ Session {session_id_2} -> {user_2_restored} (restored correctly)")
    else:
        logger.error(f"✗ Session {session_id_2} restoration failed")
    
    # Test 6: 验证用户账户存在
    logger.info("\n6. Verifying Linux user accounts...")
    import pwd
    try:
        pwd_info_1 = pwd.getpwnam(username_1)
        logger.info(f"✓ User {username_1} exists with UID {pwd_info_1.pw_uid}")
    except KeyError:
        logger.error(f"✗ User {username_1} not found in system")
    
    try:
        pwd_info_2 = pwd.getpwnam(username_2)
        logger.info(f"✓ User {username_2} exists with UID {pwd_info_2.pw_uid}")
    except KeyError:
        logger.error(f"✗ User {username_2} not found in system")
    
    logger.info("\n=== Test Completed ===")


if __name__ == "__main__":
    asyncio.run(test_persistence())
