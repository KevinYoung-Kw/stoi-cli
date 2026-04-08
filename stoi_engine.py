#!/usr/bin/env python3
"""
stoi_engine.py — STOI 含屎量分析引擎
L1: Syntax waste 语法废话检测
L3: Cache blame 缓存击穿元凶识别
"""

import re
from typing import Optional


# ── 含屎量阈值 ──────────────────────────────────────────────────────────────────
SHIT_THRESHOLDS = {
    "CLEAN":          (0,   30),
    "MILD_SHIT":      (30,  50),
    "SHIT_OVERFLOW":  (50,  75),
    "DEEP_SHIT":      (75,  101),
}

SHIT_EMOJI = {
    "CLEAN":         "✅",
    "MILD_SHIT":     "🟡",
    "SHIT_OVERFLOW": "🟠",
    "DEEP_SHIT":     "💩",
}

TTS_MESSAGES = {
    "CLEAN":          "干净！这才叫工程师。",
    "MILD_SHIT":      "含屎量偏高，你的词元在哭泣。",
    "SHIT_OVERFLOW":  "含屎量严重超标，建议立刻停止 Vibe Coding。",
    "DEEP_SHIT":      "警告！深度含屎！你的算力正在窒息！",
}


# ── L1: Syntax waste 语法废话检测 ───────────────────────────────────────────────
def l1_syntax_waste(system_prompt: str) -> dict:
    """
    检测 System Prompt 中的格式化废话：
    - **粗体** Markdown
    - ### 标题
    - JSON 缩进
    - 多余的冒号列表
    Returns: {waste_rate: float, examples: list[str], suggestion: str, token_estimate: int}
    """
    if not system_prompt:
        return {"waste_rate": 0.0, "examples": [], "suggestion": "无 System Prompt", "token_estimate": 0}

    examples = []
    waste_chars = 0
    total_chars = len(system_prompt)

    # 检测 **粗体**
    bold_matches = re.findall(r'\*\*[^*]+\*\*', system_prompt)
    if bold_matches:
        # 每个粗体标记浪费 4 个符号字符
        waste_chars += len(bold_matches) * 4
        examples.append(f"**粗体** ×{len(bold_matches)} 处 → 纯格式字符，LLM 理解不需要")

    # 检测 ### 标题
    header_matches = re.findall(r'^#{1,6}\s+', system_prompt, re.MULTILINE)
    if header_matches:
        waste_chars += sum(len(m) for m in header_matches)
        examples.append(f"Markdown 标题 ×{len(header_matches)} 处 → 纯视觉装饰，无语义价值")

    # 检测多行 JSON 缩进（连续空格缩进）
    json_indent_lines = re.findall(r'^\s{4,}', system_prompt, re.MULTILINE)
    if len(json_indent_lines) > 5:
        indent_waste = sum(len(m) for m in json_indent_lines)
        waste_chars += indent_waste
        examples.append(f"深层缩进 ×{len(json_indent_lines)} 行 → JSON 可压缩为单行节省 ~{indent_waste} 字符")

    # 检测重复的分隔线
    separator_matches = re.findall(r'^[-=*]{10,}$', system_prompt, re.MULTILINE)
    if separator_matches:
        waste_chars += sum(len(m) for m in separator_matches)
        examples.append(f"装饰分隔线 ×{len(separator_matches)} 处 → 完全没用的 ASCII 艺术")

    # 估算 token 浪费 (粗略：4 chars ≈ 1 token)
    token_estimate = waste_chars // 4

    if total_chars == 0:
        waste_rate = 0.0
    else:
        waste_rate = min(round(waste_chars / total_chars * 100, 1), 100.0)

    if not examples:
        suggestion = "✓ System Prompt 格式干净，无明显语法废话"
    else:
        suggestion = "建议压缩 Markdown 格式 → 改用纯文本或 XML 标签结构"

    return {
        "waste_rate": waste_rate,
        "examples": examples,
        "suggestion": suggestion,
        "token_estimate": token_estimate,
    }


# ── L3: Cache blame 缓存击穿元凶识别 ───────────────────────────────────────────
L3_PATTERNS = {
    'timestamp': {
        'pattern': r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}',
        'desc': '时间戳注入',
        'detail': '每次请求时间不同 → Cache 必然 Miss',
        'fix': '移至 user message 或从 system prompt 删除',
        'severity': 'HIGH',
    },
    'uuid': {
        'pattern': r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        'desc': '随机 UUID',
        'detail': '每次生成不同 → 完美的 Cache Buster',
        'fix': '使用固定 session ID 或移至 user message',
        'severity': 'HIGH',
    },
    'abs_path': {
        'pattern': r'/Users/[A-Za-z0-9_]+|/home/[A-Za-z0-9_]+',
        'desc': '用户绝对路径',
        'detail': '换机器/换用户即失效 → 跨设备 Cache Miss',
        'fix': '使用相对路径或环境变量占位符',
        'severity': 'MEDIUM',
    },
    'pid': {
        'pattern': r'\bpid[:\s=]+\d+',
        'desc': '进程 ID (PID)',
        'detail': '每次启动都变 → 完全不可复用',
        'fix': '从 system prompt 移除',
        'severity': 'HIGH',
    },
    'random_num': {
        'pattern': r'\bnonce[:\s=]+[0-9a-f]{8,}',
        'desc': 'Nonce / 随机数',
        'detail': '防重放 token 每次唯一 → 必然 Cache Miss',
        'fix': '移至 user message',
        'severity': 'HIGH',
    },
    'git_hash': {
        'pattern': r'\b[0-9a-f]{7,40}\b',
        'desc': 'Git commit hash',
        'detail': '每次部署变更 → Cache 每次失效',
        'fix': '使用版本号标签而非 commit hash',
        'severity': 'LOW',
    },
}


def l3_cache_blame(system_prompt: str) -> dict:
    """
    扫描 System Prompt，找出导致 Cache Miss 的动态元数据
    Returns: {culprits: list[dict], severity: str, suggestion: str, score_penalty: float}
    """
    if not system_prompt:
        return {
            "culprits": [],
            "severity": "NONE",
            "suggestion": "无 System Prompt 可分析",
            "score_penalty": 0.0,
        }

    culprits = []
    max_severity_rank = 0
    severity_rank = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}

    for key, info in L3_PATTERNS.items():
        matches = re.findall(info['pattern'], system_prompt, re.IGNORECASE)
        if matches:
            culprits.append({
                "type": key,
                "desc": info['desc'],
                "detail": info['detail'],
                "fix": info['fix'],
                "severity": info['severity'],
                "matches": matches[:3],  # 最多展示3个样本
                "count": len(matches),
            })
            rank = severity_rank.get(info['severity'], 0)
            if rank > max_severity_rank:
                max_severity_rank = rank

    severity_map = {0: "NONE", 1: "LOW", 2: "MEDIUM", 3: "HIGH"}
    overall_severity = severity_map[max_severity_rank]

    # 严重度惩罚分数
    score_penalty = {
        "NONE": 0.0,
        "LOW": 5.0,
        "MEDIUM": 15.0,
        "HIGH": 25.0,
    }[overall_severity]

    if not culprits:
        suggestion = "✓ 未发现动态字段，Cache 可正常命中"
    else:
        fixes = list({c['fix'] for c in culprits})
        suggestion = " | ".join(fixes[:2])

    return {
        "culprits": culprits,
        "severity": overall_severity,
        "suggestion": suggestion,
        "score_penalty": score_penalty,
    }


# ── 核心含屎量计算 ───────────────────────────────────────────────────────────────
def calc_stoi(usage: dict, turn_index: int = -1, session_turns: list = None) -> dict:
    """
    含屎量公式 v2 — 区分"正常不命中"与"可避免浪费"

    核心原则：
      - 第 0 轮（session 首次请求）：正在建缓存，不算含屎，STOI=0
      - cache_creation > 0：正在写缓存（首次或失效后重建），不算含屎
      - 后续轮 cache_read=0 但上轮有 cache_creation：才是真正的 cache miss → 含屎

    Anthropic API 字段：
      input_tokens                = 未命中缓存的新 token
      cache_read_input_tokens     = 命中缓存的 token（便宜 10x）
      cache_creation_input_tokens = 写入缓存的 token（建缓存，贵 1.25x）
    """
    new_tokens     = usage.get("input_tokens", 0)
    cache_read     = usage.get("cache_read_input_tokens", 0)
    cache_creation = usage.get("cache_creation_input_tokens", 0)
    output_tokens  = usage.get("output_tokens", 0)
    total_context  = new_tokens + cache_read + cache_creation

    if total_context == 0:
        return {
            "stoi_score": 0.0, "level": "CLEAN",
            "input_tokens": 0, "new_tokens": 0, "output_tokens": 0,
            "cache_read": 0, "cache_creation": 0,
            "cache_hit_rate": 0.0, "wasted_tokens": 0,
            "is_baseline": True, "note": "无数据",
        }

    # ── 判断是否为"正常不命中"轮次 ──────────────────────────────────────────────
    is_baseline = False
    note = ""

    # 情况0：output_tokens=0 → 流式推理中间状态 / thinking stub，不是真实对话轮次
    # Claude Code 在流式输出时会先发多个 output=0 的占位请求，这些不参与评分
    if output_tokens == 0:
        is_baseline = True
        note = "流式推理占位轮（output=0），不计入含屎量"

    # 情况1：第一轮或无法判断轮次 → 建缓存基准轮
    elif turn_index == 0:
        is_baseline = True
        note = "首轮建缓存，基准轮不计含屎"

    # 情况2：本轮正在写缓存（cache_creation 占比 > 50%）→ 重建缓存轮
    elif cache_creation > 0 and cache_creation > cache_read:
        is_baseline = True
        note = f"缓存重建轮（写入 {cache_creation:,} tokens）"

    # 情况3：无法判断轮次时，若完全没有缓存信息则跳过
    elif turn_index == -1 and cache_read == 0 and cache_creation == 0:
        is_baseline = True
        note = "无缓存信息，跳过评分"

    if is_baseline:
        # 基准轮：score=0，但仍记录数据
        cache_hit_rate = round(cache_read / total_context * 100, 1) if total_context > 0 else 0.0
        return {
            "stoi_score": 0.0, "level": "CLEAN",
            "input_tokens": total_context, "new_tokens": new_tokens,
            "output_tokens": output_tokens, "cache_read": cache_read,
            "cache_creation": cache_creation, "cache_hit_rate": cache_hit_rate,
            "wasted_tokens": 0, "is_baseline": True, "note": note,
        }

    # ── 正式计算含屎量 ──────────────────────────────────────────────────────────
    # 真正的含屎 = 本该命中缓存却没命中的 token
    # 分母用 total_context（包含 cache_read），体现真实利用率
    cache_hit_rate = round(cache_read / total_context * 100, 1)

    # 含屎量 = 未命中缓存 / 总上下文
    # 但要扣除合理的"新增内容"（output_tokens 作为下轮的新 input 是正常的）
    # 简单版：直接用 (total_context - cache_read) / total_context
    # 即：未被缓存复用的部分占比
    raw_shit = (total_context - cache_read) / total_context * 100

    # 调节：如果 cache_creation 很大（说明在积极建缓存），降低惩罚
    if cache_creation > 0:
        creation_ratio = cache_creation / total_context
        raw_shit = raw_shit * (1 - creation_ratio * 0.5)  # 建缓存最多减半惩罚

    stoi_score = round(min(raw_shit, 100.0), 1)

    level = "DEEP_SHIT"
    for lvl, (lo, hi) in SHIT_THRESHOLDS.items():
        if lo <= stoi_score < hi:
            level = lvl
            break

    return {
        "stoi_score":     stoi_score,
        "level":          level,
        "input_tokens":   total_context,
        "new_tokens":     new_tokens,
        "output_tokens":  output_tokens,
        "cache_read":     cache_read,
        "cache_creation": cache_creation,
        "cache_hit_rate": cache_hit_rate,
        "wasted_tokens":  total_context - cache_read,
        "is_baseline":    False,
        "note":           "",
    }


def calc_stoi_score(usage: dict, system_prompt: str = "") -> dict:
    """
    全层 STOI 计算：
    L0 基础 cache miss 分数（主要权重 0.65）
    L1 语法废话惩罚（权重 0.15）
    L3 缓存击穿惩罚（权重 0.35）
    最终 = L0 * 0.65 + L1_penalty * 0.15 + L3_penalty * 0.20
    Note: 这只在有 system_prompt 时才有 L1/L3，否则纯 L0。
    """
    base = calc_stoi(usage)
    l1 = l1_syntax_waste(system_prompt) if system_prompt else {"waste_rate": 0.0, "examples": [], "suggestion": "", "token_estimate": 0}
    l3 = l3_cache_blame(system_prompt) if system_prompt else {"culprits": [], "severity": "NONE", "suggestion": "", "score_penalty": 0.0}

    if system_prompt:
        # 多层加权
        combined = (
            base["stoi_score"] * 0.65
            + l1["waste_rate"] * 0.15
            + l3["score_penalty"] * 0.20
        )
        combined = round(min(combined, 100.0), 1)
    else:
        combined = base["stoi_score"]

    level = "DEEP_SHIT"
    for lvl, (lo, hi) in SHIT_THRESHOLDS.items():
        if lo <= combined < hi:
            level = lvl
            break

    return {
        **base,
        "stoi_score":    combined,
        "level":         level,
        "l1":            l1,
        "l3":            l3,
        "cache_hit_rate": base["cache_hit_rate"],
    }


def get_score_color(score: float) -> str:
    """返回 Rich 颜色字符串"""
    if score < 30:
        return "green"
    elif score < 50:
        return "yellow"
    elif score < 75:
        return "dark_orange"
    else:
        return "red"


def get_level_display(level: str) -> str:
    """返回带 emoji 的等级显示"""
    emoji = SHIT_EMOJI.get(level, "❓")
    return f"{emoji} {level}"


# ── L4：用户反馈信号法则（艺术法则）────────────────────────────────────────────
# 核心洞察：用户的下一条消息是对 AI 输出价值的最直接判断
# 不需要 LLM，不需要 embedding，用对话本身作为 ground truth

NEGATIVE_SIGNALS = [
    "没看到", "不对", "还是不行", "没改", "没有生成", "没有输出",
    "不符合", "理解错了", "为什么没有", "怎么没", "跑不起来",
    "没生效", "找不到", "没找到", "没有这个", "没变化", "还是一样",
    "没用", "不管用", "无效", "没有效果", "又报错", "还是报错",
]
POSITIVE_SIGNALS = [
    "好了", "可以了", "对了", "没问题", "谢谢", "收到", "完美",
    "很好", "不错", "可以", "好的", "ok", "成功", "搞定", "太棒了",
]
FIXUP_SIGNALS = [  # 追加修改 → 上一轮部分有效但不完整
    "再", "还要", "另外", "补上", "补一下", "修改", "改一下",
    "调整", "优化", "完善", "继续", "下一步",
]

def l4_feedback_validity(next_user_msg: str) -> dict:
    """
    L4 层：用用户下一条消息判断上一轮 AI 输出的价值

    返回：
      validity: "valid" | "invalid" | "partial" | "unknown"
      signal:   触发的关键词
      penalty:  含屎量惩罚分（0-30）
    """
    if not next_user_msg:
        return {"validity": "unknown", "signal": "", "penalty": 0}

    text = next_user_msg.strip().casefold()

    # 负面信号：上一轮无效
    for sig in NEGATIVE_SIGNALS:
        if text.startswith(sig.casefold()) or sig.casefold() in text[:20]:
            return {"validity": "invalid", "signal": sig, "penalty": 30}

    # 正面信号：上一轮有效
    for sig in POSITIVE_SIGNALS:
        if text.startswith(sig.casefold()):
            return {"validity": "valid", "signal": sig, "penalty": 0}

    # 追加修改信号：部分有效
    for sig in FIXUP_SIGNALS:
        if text.startswith(sig.casefold()):
            return {"validity": "partial", "signal": sig, "penalty": 10}

    return {"validity": "unknown", "signal": "", "penalty": 5}


def analyze_session_validity(records: list[dict]) -> list[dict]:
    """
    对整个 session 做 L4 有效性标注。
    records 需要包含 role 和 content 字段（来自原始 session 文件）。

    逻辑：
      - 找每个 assistant 轮次后的第一条 user 消息
      - 用 l4_feedback_validity 判断有效性
      - 把结果注入到对应的 stoi 记录里
    """
    annotated = []
    for i, rec in enumerate(records):
        r = dict(rec)
        # 找下一条 user 消息
        next_user = ""
        for j in range(i + 1, min(i + 3, len(records))):
            if records[j].get("role") == "user":
                next_user = records[j].get("content", "")[:100]
                break
        l4 = l4_feedback_validity(next_user)
        r["l4"] = l4
        # 把 L4 惩罚加到 stoi_score（如果是真实输出轮）
        if not r.get("stoi", {}).get("is_baseline") and l4["validity"] == "invalid":
            old = r["stoi"]["stoi_score"]
            r["stoi"]["stoi_score"] = min(100.0, old + l4["penalty"])
            r["stoi"]["l4_penalty"] = l4["penalty"]
            # 重新计算等级
            for lvl, (lo, hi) in SHIT_THRESHOLDS.items():
                if lo <= r["stoi"]["stoi_score"] < hi:
                    r["stoi"]["level"] = lvl
                    break
        annotated.append(r)
    return annotated
