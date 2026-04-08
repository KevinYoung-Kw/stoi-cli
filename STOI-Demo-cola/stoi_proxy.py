#!/usr/bin/env python3
"""
STOI Proxy — Shit Token On Investment
零侵入 API 代理，拦截 Claude Code 的 Token 消耗并计算含屎量

用法：
  1. python3 stoi_proxy.py          # 启动代理 (默认端口 8888)
  2. export ANTHROPIC_BASE_URL=http://localhost:8888
  3. 正常用 Claude Code，数据自动被拦截记录

命令：
  stoi stats    — 查看含屎量报告
  stoi blame    — 找出造屎元凶
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
PROXY_PORT = 8888
UPSTREAM = "https://api.anthropic.com"
LOG_FILE = Path("~/.stoi/sessions.jsonl").expanduser()
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# 含屎量阈值
SHIT_THRESHOLDS = {
    "CLEAN":          (0,   30),   # ✅ 干净
    "MILD_SHIT":      (30,  50),   # 🟡 轻度含屎
    "SHIT_OVERFLOW":  (50,  75),   # 🟠 含屎偏高
    "DEEP_SHIT":      (75,  100),  # 💩 严重超标
}

TTS_MESSAGES = {
    "CLEAN":          "干净！这才叫工程师。",
    "MILD_SHIT":      "含屎量偏高，你的词元在哭泣。",
    "SHIT_OVERFLOW":  "含屎量严重超标，建议立刻停止 Vibe Coding。",
    "DEEP_SHIT":      "警告！深度含屎！你的算力正在窒息！",
}


# ── 含屎量计算 ─────────────────────────────────────────────────────────────────
def calc_stoi(usage: dict) -> dict:
    """
    STOI = 1 - (cache_read / input_tokens)
    越低越好，越高说明缓存命中越差，越「屎」
    """
    input_tokens        = usage.get("input_tokens", 0)
    cache_read          = usage.get("cache_read_input_tokens", 0)
    cache_creation      = usage.get("cache_creation_input_tokens", 0)
    output_tokens       = usage.get("output_tokens", 0)

    if input_tokens == 0:
        stoi_score = 0.0
    else:
        stoi_score = round((1 - cache_read / input_tokens) * 100, 1)

    level = "CLEAN"
    for lvl, (lo, hi) in SHIT_THRESHOLDS.items():
        if lo <= stoi_score < hi:
            level = lvl
            break

    return {
        "stoi_score":     stoi_score,
        "level":          level,
        "input_tokens":   input_tokens,
        "output_tokens":  output_tokens,
        "cache_read":     cache_read,
        "cache_creation": cache_creation,
        "wasted_tokens":  input_tokens - cache_read,
    }


# ── TTS 语音播报 ───────────────────────────────────────────────────────────────
def speak(level: str):
    msg = TTS_MESSAGES.get(level, "")
    if msg:
        try:
            # macOS say 命令，零依赖
            subprocess.Popen(["say", "-v", "Ting-Ting", msg])
        except Exception:
            pass  # 非 macOS 环境静默跳过


# ── 日志写入 ───────────────────────────────────────────────────────────────────
def log_session(request_body: dict, response_body: dict, stoi: dict):
    record = {
        "ts":       datetime.now().isoformat(),
        "model":    request_body.get("model", "unknown"),
        "stoi":     stoi,
        "usage":    response_body.get("usage", {}),
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── Cache Blame：找出造屎元凶 ──────────────────────────────────────────────────
def detect_shit_culprits(system_prompt: str) -> list[str]:
    """扫描 System Prompt，找出导致 Cache Miss 的动态元数据"""
    import re
    culprits = []

    # 时间戳模式（Claude Code 的经典原罪）
    if re.search(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}', system_prompt):
        culprits.append("⚠️  时间戳注入 (timestamp injection) — Cache Miss 头号元凶")

    # 随机 UUID
    if re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', system_prompt):
        culprits.append("⚠️  随机 UUID — 每次请求都不同，必然 Cache Miss")

    # 绝对路径（频繁变动）
    if re.search(r'/Users/|/home/|C:\\Users\\', system_prompt):
        culprits.append("⚠️  绝对路径注入 — 换机器/换用户即失效")

    # 进程 ID / PID
    if re.search(r'\bpid[:\s=]+\d+', system_prompt, re.IGNORECASE):
        culprits.append("⚠️  进程 ID (PID) — 每次启动都变，导致 Cache 击穿")

    return culprits if culprits else ["✅ 未发现明显造屎元凶"]


# ── 代理核心逻辑 ───────────────────────────────────────────────────────────────
async def handle(reader, writer):
    try:
        import aiohttp

        # 读取 HTTP 请求
        raw = await reader.read(65536)
        if not raw:
            return

        # 简单解析 HTTP (仅处理 POST /v1/messages)
        lines = raw.split(b"\r\n")
        request_line = lines[0].decode()

        # 找到请求体
        header_end = raw.find(b"\r\n\r\n")
        body_bytes = raw[header_end + 4:] if header_end != -1 else b""

        request_body = {}
        if body_bytes:
            try:
                request_body = json.loads(body_bytes)
            except Exception:
                pass

        # 转发到 Anthropic
        headers = {}
        for line in lines[1:]:
            if b": " in line:
                k, v = line.split(b": ", 1)
                key = k.decode().lower()
                if key not in ("host", "content-length"):
                    headers[k.decode()] = v.decode()

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{UPSTREAM}/v1/messages",
                json=request_body,
                headers=headers,
            ) as resp:
                response_body = await resp.json()

        # 计算含屎量
        usage = response_body.get("usage", {})
        if usage:
            stoi = calc_stoi(usage)
            log_session(request_body, response_body, stoi)

            # 打印实时报告
            score = stoi["stoi_score"]
            level = stoi["level"]
            emoji = {"CLEAN": "✅", "MILD_SHIT": "🟡", "SHIT_OVERFLOW": "🟠", "DEEP_SHIT": "💩"}[level]
            print(f"\n{'─'*50}")
            print(f"  STOI Score: {score}% {emoji}  [{level}]")
            print(f"  Input: {stoi['input_tokens']:,} tokens  |  Cache hit: {stoi['cache_read']:,}")
            print(f"  Wasted: {stoi['wasted_tokens']:,} tokens  |  Output: {stoi['output_tokens']:,}")
            print(f"{'─'*50}\n")

            # 语音播报
            speak(level)

        # 返回响应给客户端
        response_json = json.dumps(response_body).encode()
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            + f"Content-Length: {len(response_json)}\r\n".encode()
            + b"\r\n"
            + response_json
        )
        await writer.drain()

    except Exception as e:
        print(f"[STOI Proxy Error] {e}")
    finally:
        writer.close()


# ── CLI 命令：stats / blame ────────────────────────────────────────────────────
def cmd_stats():
    if not LOG_FILE.exists():
        print("📭 还没有记录。先跑 stoi_proxy.py 再用 Claude Code。")
        return

    records = [json.loads(l) for l in LOG_FILE.read_text().strip().splitlines() if l]
    if not records:
        print("📭 日志为空。")
        return

    total_input   = sum(r["stoi"]["input_tokens"] for r in records)
    total_wasted  = sum(r["stoi"]["wasted_tokens"] for r in records)
    total_output  = sum(r["stoi"]["output_tokens"] for r in records)
    avg_score     = sum(r["stoi"]["stoi_score"] for r in records) / len(records)

    level_counts = {}
    for r in records:
        lvl = r["stoi"]["level"]
        level_counts[lvl] = level_counts.get(lvl, 0) + 1

    print(f"""
╔══════════════════════════════════════════╗
║          STOI  含屎量报告                ║
╠══════════════════════════════════════════╣
║  会话总数:    {len(records):>6} 次                  ║
║  平均含屎量:  {avg_score:>5.1f}%                    ║
║  总消耗:      {total_input:>10,} tokens          ║
║  白白浪费:    {total_wasted:>10,} tokens  💩      ║
║  有效输出:    {total_output:>10,} tokens          ║
╠══════════════════════════════════════════╣""")

    for lvl, count in level_counts.items():
        emoji = {"CLEAN": "✅", "MILD_SHIT": "🟡", "SHIT_OVERFLOW": "🟠", "DEEP_SHIT": "💩"}.get(lvl, "")
        print(f"║  {emoji} {lvl:<20} {count:>4} 次             ║")

    print("╚══════════════════════════════════════════╝")

    # TTS 播报总结
    if avg_score >= 75:
        speak("DEEP_SHIT")
    elif avg_score >= 50:
        speak("SHIT_OVERFLOW")
    elif avg_score >= 30:
        speak("MILD_SHIT")
    else:
        speak("CLEAN")


def cmd_blame():
    if not LOG_FILE.exists():
        print("📭 没有日志可分析。")
        return

    print("\n🔍 stoi blame — Cache 造屎元凶分析\n")
    print("提示：请把你的 System Prompt 粘贴进来（输入 END 结束）：")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)

    prompt = "\n".join(lines)
    culprits = detect_shit_culprits(prompt)

    print("\n检测结果：")
    for c in culprits:
        print(f"  {c}")
    print()


# ── 入口 ───────────────────────────────────────────────────────────────────────
async def main_proxy():
    print(f"""
 ███████╗████████╗ ██████╗ ██╗
 ██╔════╝╚══██╔══╝██╔═══██╗██║
 ███████╗   ██║   ██║   ██║██║
 ╚════██║   ██║   ██║   ██║██║
 ███████║   ██║   ╚██████╔╝██║
 ╚══════╝   ╚═╝    ╚═════╝ ╚═╝
 Shit Token On Investment — v1.0

 代理启动中... 端口 {PROXY_PORT}
 
 现在运行：
   export ANTHROPIC_BASE_URL=http://localhost:{PROXY_PORT}
 
 然后正常使用 Claude Code，含屎量实时播报 🎙️
""")
    server = await asyncio.start_server(handle, "127.0.0.1", PROXY_PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "stats":
            cmd_stats()
        elif cmd == "blame":
            cmd_blame()
        else:
            print(f"未知命令: {cmd}。用法: python3 stoi_proxy.py [stats|blame]")
    else:
        try:
            asyncio.run(main_proxy())
        except KeyboardInterrupt:
            print("\n\n[STOI] 代理已停止。运行 `python3 stoi_proxy.py stats` 查看含屎量报告。")
