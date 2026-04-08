#!/usr/bin/env python3
"""
Tests for stoi_engine.py — STOI core algorithms.

Covers:
  - L1 syntax waste detection
  - L3 cache blame detection
  - calc_stoi baseline / scoring logic
  - calc_stoi_score multi-layer weighting
  - Edge cases (zero tokens, all-cached, all-miss, etc.)
"""

import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from stoi_engine import (
    l1_syntax_waste,
    l3_cache_blame,
    calc_stoi,
    calc_stoi_score,
    SHIT_THRESHOLDS,
    get_score_color,
    get_level_display,
)


# ── L1 Syntax Waste ──────────────────────────────────────────────────────────

class TestL1SyntaxWaste:
    def test_empty_prompt(self):
        r = l1_syntax_waste("")
        assert r["waste_rate"] == 0.0
        assert r["token_estimate"] == 0

    def test_none_prompt(self):
        r = l1_syntax_waste(None)
        assert r["waste_rate"] == 0.0

    def test_clean_text(self):
        r = l1_syntax_waste("This is plain text with no formatting.")
        assert r["waste_rate"] == 0.0
        assert r["examples"] == []

    def test_bold_markdown(self):
        text = "Use **bold** and **more bold** text here."
        r = l1_syntax_waste(text)
        assert r["waste_rate"] > 0
        assert any("粗体" in ex for ex in r["examples"])

    def test_headers(self):
        text = "## Header 1\n### Header 2\nSome content"
        r = l1_syntax_waste(text)
        assert r["waste_rate"] > 0
        assert any("标题" in ex for ex in r["examples"])

    def test_deep_indentation(self):
        lines = ["    " + "x" * 20] * 10
        text = "\n".join(lines)
        r = l1_syntax_waste(text)
        assert r["waste_rate"] > 0
        assert any("缩进" in ex for ex in r["examples"])

    def test_separators(self):
        text = "above\n----------\nbelow"
        r = l1_syntax_waste(text)
        assert r["waste_rate"] > 0
        assert any("分隔线" in ex for ex in r["examples"])

    def test_token_estimate(self):
        text = "**" * 50  # 100 formatting chars
        r = l1_syntax_waste(text)
        assert r["token_estimate"] == 100 // 4


# ── L3 Cache Blame ───────────────────────────────────────────────────────────

class TestL3CacheBlame:
    def test_empty_prompt(self):
        r = l3_cache_blame("")
        assert r["severity"] == "NONE"
        assert r["score_penalty"] == 0.0

    def test_none_prompt(self):
        r = l3_cache_blame(None)
        assert r["severity"] == "NONE"

    def test_clean_prompt(self):
        r = l3_cache_blame("You are a helpful assistant.")
        assert r["severity"] == "NONE"
        assert r["culprits"] == []

    def test_timestamp_injection(self):
        text = "Current time: 2025-03-12 09:40:19. Please help."
        r = l3_cache_blame(text)
        assert r["severity"] == "HIGH"
        assert any(c["type"] == "timestamp" for c in r["culprits"])
        assert r["score_penalty"] == 25.0

    def test_uuid(self):
        text = "Session: abc12345-def4-5678-90ab-cdef12345678"
        r = l3_cache_blame(text)
        assert r["severity"] == "HIGH"
        assert any(c["type"] == "uuid" for c in r["culprits"])

    def test_absolute_path(self):
        text = "Working dir: /Users/john/project"
        r = l3_cache_blame(text)
        assert r["severity"] == "MEDIUM"
        assert any(c["type"] == "abs_path" for c in r["culprits"])
        assert r["score_penalty"] == 15.0

    def test_pid(self):
        text = "Process: pid=12345"
        r = l3_cache_blame(text)
        assert r["severity"] == "HIGH"

    def test_git_hash(self):
        text = "Build: abc123def"
        r = l3_cache_blame(text)
        assert r["severity"] == "LOW"
        assert r["score_penalty"] == 5.0

    def test_multiple_culprits(self):
        text = "Time: 2025-01-01 00:00:00\nSession: a1b2c3d4-e5f6-7890-abcd-ef1234567890\nPath: /Users/test"
        r = l3_cache_blame(text)
        assert len(r["culprits"]) >= 2
        assert r["severity"] == "HIGH"


# ── calc_stoi ────────────────────────────────────────────────────────────────

class TestCalcStoi:
    def _make_usage(self, new=0, cache_read=0, cache_creation=0, output=0):
        return {
            "input_tokens": new,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_creation,
            "output_tokens": output,
        }

    def test_zero_everything(self):
        r = calc_stoi(self._make_usage())
        assert r["stoi_score"] == 0.0
        assert r["level"] == "CLEAN"
        assert r["is_baseline"] is True

    def test_output_zero_baseline(self):
        """output=0 should be baseline (streaming placeholder)."""
        r = calc_stoi(self._make_usage(new=1000, output=0), turn_index=5)
        assert r["is_baseline"] is True
        assert r["stoi_score"] == 0.0

    def test_first_turn_baseline(self):
        """turn_index=0 should be baseline (building cache)."""
        r = calc_stoi(self._make_usage(new=5000, output=100), turn_index=0)
        assert r["is_baseline"] is True

    def test_cache_creation_dominant_baseline(self):
        """cache_creation > cache_read should be baseline (rebuilding cache)."""
        r = calc_stoi(self._make_usage(new=100, cache_creation=5000, cache_read=100, output=50), turn_index=5)
        assert r["is_baseline"] is True

    def test_no_cache_info_baseline(self):
        r = calc_stoi(self._make_usage(new=1000, output=50), turn_index=-1)
        assert r["is_baseline"] is True

    def test_all_cached(self):
        """Everything from cache → low score."""
        r = calc_stoi(self._make_usage(new=100, cache_read=9000, output=500), turn_index=5)
        assert r["is_baseline"] is False
        assert r["stoi_score"] < 20
        assert r["cache_hit_rate"] > 80

    def test_no_cache_hit(self):
        """No cache at all → high score."""
        r = calc_stoi(self._make_usage(new=9000, output=500), turn_index=5)
        assert r["is_baseline"] is False
        assert r["stoi_score"] > 50
        assert r["wasted_tokens"] == 9000

    def test_wasted_tokens_only_counts_new(self):
        """wasted_tokens should be new_tokens, not new+creation."""
        r = calc_stoi(
            self._make_usage(new=2000, cache_read=5000, cache_creation=1000, output=500),
            turn_index=5,
        )
        assert r["wasted_tokens"] == 2000

    def test_cache_creation_reduces_score(self):
        """cache_creation should reduce effective waste."""
        usage_no_creation = self._make_usage(new=3000, cache_read=3000, output=500)
        usage_with_creation = self._make_usage(new=3000, cache_read=3000, cache_creation=2000, output=500)

        r1 = calc_stoi(usage_no_creation, turn_index=5)
        r2 = calc_stoi(usage_with_creation, turn_index=5)

        # With creation, score should be lower (investment reduces penalty)
        assert r2["stoi_score"] < r1["stoi_score"]

    def test_score_levels(self):
        for expected_level, (lo, hi) in SHIT_THRESHOLDS.items():
            # Manufacture a score in [lo, hi)
            # total_context = 10000, new = score% * 10000
            target = (lo + hi) / 2
            new = int(target / 100 * 10000)
            r = calc_stoi(
                self._make_usage(new=new, cache_read=10000 - new, output=500),
                turn_index=5,
            )
            assert r["level"] == expected_level, (
                f"Expected {expected_level} for score ~{target}, got {r['level']} ({r['stoi_score']})"
            )


# ── calc_stoi_score ──────────────────────────────────────────────────────────

class TestCalcStoiScore:
    def _make_usage(self, new=5000, cache_read=3000, output=500):
        return {
            "input_tokens": new,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": 0,
            "output_tokens": output,
        }

    def test_no_system_prompt(self):
        r = calc_stoi_score(self._make_usage())
        assert "l1" not in r or r["l1"]["waste_rate"] == 0.0

    def test_with_clean_system_prompt(self):
        r = calc_stoi_score(self._make_usage(), system_prompt="Clean prompt")
        assert "l1" in r
        assert "l3" in r
        # Clean prompt shouldn't add much penalty
        assert r["stoi_score"] >= 0

    def test_with_dirty_system_prompt(self):
        dirty = "Time: 2025-01-01 00:00:00\n## **Important**\nSession: a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        r = calc_stoi_score(self._make_usage(), system_prompt=dirty)
        assert r["l3"]["severity"] == "HIGH"
        # Combined score should be higher than base
        base = calc_stoi(self._make_usage(), turn_index=5)
        assert r["stoi_score"] >= base["stoi_score"] * 0.65

    def test_weights_sum_to_one(self):
        """Verify the weight comment matches the code (0.65 + 0.15 + 0.20 = 1.0)."""
        dirty = "Time: 2025-01-01 00:00:00\n**bold**"
        usage = self._make_usage()
        base = calc_stoi(usage, turn_index=5)
        l1 = l1_syntax_waste(dirty)
        l3 = l3_cache_blame(dirty)
        expected = (
            base["stoi_score"] * 0.65
            + l1["waste_rate"] * 0.15
            + l3["score_penalty"] * 0.20
        )
        r = calc_stoi_score(usage, system_prompt=dirty)
        assert abs(r["stoi_score"] - round(min(expected, 100.0), 1)) < 0.2


# ── Helpers ──────────────────────────────────────────────────────────────────

class TestHelpers:
    def test_score_color(self):
        assert get_score_color(10) == "green"
        assert get_score_color(40) == "yellow"
        assert get_score_color(60) == "dark_orange"
        assert get_score_color(90) == "red"

    def test_get_level_display(self):
        assert "CLEAN" in get_level_display("CLEAN")
        assert "DEEP_SHIT" in get_level_display("DEEP_SHIT")
