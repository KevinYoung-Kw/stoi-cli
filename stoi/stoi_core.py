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


# ── L2: Feedback Validity（LLM 判断，替代规则匹配）─────────────────────────────
def _llm_evaluate_batch(pairs: list[dict]) -> list[dict]:
    """
    批量用 LLM 判断 AI 输出有效性。
    pairs: [{"turn_idx": int, "ai_output": str, "user_followup": str, "context": str}]
    返回: [{"turn_idx": int, "effectiveness": str, "confidence": float, "reason": str}]
    """
    if not pairs:
        return []
    try:
        from .stoi_config import load_config, get_api_key
        cfg = load_config()
        llm = cfg.get("llm", {})
        provider = llm.get("provider", "")
        api_key  = llm.get("api_key", "") or get_api_key(provider)
        model    = llm.get("model", "")
        base_url = llm.get("base_url", "")
        if not api_key:
            return []

        # 构建批量评估 prompt
        items_text = ""
        for p in pairs:
            items_text += f"""
---轮次 {p['turn_idx']}---
AI输出（前200字）: {p['ai_output'][:200]}
用户下一条消息: {p['user_followup'][:150]}
"""

        prompt = f"""你是对话效率分析师。判断以下每轮 AI 输出对用户是否真正有价值。

任务背景: {pairs[0].get('context', 'AI 编程助手对话')}

{items_text}

对每轮输出，判断：
- valid: 用户消息在推进任务，AI输出有实质帮助
- invalid: 用户在纠错/重新提问/AI完全答非所问
- partial: AI输出部分有用，用户在补充或修正方向
- unclear: 无法从用户消息判断

注意：
- 用户情绪（沮丧、兴奋）是重要信号
- "继续"、"好的"通常是 valid
- "不对"、"还是不行" 是 invalid
- 用户问了完全不相关的新问题 → unclear

返回 JSON 数组，每项：{{"turn_idx": N, "effectiveness": "valid/invalid/partial/unclear", "confidence": 0.0-1.0, "reason": "一句话中文"}}
只输出 JSON，不要其他内容。"""

        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=model or "claude-haiku-3-5",  # 用最轻模型控制成本
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
        else:
            from openai import OpenAI
            url_map = {"qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                       "deepseek": "https://api.deepseek.com/v1"}
            client = OpenAI(
                api_key=api_key,
                base_url=base_url or url_map.get(provider, "https://api.openai.com/v1")
            )
            resp = client.chat.completions.create(
                model=model or "qwen-turbo",  # 用最快模型控制延迟
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                response_format={"type": "json_object"} if provider == "openai" else None,
            )
            text = resp.choices[0].message.content

        # 解析 JSON
        import re
        json_match = re.search(r'\[.*\]', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(text)

    except Exception:
        return []


def _apply_feedback(turns: list[TurnRecord], use_llm: bool = False) -> list[TurnRecord]:
    """
    标注每轮 assistant 输出的有效性。
    use_llm=True: 用 LLM 批量评估（准确，慢，有成本）
    use_llm=False: 用规则兜底（快，适合无 API key 场景）
    """
    # 收集需要评估的轮次对
    pairs_to_eval = []
    # 提取任务背景（取前两条 user 消息）
    context_msgs = [t.content for t in turns if t.role == "user" and t.content][:2]
    context = " / ".join(context_msgs)[:200] if context_msgs else "AI 编程助手"

    for i, rec in enumerate(turns):
        if rec.role != "assistant" or rec.is_stub or rec.is_baseline:
            continue
        # 找下一条 user 消息
        next_user_text = ""
        for j in range(i + 1, min(i + 4, len(turns))):
            if turns[j].role == "user" and turns[j].content:
                next_user_text = turns[j].content[:150]
                break

        if use_llm and next_user_text and rec.content:
            pairs_to_eval.append({
                "turn_idx": i,
                "ai_output": rec.content,
                "user_followup": next_user_text,
                "context": context,
            })
        else:
            # 规则兜底（快速路径）
            _apply_rule_feedback(rec, next_user_text)

    # LLM 批量评估（每批最多 10 轮，控制成本）
    if use_llm and pairs_to_eval:
        # 只评估含屎量高的轮次或随机采样，控制 API 调用量
        scored_pairs = [p for p in pairs_to_eval
                        if not turns[p["turn_idx"]].is_baseline][:10]
        results = _llm_evaluate_batch(scored_pairs)
        result_map = {r["turn_idx"]: r for r in results}

        for p in scored_pairs:
            rec = turns[p["turn_idx"]]
            if p["turn_idx"] in result_map:
                r = result_map[p["turn_idx"]]
                rec.feedback_label      = r.get("effectiveness", "unclear")
                rec.feedback_signal     = r.get("reason", "")[:80]
                rec.token_effectiveness = r.get("effectiveness", "unclear")
            else:
                _apply_rule_feedback(rec, p["user_followup"])

    return turns


def _apply_rule_feedback(rec: TurnRecord, next_user_text: str):
    """规则兜底：快速判断，无需 API"""
    if not next_user_text:
        rec.token_effectiveness = "unknown"
        return

    t = next_user_text.strip().casefold()

    for sig in NEGATIVE_SIGNALS:
        if t.startswith(sig) or (len(t) < 15 and sig in t):
            rec.feedback_label      = "negative"
            rec.feedback_signal     = sig
            rec.token_effectiveness = "invalid"
            return

    for sig in POSITIVE_SIGNALS:
        if t.startswith(sig):
            rec.feedback_label      = "positive"
            rec.feedback_signal     = sig
            rec.token_effectiveness = "valid"
            return

    for sig in FIXUP_SIGNALS:
        if t.startswith(sig):
            rec.feedback_label      = "partial"
            rec.feedback_signal     = sig
            rec.token_effectiveness = "partial"
            return

    # 启发式：output 多但 followup 短 → 可能有效
    if rec.output_tokens > 300 and len(next_user_text) < 15:
        rec.token_effectiveness = "valid"
    else:
        rec.token_effectiveness = "unknown"


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
    turns = _apply_feedback(turns, use_llm=llm_enabled)

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
    if llm_enabled:
        from .stoi_advisor import get_suggestions
        report.llm_suggestions = get_suggestions(report)

    return report


# ── LLM 建议 ─────────────────────────────────────────────────────────────────
INSIGHTS_KNOWLEDGE = """你是 STOI（Shit Token On Investment）的 AI 分析引擎，专注于 AI 编程工具的 Token 效率优化。

你掌握以下领域的专业知识：

## KV Cache 优化原则
- KV Cache 命中与不命中的成本差达 10x（Anthropic 定价：cache read $0.30/M vs input $3.00/M）
- Cache miss 最常见原因（按严重程度）：
  1. System Prompt 中注入时间戳（Claude Code 已知 bug，每次请求时间不同导致前缀变化）
  2. 动态切换 tools 列表（每次变动导致模板重新插入，cache 全失效）
  3. 绝对路径注入（/Users/xxx 换机器必失效）
  4. 随机 UUID 注入
- 修复方法：将所有动态字段移至 user message，System Prompt 保持静态

## 上下文膨胀（Context Bloat）
- 来源：Liu et al. (2023) "Lost in the Middle"，TACL
- 核心：LLM 对长上下文中间部分注意力最弱，早期信息被付费但被忽视
- 量化标准：上下文增长 >300% 即为严重膨胀
- 修复方法：
  1. 超过 10 轮后启用对话摘要压缩（固定左侧系统提示 + 压缩右侧历史）
  2. LLMLingua-2（Microsoft ACL 2024）：可压缩至 1/4 tokens，RAG 性能不降反升 21.4%
  3. 拆分 session：将独立任务拆成独立 session，避免上下文污染

## 输出有效性（Feedback Validity）
- 用户说"不对/还是不行/没改" → 上一轮 AI 输出无效，token 全浪费
- 有效率 <70% 说明 prompt 设计有问题，AI 经常误解需求
- 修复方法：在 prompt 中更明确地描述任务边界、输出格式、成功标准

## 模型选择
- claude-opus-4-5 适合：复杂推理、架构设计、长文档分析
- claude-sonnet-4-5 适合：日常编程、代码审查、一般问答（成本 1/5）
- 简单任务用 Opus 是常见的"过度工程"浪费

## 多轮优化策略
- 每 5-10 轮检查一次上下文质量，超过 80K tokens 考虑压缩
- 工具调用结果在使用后应摘要化，不要原始堆积
- 把"大任务"拆成"小任务链"，每个 session 有明确的结束条件

你的建议必须：
1. 基于上述知识，针对具体数据给出精准诊断
2. 每条建议包含：问题根因 + 具体操作 + 预期收益
3. 不给通用废话，不给"建议优化提示词"这种无意义建议
4. 如果数据显示该指标已经很好，直接说"该指标良好，无需优化"
"""

def _get_llm_suggestions(report: STOIReport) -> list[str]:
    try:
        from .stoi_config import load_config, get_api_key
        cfg = load_config()
        llm = cfg.get("llm", {})
        provider = llm.get("provider", "")
        api_key  = llm.get("api_key", "") or get_api_key(provider)
        model    = llm.get("model", "")
        if not api_key:
            return []

        # 构建详细的数据摘要
        issues_text = "\n".join(
            f'- [{i["severity"]}] {i["title"]}\n  详情：{i["detail"]}\n  当前建议：{i["fix"]}'
            for i in report.issues[:3]
        ) if report.issues else "- 未检测到明显问题"

        # 趋势分析
        scored = [t for t in report.turns if not t.is_stub and not t.is_baseline and t.role == "assistant"]
        trend = ""
        if len(scored) >= 4:
            first_half = [t.stoi_score for t in scored[:len(scored)//2]]
            second_half = [t.stoi_score for t in scored[len(scored)//2:]]
            fa = sum(first_half)/len(first_half)
            sa = sum(second_half)/len(second_half)
            trend = f"前半段均值 {fa:.1f}% → 后半段均值 {sa:.1f}%"

        prompt = f"""请根据以下 STOI 分析数据，给出 3 条具体的改进建议。

## 会话数据
- 工具：Claude Code，会话名：{report.session_name}
- 总轮次：{report.total_turns}（有效：{report.valid_turns}）
- 模型：{report.model}

## L1: KV Cache 效率
- 平均含屎量：{report.avg_stoi_score:.1f}%（{report.stoi_level}）
- 平均缓存命中率：{report.avg_cache_hit_rate:.1f}%
- 总输入：{report.total_input:,} tokens，其中缓存命中：{report.total_cache_read:,} tokens
- 实际花费：${report.total_cost_actual:.4f}，因 cache 节省：${report.total_cost_saved:.4f}
- 趋势：{trend or "数据不足"}

## L2: 输出有效性
- 有效轮次：{report.valid_turns_count}，被否定：{report.invalid_turns_count}，部分有效：{report.partial_turns_count}
- 有效率：{report.effectiveness_rate:.1f}%
- 被否定输出浪费：${report.waste_cost:.4f}

## 检测到的问题
{issues_text}

请给出 3 条建议，每条一段，格式：
**问题**：XXX
**操作**：具体怎么做（不超过 2 句话）
**收益**：预期节省 XX% token 或 $XX"""

        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=model or "claude-sonnet-4-5",
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


# ── Claude Code 全局统计（stats-cache.json）─────────────────────────────────
def load_claude_stats() -> dict:
    """
    读取 ~/.claude/stats-cache.json，返回全局统计。
    这是 STOI 最有价值的数据源之一——涵盖所有历史 session。
    """
    stats_file = Path("~/.claude/stats-cache.json").expanduser()
    if not stats_file.exists():
        return {}
    try:
        data = json.loads(stats_file.read_text(encoding="utf-8"))
        return data
    except Exception:
        return {}


def get_global_efficiency_report() -> dict:
    """
    基于 stats-cache.json 生成全局 Token 效率报告。
    不需要分析单个 session，直接从汇总数据中提取。
    """
    data = load_claude_stats()
    if not data:
        return {"error": "未找到 ~/.claude/stats-cache.json"}

    # 模型使用情况
    model_usage = data.get("modelUsage", {})
    total_input      = sum(v.get("inputTokens", 0) for v in model_usage.values())
    total_output     = sum(v.get("outputTokens", 0) for v in model_usage.values())
    total_cache_read = sum(v.get("cacheReadInputTokens", 0) for v in model_usage.values())
    total_cache_write= sum(v.get("cacheCreationInputTokens", 0) for v in model_usage.values())
    total_context    = total_input + total_cache_read + total_cache_write

    # 全局含屎量（cache miss 比例）
    global_stoi = round(total_input / total_context * 100, 1) if total_context > 0 else 0.0
    global_hit  = round(total_cache_read / total_context * 100, 1) if total_context > 0 else 0.0

    # 按模型排序
    model_stats = []
    for model, v in sorted(model_usage.items(),
                            key=lambda x: x[1].get("inputTokens", 0), reverse=True)[:5]:
        ctx = v.get("inputTokens", 0) + v.get("cacheReadInputTokens", 0) + v.get("cacheCreationInputTokens", 0)
        model_stats.append({
            "model":      model,
            "input":      v.get("inputTokens", 0),
            "output":     v.get("outputTokens", 0),
            "cache_read": v.get("cacheReadInputTokens", 0),
            "hit_rate":   round(v.get("cacheReadInputTokens", 0) / ctx * 100, 1) if ctx > 0 else 0.0,
            "cost_usd":   v.get("costUSD", 0),
        })

    # 每日活动
    daily = data.get("dailyActivity", [])
    recent_days = sorted(daily, key=lambda x: x.get("date", ""))[-14:]
    avg_msg_per_day = sum(d.get("messageCount", 0) for d in recent_days) / max(len(recent_days), 1)
    avg_session_len = (
        sum(d.get("messageCount", 0) for d in recent_days) /
        max(sum(d.get("sessionCount", 1) for d in recent_days), 1)
    )

    # 重复发送检测（从 history.jsonl 取最近消息）
    repeat_count = _detect_repeat_messages()

    # 最长 session
    longest = data.get("longestSession", {})

    # 按项目分组统计（从 session 文件目录名提取）
    project_stats = _get_project_stats()

    return {
        "total_messages":   data.get("totalMessages", 0),
        "total_sessions":   data.get("totalSessions", 0),
        "total_input":      total_input,
        "total_output":     total_output,
        "total_cache_read": total_cache_read,
        "total_context":    total_context,
        "global_stoi":      global_stoi,
        "global_hit_rate":  global_hit,
        "model_stats":      model_stats,
        "avg_msg_per_day":  round(avg_msg_per_day, 1),
        "avg_session_len":  round(avg_session_len, 1),
        "repeat_messages":  repeat_count,
        "longest_session":  longest,
        "recent_days":      recent_days[-7:],
        "project_stats":    project_stats,
    }


def _get_project_stats(top: int = 5) -> list[dict]:
    """
    按项目分组统计 session 数量和大小。
    项目 = ~/.claude/projects/ 下的目录名（对应工作目录路径）
    """
    base = Path("~/.claude/projects").expanduser()
    if not base.exists():
        return []

    projects = []
    for proj_dir in base.iterdir():
        if not proj_dir.is_dir():
            continue
        sessions = list(proj_dir.glob("*.jsonl"))
        if not sessions:
            continue
        total_size = sum(f.stat().st_size for f in sessions)
        latest_mtime = max(f.stat().st_mtime for f in sessions)
        # 把目录名还原为路径（-Users-kevinyoung-Desktop-xxx → ~/Desktop/xxx）
        readable = proj_dir.name.replace("-", "/").lstrip("/")
        readable = "~/" + "/".join(readable.split("/")[2:]) if "/" in readable else readable
        projects.append({
            "path":         readable[:40],
            "dir_name":     proj_dir.name[:30],
            "sessions":     len(sessions),
            "total_size_mb": round(total_size / 1024 / 1024, 1),
            "latest_mtime": latest_mtime,
        })

    return sorted(projects, key=lambda x: x["total_size_mb"], reverse=True)[:top]


def _detect_repeat_messages(window_minutes: int = 5) -> int:
    """检测 history.jsonl 中短时间内重复发送的消息数量"""
    history_file = Path("~/.claude/history.jsonl").expanduser()
    if not history_file.exists():
        return 0
    try:
        records = []
        with open(history_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    records.append({
                        "text": obj.get("display", "")[:100],
                        "ts":   obj.get("timestamp", 0),
                    })
                except Exception:
                    continue

        # 找 window 内的重复
        repeat_count = 0
        for i in range(1, len(records)):
            if (records[i]["text"] == records[i-1]["text"] and
                abs(records[i]["ts"] - records[i-1]["ts"]) < window_minutes * 60 * 1000):
                repeat_count += 1
        return repeat_count
    except Exception:
        return 0


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
