#!/usr/bin/env python3
"""
Claude Code 历史反馈 token 有效性分析

基于本地 ~/.claude/history.jsonl 和 ~/.claude/usage-data/session-meta
估算每条 prompt 的 input/output token，并根据下一条用户消息是否为负面反馈
判断该 prompt 消耗的 token 是否有效。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

try:
    import tiktoken
except ImportError:  # pragma: no cover - optional dependency
    tiktoken = None


TOKEN_CALC_VERSION = "v7_refined_invalidation"
NEGATIVE_PREFIXES = [
    "没看到",
    "不对",
    "还是不行",
    "没有这个",
    "没改",
    "没有生成",
    "没有输出",
    "不符合",
    "理解错了",
    "为什么没有",
    "怎么没",
    "跑不起来",
    "没生效",
    "找不到",
    "没找到",
    "在命令行找不到",
]
WEAK_NEGATIVE_PREFIXES = [
    "报错了",
    "失败了",
    "有问题",
]
NEGATIVE_REGEXES = [
    re.compile(r"^(还是|又|一直).*(报错|失败|不行)$"),
    re.compile(r"^(运行|启动|执行|部署).*(报错|失败)$"),
]
POSITIVE_PREFIXES = [
    "好了",
    "可以",
    "可以了",
    "对了",
    "没问题",
    "好的",
    "收到",
    "谢谢",
    "谢了",
    "继续",
    "继续吧",
    "很好",
    "ok",
]
WEAK_CONTINUE_PREFIXES = [
    "继续",
    "下一步",
    "继续吧",
]
WEAK_FIXUP_PREFIXES = [
    "重新",
    "重做",
    "重来",
    "改一下",
    "修改一下",
    "请修改",
    "帮我修改",
    "补上",
    "补一下",
    "补充",
    "补齐",
    "补全",
    "修复",
    "修一下",
    "优化",
    "更新",
    "请更新",
    "帮我更新",
    "改成",
    "改为",
    "调整",
    "调整一下",
    "完善",
    "请把",
    "把",
    "请根据",
    "根据",
    "下次",
    "不要",
    "别",
    "去掉",
]
COMMAND_PREFIXES = [
    "/",
    "!",
    "source ",
    "export ",
    "curl ",
    "git ",
    "gh ",
    "python ",
    "python3 ",
    "pip ",
    "pip3 ",
    "npm ",
    "pnpm ",
    "bash ",
    "sh ",
]
LOW_SIGNAL_PROMPTS = {
    "hi",
    "hello",
    "你好",
    "您好",
    "test",
    "测试",
    "好的",
    "ok",
}


@dataclass
class PromptMessage:
    session_id: str
    prompt_index: int
    timestamp_ms: int
    project_path: str
    prompt_text: str
    full_prompt_text: str
    prompt_hash: str


@dataclass
class PromptTokenUsage:
    session_id: str
    prompt_index: int
    input_tokens: int
    output_tokens: int
    token_source: str
    calc_version: str = TOKEN_CALC_VERSION


@dataclass
class PromptFeedbackLabel:
    session_id: str
    prompt_index: int
    feedback_prompt_index: Optional[int]
    feedback_text: str
    feedback_label: str
    token_effectiveness: str
    rule_hits: List[str]
    calc_version: str = TOKEN_CALC_VERSION


class TokenCounter:
    """优先使用 tiktoken，否则回退到启发式估算。"""

    def __init__(self):
        self.encoder = None
        if tiktoken is not None:
            try:
                self.encoder = tiktoken.get_encoding("cl100k_base")
            except Exception:
                self.encoder = None

    def count(self, text: str) -> int:
        if not text:
            return 0
        if self.encoder is not None:
            return len(self.encoder.encode(text))
        return self._heuristic_count(text)

    def _heuristic_count(self, text: str) -> int:
        # CJK 字符大致按 1 token 估算；其余按每 4 字符约 1 token 估算。
        cjk_chars = re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text)
        cjk_count = len(cjk_chars)
        ascii_like = re.sub(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", " ", text)

        ascii_tokens = 0
        for chunk in re.findall(r"\S+", ascii_like):
            ascii_tokens += max(1, math.ceil(len(chunk) / 4))
        return cjk_count + ascii_tokens


def _flatten_prompt(entry: Dict) -> str:
    parts: List[str] = []
    display = (entry.get("display") or "").strip()
    if display:
        parts.append(display)

    pasted = entry.get("pastedContents") or {}
    if isinstance(pasted, dict):
        def sort_key(item: str) -> tuple[int, str]:
            return (0, str(int(item))) if str(item).isdigit() else (1, str(item))

        for key in sorted(pasted.keys(), key=sort_key):
            item = pasted.get(key) or {}
            content = (item.get("content") or "").strip()
            if content:
                parts.append(content)

    return "\n".join(parts).strip()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _allocate_proportionally(total: int, weights: Sequence[int]) -> List[int]:
    if total <= 0 or not weights:
        return [0] * len(weights)

    weight_sum = sum(max(0, int(w)) for w in weights)
    if weight_sum <= 0:
        base = total // len(weights)
        remainder = total % len(weights)
        result = [base] * len(weights)
        for i in range(remainder):
            result[i] += 1
        return result

    raw = [(max(0, int(weight)) / weight_sum) * total for weight in weights]
    floored = [int(value) for value in raw]
    remainder = total - sum(floored)
    ranked = sorted(
        enumerate(raw),
        key=lambda item: (item[1] - math.floor(item[1]), -item[0]),
        reverse=True,
    )
    for idx, _ in ranked[:remainder]:
        floored[idx] += 1
    return floored


def _is_command_like(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    lowered = stripped.casefold()
    return any(lowered.startswith(prefix.casefold()) for prefix in COMMAND_PREFIXES)


def _is_low_signal_prompt(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    lowered = stripped.casefold()
    if lowered in LOW_SIGNAL_PROMPTS:
        return True
    if len(stripped) <= 2 and re.fullmatch(r"[a-zA-Z]+", stripped):
        return True
    return False


def classify_feedback(text: str) -> tuple[str, List[str]]:
    stripped = (text or "").strip()
    if not stripped:
        return "neutral", ["empty_feedback_defaults_to_neutral"]
    if stripped.startswith("/"):
        return "neutral", ["slash_command_defaults_to_neutral"]

    lowered = stripped.casefold()
    hits: List[str] = []
    for pattern in NEGATIVE_PREFIXES:
        if lowered.startswith(pattern.casefold()):
            hits.append(pattern)
    for regex in NEGATIVE_REGEXES:
        if regex.search(stripped):
            hits.append(regex.pattern)
    if len(stripped) <= 12:
        for pattern in WEAK_NEGATIVE_PREFIXES:
            if lowered.startswith(pattern.casefold()):
                hits.append(pattern)

    unique_hits = list(dict.fromkeys(hits))
    if unique_hits:
        return "negative", unique_hits

    positive_hits: List[str] = []
    for pattern in POSITIVE_PREFIXES:
        if lowered.startswith(pattern.casefold()):
            positive_hits.append(pattern)
    if positive_hits:
        return "positive", positive_hits

    weak_invalid_hits: List[str] = []
    for pattern in WEAK_FIXUP_PREFIXES:
        if lowered.startswith(pattern.casefold()):
            weak_invalid_hits.append(pattern)
    if weak_invalid_hits:
        return "negative", weak_invalid_hits

    weak_valid_hits: List[str] = []
    for pattern in WEAK_CONTINUE_PREFIXES:
        if lowered.startswith(pattern.casefold()):
            weak_valid_hits.append(pattern)
    if weak_valid_hits:
        return "positive", weak_valid_hits

    # 中性追问、换话题、补充说明仍保留 unknown。
    return "neutral", ["non_explicit_feedback_defaults_to_neutral"]


class ClaudeFeedbackTokenValidityStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS claude_prompt_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    prompt_index INTEGER NOT NULL,
                    timestamp_ms INTEGER,
                    project_path TEXT,
                    prompt_text TEXT NOT NULL,
                    full_prompt_text TEXT,
                    prompt_hash TEXT,
                    UNIQUE(session_id, prompt_index)
                );

                CREATE TABLE IF NOT EXISTS claude_prompt_token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    prompt_index INTEGER NOT NULL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    token_source TEXT NOT NULL,
                    calc_version TEXT NOT NULL,
                    UNIQUE(session_id, prompt_index, calc_version)
                );

                CREATE TABLE IF NOT EXISTS claude_prompt_feedback_labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    prompt_index INTEGER NOT NULL,
                    feedback_prompt_index INTEGER,
                    feedback_text TEXT,
                    feedback_label TEXT NOT NULL,
                    token_effectiveness TEXT NOT NULL,
                    rule_hits TEXT,
                    calc_version TEXT NOT NULL,
                    UNIQUE(session_id, prompt_index, calc_version)
                );
                """
            )

    def upsert_prompt_messages(self, messages: Iterable[PromptMessage]):
        rows = [
            (
                msg.session_id,
                msg.prompt_index,
                msg.timestamp_ms,
                msg.project_path,
                msg.prompt_text,
                msg.full_prompt_text,
                msg.prompt_hash,
            )
            for msg in messages
        ]
        if not rows:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT INTO claude_prompt_messages (
                    session_id, prompt_index, timestamp_ms, project_path,
                    prompt_text, full_prompt_text, prompt_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, prompt_index) DO UPDATE SET
                    timestamp_ms=excluded.timestamp_ms,
                    project_path=excluded.project_path,
                    prompt_text=excluded.prompt_text,
                    full_prompt_text=excluded.full_prompt_text,
                    prompt_hash=excluded.prompt_hash
                """,
                rows,
            )

    def upsert_prompt_token_usage(self, usages: Iterable[PromptTokenUsage]):
        rows = [
            (
                usage.session_id,
                usage.prompt_index,
                usage.input_tokens,
                usage.output_tokens,
                usage.token_source,
                usage.calc_version,
            )
            for usage in usages
        ]
        if not rows:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT INTO claude_prompt_token_usage (
                    session_id, prompt_index, input_tokens, output_tokens,
                    token_source, calc_version
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, prompt_index, calc_version) DO UPDATE SET
                    input_tokens=excluded.input_tokens,
                    output_tokens=excluded.output_tokens,
                    token_source=excluded.token_source
                """,
                rows,
            )

    def upsert_feedback_labels(self, labels: Iterable[PromptFeedbackLabel]):
        rows = [
            (
                label.session_id,
                label.prompt_index,
                label.feedback_prompt_index,
                label.feedback_text,
                label.feedback_label,
                label.token_effectiveness,
                json.dumps(label.rule_hits, ensure_ascii=False),
                label.calc_version,
            )
            for label in labels
        ]
        if not rows:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT INTO claude_prompt_feedback_labels (
                    session_id, prompt_index, feedback_prompt_index, feedback_text,
                    feedback_label, token_effectiveness, rule_hits, calc_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, prompt_index, calc_version) DO UPDATE SET
                    feedback_prompt_index=excluded.feedback_prompt_index,
                    feedback_text=excluded.feedback_text,
                    feedback_label=excluded.feedback_label,
                    token_effectiveness=excluded.token_effectiveness,
                    rule_hits=excluded.rule_hits
                """,
                rows,
            )

    def get_prompt_rows(
        self,
        session_id: Optional[str] = None,
        project_path: Optional[str] = None,
        limit: Optional[int] = None,
        only: str = "all",
        calc_version: str = TOKEN_CALC_VERSION,
    ) -> List[Dict]:
        query = """
            SELECT
                m.session_id,
                m.prompt_index,
                m.timestamp_ms,
                m.project_path,
                m.prompt_text,
                m.full_prompt_text,
                u.input_tokens,
                u.output_tokens,
                u.token_source,
                f.feedback_prompt_index,
                f.feedback_text,
                f.feedback_label,
                f.token_effectiveness,
                f.rule_hits
            FROM claude_prompt_messages m
            JOIN claude_prompt_token_usage u
                ON m.session_id = u.session_id
               AND m.prompt_index = u.prompt_index
               AND u.calc_version = ?
            JOIN claude_prompt_feedback_labels f
                ON m.session_id = f.session_id
               AND m.prompt_index = f.prompt_index
               AND f.calc_version = ?
            WHERE 1 = 1
        """
        params: List[object] = [calc_version, calc_version]
        if session_id:
            query += " AND m.session_id = ?"
            params.append(session_id)
        if project_path:
            query += " AND m.project_path = ?"
            params.append(project_path)
        if only == "valid":
            query += " AND f.token_effectiveness = 'valid'"
        elif only == "invalid":
            query += " AND f.token_effectiveness = 'invalid'"
        if session_id:
            query += " ORDER BY m.prompt_index ASC"
        else:
            query += " ORDER BY m.timestamp_ms DESC"

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            data = dict(row)
            try:
                data["rule_hits"] = json.loads(data["rule_hits"] or "[]")
            except json.JSONDecodeError:
                data["rule_hits"] = []
            result.append(data)
        return result


class ClaudeFeedbackTokenValidityService:
    def __init__(
        self,
        db_path: str = "~/.stoi/stoi.db",
        claude_dir: Optional[Path] = None,
    ):
        self.db_path = Path(db_path).expanduser()
        self.claude_dir = claude_dir or (Path.home() / ".claude")
        self.history_file = self.claude_dir / "history.jsonl"
        self.session_meta_dir = self.claude_dir / "usage-data" / "session-meta"
        self.store = ClaudeFeedbackTokenValidityStore(self.db_path)
        self.token_counter = TokenCounter()

    def backfill(self, session_id: Optional[str] = None) -> Dict[str, int]:
        sessions = self._load_prompt_sessions(session_id=session_id)
        message_count = 0
        session_count = 0

        for sid, messages in sessions.items():
            usages = self._estimate_session_token_usage(sid, messages)
            labels = self._label_session_feedback(messages)
            self.store.upsert_prompt_messages(messages)
            self.store.upsert_prompt_token_usage(usages)
            self.store.upsert_feedback_labels(labels)
            message_count += len(messages)
            session_count += 1

        return {
            "session_count": session_count,
            "prompt_count": message_count,
        }

    def get_rows(
        self,
        session_id: Optional[str] = None,
        project_path: Optional[str] = None,
        limit: Optional[int] = None,
        only: str = "all",
    ) -> List[Dict]:
        rows = self.store.get_prompt_rows(
            session_id=session_id,
            project_path=project_path,
            limit=limit,
            only=only,
        )
        if rows:
            return rows
        if session_id:
            self.backfill(session_id=session_id)
        else:
            self.backfill()
        return self.store.get_prompt_rows(
            session_id=session_id,
            project_path=project_path,
            limit=limit,
            only=only,
        )

    def summarize_rows(self, rows: Sequence[Dict]) -> Dict:
        total_input = sum(int(row["input_tokens"] or 0) for row in rows)
        total_output = sum(int(row["output_tokens"] or 0) for row in rows)
        valid_rows = [row for row in rows if row["token_effectiveness"] == "valid"]
        invalid_rows = [row for row in rows if row["token_effectiveness"] == "invalid"]

        valid_input = sum(int(row["input_tokens"] or 0) for row in valid_rows)
        valid_output = sum(int(row["output_tokens"] or 0) for row in valid_rows)
        invalid_input = sum(int(row["input_tokens"] or 0) for row in invalid_rows)
        invalid_output = sum(int(row["output_tokens"] or 0) for row in invalid_rows)
        total_tokens = total_input + total_output
        valid_tokens = valid_input + valid_output
        invalid_tokens = invalid_input + invalid_output

        return {
            "total_prompt_count": len(rows),
            "valid_prompt_count": len(valid_rows),
            "invalid_prompt_count": len(invalid_rows),
            "total_input_tokens": total_input,
            "valid_input_tokens": valid_input,
            "invalid_input_tokens": invalid_input,
            "total_output_tokens": total_output,
            "valid_output_tokens": valid_output,
            "invalid_output_tokens": invalid_output,
            "total_tokens": total_tokens,
            "valid_tokens": valid_tokens,
            "invalid_tokens": invalid_tokens,
            "valid_token_ratio": round(valid_tokens / total_tokens, 4) if total_tokens else 0.0,
            "invalid_token_ratio": round(invalid_tokens / total_tokens, 4) if total_tokens else 0.0,
        }

    def summarize_by_session(self, rows: Sequence[Dict]) -> List[Dict]:
        grouped: Dict[str, List[Dict]] = defaultdict(list)
        for row in rows:
            grouped[row["session_id"]].append(row)

        summaries = []
        for session_id, session_rows in grouped.items():
            summary = self.summarize_rows(session_rows)
            summary.update(
                {
                    "session_id": session_id,
                    "project_path": session_rows[0]["project_path"],
                }
            )
            summaries.append(summary)

        summaries.sort(
            key=lambda item: (item["invalid_tokens"], item["total_tokens"]),
            reverse=True,
        )
        return summaries

    def _load_prompt_sessions(self, session_id: Optional[str] = None) -> Dict[str, List[PromptMessage]]:
        if not self.history_file.exists():
            return {}

        sessions: Dict[str, List[Dict]] = defaultdict(list)
        with open(self.history_file, "r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                sid = entry.get("sessionId")
                if not sid or (session_id and sid != session_id):
                    continue

                full_prompt_text = _flatten_prompt(entry)
                prompt_text = (entry.get("display") or "").strip()
                if not full_prompt_text:
                    continue

                sessions[sid].append(
                    {
                        "timestamp_ms": int(entry.get("timestamp") or 0),
                        "project_path": entry.get("project") or "",
                        "prompt_text": prompt_text or full_prompt_text,
                        "full_prompt_text": full_prompt_text,
                        "line_no": line_no,
                    }
                )

        result: Dict[str, List[PromptMessage]] = {}
        for sid, items in sessions.items():
            items.sort(key=lambda item: (item["timestamp_ms"], item["line_no"]))
            result[sid] = [
                PromptMessage(
                    session_id=sid,
                    prompt_index=index,
                    timestamp_ms=item["timestamp_ms"],
                    project_path=item["project_path"],
                    prompt_text=item["prompt_text"],
                    full_prompt_text=item["full_prompt_text"],
                    prompt_hash=_hash_text(item["full_prompt_text"]),
                )
                for index, item in enumerate(items, start=1)
            ]
        return result

    def _read_session_meta(self, session_id: str) -> Dict[str, int]:
        meta_file = self.session_meta_dir / f"{session_id}.json"
        if not meta_file.exists():
            return {"input_tokens": 0, "output_tokens": 0}
        try:
            with open(meta_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return {"input_tokens": 0, "output_tokens": 0}
        return {
            "input_tokens": int(data.get("input_tokens") or 0),
            "output_tokens": int(data.get("output_tokens") or 0),
        }

    def _estimate_session_token_usage(
        self,
        session_id: str,
        messages: Sequence[PromptMessage],
    ) -> List[PromptTokenUsage]:
        meta = self._read_session_meta(session_id)
        raw_tokens = [self.token_counter.count(msg.full_prompt_text) for msg in messages]
        session_input_tokens = meta["input_tokens"]
        session_output_tokens = meta["output_tokens"]

        if session_input_tokens > 0 and sum(raw_tokens) > 0:
            input_tokens = _allocate_proportionally(session_input_tokens, raw_tokens)
            token_source = "estimated_session_scaled"
        else:
            input_tokens = raw_tokens
            token_source = "estimated_text_only"

        if session_output_tokens > 0 and sum(input_tokens) > 0:
            output_tokens = _allocate_proportionally(session_output_tokens, input_tokens)
        else:
            output_tokens = [0] * len(messages)

        usages = []
        for msg, est_input, est_output in zip(messages, input_tokens, output_tokens):
            usages.append(
                PromptTokenUsage(
                    session_id=msg.session_id,
                    prompt_index=msg.prompt_index,
                    input_tokens=int(est_input),
                    output_tokens=int(est_output),
                    token_source=token_source,
                )
            )
        return usages

    def _label_session_feedback(self, messages: Sequence[PromptMessage]) -> List[PromptFeedbackLabel]:
        labels = []
        for index, message in enumerate(messages):
            next_message = messages[index + 1] if index + 1 < len(messages) else None
            feedback_text = next_message.prompt_text if next_message else ""
            feedback_label, base_rule_hits = classify_feedback(feedback_text)
            rule_hits = list(base_rule_hits)

            if next_message is None:
                feedback_label = "negative"
                token_effectiveness = "invalid"
                rule_hits.append("no_followup_defaults_to_invalid")
            elif feedback_label == "positive":
                token_effectiveness = "valid"
            elif feedback_label == "negative":
                token_effectiveness = "invalid"
            else:
                if _is_command_like(message.prompt_text):
                    feedback_label = "negative"
                    token_effectiveness = "invalid"
                    rule_hits.append("command_like_prompt_defaults_to_invalid")
                elif _is_low_signal_prompt(message.prompt_text):
                    feedback_label = "negative"
                    token_effectiveness = "invalid"
                    rule_hits.append("low_signal_prompt_defaults_to_invalid")
                elif _is_command_like(feedback_text):
                    feedback_label = "negative"
                    token_effectiveness = "invalid"
                    rule_hits.append("command_like_followup_is_not_validation")
                else:
                    token_effectiveness = "valid"
            labels.append(
                PromptFeedbackLabel(
                    session_id=message.session_id,
                    prompt_index=message.prompt_index,
                    feedback_prompt_index=next_message.prompt_index if next_message else None,
                    feedback_text=feedback_text,
                    feedback_label=feedback_label,
                    token_effectiveness=token_effectiveness,
                    rule_hits=list(dict.fromkeys(rule_hits)),
                )
            )
        return labels


def rows_to_jsonable(rows: Sequence[Dict]) -> List[Dict]:
    return [dict(row) for row in rows]


def summary_to_jsonable(summary: Dict) -> Dict:
    return dict(summary)
