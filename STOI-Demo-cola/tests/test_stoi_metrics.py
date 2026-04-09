#!/usr/bin/env python3
"""
Tests for stoi_metrics.py — Step-level token attribution & quality metrics.

Covers:
  - StepParser: structured & fallback parsing
  - TokenAttributor: heuristic attribution
  - QualityScorer: F/V/C/U dimensions
  - MetricsCalculator: TE, SUS, FR, MG, RR
  - analyze_output: end-to-end convenience function
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from stoi_metrics import (
    Step,
    StepQuality,
    StepParser,
    TokenAttributor,
    QualityScorer,
    MetricsCalculator,
    MetricsResult,
    analyze_output,
)
from stoi_analyze import (
    compute_step_metrics,
    aggregate_step_metrics,
)


# ── StepParser ───────────────────────────────────────────────────────────────

class TestStepParser:
    def test_structured_trace_answer(self):
        text = (
            "<trace>\n"
            "Step 1: First we analyze the input data.\n"
            "Step 2: Then we compute the result.\n"
            "</trace>\n"
            "<answer>42</answer>"
        )
        steps, answer = StepParser.parse(text)
        assert len(steps) == 2
        assert answer == "42"
        assert "First" in steps[0].text
        assert "compute" in steps[1].text

    def test_structured_no_answer_tag(self):
        text = (
            "<trace>\n"
            "Step 1: Analysis step.\n"
            "</trace>\n"
            "The answer is 42."
        )
        steps, answer = StepParser.parse(text)
        assert len(steps) == 1
        assert "42" in answer

    def test_fallback_numbered_list(self):
        text = (
            "Let me think about this.\n"
            "1. First consideration.\n"
            "2. Second consideration.\n"
            "Therefore the answer is X."
        )
        steps, answer = StepParser.parse(text)
        assert len(steps) >= 2

    def test_fallback_double_newline(self):
        text = "Part one of reasoning.\n\nPart two of reasoning.\n\nAnswer: 42"
        steps, answer = StepParser.parse(text)
        assert len(steps) >= 2

    def test_fallback_answer_marker(self):
        text = "Some reasoning.\n\n因此，答案是 42。"
        steps, answer = StepParser.parse(text)
        assert len(steps) >= 1
        assert "42" in answer

    def test_single_step_no_structure(self):
        text = "Just a single paragraph of reasoning with no clear structure."
        steps, answer = StepParser.parse(text)
        assert len(steps) == 1
        assert steps[0].text == text.strip()

    def test_empty_text(self):
        steps, answer = StepParser.parse("")
        assert steps == []
        assert answer == ""

    def test_merge_short_steps(self):
        text = (
            "<trace>\n"
            "Step 1: Hi\n"
            "Step 2: This is a longer step with enough content to stand alone.\n"
            "Step 3: Ok\n"
            "</trace>\n"
            "<answer>done</answer>"
        )
        steps, _ = StepParser.parse(text, min_step_tokens=3)
        # Short steps should be merged
        assert len(steps) <= 3

    def test_step_indices_from_explicit(self):
        text = (
            "<trace>\n"
            "Step 1: A\n"
            "Step 2: B\n"
            "Step 3: C\n"
            "</trace>\n"
            "<answer>X</answer>"
        )
        steps, _ = StepParser.parse(text, min_step_tokens=0)
        assert len(steps) == 3
        # Explicit Step markers preserve their original numbers
        assert steps[0].index == 1
        assert steps[1].index == 2
        assert steps[2].index == 3

    def test_chinese_step_markers(self):
        text = (
            "<trace>\n"
            "Step 1: 首先分析数据\n"
            "Step 2: 然后计算结果\n"
            "</trace>\n"
            "<answer>答案是 42</answer>"
        )
        steps, answer = StepParser.parse(text, min_step_tokens=0)
        assert len(steps) == 2
        assert "42" in answer


# ── TokenAttributor ──────────────────────────────────────────────────────────

class TestTokenAttributor:
    def test_heuristic_attribution(self):
        attr = TokenAttributor()
        # Force heuristic by not using tiktoken
        attr.encoder = None

        text = "Step 1: " + "A" * 100 + "\nStep 2: " + "B" * 100
        steps, _ = StepParser.parse(text, min_step_tokens=0)
        steps = attr.attribute(text, steps)

        assert all(s.token_count > 0 for s in steps)
        total = sum(s.token_count for s in steps)
        assert total > 0

    def test_heuristic_proportional(self):
        attr = TokenAttributor()
        attr.encoder = None

        long_text = "A" * 300
        short_text = "B" * 100
        text = f"{long_text}\n{short_text}"
        steps, _ = StepParser.parse(text, min_step_tokens=0)
        steps = attr.attribute(text, steps)

        if len(steps) >= 2:
            # Longer step should get more tokens
            assert steps[0].token_count >= steps[1].token_count

    def test_empty_text(self):
        attr = TokenAttributor()
        steps = attr.attribute("", [])
        assert steps == []


# ── QualityScorer ────────────────────────────────────────────────────────────

class TestQualityScorer:
    def test_high_quality_step(self):
        step = Step(
            index=0,
            text="Based on [Doc#1], the calculation shows 2 + 2 = 4. Therefore, the result is 4.",
            start_char=0,
            end_char=80,
            token_count=20,
        )
        q = QualityScorer.score_step(step)
        # Should have decent scores
        assert q.validity >= 0.3  # has logical markers
        assert q.factuality >= 0.3  # has evidence reference

    def test_low_factuality_hedging(self):
        step = Step(
            index=0,
            text="Maybe possibly the answer might be approximately something.",
            start_char=0,
            end_char=60,
            token_count=15,
        )
        q = QualityScorer.score_step(step)
        assert q.factuality < 0.6  # heavy hedging

    def test_low_coherence_redundancy(self):
        step = Step(
            index=0,
            text="As mentioned above, as noted before, this is the same as before. Again repeat.",
            start_char=0,
            end_char=80,
            token_count=20,
        )
        q = QualityScorer.score_step(step)
        assert q.coherence < 0.5

    def test_low_utility_short(self):
        step = Step(index=0, text="ok", start_char=0, end_char=2, token_count=1)
        q = QualityScorer.score_step(step)
        assert q.utility < 0.5

    def test_pure_decoration(self):
        step = Step(
            index=0,
            text="---===---",
            start_char=0,
            end_char=9,
            token_count=2,
        )
        q = QualityScorer.score_step(step)
        assert q.utility < 0.2

    def test_validity_with_arithmetic(self):
        step = Step(
            index=0,
            text="The total is 100 + 200 = 300 units.",
            start_char=0,
            end_char=35,
            token_count=10,
        )
        q = QualityScorer.score_step(step)
        assert q.validity >= 0.5  # arithmetic present

    def test_score_steps_batch(self):
        steps = [
            Step(index=i, text=f"Step {i} content " * 5, start_char=0, end_char=50, token_count=10)
            for i in range(5)
        ]
        qualities = QualityScorer.score_steps(steps)
        assert len(qualities) == 5
        for q in qualities:
            assert 0 <= q.factuality <= 1
            assert 0 <= q.validity <= 1
            assert 0 <= q.coherence <= 1
            assert 0 <= q.utility <= 1

    def test_scores_bounded(self):
        """All scores must be in [0, 1]."""
        step = Step(
            index=0,
            text="x" * 5000,  # very long
            start_char=0,
            end_char=5000,
            token_count=1250,
        )
        q = QualityScorer.score_step(step)
        for dim in [q.factuality, q.validity, q.coherence, q.utility]:
            assert 0.0 <= dim <= 1.0


# ── MetricsCalculator ────────────────────────────────────────────────────────

class TestMetricsCalculator:
    def _make_steps_and_qualities(self, n=5, token_count=20, utility=0.7):
        steps = [
            Step(index=i, text=f"Step {i}", start_char=i * 10, end_char=i * 10 + 10, token_count=token_count)
            for i in range(n)
        ]
        qualities = [
            StepQuality(factuality=0.7, validity=0.8, coherence=0.6, utility=utility)
            for _ in range(n)
        ]
        return steps, qualities

    def test_basic_calculation(self):
        steps, qualities = self._make_steps_and_qualities()
        calc = MetricsCalculator()
        result = calc.calculate(steps, qualities)

        assert 0 <= result.token_efficiency
        assert 0 <= result.step_utility_score <= 1
        assert 0 <= result.faithfulness_risk <= 1
        assert 0 <= result.monitorability_gain <= 1
        assert 0 <= result.redundancy_ratio <= 1
        assert 0 <= result.composite_quality <= 1

    def test_empty_input(self):
        calc = MetricsCalculator()
        result = calc.calculate([], [])
        assert result.token_efficiency == 0.0
        assert result.step_utility_score == 0.0
        assert result.composite_quality == 0.0

    def test_sus_high_utility(self):
        steps, qualities = self._make_steps_and_qualities(utility=0.9)
        result = MetricsCalculator().calculate(steps, qualities)
        assert result.step_utility_score > 0.8

    def test_sus_low_utility(self):
        steps, qualities = self._make_steps_and_qualities(utility=0.1)
        result = MetricsCalculator().calculate(steps, qualities)
        assert result.step_utility_score < 0.2

    def test_rr_with_low_utility(self):
        """Steps with utility <= epsilon should count as redundant."""
        steps, qualities = self._make_steps_and_qualities(utility=0.1)
        result = MetricsCalculator().calculate(steps, qualities)
        assert result.redundancy_ratio > 0.5  # most tokens redundant

    def test_rr_with_high_utility(self):
        steps, qualities = self._make_steps_and_qualities(utility=0.8)
        result = MetricsCalculator().calculate(steps, qualities)
        assert result.redundancy_ratio == 0.0  # no redundancy

    def test_fr_with_low_validity(self):
        """Low validity should increase faithfulness risk."""
        steps = [Step(index=0, text="test", start_char=0, end_char=4, token_count=10)]
        qualities = [StepQuality(factuality=0.1, validity=0.1, coherence=0.5, utility=0.5)]
        result = MetricsCalculator().calculate(steps, qualities)
        assert result.faithfulness_risk > 0.3

    def test_fr_with_high_quality(self):
        steps, qualities = self._make_steps_and_qualities(
            n=3, token_count=20, utility=0.9
        )
        # Override to high quality
        qualities = [
            StepQuality(factuality=0.9, validity=0.9, coherence=0.9, utility=0.9)
            for _ in range(3)
        ]
        result = MetricsCalculator().calculate(steps, qualities)
        assert result.faithfulness_risk < 0.1

    def test_mg_increases_with_steps(self):
        """More steps → higher monitorability."""
        steps_few, qualities_few = self._make_steps_and_qualities(n=2, utility=0.7)
        steps_many, qualities_many = self._make_steps_and_qualities(n=12, utility=0.7)

        mg_few = MetricsCalculator().calculate(steps_few, qualities_few).monitorability_gain
        mg_many = MetricsCalculator().calculate(steps_many, qualities_many).monitorability_gain

        assert mg_many > mg_few

    def test_te_with_baseline(self):
        steps, qualities = self._make_steps_and_qualities(n=5, token_count=20, utility=0.7)
        result = MetricsCalculator().calculate(
            steps, qualities,
            baseline_quality=0.3,
            baseline_reasoning_tokens=50,
        )
        # Should calculate delta-Q / delta-tokens
        assert result.token_efficiency > 0

    def test_te_without_baseline(self):
        steps, qualities = self._make_steps_and_qualities(n=5, token_count=20)
        result = MetricsCalculator().calculate(steps, qualities)
        # Should calculate Q per 1k tokens
        assert result.token_efficiency > 0

    def test_composite_quality_weights(self):
        steps = [Step(index=0, text="test", start_char=0, end_char=4, token_count=10)]
        qualities = [StepQuality(factuality=1.0, validity=0.0, coherence=0.0, utility=0.0)]

        # Default weights: F=0.25
        result = MetricsCalculator().calculate(steps, qualities)
        assert abs(result.composite_quality - 0.25) < 0.01

    def test_custom_weights(self):
        steps = [Step(index=0, text="test", start_char=0, end_char=4, token_count=10)]
        qualities = [StepQuality(factuality=1.0, validity=0.0, coherence=0.0, utility=0.0)]

        calc = MetricsCalculator(weights={'F': 0.5, 'V': 0.2, 'C': 0.2, 'U': 0.1})
        result = calc.calculate(steps, qualities)
        assert abs(result.composite_quality - 0.5) < 0.01

    def test_zero_token_steps(self):
        """Steps with 0 tokens should use equal weighting fallback."""
        steps = [Step(index=i, text=f"Step {i}", start_char=i * 10, end_char=i * 10 + 10, token_count=0) for i in range(3)]
        qualities = [StepQuality(0.5, 0.5, 0.5, 0.5) for _ in range(3)]
        result = MetricsCalculator().calculate(steps, qualities)
        assert result.composite_quality == 0.5
        assert result.total_reasoning_tokens == 0


# ── analyze_output (end-to-end) ──────────────────────────────────────────────

class TestAnalyzeOutput:
    def test_structured_output(self):
        text = (
            "<trace>\n"
            "Step 1: Based on [Doc#1], the data shows 100 users.\n"
            "Step 2: Therefore, the conversion rate is 100/200 = 50%.\n"
            "</trace>\n"
            "<answer>The conversion rate is 50%.</answer>"
        )
        result = analyze_output(text)
        assert len(result.steps) == 2
        assert result.composite_quality > 0
        assert result.step_utility_score > 0

    def test_unstructured_output(self):
        text = (
            "Let me analyze this.\n\n"
            "The data shows 100 out of 200 users converted.\n\n"
            "Therefore the rate is 50%."
        )
        result = analyze_output(text)
        assert len(result.steps) >= 1
        assert result.composite_quality > 0

    def test_empty_output(self):
        result = analyze_output("")
        assert result.token_efficiency == 0.0
        assert result.composite_quality == 0.0

    def test_result_fields_complete(self):
        text = "<trace>\nStep 1: Analysis.\n</trace>\n<answer>42</answer>"
        result = analyze_output(text)

        for field_name in [
            'token_efficiency', 'step_utility_score', 'faithfulness_risk',
            'monitorability_gain', 'redundancy_ratio', 'composite_quality',
            'avg_factuality', 'avg_validity', 'avg_coherence', 'avg_utility',
        ]:
            assert hasattr(result, field_name), f"Missing field: {field_name}"

    def test_multi_step_metrics(self):
        """5-step output should produce reasonable metrics."""
        steps_text = "\n".join(
            f"Step {i}: {desc}"
            for i, desc in enumerate([
                "First, we gather data from the database.",
                "Based on [Doc#2], there are 500 records.",
                "We filter to 300 valid records using the criteria.",
                "The calculation shows 300 / 500 = 60% success rate.",
                "Therefore, the success rate is 60%.",
            ], 1)
        )
        text = f"<trace>\n{steps_text}\n</trace>\n<answer>60%</answer>"
        result = analyze_output(text)

        assert len(result.steps) == 5
        assert result.total_reasoning_tokens > 0
        assert result.monitorability_gain > 0


# ── Integration: compute_step_metrics ────────────────────────────────────────

class TestComputeStepMetrics:
    def test_records_with_output_text(self):
        records = [
            {
                "ts": "2026-01-01",
                "output_text": (
                    "<trace>\nStep 1: Based on [Doc#1], the data shows 100 users.\n"
                    "Step 2: Therefore the result is 50%.\n</trace>\n<answer>50%</answer>"
                ),
                "stoi": {"stoi_score": 30.0},
            },
        ]
        result = compute_step_metrics(records)
        assert result[0]["step_metrics"] is not None
        assert result[0]["step_metrics"].composite_quality > 0

    def test_short_text_skipped(self):
        records = [
            {"ts": "2026-01-01", "output_text": "short", "stoi": {"stoi_score": 10.0}},
        ]
        result = compute_step_metrics(records)
        assert result[0]["step_metrics"] is None

    def test_no_output_text(self):
        records = [
            {"ts": "2026-01-01", "stoi": {"stoi_score": 20.0}},
        ]
        result = compute_step_metrics(records)
        assert result[0]["step_metrics"] is None

    def test_mixed_records(self):
        records = [
            {
                "ts": "2026-01-01",
                "output_text": "Step 1: Analysis with enough content to be analyzed. " * 3,
                "stoi": {"stoi_score": 30.0},
            },
            {
                "ts": "2026-01-02",
                "output_text": "too short",
                "stoi": {"stoi_score": 40.0},
            },
            {
                "ts": "2026-01-03",
                "stoi": {"stoi_score": 50.0},
            },
        ]
        result = compute_step_metrics(records)
        assert result[0]["step_metrics"] is not None
        assert result[1]["step_metrics"] is None
        assert result[2]["step_metrics"] is None


# ── Integration: aggregate_step_metrics ───────────────────────────────────────

class TestAggregateStepMetrics:
    def test_empty_records(self):
        assert aggregate_step_metrics([]) is None

    def test_no_valid_metrics(self):
        records = [
            {"ts": "2026-01-01", "output_text": "short", "stoi": {"stoi_score": 10.0}},
        ]
        compute_step_metrics(records)
        assert aggregate_step_metrics(records) is None

    def test_valid_aggregation(self):
        # Pre-compute metrics for two records with substantial text
        long_text_a = (
            "<trace>\nStep 1: Based on [Doc#1], the calculation shows 100 + 200 = 300.\n"
            "Step 2: Therefore, the total is 300 units.\n</trace>\n<answer>300</answer>"
        )
        long_text_b = (
            "<trace>\nStep 1: According to the data, we have 500 records to process.\n"
            "Step 2: We filter and find 250 valid records.\n</trace>\n<answer>250</answer>"
        )
        records = [
            {"ts": "2026-01-01", "output_text": long_text_a, "stoi": {"stoi_score": 30.0}},
            {"ts": "2026-01-02", "output_text": long_text_b, "stoi": {"stoi_score": 40.0}},
        ]
        compute_step_metrics(records)
        agg = aggregate_step_metrics(records)

        assert agg is not None
        assert agg["count"] == 2
        assert 0 <= agg["avg_factuality"] <= 1
        assert 0 <= agg["avg_validity"] <= 1
        assert 0 <= agg["avg_coherence"] <= 1
        assert 0 <= agg["avg_utility"] <= 1
        assert "token_efficiency" in agg
        assert "faithfulness_risk" in agg
        assert "redundancy_ratio" in agg
        assert agg["total_steps"] > 0
        assert agg["total_reasoning_tokens"] >= 0


# ── Integration: output_text extraction ───────────────────────────────────────

class TestOutputTextExtraction:
    def test_parse_extracts_output_text(self):
        """Verify parse_claude_code_session extracts output_text from content blocks."""
        import json
        import tempfile

        # Create a mock JSONL session file
        records_data = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet",
                    "usage": {
                        "input_tokens": 5000,
                        "cache_read_input_tokens": 3000,
                        "cache_creation_input_tokens": 0,
                        "output_tokens": 200,
                    },
                    "content": [
                        {"type": "text", "text": "Step 1: Analysis of the problem.\nStep 2: Therefore the answer is 42."},
                    ],
                },
                "timestamp": "2026-03-12T09:40:19.768Z",
                "sessionId": "test-session-123",
            },
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            for r in records_data:
                f.write(json.dumps(r) + "\n")
            tmp_path = f.name

        try:
            from stoi_analyze import parse_claude_code_session
            records = parse_claude_code_session(tmp_path)
            assert len(records) == 1
            assert "output_text" in records[0]
            assert "Step 1: Analysis" in records[0]["output_text"]
            assert "42" in records[0]["output_text"]
        finally:
            import os
            os.unlink(tmp_path)

    def test_parse_with_string_content(self):
        """Verify output_text is extracted when content is a plain string."""
        import json
        import tempfile

        records_data = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "usage": {
                        "input_tokens": 3000,
                        "cache_read_input_tokens": 1000,
                        "cache_creation_input_tokens": 0,
                        "output_tokens": 100,
                    },
                    "content": "This is the assistant response text.",
                },
                "timestamp": "2026-03-12T09:40:19.768Z",
                "sessionId": "test-session-456",
            },
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            for r in records_data:
                f.write(json.dumps(r) + "\n")
            tmp_path = f.name

        try:
            from stoi_analyze import parse_claude_code_session
            records = parse_claude_code_session(tmp_path)
            assert len(records) == 1
            assert records[0]["output_text"] == "This is the assistant response text."
        finally:
            import os
            os.unlink(tmp_path)

    def test_parse_no_content(self):
        """Verify output_text is empty when no content is present."""
        import json
        import tempfile

        records_data = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "usage": {
                        "input_tokens": 3000,
                        "cache_read_input_tokens": 1000,
                        "cache_creation_input_tokens": 0,
                        "output_tokens": 50,
                    },
                },
                "timestamp": "2026-03-12T09:40:19.768Z",
                "sessionId": "test-session-789",
            },
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            for r in records_data:
                f.write(json.dumps(r) + "\n")
            tmp_path = f.name

        try:
            from stoi_analyze import parse_claude_code_session
            records = parse_claude_code_session(tmp_path)
            assert len(records) == 1
            assert records[0]["output_text"] == ""
        finally:
            import os
            os.unlink(tmp_path)
