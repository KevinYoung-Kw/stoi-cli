#!/usr/bin/env python3
"""
stoi_tokenizer.py — Token 重要性可视化

评分方法：
  主路径: LLM 批量评估（Integrated Gradients 离散近似，Sundararajan et al. ICML 2017）
    - 将文本分割为语义片段，单次 LLM 调用批量打分
    - "high"    → 删除此片段会导致任务失败或结果完全不同
    - "low"     → 删除此片段不影响任务结果
    - "neutral" → 不确定

  降级路径（无 API key 或 LLM 调用失败时）：
    - 仅检测 Markdown 装饰符（**bold**、### headers、---）作为 "waste"
    - 不标记时间戳、路径、UUID——这些可能是用户主动传入的必要信息

  渲染路径：
    - 用 tiktoken (cl100k_base) 做 token 计数
    - 把 LLM 的片段级打分映射回 tiktoken token 粒度，用于 HTML 着色

Python 3.9 兼容（无 str | None 语法）
"""

import json
import re
from typing import List, Dict, Optional, Tuple

# ── Markdown 装饰符 pattern（唯一的 "waste" fallback 规则）──────────────────
# 这类符号本身没有语义价值，不管上下文如何都是格式噪音
_MARKDOWN_WASTE_RE = re.compile(
    r'(?m)'
    r'(?:\*{2,3})'           # **bold** / ***bold*** 标记符本身
    r'|(?:^#{1,6}\s)'        # ### 标题前缀
    r'|(?:^-{3,}\s*$)'       # --- 分隔线
    r'|(?:^={3,}\s*$)'       # === 分隔线
    r'|(?:^>\s*$)'            # 空 blockquote
)

# ── 文本分片 ─────────────────────────────────────────────────────────────────

def _split_into_segments(text: str, target_words: int = 10) -> List[str]:
    """
    把文本分割为语义片段，供 LLM 批量评估。

    策略（优先级从高到低）：
      1. 按句子边界（。！？.!?）分割
      2. 按逗号/顿号分割过长的片段
      3. 若片段仍然超过 target_words * 2 个 token，按词窗口截断

    返回非空片段列表，保留原始文本（含空白），以便后续还原位置。
    """
    if not text or not text.strip():
        return []

    # 1. 先按中英文句子边界分割
    raw_sents = re.split(r'([。！？!?\n]+)', text)
    segments = []
    buf = ""
    for part in raw_sents:
        buf += part
        if re.search(r'[。！？!?\n]', part):
            s = buf.strip()
            if s:
                segments.append(s)
            buf = ""
    if buf.strip():
        segments.append(buf.strip())

    # 2. 过长片段再按逗号/顿号拆分
    refined = []
    for seg in segments:
        words = seg.split()
        if len(words) > target_words * 2:
            sub_parts = re.split(r'([,，、；;]+)', seg)
            sub_buf = ""
            for sp in sub_parts:
                sub_buf += sp
                if re.search(r'[,，、；;]', sp) and len(sub_buf.split()) >= target_words:
                    s = sub_buf.strip()
                    if s:
                        refined.append(s)
                    sub_buf = ""
            if sub_buf.strip():
                refined.append(sub_buf.strip())
        else:
            refined.append(seg)

    # 3. 仍然过长的片段按词窗口截断
    final = []
    for seg in refined:
        words = seg.split()
        if len(words) > target_words * 3:
            for i in range(0, len(words), target_words * 2):
                chunk = " ".join(words[i: i + target_words * 2])
                if chunk.strip():
                    final.append(chunk)
        else:
            if seg.strip():
                final.append(seg)

    return final if final else [text.strip()]


# ── LLM 调用 ─────────────────────────────────────────────────────────────────

_LLM_PROMPT_TEMPLATE = """你是 Token 效率分析专家。分析下面的用户输入，判断每个片段对完成任务的重要性。

用户输入（已分片）：
{segments_json}

规则：
- high（绿色）: 这个片段是任务的核心信息，删掉会导致任务失败或结果完全不同
- low（灰色）: 这个片段可以删掉，不影响任务结果
- neutral（白色）: 不确定

注意：时间戳、路径、UUID 等如果是用户主动传入的，可能是 high；如果是格式噪音，是 low。

输出JSON数组（必须是有效JSON，不要输出任何其他内容）:
[{{"segment": "原始片段文本", "score": "high/low/neutral", "reason": "一句话中文"}}]"""


def _call_llm_score_segments(segments: List[str]) -> Optional[List[Dict]]:
    """
    调用已配置的 LLM，对片段列表批量打分。

    返回 list of {"segment": str, "score": "high"|"low"|"neutral", "reason": str}
    失败时返回 None（触发 fallback）。
    """
    if not segments:
        return None

    try:
        from .stoi_config import load_config, get_api_key, PROVIDER_MODELS
    except ImportError:
        try:
            from stoi_config import load_config, get_api_key, PROVIDER_MODELS
        except ImportError:
            return None

    try:
        cfg      = load_config()
        llm_cfg  = cfg.get("llm", {})
        provider = llm_cfg.get("provider", "")
        api_key  = llm_cfg.get("api_key", "") or get_api_key(provider)
        model    = llm_cfg.get("model", "")
        base_url = llm_cfg.get("base_url", "")

        if not api_key or not provider:
            return None

        segments_json = json.dumps(
            [{"index": i, "segment": s} for i, s in enumerate(segments)],
            ensure_ascii=False, indent=2
        )
        prompt = _LLM_PROMPT_TEMPLATE.format(segments_json=segments_json)

        raw_text = ""

        if provider == "anthropic":
            import urllib.request as _ur
            if not base_url:
                base_url = "https://api.anthropic.com"
            if not model:
                model = "claude-haiku-3-5"
            body = json.dumps({
                "model": model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            }).encode()
            req = _ur.Request(
                f"{base_url.rstrip('/')}/v1/messages",
                data=body, method="POST"
            )
            req.add_header("Content-Type", "application/json")
            req.add_header("x-api-key", api_key)
            req.add_header("anthropic-version", "2023-06-01")
            with _ur.urlopen(req, timeout=20) as resp:
                result = json.loads(resp.read())
            raw_text = result["content"][0]["text"]

        else:
            # OpenAI-compatible (openai / qwen / deepseek / custom)
            import urllib.request as _ur
            pinfo = PROVIDER_MODELS.get(provider, {})
            if not base_url:
                base_url = pinfo.get("base_url", "https://api.openai.com/v1")
            if not model:
                model = pinfo.get("default", "gpt-4o-mini")
            body = json.dumps({
                "model": model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            }).encode()
            req = _ur.Request(
                f"{base_url.rstrip('/')}/chat/completions",
                data=body, method="POST"
            )
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", f"Bearer {api_key}")
            with _ur.urlopen(req, timeout=20) as resp:
                result = json.loads(resp.read())
            raw_text = result["choices"][0]["message"]["content"]

        # 解析 JSON 数组
        json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            parsed = json.loads(raw_text.strip())

        if not isinstance(parsed, list):
            return None

        # 标准化 score 字段
        out = []
        for item in parsed:
            score = str(item.get("score", "neutral")).lower().strip()
            if score not in ("high", "low", "neutral"):
                score = "neutral"
            out.append({
                "segment": str(item.get("segment", "")),
                "score":   score,
                "reason":  str(item.get("reason", "")),
            })
        return out if out else None

    except Exception:
        return None


# ── 片段分数 → tiktoken token 粒度映射 ────────────────────────────────────

def _map_segments_to_tokens(
    text: str,
    segment_scores: List[Dict],
) -> List[Dict]:
    """
    将片段级的 LLM 分数转换为显示单位。

    策略：直接以原始片段作为显示单位，不经过 tiktoken 重新分词。
    原因：tiktoken 对中文做 byte-level 分词会产生乱码，直接用语义片段更准确且显示正确。
    token_ids 用估算的 token 数量填充（用于统计）。
    """
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        def count_tokens(t):
            try:
                return len(enc.encode(t))
            except Exception:
                return max(1, len(t) // 4)
    except Exception:
        def count_tokens(t):
            return max(1, len(t) // 4)

    score_map = {"high": 1.0, "low": 0.3, "neutral": 0.6, "waste": 0.0}
    result = []
    for item in segment_scores:
        seg_text = item.get("segment", "").strip()
        if not seg_text:
            continue
        cat = item.get("score", "neutral")
        n_tokens = count_tokens(seg_text)
        result.append({
            "text":      seg_text + " ",  # 加空格作为视觉分隔
            "token_ids": list(range(n_tokens)),  # 虚拟 ID，只用于计数
            "score":     score_map.get(cat, 0.6),
            "category":  cat,
        })

    return result if result else _segments_to_word_tokens(text, segment_scores)

    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
    except Exception:
        return _segments_to_word_tokens(text, segment_scores)

    # 建立片段 → (start_char, end_char, score) 映射
    seg_ranges = []  # list of (start, end, score, reason)
    search_start = 0
    for item in segment_scores:
        seg_text = item.get("segment", "")
        if not seg_text:
            continue
        idx = text.find(seg_text, search_start)
        if idx == -1:
            # 尝试忽略首尾空白后再找
            stripped = seg_text.strip()
            idx = text.find(stripped, search_start)
            if idx == -1:
                continue
            seg_text = stripped
        seg_ranges.append((idx, idx + len(seg_text), item["score"], item.get("reason", "")))
        search_start = idx  # 允许重叠搜索

    def _score_at(char_pos: int) -> str:
        for start, end, score, _ in seg_ranges:
            if start <= char_pos < end:
                return score
        return "neutral"

    # tiktoken encode with offsets
    token_ids = enc.encode(text)
    score_map = {"high": 1.0, "low": 0.3, "neutral": 0.6}

    # tiktoken 不直接暴露字符偏移，用 decode 累积来估算
    result = []
    char_cursor = 0
    for tid in token_ids:
        try:
            token_bytes = enc.decode_single_token_bytes(tid)
            token_text  = token_bytes.decode("utf-8", errors="replace")
        except Exception:
            token_text = ""

        # 在原文中找 token 对应的字符位置
        tok_pos = text.find(token_text, char_cursor)
        if tok_pos == -1:
            tok_pos = char_cursor  # fallback：用当前光标

        cat = _score_at(tok_pos)
        result.append({
            "text":      token_text,
            "token_ids": [tid],
            "score":     score_map.get(cat, 0.6),
            "category":  cat,
        })
        if token_text:
            char_cursor = tok_pos + len(token_text)

    return _merge_whitespace_tokens(result)


def _segments_to_word_tokens(text: str, segment_scores: List[Dict]) -> List[Dict]:
    """tiktoken 不可用时的降级版本：按空白分词粒度映射"""
    seg_ranges = []
    search_start = 0
    for item in segment_scores:
        seg_text = item.get("segment", "").strip()
        if not seg_text:
            continue
        idx = text.find(seg_text, search_start)
        if idx == -1:
            continue
        seg_ranges.append((idx, idx + len(seg_text), item["score"]))
        search_start = idx

    def _score_at(pos: int) -> str:
        for start, end, score in seg_ranges:
            if start <= pos < end:
                return score
        return "neutral"

    score_map = {"high": 1.0, "low": 0.3, "neutral": 0.6}
    result = []
    for m in re.finditer(r'\S+|\s+', text):
        cat = _score_at(m.start())
        result.append({
            "text":      m.group(),
            "token_ids": [m.start()],
            "score":     score_map.get(cat, 0.6),
            "category":  cat,
        })
    return result


# ── Fallback：仅检测 Markdown 装饰符 ────────────────────────────────────────

def _fallback_score_token(token_text: str) -> str:
    """
    无 LLM 时的降级打分。

    只标记 Markdown 格式装饰符为 "waste"——这类符号无语义价值，
    任何上下文下都是格式噪音。

    时间戳、路径、UUID 一律不标记：它们可能是用户主动传入的必要信息。
    """
    if not token_text.strip():
        return "neutral"
    if _MARKDOWN_WASTE_RE.search(token_text):
        return "waste"
    return "neutral"


def _analyze_fallback(text: str) -> List[Dict]:
    """LLM 不可用时的完整降级实现"""
    score_map = {"high": 1.0, "waste": 0.0, "low": 0.3, "neutral": 0.6}

    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        token_ids = enc.encode(text)
        result = []
        for tid in token_ids:
            try:
                token_bytes = enc.decode_single_token_bytes(tid)
                token_text  = token_bytes.decode("utf-8", errors="replace")
            except Exception:
                token_text = ""
            cat = _fallback_score_token(token_text)
            result.append({
                "text":      token_text,
                "token_ids": [tid],
                "score":     score_map.get(cat, 0.6),
                "category":  cat,
            })
        return _merge_whitespace_tokens(result)
    except Exception:
        # tiktoken 也不可用，按空白分词
        result = []
        idx = 0
        for m in re.finditer(r'\S+|\s+', text):
            cat = _fallback_score_token(m.group())
            result.append({
                "text":      m.group(),
                "token_ids": [idx],
                "score":     score_map.get(cat, 0.6),
                "category":  cat,
            })
            idx += 1
        return result


# ── 公共工具 ─────────────────────────────────────────────────────────────────

def _merge_whitespace_tokens(tokens: List[Dict]) -> List[Dict]:
    """将纯空白 token 附加到前一个 token，减少 HTML 噪音"""
    if not tokens:
        return tokens
    merged = []
    for tok in tokens:
        if tok["text"].strip() == "" and merged:
            merged[-1]["text"]      += tok["text"]
            merged[-1]["token_ids"] += tok["token_ids"]
        else:
            merged.append(dict(tok))
    return merged


# ── 主公共接口 ────────────────────────────────────────────────────────────────

def analyze_token_importance(text: str) -> List[Dict]:
    """
    分析文本中每个 token 的重要性。

    主路径（LLM 可用时）：
      基于 Integrated Gradients 离散近似（Sundararajan et al. ICML 2017）：
        1. 将 text 分割为语义片段（句子/子句，约 10 词每段）
        2. 单次 LLM 调用批量打分所有片段
        3. 将片段级分数映射回 tiktoken token 粒度
      分数含义：
        high    → 删除此片段会导致任务失败或结果完全不同
        low     → 删除此片段不影响任务结果
        neutral → 不确定

    降级路径（LLM 不可用时）：
      仅标记 Markdown 装饰符为 "waste"，其余均为 "neutral"
      不对时间戳、路径、UUID 做任何假设

    返回 list of dict:
      {
        "text":      str,        # token 原始文本（可能包含尾随空白）
        "token_ids": list[int],  # tiktoken token ID 列表
        "score":     float,      # high=1.0, neutral=0.6, low=0.3, waste=0.0
        "category":  str         # "high" | "low" | "neutral" | "waste"
      }
    """
    if not text or not text.strip():
        return []

    # 1. 分片
    segments = _split_into_segments(text)

    # 2. LLM 批量打分
    llm_scores = _call_llm_score_segments(segments)

    # 3a. LLM 成功 → 映射回 token 粒度
    if llm_scores:
        return _map_segments_to_tokens(text, llm_scores)

    # 3b. LLM 失败 → 降级
    return _analyze_fallback(text)


def analyze_token_importance_llm(text: str) -> List[Dict]:
    """
    analyze_token_importance 的显式 LLM 路径别名。
    调用方可用此名强调"需要 LLM"，行为与 analyze_token_importance 完全一致。
    """
    return analyze_token_importance(text)


# ── HTML 渲染 ─────────────────────────────────────────────────────────────────

def render_token_html(tokens: List[Dict]) -> str:
    """
    将 token 列表渲染为 HTML，带颜色标注。

    配色方案：
      high    (green): background-color: #bbf7d0; color: #166534
      waste   (red):   background-color: #fecaca; color: #991b1b; text-decoration: line-through
      low     (gray):  color: #9ca3af
      neutral:         无样式

    末尾附加统计行：
      X tokens 总计 | Y 高贡献 (绿) | Z 冗余 (红) | 潜在节省: Z/X*100%
    """
    import html as _html

    if not tokens:
        return "<span style='color:#9ca3af'>(空文本)</span>"

    STYLES = {
        "high":    "background-color:#bbf7d0;color:#166534;border-radius:3px;padding:1px 3px;",
        "waste":   "background-color:#fecaca;color:#991b1b;border-radius:3px;padding:1px 3px;text-decoration:line-through;",
        "low":     "color:#9ca3af;",
        "neutral": "",
    }

    parts = []
    for tok in tokens:
        text_escaped = _html.escape(tok["text"])
        cat   = tok.get("category", "neutral")
        style = STYLES.get(cat, "")
        if style:
            parts.append(f'<span style="{style}">{text_escaped}</span>')
        else:
            parts.append(text_escaped)

    total       = len(tokens)
    high_count  = sum(1 for t in tokens if t["category"] == "high")
    waste_count = sum(1 for t in tokens if t["category"] == "waste")
    low_count   = sum(1 for t in tokens if t["category"] == "low")
    waste_pct   = f"{waste_count / total * 100:.1f}" if total > 0 else "0.0"

    html_tokens = "".join(parts)
    stats_line = (
        f'<div style="margin-top:8px;font-size:11px;color:#6b7280;font-family:monospace;">'
        f'{total} tokens 总计 &nbsp;|&nbsp; '
        f'<span style="color:#166534;font-weight:600;">{high_count} 高贡献</span> (绿) &nbsp;|&nbsp; '
        f'<span style="color:#991b1b;font-weight:600;">{waste_count} 冗余</span> (红) &nbsp;|&nbsp; '
        f'潜在节省: <span style="color:#991b1b;font-weight:600;">{waste_pct}%</span>'
        f'</div>'
    )

    return (
        f'<div style="font-family:\'SF Mono\',Consolas,monospace;font-size:13px;'
        f'line-height:1.8;word-break:break-word;">'
        f'{html_tokens}'
        f'</div>'
        f'{stats_line}'
    )


# ── Stats helper ─────────────────────────────────────────────────────────────

def get_token_stats(tokens: List[Dict]) -> Dict:
    """
    从 analyze_token_importance 的输出中提取统计数字。

    返回:
      {
        "total":         int,
        "high_count":    int,
        "waste_count":   int,
        "low_count":     int,
        "neutral_count": int,
        "waste_pct":     float,
        "high_pct":      float,
      }
    """
    total   = len(tokens)
    high    = sum(1 for t in tokens if t["category"] == "high")
    waste   = sum(1 for t in tokens if t["category"] == "waste")
    low     = sum(1 for t in tokens if t["category"] == "low")
    neutral = sum(1 for t in tokens if t["category"] == "neutral")
    return {
        "total":         total,
        "high_count":    high,
        "waste_count":   waste,
        "low_count":     low,
        "neutral_count": neutral,
        "waste_pct":     round(waste / total * 100, 1) if total > 0 else 0.0,
        "high_pct":      round(high / total * 100, 1) if total > 0 else 0.0,
    }
