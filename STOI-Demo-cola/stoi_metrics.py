#!/usr/bin/env python3
"""
stoi_metrics.py — Step-Level Token Attribution & Quality Metrics

Based on the Deep Research Report framework:
- Step-level parsing (structured <trace>/<answer> + fallback)
- Token-to-step attribution (tiktoken + heuristic fallback)
- Four-dimensional quality scoring: F(factuality), V(validity), C(coherence), U(utility)
- Five core metrics: TE, SUS, FR, MG, RR

References:
  - Wei et al. (2022): Chain-of-Thought Prompting Elicits Reasoning
  - 2025 Survey: Four-dimensional trace evaluation (F/V/C/U)
  - OpenAI CoT Monitorability Framework
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

try:
    import tiktoken
except ImportError:
    tiktoken = None


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class Step:
    """A single reasoning step parsed from model output."""
    index: int
    text: str
    start_char: int
    end_char: int
    token_count: int = 0
    token_indices: List[int] = field(default_factory=list)


@dataclass
class StepQuality:
    """Four-dimensional quality scores for a step, each in [0, 1]."""
    factuality: float  # F: groundedness / evidence alignment
    validity: float    # V: logical / arithmetic correctness
    coherence: float   # C: pragmatic coherence and informativeness
    utility: float     # U: contribution to correct answer


@dataclass
class MetricsResult:
    """Complete metrics calculation result."""
    token_efficiency: float      # TE: quality per reasoning token
    step_utility_score: float    # SUS: token-weighted utility
    faithfulness_risk: float     # FR: shortcut reasoning risk
    monitorability_gain: float   # MG: CoT monitoring value
    redundancy_ratio: float      # RR: token-weighted redundancy fraction
    composite_quality: float     # Q: weighted F+V+C+U
    avg_factuality: float        # token-weighted average F
    avg_validity: float          # token-weighted average V
    avg_coherence: float         # token-weighted average C
    avg_utility: float           # token-weighted average U
    steps: List[Step] = field(default_factory=list)
    step_qualities: List[StepQuality] = field(default_factory=list)
    total_reasoning_tokens: int = 0
    total_answer_tokens: int = 0


# ── Step Parser ──────────────────────────────────────────────────────────────

class StepParser:
    """Parse model output text into reasoning steps."""

    TRACE_PATTERN = re.compile(r'<trace>(.*?)</trace>', re.DOTALL)
    ANSWER_PATTERN = re.compile(r'<answer>(.*?)</answer>', re.DOTALL)
    STEP_EXPLICIT = re.compile(
        r'Step\s+(\d+)\s*[:：]\s*(.*?)(?=Step\s+\d+\s*[:：]|$)', re.DOTALL
    )

    # Fallback split patterns, in priority order
    FALLBACK_SPLITTERS = [
        re.compile(r'\n(?=\d+\.\s)'),           # "1. ..."
        re.compile(r'\n(?=[-\*]\s)'),            # "- ..."
        re.compile(
            r'\n(?=(?:因此|所以|综上|总之|结论|result|thus|therefore|hence|conclusion))',
            re.IGNORECASE,
        ),
        re.compile(r'\n{2,}'),                    # double newline
    ]

    # Markers that signal the start of the answer section
    ANSWER_MARKERS = [
        re.compile(r'\n(?:答案|结论|结果|Answer|Conclusion|Result)\s*[:：]', re.IGNORECASE),
        re.compile(r'\n(?:因此|所以|综上|总之|Thus|Therefore|Hence)', re.IGNORECASE),
    ]

    @classmethod
    def parse(cls, output_text: str, min_step_tokens: int = 5) -> Tuple[List[Step], str]:
        """
        Parse *output_text* into (steps, answer_text).

        Tries structured ``<trace>/<answer>`` first, then falls back to
        heuristic splitting.
        """
        trace_text = ""
        answer_text = ""

        # --- structured format ---
        trace_match = cls.TRACE_PATTERN.search(output_text)
        if trace_match:
            trace_text = trace_match.group(1).strip()
            answer_match = cls.ANSWER_PATTERN.search(output_text)
            if answer_match:
                answer_text = answer_match.group(1).strip()
            else:
                answer_text = output_text[trace_match.end():].strip()
        else:
            trace_text, answer_text = cls._fallback_split(output_text)

        steps = cls._parse_steps(trace_text, output_text)

        if min_step_tokens > 0:
            steps = cls._merge_short_steps(steps, min_step_tokens)

        return steps, answer_text

    # ── internal helpers ──────────────────────────────────────────────────

    @classmethod
    def _parse_steps(cls, trace_text: str, original_text: str) -> List[Step]:
        steps: List[Step] = []

        # Try explicit "Step k:" markers
        for match in cls.STEP_EXPLICIT.finditer(trace_text):
            step_text = match.group(2).strip()
            if not step_text:
                continue
            start = original_text.find(step_text[:30])
            if start == -1:
                start = 0
            steps.append(Step(
                index=int(match.group(1)),
                text=step_text,
                start_char=start,
                end_char=start + len(step_text),
            ))

        if steps:
            return steps

        # Fallback splitters
        for splitter in cls.FALLBACK_SPLITTERS:
            parts = splitter.split(trace_text)
            if len(parts) >= 2:
                pos = 0
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    start = original_text.find(part[:30])
                    if start == -1:
                        start = pos
                    steps.append(Step(
                        index=len(steps),
                        text=part,
                        start_char=start,
                        end_char=start + len(part),
                    ))
                    pos = start + len(part)
                if steps:
                    return steps

        # Whole trace as single step
        if trace_text:
            start = original_text.find(trace_text[:30])
            if start == -1:
                start = 0
            steps.append(Step(
                index=0,
                text=trace_text,
                start_char=start,
                end_char=start + len(trace_text),
            ))
        return steps

    @classmethod
    def _merge_short_steps(cls, steps: List[Step], min_tokens: int) -> List[Step]:
        if not steps:
            return steps

        merged: List[Step] = []
        buf = steps[0]

        for step in steps[1:]:
            # ~4 chars per token heuristic
            if len(buf.text) // 4 < min_tokens:
                buf = Step(
                    index=buf.index,
                    text=buf.text + "\n" + step.text,
                    start_char=buf.start_char,
                    end_char=step.end_char,
                )
            else:
                merged.append(buf)
                buf = step
        merged.append(buf)

        for i, s in enumerate(merged):
            s.index = i
        return merged

    @classmethod
    def _fallback_split(cls, text: str) -> Tuple[str, str]:
        trace = text
        answer = ""
        for marker in cls.ANSWER_MARKERS:
            m = marker.search(text)
            if m:
                trace = text[:m.start()].strip()
                answer = text[m.start():].strip()
                break
        return trace, answer


# ── Token Attributor ─────────────────────────────────────────────────────────

class TokenAttributor:
    """Map tokens to steps via character offsets."""

    def __init__(self, encoding_name: str = "cl100k_base"):
        self.encoder = None
        if tiktoken is not None:
            try:
                self.encoder = tiktoken.get_encoding(encoding_name)
            except Exception:
                self.encoder = None

    def attribute(self, output_text: str, steps: List[Step]) -> List[Step]:
        if self.encoder is not None:
            return self._attribute_tiktoken(output_text, steps)
        return self._attribute_heuristic(output_text, steps)

    def _attribute_tiktoken(self, output_text: str, steps: List[Step]) -> List[Step]:
        token_ids = self.encoder.encode(output_text)
        try:
            _, offsets = self.encoder.decode_with_offsets(token_ids)
        except Exception:
            return self._attribute_heuristic(output_text, steps)

        for step in steps:
            step.token_indices = [
                k for k, o in enumerate(offsets)
                if step.start_char <= o < step.end_char
            ]
            step.token_count = len(step.token_indices)
        return steps

    def _attribute_heuristic(self, output_text: str, steps: List[Step]) -> List[Step]:
        total_chars = len(output_text)
        if total_chars == 0:
            return steps
        total_est = max(1, total_chars // 4)
        for step in steps:
            chars = step.end_char - step.start_char
            step.token_count = max(1, round(chars / total_chars * total_est))
            step.token_indices = []
        return steps


# ── Quality Scorer ───────────────────────────────────────────────────────────

class QualityScorer:
    """
    Four-dimensional quality scoring: F, V, C, U.

    Heuristic-based scoring that evaluates:
      - F (factuality): evidence refs, specificity, hedging
      - V (validity): logical markers, arithmetic, structure
      - C (coherence): info density, redundancy, clear purpose
      - U (utility): novelty, progress, non-decorative content
    """

    HEDGING = [
        re.compile(r'(?:可能|也许|大概|或许|should|might|maybe|perhaps)', re.I),
        re.compile(r'(?:我不确定|不太清楚|I\'?m not sure|uncertain)', re.I),
    ]
    REDUNDANCY = [
        re.compile(r'(?:如前所述|如上所述|前面提到|as mentioned|as noted)', re.I),
        re.compile(r'(?:重复|再次|同样|again|repeat|same as)', re.I),
    ]
    EVIDENCE = [
        re.compile(r'\[(?:Doc|Ref|Source|文档|引用)#?\s*\w+\]', re.I),
        re.compile(r'(?:根据|基于|according to|based on|from)\s+[\w\d]+', re.I),
    ]
    LOGICAL = [
        re.compile(r'(?:因此|所以|故|thus|therefore|hence|so)\b', re.I),
        re.compile(r'(?:因为|由于|because|since|due to)\b', re.I),
        re.compile(r'(?:如果|假如|假设|if|suppose|assume)\b', re.I),
        re.compile(r'(?:那么|则|then|implies|means)\b', re.I),
    ]

    DEFAULT_WEIGHTS = {'F': 0.25, 'V': 0.25, 'C': 0.25, 'U': 0.25}

    @classmethod
    def score_step(cls, step: Step, context: dict | None = None) -> StepQuality:
        text = step.text
        return StepQuality(
            factuality=round(cls._factuality(text), 3),
            validity=round(cls._validity(text), 3),
            coherence=round(cls._coherence(text), 3),
            utility=round(cls._utility(text, context), 3),
        )

    @classmethod
    def score_steps(cls, steps: List[Step], context: dict | None = None) -> List[StepQuality]:
        return [cls.score_step(s, context) for s in steps]

    # ── per-dimension scorers ──────────────────────────────────────────

    @classmethod
    def _factuality(cls, text: str) -> float:
        s = 0.5
        # evidence refs boost
        s += min(0.2, sum(len(p.findall(text)) for p in cls.EVIDENCE) * 0.1)
        # hedging reduces
        s -= min(0.2, sum(len(p.findall(text)) for p in cls.HEDGING) * 0.1)
        # specific numbers boost
        s += min(0.15, len(re.findall(r'\d+(?:\.\d+)?', text)) * 0.03)
        # very short = less informative
        if len(text) < 20:
            s -= 0.1
        elif len(text) > 50:
            s += 0.05
        return max(0.0, min(1.0, s))

    @classmethod
    def _validity(cls, text: str) -> float:
        s = 0.5
        s += min(0.2, sum(len(p.findall(text)) for p in cls.LOGICAL) * 0.05)
        if re.search(r'\d+\s*[+\-*/=]\s*\d+', text):
            s += 0.1
        if re.search(r'(?:首先|其次|最后|first|second|then|finally)', text, re.I):
            s += 0.05
        if re.search(r'(?:但是.*?不过|however.*?but|矛盾)', text, re.I):
            s -= 0.1
        if len(text.strip()) < 10:
            s -= 0.15
        return max(0.0, min(1.0, s))

    @classmethod
    def _coherence(cls, text: str) -> float:
        s = 0.5
        s -= min(0.2, sum(len(p.findall(text)) for p in cls.REDUNDANCY) * 0.1)
        words = re.findall(r'\b\w+\b', text.lower())
        if words:
            s += (len(set(words)) / len(words) - 0.5) * 0.3
        # repeated 20-char substrings
        if len(text) > 100:
            seen: set[str] = set()
            for i in range(len(text) - 20):
                sub = text[i:i + 20]
                if sub in seen:
                    s -= 0.1
                    break
                seen.add(sub)
        if re.search(r'(?:总结|结论|因此|in summary|conclusion)', text, re.I):
            s += 0.05
        return max(0.0, min(1.0, s))

    @classmethod
    def _utility(cls, text: str, context: dict | None = None) -> float:
        s = 0.5
        if re.search(r'(?:发现|结果|得到|found|result|got|yielded)', text, re.I):
            s += 0.1
        if re.search(r'(?:接下来|下一步|then|next|moving on)', text, re.I):
            s += 0.05
        word_count = len(re.findall(r'\b\w+\b', text))
        if word_count < 5:
            s -= 0.15
        elif word_count < 10:
            s -= 0.05
        # pure decoration
        if re.match(r'^[\s\-\*=#]+$', text):
            s = 0.1
        # exact repeat of previous step text
        if context and 'previous_steps' in context:
            for prev in context['previous_steps']:
                if hasattr(prev, 'text') and text.strip() in prev.text:
                    s -= 0.2
                    break
        return max(0.0, min(1.0, s))


# ── Metrics Calculator ───────────────────────────────────────────────────────

class MetricsCalculator:
    """
    Calculate the five core metrics:

    - **TE** (Token Efficiency): quality gained per reasoning token
    - **SUS** (Step Utility Score): token-weighted average utility
    - **FR** (Faithfulness Risk): shortcut-reasoning risk  (IBC + CIR)
    - **MG** (Monitorability Gain): estimated CoT monitoring value
    - **RR** (Redundancy Ratio): token-weighted fraction of redundant steps
    """

    def __init__(self, weights: Dict[str, float] | None = None):
        self.weights = weights or QualityScorer.DEFAULT_WEIGHTS

    def calculate(
        self,
        steps: List[Step],
        qualities: List[StepQuality],
        baseline_quality: float | None = None,
        baseline_reasoning_tokens: int | None = None,
    ) -> MetricsResult:
        if not steps or not qualities:
            return MetricsResult(
                token_efficiency=0.0,
                step_utility_score=0.0,
                faithfulness_risk=0.0,
                monitorability_gain=0.0,
                redundancy_ratio=0.0,
                composite_quality=0.0,
                avg_factuality=0.0,
                avg_validity=0.0,
                avg_coherence=0.0,
                avg_utility=0.0,
            )

        total_tokens = sum(s.token_count for s in steps)
        if total_tokens == 0:
            token_counts = [1] * len(steps)
            total_tokens = len(steps)
        else:
            token_counts = [s.token_count for s in steps]

        avg_f = sum(tc * q.factuality for tc, q in zip(token_counts, qualities)) / total_tokens
        avg_v = sum(tc * q.validity for tc, q in zip(token_counts, qualities)) / total_tokens
        avg_c = sum(tc * q.coherence for tc, q in zip(token_counts, qualities)) / total_tokens
        avg_u = sum(tc * q.utility for tc, q in zip(token_counts, qualities)) / total_tokens

        Q = (
            self.weights['F'] * avg_f
            + self.weights['V'] * avg_v
            + self.weights['C'] * avg_c
            + self.weights['U'] * avg_u
        )

        te = self._te(Q, total_tokens, baseline_quality, baseline_reasoning_tokens)
        sus = self._sus(token_counts, qualities, total_tokens)
        fr = self._fr(qualities, token_counts, total_tokens)
        mg = self._mg(steps, qualities)
        rr = self._rr(steps, qualities, token_counts, total_tokens)

        return MetricsResult(
            token_efficiency=round(te, 4),
            step_utility_score=round(sus, 4),
            faithfulness_risk=round(fr, 4),
            monitorability_gain=round(mg, 4),
            redundancy_ratio=round(rr, 4),
            composite_quality=round(Q, 4),
            avg_factuality=round(avg_f, 4),
            avg_validity=round(avg_v, 4),
            avg_coherence=round(avg_c, 4),
            avg_utility=round(avg_u, 4),
            steps=steps,
            step_qualities=qualities,
            total_reasoning_tokens=sum(s.token_count for s in steps),
        )

    # ── individual metrics ──────────────────────────────────────────────

    @staticmethod
    def _te(
        quality: float,
        tokens: int,
        base_q: float | None,
        base_t: int | None,
    ) -> float:
        """Token Efficiency: delta-Q / delta-tokens (or Q per 1k tokens)."""
        if base_q is not None and base_t is not None:
            dt = tokens - base_t
            if dt > 0:
                return (quality - base_q) / dt
            return 0.0
        if tokens > 0:
            return quality / (tokens / 1000)
        return 0.0

    @staticmethod
    def _sus(
        token_counts: List[int],
        qualities: List[StepQuality],
        total_tokens: int,
    ) -> float:
        if total_tokens == 0:
            return 0.0
        return sum(tc * q.utility for tc, q in zip(token_counts, qualities)) / total_tokens

    @staticmethod
    def _fr(
        qualities: List[StepQuality],
        token_counts: List[int],
        total_tokens: int,
        tau_v: float = 0.3,
        tau_f: float = 0.3,
        alpha: float = 0.5,
    ) -> float:
        """Faithfulness Risk = alpha*IBC + (1-alpha)*CIR."""
        if not qualities or total_tokens == 0:
            return 0.0
        ibc = 0
        cir = 0
        avg_tc = total_tokens / len(qualities)
        for tc, q in zip(token_counts, qualities):
            if q.validity < tau_v or q.factuality < tau_f:
                ibc += tc
            if q.utility < 0.3 and tc > avg_tc:
                cir += tc
        return alpha * (ibc / total_tokens) + (1 - alpha) * (cir / total_tokens)

    @staticmethod
    def _mg(steps: List[Step], qualities: List[StepQuality]) -> float:
        """Estimated monitorability gain from structured steps."""
        if not steps:
            return 0.0
        n = len(steps)
        base = min(1.0, n / 10)
        avg_tokens = sum(s.token_count for s in steps) / n
        boundary = min(1.0, avg_tokens / 20)
        utils = [q.utility for q in qualities]
        if len(utils) > 1:
            mean = sum(utils) / len(utils)
            var = sum((u - mean) ** 2 for u in utils) / len(utils)
            var_score = min(1.0, var * 4)
        else:
            var_score = 0.5
        return base * 0.4 + boundary * 0.3 + var_score * 0.3

    @staticmethod
    def _rr(
        steps: List[Step],
        qualities: List[StepQuality],
        token_counts: List[int],
        total_tokens: int,
        epsilon: float = 0.2,
    ) -> float:
        """Redundancy Ratio: token-weighted fraction of steps with U <= epsilon."""
        if total_tokens == 0:
            return 0.0
        red = sum(tc for tc, q in zip(token_counts, qualities) if q.utility <= epsilon)
        return red / total_tokens


# ── Convenience ──────────────────────────────────────────────────────────────

def analyze_output(
    output_text: str,
    context: dict | None = None,
    weights: Dict[str, float] | None = None,
) -> MetricsResult:
    """One-call: parse -> attribute -> score -> calculate metrics."""
    steps, answer = StepParser.parse(output_text)
    attributor = TokenAttributor()
    steps = attributor.attribute(output_text, steps)
    qualities = QualityScorer.score_steps(steps, context)
    return MetricsCalculator(weights).calculate(steps, qualities)
