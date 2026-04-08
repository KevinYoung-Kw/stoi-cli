#!/usr/bin/env python3
"""
STOI Rich CLI - 增强版屎量分析仪

集成 Rich UI 组件，提供专业的终端界面

Usage:
    python3 stoi_rich.py analyze --session <id> [--dashboard]
    python3 stoi_rich.py demo
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint

from ui import DisplayMode, LayoutManager
from ui.theme import STOI_THEME
from ui.components import LiveProgressTracker


def demo_live_progress():
    """演示实时进度 - 模拟 Claude Code 调用时的场景"""
    console = Console()

    console.print(Panel(
        "[bold cyan]💩 STOI 实时分析演示[/bold cyan]\n"
        "模拟 Claude Code 调用 CLI 时的进度显示",
        border_style="cyan"
    ))

    with LiveProgressTracker("正在分析 Token 效率...") as tracker:
        # 阶段 1: 数据加载
        tracker.update(10, "加载会话数据...")
        time.sleep(0.5)

        # 阶段 2: Token 统计
        tracker.update(25, "统计 Token 消耗...")
        time.sleep(0.7)

        # 阶段 3: LLM 评估
        tracker.update(50, "调用 DashScope 评估...")
        time.sleep(1.0)

        # 阶段 4: 生成报告
        tracker.update(80, "生成可视化报告...")
        time.sleep(0.5)

        # 完成
        tracker.update(100, "分析完成！")
        time.sleep(0.3)

    console.print("\n[green]✓[/green] 分析完成！\n")


def demo_compact_mode():
    """演示简洁模式"""
    console = Console()

    console.print(Panel(
        "[bold]💩 简洁模式演示[/bold]",
        border_style="cyan"
    ))

    # 模拟数据
    data = {
        "session_id": "demo_session_compact",
        "evaluation": {
            "grade": "S",
            "stoi_index": 95.0,
            "waste_ratio": 0.05,
            "problem_solving": 5,
            "code_quality": 5,
            "information_density": 4,
            "context_efficiency": 5,
            "summary": "代码结构清晰，逻辑严谨，无明显冗余。建议继续保持！",
            "advice": "🌸 太棒了！你的代码清新脱俗，继续保持！"
        }
    }

    manager = LayoutManager(DisplayMode.COMPACT)
    manager.render(data)


def demo_dashboard_mode():
    """演示仪表盘模式"""
    console = Console()

    console.print(Panel(
        "[bold]💩 仪表盘模式演示[/bold]",
        border_style="cyan"
    ))

    # 模拟数据
    data = {
        "session_id": "demo_session_dashboard",
        "timestamp": "2026-04-08T14:30:00",
        "evaluation": {
            "grade": "C",
            "stoi_index": 45.0,
            "waste_ratio": 0.55,
            "problem_solving": 3,
            "code_quality": 4,
            "information_density": 2,
            "context_efficiency": 3,
            "summary": "回复冗长且缺乏实质性内容，信息密度较低。",
            "advice": "💩 开始有屎了！建议检查是否有冗余代码或废话。"
        }
    }

    manager = LayoutManager(DisplayMode.DASHBOARD)
    manager.render(data)


def demo_comparison():
    """对比两种模式"""
    console = Console()

    console.print(Panel(
        "[bold]💩 双模式对比[/bold]",
        border_style="cyan"
    ))

    # 同一数据，两种展示
    data = {
        "session_id": "comparison_demo",
        "evaluation": {
            "grade": "A",
            "stoi_index": 85.0,
            "waste_ratio": 0.15,
            "problem_solving": 5,
            "code_quality": 4,
            "information_density": 4,
            "context_efficiency": 5,
            "summary": "整体表现优秀，只有轻微的优化空间。",
            "advice": "✨ 表现优秀！只有轻微的优化空间。"
        }
    }

    console.print("\n[bold cyan]简洁模式:[/bold cyan]\n")
    manager = LayoutManager(DisplayMode.COMPACT)
    manager.render(data)

    console.print("\n[bold cyan]仪表盘模式:[/bold cyan]\n")
    manager = LayoutManager(DisplayMode.DASHBOARD)
    manager.render(data)


def analyze_with_progress(session_id: str, dashboard: bool = False):
    """分析会话并显示进度"""
    console = Console()

    # 模拟分析流程
    with LiveProgressTracker("正在分析 Token 效率...") as tracker:
        tracker.update(10, "加载会话数据...")
        time.sleep(0.3)

        tracker.update(30, "统计 Token 消耗...")
        time.sleep(0.3)

        tracker.update(60, "调用 DashScope 评估...")
        time.sleep(0.5)

        tracker.update(90, "生成可视化报告...")
        time.sleep(0.3)

        tracker.update(100, "完成！")

    # 显示结果
    mode = DisplayMode.DASHBOARD if dashboard else DisplayMode.COMPACT

    # 模拟评估结果
    import random
    waste_ratio = random.uniform(0.1, 0.7)
    stoi_index = (1 - waste_ratio) * 100

    grade = "S" if stoi_index >= 90 else "A" if stoi_index >= 80 else "B" if stoi_index >= 60 else "C" if stoi_index >= 40 else "D"

    data = {
        "session_id": session_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "evaluation": {
            "grade": grade,
            "stoi_index": stoi_index,
            "waste_ratio": waste_ratio,
            "problem_solving": random.randint(3, 5),
            "code_quality": random.randint(3, 5),
            "information_density": random.randint(2, 5),
            "context_efficiency": random.randint(3, 5),
            "summary": f"分析完成，等级{grade}，{'表现优秀！' if grade in ['S', 'A'] else '有改进空间。'}",
            "advice": "建议优化信息密度，减少冗余内容。" if waste_ratio > 0.3 else "继续保持！"
        }
    }

    manager = LayoutManager(mode)
    manager.render(data)


def main():
    parser = argparse.ArgumentParser(
        description="💩 STOI Rich CLI - 屎量分析仪",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python3 stoi_rich.py demo              # 运行所有演示
    python3 stoi_rich.py demo --progress   # 演示实时进度
    python3 stoi_rich.py demo --compact    # 演示简洁模式
    python3 stoi_rich.py demo --dashboard  # 演示仪表盘模式
    python3 stoi_rich.py demo --compare    # 对比两种模式

    python3 stoi_rich.py analyze --session test_session
    python3 stoi_rich.py analyze --session test_session --dashboard
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # demo 命令
    demo_parser = subparsers.add_parser('demo', help='运行演示')
    demo_parser.add_argument('--progress', action='store_true', help='实时进度演示')
    demo_parser.add_argument('--compact', action='store_true', help='简洁模式演示')
    demo_parser.add_argument('--dashboard', action='store_true', help='仪表盘模式演示')
    demo_parser.add_argument('--compare', action='store_true', help='对比演示')

    # analyze 命令
    analyze_parser = subparsers.add_parser('analyze', help='分析会话')
    analyze_parser.add_argument('--session', '-s', required=True, help='会话ID')
    analyze_parser.add_argument('--dashboard', '-d', action='store_true', help='使用仪表盘模式')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == 'demo':
        # 如果没有指定具体演示，运行全部
        if not any([args.progress, args.compact, args.dashboard, args.compare]):
            demo_live_progress()
            print("\n" + "=" * 60 + "\n")
            demo_compact_mode()
            print("\n" + "=" * 60 + "\n")
            demo_dashboard_mode()
        else:
            if args.progress:
                demo_live_progress()
            if args.compact:
                demo_compact_mode()
            if args.dashboard:
                demo_dashboard_mode()
            if args.compare:
                demo_comparison()

    elif args.command == 'analyze':
        analyze_with_progress(args.session, args.dashboard)


if __name__ == "__main__":
    main()
