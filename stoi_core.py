#!/usr/bin/env python3
"""
stoi_core.py — STOI 核心分析引擎 v2

三层分析：
  L1: Cache Efficiency  — KV Cache 命中率，量化结构性浪费
  L2: Feedback Validity — 用户反馈信号，判断 AI 输出是否真正有效
  L3: Cost Breakdown    — 换算真实费用，定位最贵的浪费来源

支持输入：
  - Claude Code session JSONL (~/.claude/projects/)
  - OpenCode SQLite (~/.local/share/opencode/)
  - STOI Proxy log (~/.stoi/sessions.jsonl)

输出：STOIReport dataclass，可渲染为 CLI 或 HTML
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── 价格表（美元/百万 token，Anthropic 2026）──────────────────────────────────
PRICING = {
    "claude-opus-4-5":   {"input": 15.0,  "output": 75.0,  "cache_read": 1.50,  "cache_write": 18.75},
    "claude-sonnet-4-5": {"input": 3.0,   "output": 15.0,  "cache_read": 0.30,  "cache_write": 3.75},
    "claude-haiku-3-5":  {"input": 0.8,   "output": 4.0,   "cache_read": 0.08,  "cache_write": 1.00},
    "default":           {"input": 3.0,   "output": 15.0,  "cache_read": 0.30,  "cache_write": 3.75},
}

# ── 反馈信号词典 ───────────────────────────────────────────────────────────────
NEGATIVE_SIGNALS = [
    "没看到", "不对", "还是不行", "没改", "没有生成", "没有输出",
    "不符合", "理解错了", "为什么没有", "怎么没", "跑不起来",
    "没生效", "找不到", "没找到", "没有这个", "没变化", "还是一样",
    "没用", "不管用", "无效", "没有效果", "又报错", "还是报错",
    "不行", "错了", "有问题", "报错了",
]
POSITIVE_SIGNALS = [
    "好了", "可以了", "对了", "没问题", "谢谢", "收到", "完美",
    "很好", "不错", "可以", "好的", "ok", "成功", "搞定", "太棒了",
    "完成了", "行了", "正确", "没错",
]
FIXUP_SIGNALS = [
    "再", "还要", "另外", "补上", "补一下", "修改", "改一下",
    "调整", "优化", "完善", "继续", "下一步", "然后",
]


# ── 数据结构 ───────────────────────────────────────────────────────────────────
@dataclass
class TurnRecord:
    turn_index:    int
    timestamp:     float        # Unix ms
    role:          str          # "assistant" | "user"
    content:       str          # 文本内容（用于 feedback 分析）
    model:         str
    input_tokens:  int
    output_tokens: int
    cache_read:    int
    cache_write:   int
    is_stub:       bool = False  # output=0 的流式占位轮
    # L2 feedback
    feedback_label:      str = ""   # "positive" | "negative" | "neutral" | "unknown"
    feedback_signal:     str = ""   # 触发的关键词
    token_effectiveness: str = ""   # "valid" | "invalid" | "partial" | "unknown"
    # L1 cache
    cache_hit_rate:  float = 0.0
    stoi_score:      float = 0.0    # 0-100，越低越好
    stoi_level:      str   = "CLEAN"
    is_baseline:     bool  = False
    # L3 cost
    cost_actual:     float = 0.0    # 实际花费（含 cache）
    cost_if_no_cache: float = 0.0   # 若无 cache 的花费
    cost_saved:      float = 0.0    # 因 cache 节省的钱


@dataclass
class STOIReport:
    session_id:    str
    session_name:  str
    source_tool:   str   # "claude_code" | "opencode" | "proxy"
    model:         str
    generated_at:  str

    # 基础统计
    total_turns:   int = 0
    valid_turns:   int = 0   # 过滤 stub 后
    total_input:   int = 0
    total_output:  int = 0
    total_cache_read:  int = 0
    total_cache_write: int = 0
    total_wasted:  int = 0

    # L1: Cache
    avg_cache_hit_rate: float = 0.0
    avg_stoi_score:     float = 0.0
    stoi_level:         str   = "CLEAN"

    # L2: Feedback Validity
    valid_turns_count:   int = 0
    invalid_turns_count: int = 0
    partial_turns_count: int = 0
    unknown_turns_count: int = 0
    effectiveness_rate:  float = 0.0  # valid / (valid + invalid)

    # L3: Cost
    total_cost_actual:    float = 0.0
    total_cost_no_cache:  float = 0.0
    total_cost_saved:     float = 0.0
    waste_cost:           float = 0.0  # invalid turns 的费用

    # 详细轮次
    turns: list[TurnRecord] = field(default_factory=list)

    # 问题列表（排序后）
    issues: list[dict] = field(default_factory=list)

    # LLM 建议（可选）
    llm_suggestions: list[str] = field(default_factory=list)


# ── L1: Cache 效率分析 ────────────────────────────────────────────────────────
SHIT_THRESHOLDS = [
    (0,  30,  "CLEAN",         "✅"),
    (30, 50,  "MILD_SHIT",     "🟡"),
    (50, 75,  "SHIT_OVERFLOW", "🟠"),
    (75, 101, "DEEP_SHIT",     "💩"),
]

def _get_level(score: float) -> tuple[str, str]:
    for lo, hi, name, emoji in SHIT_THRESHOLDS:
        if lo <= score < hi:
            return name, emoji
    return "DEEP_SHIT", "💩"


def _calc_cache_score(rec: TurnRecord) -> TurnRecord:
    total = rec.input_tokens + rec.cache_read + rec.cache_write

    # 跳过条件：流式占位轮（output=0）或无数据
    if rec.output_tokens == 0 or total == 0:
        rec.is_stub = True
        rec.is_baseline = True
        rec.stoi_score = 0.0
        rec.stoi_level = "CLEAN"
        rec.cache_hit_rate = 0.0
        return rec

    # 第一轮（建缓存）不算含屎
    if rec.turn_index == 0 or (rec.cache_write > rec.cache_read):
        rec.is_baseline = True
        rec.stoi_score = 0.0
        rec.stoi_level = "CLEAN"
        rec.cache_hit_rate = round(rec.cache_read / total * 100, 1)
        return rec

    rec.cache_hit_rate = round(rec.cache_read / total * 100, 1)
    raw = (total - rec.cache_read) / total * 100
    # 建缓存减半惩罚
    if rec.cache_write > 0:
        raw *= (1 - (rec.cache_write / total) * 0.5)
    rec.stoi_score = round(min(raw, 100.0), 1)
    rec.stoi_level, _ = _get_level(rec.stoi_score)
    return rec


# ── L2: Feedback Validity ─────────────────────────────────────────────────────
def classify_feedback(text: str) -> tuple[str, str]:
    """返回 (label, signal)"""
    if not text:
        return "unknown", ""
    t = text.strip().casefold()
    for sig in NEGATIVE_SIGNALS:
        if t.startswith(sig) or (len(t) < 15 and sig in t):
            return "negative", sig
    for sig in POSITIVE_SIGNALS:
        if t.startswith(sig):
            return "positive", sig
    for sig in FIXUP_SIGNALS:
        if t.startswith(sig):
            return "partial", sig
    return "unknown", ""


def _apply_feedback(turns: list[TurnRecord]) -> list[TurnRecord]:
    """用下一条 user 消息标注当前 assistant 轮次的有效性"""
    for i, rec in enumerate(turns):
        if rec.role != "assistant" or rec.is_stub:
            continue
        # 找下一条 user 消息
        next_user_text = ""
        for j in range(i + 1, min(i + 3, len(turns))):
            if turns[j].role == "user":
                next_user_text = turns[j].content[:100]
                break

        label, signal = classify_feedback(next_user_text)
        rec.feedback_label  = label
        rec.feedback_signal = signal

        if label == "positive":
            rec.token_effectiveness = "valid"
        elif label == "negative":
            rec.token_effectiveness = "invalid"
        elif label == "partial":
            rec.token_effectiveness = "partial"
        else:
            # 启发式兜底：如果 output 很多但 next user 很短 → 可能有效
            if rec.output_tokens > 200 and len(next_user_text) < 10:
                rec.token_effectiveness = "valid"
            else:
                rec.token_effectiveness = "unknown"

    return turns


# ── L3: Cost Breakdown ────────────────────────────────────────────────────────
def _calc_cost(rec: TurnRecord) -> TurnRecord:
    prices = PRICING.get(rec.model, PRICING["default"])
    M = 1_000_000

    # 实际费用
    rec.cost_actual = (
        rec.input_tokens  * prices["input"]        / M +
        rec.output_tokens * prices["output"]       / M +
        rec.cache_read    * prices["cache_read"]   / M +
        rec.cache_write   * prices["cache_write"]  / M
    )
    # 如果没有 cache 的费用（全按 input 算）
    total_input = rec.input_tokens + rec.cache_read + rec.cache_write
    rec.cost_if_no_cache = (
        total_input       * prices["input"]  / M +
        rec.output_tokens * prices["output"] / M
    )
    rec.cost_saved = max(0.0, rec.cost_if_no_cache - rec.cost_actual)
    return rec


# ── 问题检测 ───────────────────────────────────────────────────────────────────
DYNAMIC_PATTERNS = {
    "timestamp": (r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', "时间戳注入 → Cache 必然失效"),
    "uuid":      (r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', "随机 UUID → 每次 Cache Miss"),
    "abs_path":  (r'/Users/[A-Za-z0-9_]+|/home/[A-Za-z0-9_]+', "绝对路径注入 → 跨设备失效"),
    "pid":       (r'\bpid[:\s=]+\d+', "进程 ID 注入 → 每次不同"),
}

def _detect_issues(turns: list[TurnRecord]) -> list[dict]:
    issues = []

    # 问题1：高 cache miss 率
    valid = [t for t in turns if not t.is_stub and not t.is_baseline]
    if valid:
        avg_miss = sum(t.stoi_score for t in valid) / len(valid)
        miss_turns = [t for t in valid if t.cache_hit_rate < 10]
        if avg_miss > 50:
            issues.append({
                "severity": "HIGH",
                "type": "cache_miss",
                "title": f"缓存命中率过低（均值 {100-avg_miss:.0f}%）",
                "detail": f"{len(miss_turns)}/{len(valid)} 轮次缓存完全失效",
                "fix": "检查 System Prompt 中是否有时间戳、UUID 等动态字段（运行 stoi blame 定位）",
                "impact": f"每轮多花 ~{avg_miss/100*3:.4f}¢",
            })

    # 问题2：高无效输出率
    scored = [t for t in turns if t.token_effectiveness in ("valid", "invalid")]
    if scored:
        invalid = [t for t in scored if t.token_effectiveness == "invalid"]
        invalid_rate = len(invalid) / len(scored)
        if invalid_rate > 0.3:
            waste = sum(t.cost_actual for t in invalid)
            issues.append({
                "severity": "HIGH",
                "type": "invalid_output",
                "title": f"{invalid_rate*100:.0f}% 的 AI 输出被用户否定",
                "detail": f"{len(invalid)} 轮次在用户反馈后被重做，浪费 ${waste:.4f}",
                "fix": "考虑在 prompt 里加更多约束，或者拆分复杂任务为更小的步骤",
                "impact": f"浪费 ${waste:.4f}",
            })

    # 问题3：上下文膨胀
    if len(valid) >= 5:
        inputs = [t.input_tokens + t.cache_read + t.cache_write for t in valid]
        growth = (inputs[-1] - inputs[0]) / max(inputs[0], 1) * 100
        if growth > 300:
            issues.append({
                "severity": "MED",
                "type": "context_bloat",
                "title": f"上下文膨胀 {growth:.0f}%",
                "detail": f"Token 从首轮 {inputs[0]:,} 增长到最后 {inputs[-1]:,}",
                "fix": f"建议在第 {len(valid)//2} 轮后压缩历史对话，或启用滑动窗口",
                "impact": "每轮成本持续增加",
            })

    # 问题4：过度使用 opus（用 opus 做简单任务）
    opus_turns = [t for t in valid if "opus" in t.model.lower()]
    simple_opus = [t for t in opus_turns if t.output_tokens < 50 and t.input_tokens < 5000]
    if len(simple_opus) > len(opus_turns) * 0.4 and opus_turns:
        savings = sum(t.cost_actual for t in simple_opus) * 0.8  # sonnet 便宜 ~5x
        issues.append({
            "severity": "MED",
            "type": "model_overkill",
            "title": f"{len(simple_opus)} 个简单任务使用了 Opus",
            "detail": "短输出的任务用 Sonnet 准确率无差别，但便宜 5 倍",
            "fix": "简单问答、格式转换等任务使用 claude-sonnet-4-5",
            "impact": f"可节省 ~${savings:.4f}",
        })

    # 按严重程度排序
    severity_order = {"HIGH": 0, "MED": 1, "LOW": 2}
    issues.sort(key=lambda x: severity_order.get(x["severity"], 3))
    return issues


# ── Session 解析器 ─────────────────────────────────────────────────────────────
def parse_claude_code(path: Path) -> list[TurnRecord]:
    records = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue

                # User 消息（保留用于 feedback）
                if obj.get("type") == "human":
                    msg = obj.get("message", {})
                    content = ""
                    raw = msg.get("content", "")
                    if isinstance(raw, str):
                        content = raw[:200]
                    elif isinstance(raw, list):
                        for c in raw:
                            if isinstance(c, dict) and c.get("type") == "text":
                                content = c.get("text", "")[:200]
                                break
                    records.append(TurnRecord(
                        turn_index=len(records), timestamp=obj.get("timestamp", 0) or 0,
                        role="user", content=content, model="",
                        input_tokens=0, output_tokens=0, cache_read=0, cache_write=0,
                    ))
                    continue

                if obj.get("type") != "assistant":
                    continue

                msg = obj.get("message", {})
                usage = msg.get("usage", {})
                if not usage:
                    continue

                inp  = usage.get("input_tokens", 0)
                out  = usage.get("output_tokens", 0)
                cr   = usage.get("cache_read_input_tokens", 0)
                cw_raw = usage.get("cache_creation_input_tokens", 0)
                # 新版 API cache_creation 可能是 dict
                if isinstance(cw_raw, dict):
                    cw = cw_raw.get("ephemeral_1h_input_tokens", 0) + cw_raw.get("ephemeral_5m_input_tokens", 0)
                else:
                    cw = int(cw_raw) if cw_raw else 0

                if inp + cr + cw == 0:
                    continue

                # 提取 assistant 文本内容
                content = ""
                for c in (msg.get("content") or []):
                    if isinstance(c, dict) and c.get("type") == "text":
                        content = c.get("text", "")[:200]
                        break

                ts = obj.get("timestamp", 0)
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000
                    except Exception:
                        ts = 0

                rec = TurnRecord(
                    turn_index=len(records), timestamp=float(ts),
                    role="assistant", content=content,
                    model=msg.get("model", "unknown"),
                    input_tokens=inp, output_tokens=out,
                    cache_read=cr, cache_write=cw,
                )
                records.append(rec)
    except Exception:
        pass
    return records


def parse_opencode(session_id: str) -> list[TurnRecord]:
    db_path = Path("~/.local/share/opencode/opencode.db").expanduser()
    if not db_path.exists():
        return []
    records = []
    try:
        db = sqlite3.connect(str(db_path))
        rows = db.execute(
            "SELECT data, time_created FROM message WHERE session_id=? ORDER BY time_created",
            (session_id,)
        ).fetchall()
        db.close()
        for data_str, ts_ms in rows:
            try:
                d = json.loads(data_str)
            except Exception:
                continue
            role = d.get("role", "")
            if role == "user":
                records.append(TurnRecord(
                    turn_index=len(records), timestamp=float(ts_ms or 0),
                    role="user", content=str(d.get("content", ""))[:200], model="",
                    input_tokens=0, output_tokens=0, cache_read=0, cache_write=0,
                ))
                continue
            if role != "assistant":
                continue
            t = d.get("tokens", {})
            cache = t.get("cache", {})
            rec = TurnRecord(
                turn_index=len(records), timestamp=float(ts_ms or 0),
                role="assistant", content="",
                model=d.get("modelID", "unknown"),
                input_tokens=t.get("input", 0), output_tokens=t.get("output", 0),
                cache_read=cache.get("read", 0) if isinstance(cache, dict) else 0,
                cache_write=cache.get("write", 0) if isinstance(cache, dict) else 0,
            )
            records.append(rec)
    except Exception:
        pass
    return records


def parse_proxy_log(path: Path) -> list[TurnRecord]:
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
                    rec = TurnRecord(
                        turn_index=len(records),
                        timestamp=0,
                        role="assistant", content="",
                        model=obj.get("model", "unknown"),
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                        cache_read=usage.get("cache_read_input_tokens", 0),
                        cache_write=usage.get("cache_creation_input_tokens", 0),
                    )
                    records.append(rec)
                except Exception:
                    continue
    except Exception:
        pass
    return records


# ── 主分析入口 ────────────────────────────────────────────────────────────────
def analyze(
    path: Optional[Path] = None,
    session_id: Optional[str] = None,
    source: str = "claude_code",
    llm_enabled: bool = False,
) -> STOIReport:
    """
    主入口：给定 session 路径/ID，返回完整的 STOIReport

    Args:
        path:       session 文件路径（claude_code / proxy）
        session_id: OpenCode session ID
        source:     "claude_code" | "opencode" | "proxy"
        llm_enabled: 是否调用 LLM 生成深度建议
    """
    # 1. 解析原始 turns
    if source == "opencode" and session_id:
        raw_turns = parse_opencode(session_id)
        name = f"opencode/{session_id[:8]}"
    elif source == "proxy" and path:
        raw_turns = parse_proxy_log(path)
        name = "proxy_log"
    else:
        if not path or not path.exists():
            return STOIReport(
                session_id="", session_name="not found",
                source_tool=source, model="", generated_at=datetime.now().isoformat(),
            )
        raw_turns = parse_claude_code(path)
        name = f"{path.parent.name[:16]}/{path.stem[:12]}"

    if not raw_turns:
        return STOIReport(
            session_id="", session_name=name,
            source_tool=source, model="", generated_at=datetime.now().isoformat(),
        )

    # 2. L1: Cache 分析
    turns = [_calc_cache_score(t) for t in raw_turns]

    # 3. L2: Feedback Validity
    turns = _apply_feedback(turns)

    # 4. L3: Cost
    turns = [_calc_cost(t) for t in turns]

    # 5. 统计汇总
    assistant_turns = [t for t in turns if t.role == "assistant"]
    valid_turns = [t for t in assistant_turns if not t.is_stub]
    scored_turns = [t for t in valid_turns if not t.is_baseline]

    report = STOIReport(
        session_id=str(path.stem if path else session_id or ""),
        session_name=name,
        source_tool=source,
        model=next((t.model for t in valid_turns if t.model), "unknown"),
        generated_at=datetime.now().isoformat(),
        total_turns=len(assistant_turns),
        valid_turns=len(valid_turns),
        total_input=sum(t.input_tokens + t.cache_read + t.cache_write for t in valid_turns),
        total_output=sum(t.output_tokens for t in valid_turns),
        total_cache_read=sum(t.cache_read for t in valid_turns),
        total_cache_write=sum(t.cache_write for t in valid_turns),
        total_wasted=sum(t.input_tokens for t in scored_turns),
        turns=turns,
    )

    if scored_turns:
        report.avg_cache_hit_rate = round(
            sum(t.cache_hit_rate for t in scored_turns) / len(scored_turns), 1
        )
        report.avg_stoi_score = round(
            sum(t.stoi_score for t in scored_turns) / len(scored_turns), 1
        )
        report.stoi_level, _ = _get_level(report.avg_stoi_score)

    # L2 统计
    fb_turns = [t for t in valid_turns if t.token_effectiveness]
    report.valid_turns_count   = sum(1 for t in fb_turns if t.token_effectiveness == "valid")
    report.invalid_turns_count = sum(1 for t in fb_turns if t.token_effectiveness == "invalid")
    report.partial_turns_count = sum(1 for t in fb_turns if t.token_effectiveness == "partial")
    report.unknown_turns_count = sum(1 for t in fb_turns if t.token_effectiveness == "unknown")
    rated = report.valid_turns_count + report.invalid_turns_count
    report.effectiveness_rate = round(
        report.valid_turns_count / rated * 100 if rated > 0 else 0, 1
    )

    # L3 成本
    report.total_cost_actual   = sum(t.cost_actual for t in valid_turns)
    report.total_cost_no_cache = sum(t.cost_if_no_cache for t in valid_turns)
    report.total_cost_saved    = sum(t.cost_saved for t in valid_turns)
    report.waste_cost = sum(
        t.cost_actual for t in valid_turns if t.token_effectiveness == "invalid"
    )

    # 6. 问题检测
    report.issues = _detect_issues(turns)

    # 7. LLM 深度建议（可选）
    if llm_enabled and report.issues:
        report.llm_suggestions = _get_llm_suggestions(report)

    return report


# ── LLM 建议 ─────────────────────────────────────────────────────────────────
def _get_llm_suggestions(report: STOIReport) -> list[str]:
    try:
        from stoi_config import load_config, get_api_key
        cfg = load_config()
        llm = cfg.get("llm", {})
        provider = llm.get("provider", "")
        api_key  = llm.get("api_key", "") or get_api_key(provider)
        model    = llm.get("model", "")
        if not api_key:
            return []

        prompt = f"""你是 STOI Token 效率分析师。根据以下分析数据，给出 3 条具体、可立即执行的改进建议。

数据摘要：
- 会话：{report.session_name}，{report.valid_turns} 轮
- 平均含屎量：{report.avg_stoi_score:.1f}%（{report.stoi_level}）
- 缓存命中率：{report.avg_cache_hit_rate:.1f}%
- AI 输出有效率：{report.effectiveness_rate:.1f}%（{report.invalid_turns_count} 轮被用户否定）
- 实际花费：${report.total_cost_actual:.4f}，其中 ${report.waste_cost:.4f} 花在被否定的输出上

主要问题：
{chr(10).join(f'- [{i["severity"]}] {i["title"]}: {i["detail"]}' for i in report.issues[:3])}

要求：
- 每条建议一行
- 包含具体操作（不是"建议优化"，而是"把 system prompt 第 X 行的时间戳删掉"）
- 包含预期收益
- 用中文，不超过 50 字每条"""

        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=model or "claude-haiku-3-5",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
        else:
            from openai import OpenAI
            url_map = {"qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                       "deepseek": "https://api.deepseek.com/v1"}
            client = OpenAI(
                api_key=api_key,
                base_url=llm.get("base_url") or url_map.get(provider, "https://api.openai.com/v1")
            )
            resp = client.chat.completions.create(
                model=model or "qwen-plus",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
            )
            text = resp.choices[0].message.content

        return [s.strip().lstrip("1234567890.-） ") for s in text.strip().splitlines() if s.strip()][:3]

    except Exception:
        return []


# ── 工具函数 ─────────────────────────────────────────────────────────────────
def find_claude_sessions(top: int = 20) -> list[Path]:
    base = Path("~/.claude/projects").expanduser()
    if not base.exists():
        return []
    files = list(base.rglob("*.jsonl"))
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return files[:top]


def find_opencode_sessions(top: int = 10) -> list[dict]:
    db_path = Path("~/.local/share/opencode/opencode.db").expanduser()
    if not db_path.exists():
        return []
    try:
        db = sqlite3.connect(str(db_path))
        rows = db.execute(
            "SELECT id, title, time_updated FROM session ORDER BY time_updated DESC LIMIT ?",
            (top,)
        ).fetchall()
        db.close()
        return [{"id": r[0], "title": r[1] or f"Session {r[0][:8]}", "updated": r[2]} for r in rows]
    except Exception:
        return []
