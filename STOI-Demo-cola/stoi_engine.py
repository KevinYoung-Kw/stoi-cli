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
def calc_stoi(usage: dict) -> dict:
    """
    STOI = (non_cached_input / total_context) * 100
    
    Anthropic API 返回:
      input_tokens              = 未命中缓存的新 token（需要实际计算的部分）
      cache_read_input_tokens   = 命中缓存的 token（便宜 10x）
      cache_creation_input_tokens = 写入缓存的 token（贵 1.25x，首次）
    
    total_context = input_tokens + cache_read + cache_creation
    STOI = input_tokens / total_context * 100
    越低越好（越多命中缓存 = 越省钱 = 越干净）
    """
    new_tokens     = usage.get("input_tokens", 0)           # 未命中缓存
    cache_read     = usage.get("cache_read_input_tokens", 0)   # 命中缓存
    cache_creation = usage.get("cache_creation_input_tokens", 0)  # 写入缓存
    output_tokens  = usage.get("output_tokens", 0)

    # 总上下文 token 数（三者之和才是真实发送量）
    total_context = new_tokens + cache_read + cache_creation

    if total_context == 0:
        stoi_score = 0.0
        cache_hit_rate = 0.0
    else:
        # STOI = 含屎量 = 未命中比例（越高越浪费）
        stoi_score = round(new_tokens / total_context * 100, 1)
        cache_hit_rate = round(cache_read / total_context * 100, 1)

    level = "DEEP_SHIT"
    for lvl, (lo, hi) in SHIT_THRESHOLDS.items():
        if lo <= stoi_score < hi:
            level = lvl
            break

    return {
        "stoi_score":     stoi_score,
        "level":          level,
        "input_tokens":   total_context,      # 对外展示总上下文
        "new_tokens":     new_tokens,          # 实际新计算量
        "output_tokens":  output_tokens,
        "cache_read":     cache_read,
        "cache_creation": cache_creation,
        "cache_hit_rate": cache_hit_rate,
        "wasted_tokens":  new_tokens,          # 未命中缓存的 = 浪费的
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
