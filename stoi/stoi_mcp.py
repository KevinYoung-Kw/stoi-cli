#!/usr/bin/env python3
"""
stoi_mcp.py — STOI MCP Server
让 Claude Code 直接调用 STOI 分析自己的 session

启动:
  python3 stoi_mcp.py

在 Claude Code 的 MCP 配置中添加:
  {
    "mcpServers": {
      "stoi": {
        "command": "python3",
        "args": ["/path/to/stoi_mcp.py"]
      }
    }
  }

或者用 Claude Code /mcp 命令添加。

可用工具:
  stoi_report     分析指定 session 文件，返回含屎量报告
  stoi_latest     分析最新 session，返回报告 + 建议
  stoi_insights   基于 session 数据用 LLM 给出改进建议
  stoi_blame      分析 System Prompt，定位 Cache Miss 元凶
"""

import json
import sys
import os
from pathlib import Path

# Ensure STOI modules are importable regardless of working directory
sys.path.insert(0, str(Path(__file__).parent.resolve()))

# MCP protocol over stdin/stdout
def send(obj: dict):
    print(json.dumps(obj, ensure_ascii=False), flush=True)

def recv() -> dict:
    line = sys.stdin.readline()
    if not line:
        return {}
    return json.loads(line.strip())


TOOLS = [
    {
        "name": "stoi_latest",
        "description": "分析你的最新 Claude Code session，返回含屎量报告和 AI 改进建议。在想知道'我最近用 Claude Code 的效率怎么样'时调用。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "with_insights": {
                    "type": "boolean",
                    "description": "是否同时生成 AI 改进建议（需要 LLM API key，慢约 10 秒）",
                    "default": False,
                }
            },
        }
    },
    {
        "name": "stoi_report",
        "description": "分析指定的 Claude Code session 文件，返回详细含屎量报告。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_path": {
                    "type": "string",
                    "description": "session JSONL 文件路径（不填则自动选最新）",
                },
                "with_insights": {
                    "type": "boolean",
                    "default": False,
                }
            },
        }
    },
    {
        "name": "stoi_insights",
        "description": "基于 STOI 分析数据，调用 LLM + 知识库给出具体的 Claude Code 优化建议。在想知道'我应该怎么改才能少花 token'时调用。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_path": {
                    "type": "string",
                    "description": "session 文件路径（不填则用最新）",
                }
            },
        }
    },
    {
        "name": "stoi_overview",
        "description": "查看所有历史 Claude Code session 的全局 Token 效率报告。包含总消息数、全局含屎量、缓存命中率、模型使用分布、近期活动趋势、重复发送检测。在想知道'我整体的 token 使用效率如何'时调用。",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "stoi_blame",
        "description": "分析 System Prompt 内容，找出导致 KV Cache 失效的动态字段（时间戳、UUID、绝对路径等）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "system_prompt": {
                    "type": "string",
                    "description": "要分析的 System Prompt 内容",
                }
            },
            "required": ["system_prompt"],
        }
    },
]


def handle_tool(name: str, args: dict) -> str:
    """执行工具调用，返回文本结果"""
    try:
        if name == "stoi_latest":
            return _tool_latest(args.get("with_insights", False))

        elif name == "stoi_report":
            path = args.get("session_path")
            return _tool_report(path, args.get("with_insights", False))

        elif name == "stoi_insights":
            path = args.get("session_path")
            return _tool_insights(path)

        elif name == "stoi_overview":
            return _tool_overview()

        elif name == "stoi_blame":
            return _tool_blame(args.get("system_prompt", ""))

        else:
            return f"未知工具: {name}"

    except Exception as e:
        return f"执行失败: {e}"


def _tool_latest(with_insights: bool) -> str:
    from stoi_core import analyze, find_claude_sessions

    files = find_claude_sessions(1)
    if not files:
        return "未找到 Claude Code session。请先使用 Claude Code 产生对话。"

    report = analyze(files[0], llm_enabled=with_insights)
    return _format_report(report, with_insights)


def _tool_report(path, with_insights: bool) -> str:
    from stoi_core import analyze, find_claude_sessions

    if path:
        p = Path(path)
        if not p.exists():
            return f"文件不存在: {path}"
    else:
        files = find_claude_sessions(1)
        if not files:
            return "未找到 Claude Code session"
        p = files[0]

    report = analyze(p, llm_enabled=with_insights)
    return _format_report(report, with_insights)


def _tool_insights(path=None) -> str:
    from stoi_core import analyze, find_claude_sessions
    from stoi_advisor import get_suggestions

    if path:
        p = Path(path)
        if not p.exists():
            return f"文件不存在: {path}"
    else:
        files = find_claude_sessions(1)
        if not files:
            return "未找到 Claude Code session"
        p = files[0]

    report = analyze(p, llm_enabled=False)
    if not report.valid_turns:
        return "Session 为空或无法解析"

    suggestions = get_suggestions(report)
    if not suggestions:
        return "建议生成失败，请检查 stoi config 中的 API key 配置"

    result = f"# STOI Insights — {report.session_name}\n\n"
    result += f"**含屎量**: {report.avg_stoi_score:.1f}% ({report.stoi_level})  "
    result += f"**缓存命中**: {report.avg_cache_hit_rate:.1f}%  "
    result += f"**花费**: ${report.total_cost_actual:.4f}\n\n"
    result += "## AI 改进建议（基于知识库）\n\n"
    for s in suggestions:
        result += s + "\n"
    return result


def _tool_overview() -> str:
    """全局 Token 效率报告"""
    from stoi_core import get_global_efficiency_report
    r = get_global_efficiency_report()
    if "error" in r:
        return r["error"]

    stoi = r["global_stoi"]
    emoji = "✅" if stoi < 30 else "🟡" if stoi < 50 else "🟠" if stoi < 75 else "💩"

    result = f"# STOI 全局报告\n\n"
    result += f"| 指标 | 数值 |\n|------|------|\n"
    result += f"| 总 sessions | {r['total_sessions']} |\n"
    result += f"| 总消息数 | {r['total_messages']:,} |\n"
    result += f"| 全局含屎量 | {emoji} **{stoi:.1f}%** |\n"
    result += f"| 缓存命中率 | {r['global_hit_rate']:.1f}% |\n"
    result += f"| 平均 session 长度 | {r['avg_session_len']:.0f} 条消息 |\n"
    result += f"| 重复发送消息 | {r['repeat_messages']} 条 |\n\n"
    result += "## 模型使用效率\n\n"
    for m in r["model_stats"][:3]:
        result += f"- **{m['model']}**: 命中率 {m['hit_rate']:.1f}%，{m['input']/1e9:.2f}B input tokens\n"
    result += "\n## 主要优化建议\n\n"
    if stoi > 50:
        result += f"- 全局含屎量 {stoi:.0f}%，建议检查 CLAUDE.md 是否频繁变动，并定期运行 /compact\n"
    if r["avg_session_len"] > 1000:
        result += f"- 平均 session {r['avg_session_len']:.0f} 条消息过长，超过 800 条时运行 /compact\n"
    if r["repeat_messages"] > 20:
        result += f"- {r['repeat_messages']} 条消息被重复发送，补充具体指令比原样重发效果更好\n"
    if not any([stoi > 50, r["avg_session_len"] > 1000, r["repeat_messages"] > 20]):
        result += "- 整体使用模式健康，继续保持\n"
    return result


def _tool_blame(system_prompt: str) -> str:
    if not system_prompt.strip():
        return "请提供 System Prompt 内容"

    # 使用 stoi_core 中的模式检测
    import re
    patterns = {
        "时间戳注入": r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}',
        "随机 UUID":  r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        "绝对路径":   r'/Users/[A-Za-z0-9_]+|/home/[A-Za-z0-9_]+',
        "进程 ID":    r'\bpid[:\s=]+\d+',
    }

    found = []
    for name, pattern in patterns.items():
        matches = re.findall(pattern, system_prompt, re.IGNORECASE)
        if matches:
            found.append(f"- **{name}** (示例: `{matches[0][:50]}`)\n  → 每次变化导致 KV Cache 全部失效，建议移至 user message")

    if not found:
        return "✅ 未发现明显的 Cache-busting 动态字段，System Prompt 结构干净。"

    result = f"# stoi blame 分析结果\n\n"
    result += f"发现 **{len(found)} 个** 造成 Cache Miss 的动态字段：\n\n"
    result += "\n".join(found)
    result += "\n\n**修复优先级**：时间戳 > UUID > 绝对路径 > PID\n"
    result += "**修复方法**：将动态字段从 system prompt 移至每轮的 user message\n"
    return result


def _format_report(report, with_insights: bool) -> str:
    """把 STOIReport 格式化为 markdown 文本"""
    emoji_map = {"CLEAN": "✅", "MILD_SHIT": "🟡", "SHIT_OVERFLOW": "🟠", "DEEP_SHIT": "💩"}
    emoji = emoji_map.get(report.stoi_level, "")

    result = f"# STOI Report — {report.session_name}\n\n"
    result += f"| 指标 | 数值 |\n|------|------|\n"
    result += f"| 含屎量 | {emoji} **{report.avg_stoi_score:.1f}%** ({report.stoi_level}) |\n"
    result += f"| 缓存命中率 | {report.avg_cache_hit_rate:.1f}% |\n"
    result += f"| 有效输出率 | {report.effectiveness_rate:.1f}% |\n"
    result += f"| 实际花费 | ${report.total_cost_actual:.4f} |\n"
    result += f"| Cache 节省 | ${report.total_cost_saved:.4f} |\n"
    result += f"| 总轮次 | {report.valid_turns} |\n\n"

    if report.issues:
        result += "## 发现的问题\n\n"
        for issue in report.issues:
            sev = {"HIGH": "🔴", "MED": "🟡", "LOW": "🟢"}.get(issue["severity"], "")
            result += f"**{sev} {issue['title']}**\n"
            result += f"- 详情：{issue['detail']}\n"
            result += f"- 建议：{issue['fix']}\n\n"
    else:
        result += "## 无明显问题\n\n该 session 整体效率良好。\n\n"

    if with_insights and report.llm_suggestions:
        result += "## AI 改进建议\n\n"
        for s in report.llm_suggestions:
            result += s + "\n"

    return result


# ── MCP 协议主循环 ─────────────────────────────────────────────────────────────
def run_mcp_server():
    """MCP 协议主循环（可被外部导入调用）"""
    # 检查是否有预读取的初始化消息（由 stoi.py 自动模式检测注入）
    init_msg = getattr(sys, "_mcp_first_message", None)
    if init_msg is None:
        init_msg = recv()

    if init_msg.get("method") == "initialize":
        send({
            "jsonrpc": "2.0",
            "id": init_msg.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "stoi", "version": "2.0"},
            }
        })

    # 主循环
    while True:
        msg = recv()
        if not msg:
            break

        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "tools/list":
            send({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}})

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            result_text = handle_tool(tool_name, tool_args)
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}],
                    "isError": False,
                }
            })

        elif method == "notifications/initialized":
            pass  # 忽略

        else:
            if msg_id:
                send({"jsonrpc": "2.0", "id": msg_id,
                      "error": {"code": -32601, "message": f"Unknown method: {method}"}})


def main():
    run_mcp_server()


if __name__ == "__main__":
    main()
