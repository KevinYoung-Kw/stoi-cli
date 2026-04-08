#!/usr/bin/env python3
"""
stoi_output_analysis.py — Output Token 冗余检测

借鉴 Thinking Token 冗余分析的方法论（Yuan 2026, Zhu 2026, Jiang 2026）
将五种冗余模式映射到普通 Output Token 的检测：

Thinking Token 模式          → Output Token 对应问题
─────────────────────────────────────────────────────
重复验证（Jaccard > 0.8）    → 连续轮次输出高度重复
无关探索（Forest of Errors） → 给出多方案但用户只需一个
无差别反思                   → Yapping 废话框架
深度冗余                     → 回答末尾重复开头内容
过度思考                     → 简单问题输出过长

数据来源：stoi_proxy.py 存储的 output_text 字段
"""

import re
import json
from pathlib import Path
from typing import Optional


# ── Yapping 模式（针对 Claude Code 工具型输出）────────────────────────────────
# Claude Code 的输出不是对话式，而是任务执行报告
# Yapping = 重复总结、不必要的验证说明、多余的成功确认
YAPPING_PATTERNS = [
    # 对话式废话（仍然可能出现）
    (r'^(好的|当然|非常好|很好)[,，]?\s*(我|让我)', "开头客套"),
    (r'^作为.*?(AI|助手|语言模型)', "自我介绍废话"),
    (r'希望.*?对您?有(所)?帮助', "结尾客套"),
    (r'如果.*?(还有|有任何).*?问题.*?随时', "结尾问询"),
    # Claude Code 特有的冗余模式
    (r'(已完成|操作完成|执行完毕)[。！]?\s*(如果|需要|请)', "完成后追问"),
    (r'(以上|如上|综上)(所述|内容|改动).*?(完整|正确|符合)', "重复总结"),
    (r'(总结|总结如下|主要改动|改动如下)[:：]\s*\n.*?[-•].*?\n.*?[-•]', "不必要的总结列表"),
    # 重复验证（执行完还要说一遍做了什么）
    (r'(文件|代码|内容).{0,10}(已|成功).{0,20}(创建|修改|更新|完成).*?主要(改动|变化|内容)', "执行+验证重复"),
]


# ── Yapping 废话参考库（embedding 相似度匹配用）─────────────────────────────
YAPPING_TEMPLATES = [
    "好的，让我来帮您解决这个问题。",
    "当然，我很乐意为您提供帮助。",
    "希望以上内容对您有所帮助！",
    "如果您还有任何问题，请随时告诉我。",
    "以上是本次操作的完整总结。",
    "综上所述，所有改动均已完成并验证。",
    "主要改动如上所列，如需进一步调整请告知。",
    "操作成功完成，请查看上述详细说明。",
]

_yapping_embeddings = None
_embed_cache: dict = {}


def _get_api_config() -> tuple[str, str, str]:
    """从 stoi config 获取 API 配置"""
    try:
        cfg = json.loads(Path("~/.stoi/config.json").expanduser().read_text())
        llm = cfg.get("llm", {})
        return (
            llm.get("api_key", ""),
            llm.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            llm.get("model", "qwen-turbo"),
        )
    except Exception:
        return "", "", "qwen-turbo"


def _get_embedding(text: str):
    """调用 embedding API（dashscope text-embedding-v3）"""
    key = text[:100]
    if key in _embed_cache:
        return _embed_cache[key]
    try:
        api_key, base_url, _ = _get_api_config()
        if not api_key:
            return None
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.embeddings.create(model="text-embedding-v3", input=text[:512])
        vec = resp.data[0].embedding
        _embed_cache[key] = vec
        return vec
    except Exception:
        return None


def _cosine_sim(a: list[float], b: list[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na * nb > 0 else 0.0


def _get_yapping_embeddings():
    """懒加载废话模板的 embedding，只计算一次"""
    global _yapping_embeddings
    if _yapping_embeddings is not None:
        return _yapping_embeddings
    vecs = [v for v in (_get_embedding(t) for t in YAPPING_TEMPLATES) if v]
    _yapping_embeddings = vecs
    return vecs


def _llm_judge_yapping(text: str) -> dict:
    """用 qwen-turbo 精确判断 Yapping（仅在 embedding 疑似时调用）"""
    try:
        api_key, base_url, model = _get_api_config()
        if not api_key:
            return {"score": 0.0, "reason": ""}
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        prompt = f"""判断这段 AI 输出中有多少是废话（对完成任务没有实质贡献）。

废话包括：开头客套、结尾问询、不必要的总结列表、执行完成后的重复确认。

输出（前300字）：
{text[:300]}

只输出 JSON：{{"yapping_score": 0.0-1.0, "reason": "一句话", "sample": "最典型废话片段（20字内）"}}"""
        resp = client.chat.completions.create(
            model="qwen-turbo",  # 强制用最轻量模型
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
        )
        result = json.loads(resp.choices[0].message.content)
        return {
            "score":  float(result.get("yapping_score", 0)),
            "reason": result.get("reason", ""),
            "sample": result.get("sample", ""),
        }
    except Exception:
        return {"score": 0.0, "reason": ""}


def detect_yapping(text: str, use_llm: bool = False) -> dict:
    """
    三层 Yapping 检测：
    1. 正则（0成本，快）
    2. embedding 相似度（极低成本，语义）
    3. qwen-turbo judge（低成本，精确，仅在前两层疑似时触发）
    """
    if not text:
        return {"yapping_rate": 0.0, "patterns": [], "method": "none"}

    total_chars = len(text)
    found = []
    yapping_chars = 0

    # 第一层：正则
    for pattern, label in YAPPING_PATTERNS:
        matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
        if matches:
            for m in matches:
                chars = len(m) if isinstance(m, str) else sum(len(x) for x in m)
                yapping_chars += chars
                found.append({"pattern": label, "sample": str(m)[:50]})

    regex_rate = round(min(yapping_chars / total_chars, 1.0), 3) if total_chars > 0 else 0.0

    # 第二层：embedding 相似度
    text_vec = _get_embedding(text[:300])
    yapping_vecs = _get_yapping_embeddings() if text_vec else []

    embed_max_sim = 0.0
    if text_vec and yapping_vecs:
        embed_max_sim = max(_cosine_sim(text_vec, yv) for yv in yapping_vecs)

    # 相似度 > 0.7 认为疑似废话
    embed_rate = round(max(embed_max_sim - 0.5, 0) * 2, 3)

    # 第三层：LLM judge（疑似且启用时才调用）
    if use_llm and (regex_rate > 0.05 or embed_rate > 0.4):
        llm_result = _llm_judge_yapping(text)
        final_rate = max(regex_rate, embed_rate * 0.6, llm_result["score"] * 0.8)
        return {
            "yapping_rate": round(final_rate, 3),
            "patterns":     found + ([{"pattern": "llm", "sample": llm_result["sample"]}]
                                      if llm_result["sample"] else []),
            "method":       "regex+embedding+llm",
            "embed_sim":    round(embed_max_sim, 3),
            "llm_score":    llm_result["score"],
            "llm_reason":   llm_result["reason"],
        }

    final_rate = max(regex_rate, embed_rate * 0.7)
    method = "regex+embedding" if embed_max_sim > 0 else "regex"
    return {
        "yapping_rate": round(final_rate, 3),
        "patterns": found[:5],
        "method":   method,
        "embed_sim": round(embed_max_sim, 3) if embed_max_sim > 0 else None,
    }


# ── 重复内容检测（重复验证对应）──────────────────────────────────────────────
def jaccard_similarity(text_a: str, text_b: str) -> float:
    """计算两段文本的 Jaccard 相似度（词级别）"""
    if not text_a or not text_b:
        return 0.0
    words_a = set(re.findall(r'\w+', text_a.lower()))
    words_b = set(re.findall(r'\w+', text_b.lower()))
    if not words_a and not words_b:
        return 0.0
    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    return intersection / union if union > 0 else 0.0


def detect_repetition(turns: list[dict]) -> dict:
    """
    检测连续轮次之间的重复（对应 Thinking 的重复验证）
    turns: [{"output_text": str, "turn": int}, ...]
    """
    if len(turns) < 2:
        return {"repetition_rate": 0.0, "repeat_pairs": []}

    outputs = [(t.get("turn", i), t.get("output_text", ""))
               for i, t in enumerate(turns) if t.get("output_text")]

    repeat_pairs = []
    for i in range(len(outputs) - 1):
        turn_a, text_a = outputs[i]
        turn_b, text_b = outputs[i + 1]
        sim = jaccard_similarity(text_a[:500], text_b[:500])
        if sim > 0.5:  # 50% 相似即为潜在重复
            repeat_pairs.append({
                "turns": [turn_a, turn_b],
                "similarity": round(sim, 3),
                "severity": "HIGH" if sim > 0.8 else "MED",
            })

    total_pairs = len(outputs) - 1
    rep_rate = len(repeat_pairs) / total_pairs if total_pairs > 0 else 0.0

    return {
        "repetition_rate": round(rep_rate, 3),
        "repeat_pairs": repeat_pairs[:5],
        "high_severity_count": sum(1 for p in repeat_pairs if p["severity"] == "HIGH"),
    }


# ── 多方案冗余（无关探索对应）────────────────────────────────────────────────
MULTI_SOLUTION_PATTERNS = [
    r'(方案|方法|选项|option|approach)\s*[一二三1-3①-③]',
    r'(第[一二三]种|第[123]个)\s*(方案|方法|选择)',
    r'(alternatively|alternatively,|another approach)',
    r'(或者你也可以|你还可以|另一种方式)',
]

def detect_multi_solution(text: str) -> dict:
    """检测是否给出了不必要的多个方案（对应 Thinking 的无关探索）"""
    if not text:
        return {"has_multi_solution": False, "solution_count": 0}

    count = 0
    for pattern in MULTI_SOLUTION_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        count += len(matches)

    return {
        "has_multi_solution": count >= 2,
        "solution_count": count,
        "note": "给出多个方案时，用户通常只需要最优的一个（参考 Forest of Errors 论文）" if count >= 2 else "",
    }


# ── 首尾重复（深度冗余对应）──────────────────────────────────────────────────
def detect_head_tail_redundancy(text: str) -> dict:
    """检测回答首尾是否重复总结（对应 Thinking 的深度冗余）"""
    if not text or len(text) < 200:
        return {"has_redundancy": False, "similarity": 0.0}

    # 取前 20% 和后 20% 对比
    split = max(len(text) // 5, 100)
    head = text[:split]
    tail = text[-split:]
    sim = jaccard_similarity(head, tail)

    return {
        "has_redundancy": sim > 0.4,
        "similarity": round(sim, 3),
        "note": "回答末尾重复了开头的内容，可删除" if sim > 0.4 else "",
    }


# ── 任务复杂度 vs 输出长度（过度思考对应）───────────────────────────────────
def detect_overthinking(user_message: str, output_text: str) -> dict:
    """
    检测是否对简单问题给出了过长回答（对应 Thinking 的过度思考/Overthinking）
    启发式：用户消息很短 + 输出很长 → 可能过度
    """
    if not user_message or not output_text:
        return {"is_overthinking": False, "ratio": 0.0}

    user_len   = len(user_message.split())
    output_len = len(output_text.split())
    ratio = output_len / max(user_len, 1)

    # 用户消息 < 10 词但输出 > 200 词，比例 > 20x → 可能过度
    is_overthinking = user_len < 10 and output_len > 200 and ratio > 20

    return {
        "is_overthinking": is_overthinking,
        "ratio": round(ratio, 1),
        "user_words":   user_len,
        "output_words": output_len,
        "note": f"简单问题（{user_len}词）却给出{output_len}词回答，考虑加输出长度约束" if is_overthinking else "",
    }


# ── 综合分析 ──────────────────────────────────────────────────────────────────
def analyze_output_quality(proxy_records: list[dict]) -> dict:
    """
    基于 proxy 记录的 output_text 做综合输出质量分析。
    proxy_records: stoi proxy log 里的记录（需有 output_text 字段）
    """
    valid_records = [r for r in proxy_records
                     if r.get("output_text") and not r.get("stoi", {}).get("is_baseline")]

    if not valid_records:
        return {"error": "无 output_text 数据，请先使用 stoi start 代理模式收集数据"}

    # 汇总各维度分析
    yapping_scores   = []
    multi_sol_count  = 0
    head_tail_count  = 0
    overthink_count  = 0

    for rec in valid_records:
        out  = rec.get("output_text", "")
        user = rec.get("user_message", "")

        y = detect_yapping(out)
        yapping_scores.append(y["yapping_rate"])

        ms = detect_multi_solution(out)
        if ms["has_multi_solution"]:
            multi_sol_count += 1

        ht = detect_head_tail_redundancy(out)
        if ht["has_redundancy"]:
            head_tail_count += 1

        ot = detect_overthinking(user, out)
        if ot["is_overthinking"]:
            overthink_count += 1

    n = len(valid_records)
    avg_yapping = sum(yapping_scores) / n if n > 0 else 0.0

    # 重复检测
    rep = detect_repetition(valid_records)

    # 综合输出质量分（越高越浪费）
    output_waste_score = round(
        avg_yapping * 40 +
        (rep["repetition_rate"]) * 30 +
        (multi_sol_count / n) * 20 +
        (head_tail_count / n) * 10,
        1
    )

    issues = []
    if avg_yapping > 0.05:
        issues.append({
            "type": "yapping",
            "severity": "HIGH" if avg_yapping > 0.15 else "MED",
            "detail": f"平均 {avg_yapping*100:.1f}% 输出是礼貌废话（Yapping）",
            "fix": "在 CLAUDE.md 中加入：不要开头客套，不要结尾确认，直接输出结果",
        })
    if rep["repetition_rate"] > 0.2:
        issues.append({
            "type": "repetition",
            "severity": "HIGH" if rep["repetition_rate"] > 0.5 else "MED",
            "detail": f"{rep['repetition_rate']*100:.0f}% 的相邻轮次输出高度相似（Jaccard 相似度 > 50%）",
            "fix": "任务已完成后开新 session，避免 AI 重复解释同样内容",
        })
    if multi_sol_count > n * 0.3:
        issues.append({
            "type": "multi_solution",
            "severity": "MED",
            "detail": f"{multi_sol_count}/{n} 轮输出给了多个方案（参考 Forest of Errors：第一个方案通常最优）",
            "fix": "在 prompt 中明确：只给一个最优方案，不需要列举备选",
        })
    if overthink_count > n * 0.2:
        issues.append({
            "type": "overthinking",
            "severity": "MED",
            "detail": f"{overthink_count} 轮对简单问题给出了过长回答",
            "fix": "加入输出约束：简单问题控制在 200 token 以内",
        })

    return {
        "analyzed_turns":     n,
        "output_waste_score": output_waste_score,
        "avg_yapping_rate":   round(avg_yapping, 3),
        "repetition_rate":    rep["repetition_rate"],
        "multi_solution_pct": round(multi_sol_count / n, 3) if n > 0 else 0,
        "head_tail_redundancy_pct": round(head_tail_count / n, 3) if n > 0 else 0,
        "overthinking_pct":   round(overthink_count / n, 3) if n > 0 else 0,
        "issues":             issues,
        "high_repeat_pairs":  rep.get("high_severity_count", 0),
    }


def load_proxy_records() -> list[dict]:
    """从 ~/.stoi/sessions.jsonl 加载 proxy 记录"""
    log_file = Path("~/.stoi/sessions.jsonl").expanduser()
    if not log_file.exists():
        return []
    records = []
    try:
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    return records


def load_session_conversation(session_path: Path) -> list[dict]:
    """
    从 Claude Code session JSONL 直接读取对话对（不需要代理模式）
    结合 ~/.claude/history.jsonl 的用户消息 + session 文件的 AI 回复
    返回：[{"turn": int, "user_message": str, "output_text": str, "stoi": dict}]
    """
    records = []

    # 读 AI 回复（含 usage）
    try:
        with open(session_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("type") != "assistant":
                        continue
                    msg = obj.get("message", {})
                    usage = msg.get("usage", {})
                    if not usage:
                        continue

                    # 提取 AI 输出文本
                    output_text = ""
                    for c in (msg.get("content") or []):
                        if isinstance(c, dict) and c.get("type") == "text":
                            output_text += c.get("text", "")

                    # 过滤流式占位轮
                    if usage.get("output_tokens", 0) == 0:
                        continue

                    records.append({
                        "turn":        len(records),
                        "output_text": output_text[:1000],
                        "user_message": "",  # 稍后填充
                        "stoi":        {"is_baseline": False},
                        "usage":       usage,
                        "session_id":  obj.get("sessionId", ""),
                        "ts":          obj.get("timestamp", 0),
                    })
                except Exception:
                    continue
    except Exception:
        return []

    # 用 history.jsonl 回填用户消息
    history_file = Path("~/.claude/history.jsonl").expanduser()
    if history_file.exists():
        try:
            session_id = records[0]["session_id"] if records else ""
            user_msgs = []
            with open(history_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if obj.get("sessionId") == session_id:
                            user_msgs.append({
                                "text": obj.get("display", "")[:200],
                                "ts":   obj.get("timestamp", 0),
                            })
                    except Exception:
                        continue

            # 按时间戳配对：每条 AI 回复找前面最近的用户消息
            for rec in records:
                rec_ts = rec.get("ts", 0)
                if isinstance(rec_ts, str):
                    try:
                        from datetime import datetime
                        rec_ts = datetime.fromisoformat(rec_ts.replace("Z", "+00:00")).timestamp() * 1000
                    except Exception:
                        rec_ts = 0
                # 找时间戳比这轮小的最后一条用户消息
                preceding = [u for u in user_msgs if u["ts"] <= rec_ts]
                if preceding:
                    rec["user_message"] = preceding[-1]["text"]

        except Exception:
            pass

    return records
