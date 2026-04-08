#!/usr/bin/env python3
"""
STOI 功能测试脚本
确保核心功能正常工作后再进行迭代开发
"""

import os
import sys
import subprocess
from pathlib import Path

# 测试配置
TEST_SESSION_ID = "test_stoi_functional"


def run_command(cmd, env=None):
    """运行命令并返回结果"""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent,
        env=env
    )
    return result.returncode, result.stdout, result.stderr


def test_init():
    """测试初始化"""
    print("🧪 测试: stoi init")
    code, stdout, stderr = run_command("python3 stoi.py init")

    if code == 0 and "初始化完成" in stdout:
        print("  ✅ 初始化成功")
        return True
    else:
        print(f"  ❌ 失败: {stderr}")
        return False


def test_config():
    """测试配置显示"""
    print("🧪 测试: stoi init (配置显示)")
    code, stdout, stderr = run_command("python3 stoi.py init")

    checks = [
        "数据库位置" in stdout,
        "配置位置" in stdout,
        "Rich UI" in stdout,
        "已配置的提供商" in stdout
    ]

    if all(checks):
        print("  ✅ 配置显示正常")
        return True
    else:
        print(f"  ❌ 失败: 缺少必要的配置信息")
        return False


def test_analyze_with_dashscope():
    """测试分析功能 (使用 DashScope)"""
    print("🧪 测试: stoi analyze (需要 DASHSCOPE_API_KEY)")

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("  ⚠️  跳过: 未设置 DASHSCOPE_API_KEY")
        return None

    # 创建测试数据
    env = os.environ.copy()
    env["DASHSCOPE_API_KEY"] = api_key

    # 先创建测试会话
    from stoi import STOIDatabase
    db = STOIDatabase()
    db.create_session(TEST_SESSION_ID)
    db.add_message(TEST_SESSION_ID, 'user', '写一个Python函数，计算斐波那契数列', 20)
    db.add_message(TEST_SESSION_ID, 'assistant', 'def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)', 100)

    # 运行分析
    code, stdout, stderr = run_command(
        f"python3 stoi.py analyze --session {TEST_SESSION_ID}",
        env=env
    )

    checks = [
        "STOI 分析结果" in stdout or "💩" in stdout,
        "维度评分" in stdout or "问题解决度" in stdout,
        "AI 屎评" in stdout or "AI" in stdout
    ]

    if any(checks):
        print("  ✅ 分析功能正常")
        return True
    else:
        print(f"  ❌ 失败: 输出格式异常")
        print(f"     stdout: {stdout[:200]}")
        print(f"     stderr: {stderr[:200]}")
        return False


def test_tts():
    """测试 TTS 功能"""
    print("🧪 测试: stoi tts")
    code, stdout, stderr = run_command('python3 stoi.py tts --message "测试"')

    if code == 0 and "播报" in stdout:
        print("  ✅ TTS 命令正常 (语音播放取决于系统)")
        return True
    else:
        print(f"  ❌ 失败: {stderr}")
        return False


def test_dashboard_mode():
    """测试仪表盘模式"""
    print("🧪 测试: stoi analyze --dashboard")

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("  ⚠️  跳过: 未设置 DASHSCOPE_API_KEY")
        return None

    env = os.environ.copy()
    env["DASHSCOPE_API_KEY"] = api_key

    code, stdout, stderr = run_command(
        f"python3 stoi.py analyze --session {TEST_SESSION_ID} --dashboard",
        env=env
    )

    # 仪表盘模式输出会更复杂，只要没有错误就算成功
    if code == 0:
        print("  ✅ 仪表盘模式正常")
        return True
    else:
        print(f"  ❌ 失败: {stderr}")
        return False


def test_database_persistence():
    """测试数据库持久化"""
    print("🧪 测试: 数据库持久化")

    from stoi import STOIDatabase
    db = STOIDatabase()

    # 创建会话
    session_id = "persistence_test"
    db.create_session(session_id)
    db.add_message(session_id, 'user', 'test', 10)

    # 重新读取
    session = db.get_session(session_id)

    if session and len(session.messages) > 0:
        print("  ✅ 数据库持久化正常")
        return True
    else:
        print("  ❌ 失败: 无法读取持久化数据")
        return False


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("💩 STOI 功能测试套件")
    print("=" * 60)
    print()

    tests = [
        ("初始化", test_init),
        ("配置显示", test_config),
        ("TTS 功能", test_tts),
        ("数据库持久化", test_database_persistence),
        ("分析功能", test_analyze_with_dashscope),
        ("仪表盘模式", test_dashboard_mode),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"  ❌ 异常: {e}")
            results.append((name, False))
        print()

    # 汇总
    print("=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)

    passed = sum(1 for _, r in results if r is True)
    skipped = sum(1 for _, r in results if r is None)
    failed = sum(1 for _, r in results if r is False)

    for name, result in results:
        status = "✅ 通过" if result is True else "⚠️  跳过" if result is None else "❌ 失败"
        print(f"  {status}: {name}")

    print()
    print(f"总计: {passed} 通过, {skipped} 跳过, {failed} 失败")

    if failed == 0:
        print("\n🎉 所有测试通过！STOI 可以正常使用。")
        return True
    else:
        print("\n⚠️  有测试失败，请修复后再进行迭代开发。")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
