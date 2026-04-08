#!/usr/bin/env python3
"""
STOI Proxy — 实时含屎量监控代理
零侵入拦截 Claude Code / OpenCode 的 API 请求，实时分析 Token 效率

用法：
  python3 stoi_proxy.py          # 启动代理 (默认端口 8888)
  export ANTHROPIC_BASE_URL=http://localhost:8888
  # 正常使用 Claude Code，含屎量实时播报

参考：ccswitch 的实时监控设计
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────────────────────────
PROXY_PORT  = 57017
# 从 Claude Code settings 读取真实 upstream，支持 ccswitch 切换的模型
def _get_upstream() -> str:
    settings = Path("~/.claude/settings.json").expanduser()
    try:
        data = json.loads(settings.read_text())
        url = data.get("env", {}).get("ANTHROPIC_BASE_URL", "")
        # 如果已经指向我们自己，取 backup
        backup = Path("~/.stoi/upstream_backup").expanduser()
        if url and "localhost" not in url and "127.0.0.1" not in url:
            return url.rstrip("/")
        elif backup.exists():
            return backup.read_text().strip()
    except Exception:
        pass
    return "https://api.anthropic.com"

UPSTREAM = _get_upstream()
LOG_FILE    = Path("~/.stoi/sessions.jsonl").expanduser()
STATS_FILE  = Path("~/.stoi/realtime_stats.json").expanduser()
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# 实时统计（内存中，每次请求更新）
_realtime_stats = {
    "session_start":   datetime.now().isoformat(),
    "total_requests":  0,
    "total_input":     0,
    "total_output":    0,
    "total_wasted":    0,
    "cache_hits":      0,
    "cache_misses":    0,
    "avg_stoi":        0.0,
    "current_level":   "CLEAN",
    "last_updated":    "",
    "recent":          [],   # 最近 10 条
}


def _save_stats():
    """写入磁盘，供 TUI 轮询读取"""
    STATS_FILE.write_text(
        json.dumps(_realtime_stats, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ── 含屎量计算（与 stoi_engine 对齐）──────────────────────────────────────────
SHIT_THRESHOLDS = {
    "CLEAN":         (0,   30),
    "MILD_SHIT":     (30,  50),
    "SHIT_OVERFLOW": (50,  75),
    "DEEP_SHIT":     (75,  101),
}
TTS_MESSAGES = {
    "CLEAN":         "干净！这才叫工程师。",
    "MILD_SHIT":     "含屎量偏高，你的词元在哭泣。",
    "SHIT_OVERFLOW": "含屎量严重超标，建议立刻停止 Vibe Coding。",
    "DEEP_SHIT":     "警告！深度含屎！你的算力正在窒息！",
}


def calc_stoi(usage: dict, turn_index: int = 1) -> dict:
    new_tokens     = usage.get("input_tokens", 0)
    cache_read     = usage.get("cache_read_input_tokens", 0)
    cache_creation = usage.get("cache_creation_input_tokens", 0)
    output_tokens  = usage.get("output_tokens", 0)
    total_context  = new_tokens + cache_read + cache_creation

    if total_context == 0 or output_tokens == 0:
        return {
            "stoi_score": 0.0, "level": "CLEAN",
            "input_tokens": total_context, "output_tokens": output_tokens,
            "cache_read": cache_read, "cache_creation": cache_creation,
            "wasted_tokens": 0, "cache_hit_rate": 0.0,
            "is_baseline": True,
        }

    cache_hit_rate = round(cache_read / total_context * 100, 1)
    raw_shit = (total_context - cache_read) / total_context * 100
    if cache_creation > 0:
        raw_shit *= (1 - (cache_creation / total_context) * 0.5)

    stoi_score = round(min(raw_shit, 100.0), 1)
    level = "DEEP_SHIT"
    for lvl, (lo, hi) in SHIT_THRESHOLDS.items():
        if lo <= stoi_score < hi:
            level = lvl
            break

    return {
        "stoi_score": stoi_score, "level": level,
        "input_tokens": total_context, "output_tokens": output_tokens,
        "cache_read": cache_read, "cache_creation": cache_creation,
        "wasted_tokens": total_context - cache_read,
        "cache_hit_rate": cache_hit_rate,
        "is_baseline": False,
    }


def speak(level: str):
    msg = TTS_MESSAGES.get(level, "")
    if msg:
        try:
            subprocess.Popen(["say", "-v", "Ting-Ting", msg])
        except Exception:
            pass


def log_and_update(request_body: dict, response_body: dict, stoi: dict):
    """记录到日志，并更新实时统计"""
    global _realtime_stats

    ts = datetime.now().isoformat()

    # 提取 thinking content（L5 分析用）
    thinking_text = ""
    output_text = ""
    content_blocks = response_body.get("content", [])
    for block in content_blocks:
        if isinstance(block, dict):
            if block.get("type") == "thinking":
                thinking_text += block.get("thinking", "")
            elif block.get("type") == "text":
                output_text += block.get("text", "")

    # 提取 user message（L2 feedback 用）
    user_message = ""
    messages = request_body.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                user_message = content[:200]
            elif isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        user_message = c.get("text", "")[:200]
                        break
            break

    record = {
        "ts":           ts,
        "model":        request_body.get("model", "unknown"),
        "stoi":         stoi,
        "usage":        response_body.get("usage", {}),
        "output_text":  output_text[:500] if output_text else "",
        "user_message": user_message,
        # L5: thinking token 分析数据
        "thinking": {
            "has_thinking":    bool(thinking_text),
            "thinking_tokens": len(thinking_text.split()) if thinking_text else 0,
            "thinking_text":   thinking_text[:1000] if thinking_text else "",
        } if thinking_text else None,
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # 更新实时统计
    if not stoi.get("is_baseline"):
        stats = _realtime_stats
        stats["total_requests"] += 1
        stats["total_input"]    += stoi["input_tokens"]
        stats["total_output"]   += stoi["output_tokens"]
        stats["total_wasted"]   += stoi["wasted_tokens"]
        if stoi["cache_hit_rate"] > 50:
            stats["cache_hits"]   += 1
        else:
            stats["cache_misses"] += 1

        # 滚动计算平均含屎量
        recent = stats.get("recent", [])
        recent.append(stoi["stoi_score"])
        recent = recent[-20:]  # 保留最近20条
        stats["recent"] = recent
        stats["avg_stoi"] = round(sum(recent) / len(recent), 1)
        stats["current_level"] = stoi["level"]
        stats["last_updated"] = ts

        _save_stats()


def print_realtime(stoi: dict, request_body: dict):
    """实时打印到终端"""
    score = stoi["stoi_score"]
    level = stoi["level"]
    emoji = {"CLEAN": "✅", "MILD_SHIT": "🟡", "SHIT_OVERFLOW": "🟠", "DEEP_SHIT": "💩"}[level]

    bar_filled = int(score / 100 * 20)
    bar_empty  = 20 - bar_filled
    color_map  = {"CLEAN": "\033[32m", "MILD_SHIT": "\033[33m",
                  "SHIT_OVERFLOW": "\033[33m", "DEEP_SHIT": "\033[31m"}
    color = color_map.get(level, "")
    reset = "\033[0m"
    bar   = f"{color}{'█' * bar_filled}{reset}{'░' * bar_empty}"

    model = request_body.get("model", "")[:20]
    ts    = datetime.now().strftime("%H:%M:%S")

    print(f"\n\033[2m{'─'*60}\033[0m")
    print(f"  {ts}  \033[1m{model}\033[0m")
    print(f"  {color}{score:>5.1f}%{reset}  {bar}  {emoji} {level}")
    print(f"  Input: {stoi['input_tokens']:>8,}  Cache: {stoi['cache_read']:>8,}  "
          f"Out: {stoi['output_tokens']:>6,}")

    # 实时统计
    stats = _realtime_stats
    if stats["total_requests"] > 0:
        print(f"  \033[2m本次会话: {stats['total_requests']}轮 | "
              f"均值: {stats['avg_stoi']:.1f}% | "
              f"累计浪费: {stats['total_wasted']:,} tokens\033[0m")
    print(f"\033[2m{'─'*60}\033[0m")


# ── HTTP 代理服务器 ────────────────────────────────────────────────────────────
async def handle_request(reader, writer):
    """处理单个 HTTP 请求"""
    try:
        import aiohttp

        # 读取请求
        raw = b""
        try:
            raw = await asyncio.wait_for(reader.read(131072), timeout=30)
        except asyncio.TimeoutError:
            writer.close()
            return

        if not raw:
            writer.close()
            return

        # 解析 HTTP
        header_end = raw.find(b"\r\n\r\n")
        if header_end == -1:
            writer.close()
            return

        headers_raw = raw[:header_end].decode("utf-8", errors="replace")
        body_bytes  = raw[header_end + 4:]
        lines = headers_raw.split("\r\n")
        request_line = lines[0] if lines else ""

        # 只处理 POST /v1/messages（Anthropic API）
        if "POST" not in request_line or "/v1/messages" not in request_line:
            # 其他请求直接透传
            writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
            writer.close()
            return

        # 解析请求头
        req_headers = {}
        for line in lines[1:]:
            if ": " in line:
                k, v = line.split(": ", 1)
                key = k.lower()
                if key not in ("host", "content-length", "transfer-encoding"):
                    req_headers[k] = v

        # 解析请求体
        request_body = {}
        if body_bytes:
            try:
                request_body = json.loads(body_bytes)
            except Exception:
                pass

        # 转发到 Anthropic
        turn_index = _realtime_stats["total_requests"]
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{UPSTREAM}/v1/messages",
                data=body_bytes,
                headers=req_headers,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                resp_body = await resp.read()
                resp_status = resp.status
                resp_headers = dict(resp.headers)

        # 解析响应，计算含屎量
        response_body = {}
        try:
            response_body = json.loads(resp_body)
        except Exception:
            pass

        usage = response_body.get("usage", {})
        if usage and (usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)) > 0:
            stoi = calc_stoi(usage, turn_index=turn_index)
            log_and_update(request_body, response_body, stoi)
            print_realtime(stoi, request_body)
            if not stoi.get("is_baseline"):
                speak(stoi["level"])

        # 返回响应给客户端
        status_line = f"HTTP/1.1 {resp_status} OK\r\n".encode()
        response_headers = b""
        for k, v in resp_headers.items():
            if k.lower() not in ("transfer-encoding", "connection"):
                response_headers += f"{k}: {v}\r\n".encode()
        response_headers += f"Content-Length: {len(resp_body)}\r\n".encode()
        response_headers += b"Connection: close\r\n"

        writer.write(status_line + response_headers + b"\r\n" + resp_body)
        await writer.drain()

    except Exception as e:
        print(f"\033[31m[STOI Proxy Error] {e}\033[0m")
        try:
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
        except Exception:
            pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


def _patch_claude_settings():
    """把 Claude Code 的 ANTHROPIC_BASE_URL 改成我们的代理"""
    settings_path = Path("~/.claude/settings.json").expanduser()
    backup_path   = Path("~/.stoi/upstream_backup").expanduser()
    try:
        data = json.loads(settings_path.read_text())
        current_url = data.get("env", {}).get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        # 备份原来的 URL（只在不是我们自己的时候）
        if "localhost" not in current_url and "127.0.0.1" not in current_url:
            backup_path.write_text(current_url)
            print(f"[2m  原始 URL 已备份: {current_url}[0m")
        # 写入代理地址
        if "env" not in data:
            data["env"] = {}
        data["env"]["ANTHROPIC_BASE_URL"] = f"http://localhost:{PROXY_PORT}"
        settings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"  [32m✅ 已自动设置 ANTHROPIC_BASE_URL → localhost:{PROXY_PORT}[0m")
        return True
    except Exception as e:
        print(f"  [33m⚠ 无法自动修改 settings.json: {e}[0m")
        print(f"  请手动运行: export ANTHROPIC_BASE_URL=http://localhost:{PROXY_PORT}")
        return False


def _restore_claude_settings():
    """退出时恢复原来的 ANTHROPIC_BASE_URL"""
    settings_path = Path("~/.claude/settings.json").expanduser()
    backup_path   = Path("~/.stoi/upstream_backup").expanduser()
    try:
        data = json.loads(settings_path.read_text())
        if backup_path.exists():
            original = backup_path.read_text().strip()
            data["env"]["ANTHROPIC_BASE_URL"] = original
            settings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            backup_path.unlink()
            print(f"  [32m✅ 已恢复 ANTHROPIC_BASE_URL → {original}[0m")
        else:
            # 没有备份就删掉我们加的
            data.get("env", {}).pop("ANTHROPIC_BASE_URL", None)
            settings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            print(f"  [32m✅ 已清除代理设置[0m")
    except Exception as e:
        print(f" [33m⚠ 恢复设置失败: {e}[0m")


async def main_proxy():
    # 初始化实时统计
    _realtime_stats["session_start"] = datetime.now().isoformat()
    _save_stats()

    # 自动修改 Claude Code settings
    _patch_claude_settings()

    server = await asyncio.start_server(
        handle_request, "127.0.0.1", PROXY_PORT,
        limit=2**20,  # 1MB read buffer
    )

    print(f""" ███████╗████████╗ ██████╗ ██╗ ██╔════╝╚══██╔══╝██╔═══██╗██║ ███████╗   ██║   ██║   ██║██║ ╚════██║   ██║   ██║   ██║██║ ███████║   ██║   ╚██████╔╝██║ ╚══════╝   ╚═╝    ╚═════╝ ╚═╝ Shit Token On Investment — 实时监控模式  代理启动: http://localhost:{PROXY_PORT}  \033[1m配置 Claude Code:\033[0m export ANTHROPIC_BASE_URL=http://localhost:{PROXY_PORT}  \033[1m实时统计:\033[0m 每次请求自动更新，TUI 每 2s 刷新 \033[1m语音播报:\033[0m 含屎量超标时自动播报 🎙️  \033[2mCtrl+C 停止，运行 stoi stats 查看完整报告\033[0m """)

    async with server:
        try:
            await server.serve_forever()
        except asyncio.CancelledError:
            pass


# ── CLI ───────────────────────────────────────────────────────────────────────
def cmd_stats():
    """打印当前实时统计"""
    if STATS_FILE.exists():
        stats = json.loads(STATS_FILE.read_text())
        print(f"\n实时统计:")
        print(f"  会话开始: {stats.get('session_start', '')[:19]}")
        print(f"  总请求数: {stats.get('total_requests', 0)}")
        print(f"  平均含屎量: {stats.get('avg_stoi', 0):.1f}%")
        print(f"  累计浪费: {stats.get('total_wasted', 0):,} tokens")
    else:
        print("还没有实时数据，先启动代理并使用 Claude Code")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        cmd_stats()
    else:
        import signal as _sig
        # 在主线程注册 SIGTERM，asyncio.run 前后都有效
        _sig.signal(_sig.SIGTERM, lambda s, f: (_restore_claude_settings(), sys.exit(0)))
        try:
            asyncio.run(main_proxy())
        except KeyboardInterrupt:
            _restore_claude_settings()
            print(f"\033[2m[STOI] 代理已停止。\033[0m")
