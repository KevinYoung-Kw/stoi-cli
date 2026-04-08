#!/usr/bin/env python3
"""
stoi_analyze.py — 离线 Claude Code 会话分析器
直接读取 ~/.claude/projects/ 无需代理

用法：
  python3 stoi_analyze.py                       # 自动找最新会话
  python3 stoi_analyze.py <path/to/file.jsonl>  # 指定文件
  python3 stoi_analyze.py --all                 # 分析所有会话
  python3 stoi_analyze.py --top 20              # 分析最近 20 个文件
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from stoi_engine import (
    calc_stoi, calc_stoi_score,
    SHIT_THRESHOLDS, SHIT_EMOJI,
    get_score_color, get_level_display, TTS_MESSAGES,
)

CLAUDE_PROJECTS = Path("~/.claude/projects").expanduser()
LOG_FILE = Path("~/.stoi/sessions.jsonl").expanduser()
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

console = Console()


def parse_claude_code_session(path: str) -> list[dict]:
    """
    解析 Claude Code JSONL 会话文件。
    每行结构示例（type=assistant，含 usage）：
    {
      "type": "assistant",
      "message": {
        "role": "assistant",
        "usage": {
          "input_tokens": 23487,
          "cache_creation_input_tokens": 0,
          "cache_read_input_tokens": 19234,
          "output_tokens": 841
        }
      },
      "timestamp": "2026-03-12T09:40:19.768Z",
      "sessionId": "b89f6208-...",
      ...
    }
    """
    records = []
    path = Path(path)

    if not path.exists():
        console.print(f"[red]文件不存在: {path}[/red]")
        return records

    try:
        with open(path, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # 同时收集 user 消息用于 L4 有效性标注
                if obj.get("type") == "human" or obj.get("message", {}).get("role") == "user":
                    msg_content = ""
                    content_raw = obj.get("message", {}).get("content", "")
                    if isinstance(content_raw, str):
                        msg_content = content_raw[:100]
                    elif isinstance(content_raw, list):
                        for c in content_raw:
                            if isinstance(c, dict) and c.get("type") == "text":
                                msg_content = c.get("text", "")[:100]
                                break
                    records.append({"role": "user", "content": msg_content, "stoi": {"is_baseline": True, "stoi_score": 0, "level": "CLEAN", "cache_hit_rate": 0, "input_tokens": 0, "output_tokens": 0, "wasted_tokens": 0, "new_tokens": 0, "cache_read": 0, "cache_creation": 0}, "ts": "", "model": "", "session": "", "usage": {}})
                    continue

                # 只处理 assistant 类型且有 usage 的条目
                if obj.get("type") != "assistant":
                    continue

                msg = obj.get("message", {})
                usage = msg.get("usage", {})

                # 必须有 input_tokens
                input_tokens = usage.get("input_tokens", 0)
                if input_tokens == 0:
                    continue

                # 解析时间戳
                ts_raw = obj.get("timestamp", "")
                try:
                    if ts_raw:
                        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        ts_str = "unknown"
                except Exception:
                    ts_str = ts_raw[:19] if ts_raw else "unknown"

                stoi = calc_stoi(usage, turn_index=len(records))

                record = {
                    "ts":        ts_str,
                    "model":     msg.get("model", "unknown"),
                    "session":   obj.get("sessionId", path.stem)[:8],
                    "stoi":      stoi,
                    "usage":     usage,
                    "source":    str(path),
                }
                records.append(record)

    except Exception as e:
        console.print(f"[red]解析失败 {path}: {e}[/red]")

    return records


def find_latest_session() -> Optional[Path]:
    """找到最新修改的 Claude Code 会话文件"""
    if not CLAUDE_PROJECTS.exists():
        return None

    all_files = list(CLAUDE_PROJECTS.rglob("*.jsonl"))
    if not all_files:
        return None

    # 按修改时间排序，取最新
    all_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return all_files[0]


def find_recent_sessions(top: int = 10) -> list[Path]:
    """找到最近修改的 N 个会话文件"""
    if not CLAUDE_PROJECTS.exists():
        return []

    all_files = list(CLAUDE_PROJECTS.rglob("*.jsonl"))
    all_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return all_files[:top]


def parse_proxy_log(path: str) -> list[dict]:
    """解析 STOI Proxy 生成的 JSONL 日志"""
    from stoi_engine import calc_stoi
    records = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    usage = obj.get("usage", {})
                    if not usage:
                        continue
                    stoi = calc_stoi(usage, turn_index=len(records))
                    records.append({
                        "ts":      obj.get("ts", ""),
                        "model":   obj.get("model", ""),
                        "session": "proxy",
                        "stoi":    stoi,
                        "usage":   usage,
                        "source":  path,
                    })
                except Exception:
                    continue
    except Exception:
        pass
    return records


def write_to_log(records: list[dict]):
    """写入到 ~/.stoi/sessions.jsonl"""
    if not records:
        return
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    console.print(f"[dim]📝 已写入 {len(records)} 条记录到 {LOG_FILE}[/dim]")


def print_session_report(records: list[dict], source_path: str = ""):
    """打印单个会话的分析报告"""
    if not records:
        console.print("[yellow]该会话无有效 token 使用记录[/yellow]")
        return

    total_input    = sum(r["stoi"]["input_tokens"] for r in records)
    total_output   = sum(r["stoi"]["output_tokens"] for r in records)
    total_cache    = sum(r["stoi"]["cache_read"] for r in records)
    total_wasted   = sum(r["stoi"]["wasted_tokens"] for r in records)
    avg_score      = sum(r["stoi"]["stoi_score"] for r in records) / len(records)
    avg_score      = round(avg_score, 1)

    cache_hit_rate = round(total_cache / total_input * 100, 1) if total_input > 0 else 0.0

    level = "DEEP_SHIT"
    for lvl, (lo, hi) in SHIT_THRESHOLDS.items():
        if lo <= avg_score < hi:
            level = lvl
            break

    color = get_score_color(avg_score)
    emoji = SHIT_EMOJI[level]

    # 标题 Panel
    title_text = Text()
    title_text.append("💩 STOI  ", style="bold #FFB800")
    title_text.append("含屎量分析报告", style="bold white")

    source_short = Path(source_path).name if source_path else "—"
    header = Panel(
        f"[bold #FFB800]文件[/bold #FFB800]: {source_short}\n"
        f"[bold #FFB800]轮次[/bold #FFB800]: {len(records)} 次对话",
        title="[bold #FFB800]💩 STOI 分析报告[/bold #FFB800]",
        border_style="#FFB800",
    )
    console.print(header)

    # 主指标表格
    table = Table(box=box.ROUNDED, border_style="dim", show_header=False, padding=(0, 2))
    table.add_column("指标", style="bold #FFB800", width=18)
    table.add_column("数值", style="white", width=20)
    table.add_column("说明", style="dim", width=30)

    score_bar = make_bar(avg_score, 20)
    table.add_row(
        "平均含屎量",
        f"[bold {color}]{avg_score}%  {emoji}[/bold {color}]",
        f"[{color}]{score_bar}[/{color}]  {level}",
    )
    table.add_row("缓存命中率", f"[green]{cache_hit_rate}%[/green]", "越高越省钱")
    table.add_row("输入 tokens",  f"{total_input:,}", "累计消耗")
    table.add_row("缓存命中",     f"[green]{total_cache:,}[/green]", "复用的部分")
    table.add_row("白白浪费",     f"[red]{total_wasted:,}[/red]", "没命中缓存的")
    table.add_row("输出 tokens",  f"{total_output:,}", "实际产出")

    console.print(table)

    # 逐轮明细（最近 10 轮）
    if len(records) > 1:
        console.print("\n[bold #FFB800]📊 最近对话轮次[/bold #FFB800]")
        detail_table = Table(box=box.SIMPLE, border_style="dim", padding=(0, 1))
        detail_table.add_column("时间", style="dim", width=20)
        detail_table.add_column("含屎量", width=12)
        detail_table.add_column("输入", width=10)
        detail_table.add_column("缓存命中", width=10)
        detail_table.add_column("浪费", width=10)
        detail_table.add_column("等级", width=16)

        for r in records[-10:]:
            s = r["stoi"]
            c = get_score_color(s["stoi_score"])
            detail_table.add_row(
                r["ts"],
                f"[{c}]{s['stoi_score']}%[/{c}]",
                f"{s['input_tokens']:,}",
                f"[green]{s['cache_read']:,}[/green]",
                f"[red]{s['wasted_tokens']:,}[/red]",
                f"{SHIT_EMOJI[s['level']]} {s['level']}",
            )

        console.print(detail_table)

    # 趋势火花线
    if len(records) >= 2:
        scores = [r["stoi"]["stoi_score"] for r in records[-20:]]
        sparkline = make_sparkline(scores)
        console.print(f"\n[bold #FFB800]📈 含屎量趋势[/bold #FFB800]: [white]{sparkline}[/white]  (最近 {len(scores)} 轮)\n")


def make_bar(pct: float, width: int = 20) -> str:
    """生成进度条"""
    filled = int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def make_sparkline(values: list[float]) -> str:
    """生成 sparkline 字符串"""
    if not values:
        return ""
    chars = "▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    if mx == mn:
        return chars[3] * len(values)
    result = ""
    for v in values:
        idx = int((v - mn) / (mx - mn) * 7)
        result += chars[min(idx, 7)]
    return result


def cmd_analyze(args: list[str]):
    """主分析入口"""
    # 解析参数
    all_sessions = "--all" in args
    top_n = 10
    for i, a in enumerate(args):
        if a == "--top" and i + 1 < len(args):
            try:
                top_n = int(args[i + 1])
            except ValueError:
                pass

    # 过滤出路径参数
    paths = [a for a in args if not a.startswith("--") and i != args.index(a) if os.path.exists(a)]
    # 更简洁的路径检测
    explicit_paths = [a for a in args if os.path.exists(a)]

    if explicit_paths:
        # 分析指定文件
        for p in explicit_paths:
            console.print(f"\n[bold #FFB800]🔍 分析文件: {p}[/bold #FFB800]")
            records = parse_claude_code_session(p)
            print_session_report(records, p)
            write_to_log(records)

    elif all_sessions:
        # 分析所有会话（聚合统计）
        all_files = find_recent_sessions(top=9999)
        console.print(f"[bold #FFB800]🔍 分析全部 {len(all_files)} 个会话文件[/bold #FFB800]\n")
        all_records = []
        for f in all_files:
            all_records.extend(parse_claude_code_session(str(f)))
        print_session_report(all_records, f"全部 {len(all_files)} 个文件")
        write_to_log(all_records)

    else:
        # 自动找最近的若干文件
        files = find_recent_sessions(top=top_n)
        if not files:
            console.print("[yellow]⚠ 未找到 Claude Code 会话文件[/yellow]")
            console.print(f"[dim]期望路径: {CLAUDE_PROJECTS}[/dim]")
            return

        console.print(f"\n[bold #FFB800]🔍 分析最近 {len(files)} 个会话文件[/bold #FFB800]")
        all_records = []
        for f in files:
            records = parse_claude_code_session(str(f))
            all_records.extend(records)

        print_session_report(all_records, f"最近 {len(files)} 个文件（共 {len(all_records)} 轮）")
        write_to_log(all_records)

        # 显示最新文件路径
        console.print(f"\n[dim]📂 最新会话: {files[0]}[/dim]")


if __name__ == "__main__":
    cmd_analyze(sys.argv[1:])
