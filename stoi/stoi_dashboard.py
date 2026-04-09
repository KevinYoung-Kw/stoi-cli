#!/usr/bin/env python3
"""
stoi_dashboard.py — STOI 对话链条可视化 Dashboard

生成自包含 HTML Dashboard，带内置 HTTP 服务器提供 per-turn LLM 分析 API。

Architecture:
  1. generate_dashboard(analysis, session_path) → Path  生成 HTML 文件
  2. serve_dashboard(html_path)                 → None  启动本地 HTTP 服务器
  3. HTML 调用 /api/analyze-turn → 服务器调用 LLM → 返回 JSON

Server port: 57018  (与 proxy 端口 57017 不同)
"""

from __future__ import annotations

import html as _html
import json
import os
import re
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional

from .stoi_chain import ChainAnalysis, ChainTurn, parse_chain


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _h(text: str) -> str:
    """HTML-escape a string."""
    return _html.escape(str(text))


def _score_css_color(score: float) -> str:
    """Return CSS color for a STOI score."""
    if score < 30:
        return "#22c55e"
    if score < 50:
        return "#f59e0b"
    if score < 75:
        return "#f97316"
    return "#ef4444"


def _score_badge(score: float) -> str:
    color = _score_css_color(score)
    bg = color + "22"
    label = f"{score:.0f}%"
    return (
        f'<span class="score-badge" style="color:{color};background:{bg};'
        f'border:1px solid {color}44">{label}</span>'
    )


def _fmt_ts(ts: float) -> str:
    """Format a millisecond timestamp into HH:MM:SS."""
    if not ts:
        return "—"
    try:
        if ts > 1e12:
            ts = ts / 1000
        return datetime.fromtimestamp(ts).strftime("%H:%M:%S")
    except Exception:
        return "—"


def _truncate(text: str, n: int = 40) -> str:
    text = text.replace("\n", " ").strip()
    return (text[:n] + "…") if len(text) > n else text


# ─── Summary stats computation ───────────────────────────────────────────────

def _compute_summary(analysis: ChainAnalysis) -> dict:
    turns = analysis.turns
    if not turns:
        return {
            "total_input": 0,
            "avg_stoi": 0.0,
            "avg_cache_hit": 0.0,
            "tool_result_ratio": 0.0,
            "optimizable_tokens": 0,
        }

    total_input = sum(t.total_input_tokens for t in turns)
    avg_stoi = sum(t.stoi_score for t in turns) / len(turns) if turns else 0.0

    # cache hit rate: cache_read / (input + cache_read)
    total_cache_read = sum(t.cache_read_tokens for t in turns)
    total_fresh = sum(t.total_input_tokens for t in turns)
    avg_cache_hit = (total_cache_read / max(total_fresh, 1)) * 100

    # tool result ratio
    total_tool_result = sum(t.tool_result_tokens for t in turns)
    tool_result_ratio = total_tool_result / max(total_input, 1) * 100

    # optimizable tokens = tool_results that are "large" (>2000 tokens)
    optimizable = sum(
        tr.output_tokens
        for t in turns
        for tr in t.tool_results
        if tr.is_large
    )

    return {
        "total_input": total_input,
        "avg_stoi": avg_stoi,
        "avg_cache_hit": avg_cache_hit,
        "tool_result_ratio": tool_result_ratio,
        "optimizable_tokens": optimizable,
    }


# ─── HTML Dashboard Generator ────────────────────────────────────────────────

_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #f8fafc;
  color: #0f172a;
  font-size: 14px;
  line-height: 1.6;
  padding: 24px 16px 48px;
}

.wrapper { max-width: 900px; margin: 0 auto; }

/* ── Header ── */
.header {
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  color: white;
  border-radius: 12px;
  padding: 24px 28px 20px;
  margin-bottom: 20px;
}
.header-top {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.header-emoji { font-size: 28px; }
.header-title {
  font-size: 22px;
  font-weight: 700;
  color: #FFB800;
  letter-spacing: -0.5px;
}
.header-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  color: #94a3b8;
  font-size: 13px;
}
.header-meta strong { color: #e2e8f0; }

/* ── Summary cards ── */
.summary-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}
.summary-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 16px 14px;
  text-align: center;
}
.summary-card.amber { border-top: 3px solid #FFB800; }
.summary-card.green { border-top: 3px solid #22c55e; }
.summary-card.blue  { border-top: 3px solid #3b82f6; }
.summary-card.purple{ border-top: 3px solid #8b5cf6; }
.summary-value {
  font-size: 26px;
  font-weight: 700;
  margin-bottom: 4px;
}
.summary-label {
  font-size: 11px;
  color: #64748b;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* ── Section ── */
.section {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 20px;
}
.section-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.section-sub {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 400;
  margin-left: auto;
}

/* ── Table ── */
.turn-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.turn-table thead th {
  text-align: left;
  padding: 8px 10px;
  background: #f8fafc;
  border-bottom: 2px solid #e2e8f0;
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.turn-table tbody tr.turn-row {
  cursor: pointer;
  border-bottom: 1px solid #f1f5f9;
  transition: background 0.12s;
}
.turn-table tbody tr.turn-row:hover { background: #fafafa; }
.turn-table tbody tr.turn-row.active { background: #fef9ec; }
.turn-table td {
  padding: 10px 10px;
  vertical-align: top;
}
.turn-num {
  font-weight: 700;
  color: #94a3b8;
  font-size: 12px;
  width: 36px;
}
.turn-ts {
  color: #94a3b8;
  font-size: 12px;
  white-space: nowrap;
  width: 70px;
}
.turn-user {
  color: #334155;
  max-width: 220px;
  word-break: break-word;
}
.turn-tools {
  color: #6366f1;
  font-size: 12px;
  font-family: 'SF Mono', 'Consolas', monospace;
  max-width: 160px;
  word-break: break-all;
}
.turn-tokens {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-size: 12px;
  color: #475569;
  width: 70px;
}
.turn-score { width: 70px; }
.turn-action { width: 80px; }

/* ── Score badge ── */
.score-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

/* ── Analyze button ── */
.btn-analyze {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid #FFB800;
  background: white;
  color: #92400e;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.btn-analyze:hover {
  background: #FFB800;
  color: white;
}
.btn-analyze:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── Analysis panel (injected below turn row) ── */
.analysis-row td {
  padding: 0;
}
.analysis-panel {
  background: #fffbeb;
  border-left: 4px solid #FFB800;
  border-top: 1px solid #fde68a;
  padding: 14px 18px;
}
.analysis-panel-header {
  font-size: 12px;
  font-weight: 700;
  color: #92400e;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.analysis-content {
  font-size: 13px;
  color: #1c1917;
  white-space: pre-wrap;
  line-height: 1.7;
}
.analysis-content strong { color: #b45309; font-weight: 700; }

/* ── Detail panel (expand/collapse) ── */
.detail-row td {
  padding: 0;
}
.detail-panel {
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
  padding: 14px 18px;
  display: none;
}
.detail-panel.open { display: block; }
.detail-section {
  margin-bottom: 12px;
}
.detail-label {
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 4px;
}
.detail-value {
  font-size: 12px;
  font-family: 'SF Mono', 'Consolas', monospace;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  padding: 8px 10px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
  color: #334155;
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.usage-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  background: #f1f5f9;
  color: #475569;
  margin: 2px;
}
.toggle-detail {
  float: right;
  font-size: 11px;
  color: #94a3b8;
  cursor: pointer;
  user-select: none;
}
.toggle-detail:hover { color: #64748b; }

/* ── Spinner ── */
@keyframes spin { to { transform: rotate(360deg); } }
.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid #fde68a;
  border-top-color: #f59e0b;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  vertical-align: middle;
}

/* ── Actionable fixes ── */
.fix-card {
  display: grid;
  grid-template-columns: 40px 1fr;
  gap: 12px;
  align-items: flex-start;
  padding: 12px 14px;
  border-radius: 8px;
  margin-bottom: 10px;
  border: 1px solid #e2e8f0;
}
.fix-layer {
  font-size: 11px;
  font-weight: 800;
  padding: 3px 6px;
  border-radius: 4px;
  text-align: center;
}
.fix-layer.L1 { background: #f1f5f9; color: #64748b; }
.fix-layer.L2 { background: #fef3c7; color: #92400e; }
.fix-layer.L3 { background: #fef2f2; color: #dc2626; }
.fix-layer.L4 { background: #f3e8ff; color: #7c3aed; }
.fix-action { font-size: 13px; font-weight: 600; color: #0f172a; margin-bottom: 4px; }
.fix-fix    { font-size: 12px; color: #059669; margin-bottom: 2px; }
.fix-saving { font-size: 11px; color: #94a3b8; }

/* ── Empty state ── */
.empty { text-align: center; color: #94a3b8; padding: 32px; font-size: 13px; }

/* ── Footer ── */
.footer {
  text-align: center;
  color: #94a3b8;
  font-size: 12px;
  margin-top: 32px;
}
"""

_JS = r"""
const SESSION_PATH = __SESSION_PATH__;
const SERVER_PORT = 57018;

// ─── Expand/collapse detail panel ──────────────────────────────────────────
function toggleDetail(turnIndex) {
  const panel = document.getElementById(`detail-${turnIndex}`);
  if (!panel) return;
  panel.classList.toggle('open');
  const btn = document.querySelector(`[data-detail="${turnIndex}"]`);
  if (btn) btn.textContent = panel.classList.contains('open') ? '▲ 收起' : '▼ 展开';
}

// ─── Per-turn LLM analysis ─────────────────────────────────────────────────
function analyzeTurn(btn, turnIndex) {
  // Prevent double-click
  if (btn.disabled) return;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 分析中…';

  // Show/create analysis panel
  let panelRow = document.getElementById(`analysis-row-${turnIndex}`);
  if (!panelRow) {
    const turnRow = document.getElementById(`turn-row-${turnIndex}`);
    panelRow = document.createElement('tr');
    panelRow.id = `analysis-row-${turnIndex}`;
    panelRow.className = 'analysis-row';
    const td = document.createElement('td');
    td.colSpan = 7;
    const panel = document.createElement('div');
    panel.className = 'analysis-panel';
    panel.id = `analysis-panel-${turnIndex}`;
    panel.innerHTML = '<div class="analysis-panel-header"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:4px"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>LLM 分析结果</div>'
                    + '<div class="analysis-content"><span class="spinner"></span> 正在调用 LLM 分析…</div>';
    td.appendChild(panel);
    panelRow.appendChild(td);
    turnRow.parentNode.insertBefore(panelRow, turnRow.nextSibling);
  } else {
    document.getElementById(`analysis-panel-${turnIndex}`).style.display = 'block';
    document.getElementById(`analysis-panel-${turnIndex}`).querySelector('.analysis-content').innerHTML
      = '<span class="spinner"></span> 正在重新分析…';
  }

  // Highlight active row
  document.querySelectorAll('.turn-row').forEach(r => r.classList.remove('active'));
  document.getElementById(`turn-row-${turnIndex}`).classList.add('active');

  // 直接打 LLM API，不需要本地 server
  const turnData = TURN_DATA[turnIndex];
  if (!turnData) {
    document.getElementById(`analysis-panel-${turnIndex}`).querySelector('.analysis-content').innerHTML
      = '<span style="color:#ef4444"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:3px"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/></svg>无法找到轮次数据</span>';
    btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:3px"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>分析'; btn.disabled = false; return;
  }

  const prompt = `你是 Claude Code Token 效率专家。分析这一轮对话，给出精确的优化建议，包括可直接使用的优化后 prompt。

## 本轮数据
- 用户输入: ${turnData.user_text || '(无)'}
- 工具调用: ${turnData.tool_calls}
- 工具返回摘要(前500字): ${turnData.tool_results_preview}
- AI 输出(前300字): ${turnData.assistant_text}
- Token: input=${turnData.input_tokens}, cache_read=${turnData.cache_read}, output=${turnData.output_tokens}
- 含屎量: ${turnData.stoi_score}% (越低越好)

## 你需要给出

**1. 浪费定位**
这轮 token 最大的浪费来自哪里？（工具返回过大？用户 prompt 太模糊？AI 输出冗余？）

**2. 优化后的 user prompt**
基于用户原始输入，给出一个 token 更少但效果相同甚至更好的版本。
格式：
\`\`\`
[优化后 prompt]
\`\`\`
改动说明：xxx（一句话）

**3. 预期收益**
节省约 XX% tokens，理由：xxx

规则：
- 如果用户输入是空或系统命令，说明无法优化
- 优化后 prompt 必须保持原意，不能改变任务目标
- 用中文回答`;

  fetch(LLM_BASE_URL + '/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + LLM_API_KEY
    },
    body: JSON.stringify({
      model: LLM_MODEL,
      messages: [{role: 'user', content: prompt}],
      max_tokens: 700
    })
  })
  .then(r => r.json())
  .then(data => {
    const el = document.getElementById(`analysis-panel-${turnIndex}`).querySelector('.analysis-content');
    if (data.error) {
      el.innerHTML = `<span style="color:#ef4444"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:3px"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/></svg>API 错误: ${escHtml(JSON.stringify(data.error))}</span>`;
    } else {
      const text = data.choices?.[0]?.message?.content || '无返回内容';
      el.innerHTML = formatAnalysis(text);
    }
    btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:3px"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></svg>重新分析'; btn.disabled = false;
  })
  .catch(err => {
    document.getElementById(`analysis-panel-${turnIndex}`).querySelector('.analysis-content').innerHTML
      = `<span style="color:#ef4444"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:3px"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/></svg>API 调用失败: ${escHtml(String(err))}</span>`;
    btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:3px"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>分析'; btn.disabled = false;
  });
}

// ─── Markdown-lite formatter for analysis output ──────────────────────────
function formatAnalysis(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code style="background:#f1f5f9;padding:1px 4px;border-radius:3px;font-family:monospace;font-size:12px">$1</code>')
    .replace(/\n/g, '<br>');
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
"""


def _build_turn_rows(turns: list[ChainTurn], session_path: Path) -> str:
    if not turns:
        return '<tr><td colspan="7" class="empty">无轮次数据</td></tr>'

    rows = []
    for t in turns:
        tool_names = ", ".join(dict.fromkeys(tc.name for tc in t.tool_calls)) or "—"
        user_preview = _truncate(t.user_text or "—", 40)
        score_badge = _score_badge(t.stoi_score)
        ts_str = _fmt_ts(t.timestamp)
        tokens_fmt = f"{t.total_input_tokens:,}"

        # ── Detail panel content ──────────────────────────────────────────
        user_full = _h(t.user_text[:1000] or "（无文本）")
        tool_calls_detail = ""
        for tc in t.tool_calls:
            try:
                inp_pretty = json.dumps(json.loads(tc.input_str), ensure_ascii=False, indent=2)
            except Exception:
                inp_pretty = tc.input_str
            tool_calls_detail += f"▸ {_h(tc.name)}\n{_h(inp_pretty[:400])}\n\n"
        tool_calls_detail = tool_calls_detail.strip() or "（无工具调用）"

        tool_results_detail = ""
        for tr in t.tool_results:
            preview = tr.content[:300]
            tool_results_detail += f"[{tr.output_tokens} tokens] {_h(preview)}\n\n"
        tool_results_detail = tool_results_detail.strip() or "（无工具返回）"

        assistant_preview = _h(t.assistant_text[:300] or "（无输出）")

        usage = t.usage
        inp_t   = usage.get("input_tokens", 0)
        cr_t    = usage.get("cache_read_input_tokens", 0)
        cw_t    = usage.get("cache_creation_input_tokens", 0)
        out_t   = usage.get("output_tokens", 0)
        usage_chips = (
            f'<span class="usage-chip">📥 input {inp_t:,}</span>'
            f'<span class="usage-chip"><svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="vertical-align:-1px;margin-right:2px"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>cache_read {cr_t:,}</span>'
            f'<span class="usage-chip">✍️ cache_write {cw_t:,}</span>'
            f'<span class="usage-chip"><svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="vertical-align:-1px;margin-right:2px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>output {out_t:,}</span>'
        )

        # context 增长标注
        growth_badge = ""
        if t.context_growth_pct > 100:
            growth_badge = f'<span style="font-size:10px;color:#ef4444;margin-left:4px">+{t.context_growth_pct:.0f}%</span>'
        elif t.context_growth_pct > 30:
            growth_badge = f'<span style="font-size:10px;color:#f97316;margin-left:4px">+{t.context_growth_pct:.0f}%</span>'
        elif t.context_growth_pct > 0:
            growth_badge = f'<span style="font-size:10px;color:#6b7280;margin-left:4px">+{t.context_growth_pct:.0f}%</span>'

        # api_call_count badge
        api_badge = f'<span style="font-size:10px;color:#8b5cf6;margin-left:4px">×{t.api_call_count}</span>' if t.api_call_count > 1 else ""

        rows.append(f"""
<tr id="turn-row-{t.turn_index}" class="turn-row">
  <td class="turn-num">#{t.turn_index + 1}</td>
  <td class="turn-ts">{ts_str}</td>
  <td class="turn-user">
    {_h(user_preview)}
    <span class="toggle-detail" data-detail="{t.turn_index}"
          onclick="event.stopPropagation();toggleDetail({t.turn_index})">▼ 展开</span>
  </td>
  <td class="turn-tools">{_h(tool_names)}{api_badge}</td>
  <td class="turn-tokens">{tokens_fmt}{growth_badge}</td>
  <td class="turn-score">{score_badge}</td>
  <td class="turn-action">
    <button class="btn-analyze"
            onclick="event.stopPropagation();analyzeTurn(this, {t.turn_index})">
      <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:3px"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>分析
    </button>
  </td>
</tr>
<tr id="detail-row-{t.turn_index}" class="detail-row">
  <td colspan="7">
    <div id="detail-{t.turn_index}" class="detail-panel">
      <div class="detail-grid">
        <div class="detail-section">
          <div class="detail-label">👤 用户输入</div>
          <div class="detail-value">{user_full}</div>
        </div>
        <div class="detail-section">
          <div class="detail-label">🤖 AI 输出</div>
          <div class="detail-value">{assistant_preview}</div>
        </div>
        <div class="detail-section">
          <div class="detail-label">🔧 工具调用</div>
          <div class="detail-value">{tool_calls_detail}</div>
        </div>
        <div class="detail-section">
          <div class="detail-label">📦 工具返回</div>
          <div class="detail-value">{tool_results_detail}</div>
        </div>
      </div>
      <div class="detail-section" style="margin-top:10px">
        <div class="detail-label"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-2px;margin-right:3px"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>Token 用量</div>
        <div>{usage_chips}</div>
      </div>
    </div>
  </td>
</tr>""")

    return "\n".join(rows)


def _build_fix_cards(analysis: ChainAnalysis) -> str:
    fixes = analysis.actionable_fixes
    if not fixes:
        return '<div class="empty"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2.5" style="vertical-align:-2px;margin-right:4px"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>未发现明显的链条级浪费</div>'

    cards = []
    for fix in fixes:
        layer = fix.get("layer", "L2")
        cards.append(f"""
<div class="fix-card">
  <div>
    <div class="fix-layer {_h(layer)}">{_h(layer)}</div>
  </div>
  <div>
    <div class="fix-action">{_h(fix.get('action', ''))}</div>
    <div class="fix-fix">→ {_h(fix.get('fix', ''))}</div>
    <div class="fix-saving">{_h(fix.get('saving', ''))}</div>
  </div>
</div>""")

    return "\n".join(cards)


def generate_dashboard(analysis: ChainAnalysis, session_path: Path) -> Path:
    """
    Generate a self-contained HTML dashboard file.

    Args:
        analysis:     ChainAnalysis produced by analyze_chain()
        session_path: Path to the .jsonl session file (used by LLM API)

    Returns:
        Path to the generated HTML file.
    """
    session_path = Path(session_path)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    stats = _compute_summary(analysis)

    avg_stoi_color  = _score_css_color(stats["avg_stoi"])
    cache_color     = "#22c55e" if stats["avg_cache_hit"] >= 70 else \
                      "#f59e0b" if stats["avg_cache_hit"] >= 40 else "#ef4444"
    tr_ratio_color  = "#ef4444" if stats["tool_result_ratio"] >= 50 else \
                      "#f97316" if stats["tool_result_ratio"] >= 30 else "#22c55e"

    opt_k = stats["optimizable_tokens"] / 1000
    opt_str = f"{opt_k:.1f}K" if opt_k >= 1 else str(stats["optimizable_tokens"])

    # ── Sections ──────────────────────────────────────────────────────────────

    sec_header = f"""
<div class="header">
  <div class="header-top">
    <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg>
    <div class="header-title">STOI Dashboard</div>
  </div>
  <div class="header-meta">
    <span><strong>{_h(analysis.session_name)}</strong></span>
    <span>{analysis.total_turns} 轮对话</span>
    <span>生成于 {_h(now_str)}</span>
    <span style="margin-left:auto;font-size:11px;opacity:.6">服务器: localhost:57018</span>
  </div>
</div>"""

    # 多轮指标
    bloat_pct = analysis.context_bloat_pct
    bloat_color = "#ef4444" if bloat_pct > 300 else "#f97316" if bloat_pct > 100 else "#22c55e"
    eff_pct = round(analysis.avg_efficiency_score * 100, 1)
    eff_color = "#22c55e" if eff_pct >= 70 else "#f59e0b" if eff_pct >= 40 else "#ef4444"

    compress_html = ""
    if analysis.compress_saving_estimate:
        ce = analysis.compress_saving_estimate
        compress_html = f"""
<div class="compress-banner">
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="vertical-align:-2px;margin-right:6px"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/></svg>
  <strong>上下文膨胀 {bloat_pct:.0f}%</strong> — 压缩 50% 历史可节省 {ce['tokens_saved']:,} tokens ({ce['pct_saved']}%)
  &nbsp;|&nbsp; <span style="color:#6b7280">{_h(ce['action'])}</span>
</div>"""

    sec_summary = f"""
{compress_html}
<div class="summary-row">
  <div class="summary-card amber">
    <div class="summary-value" style="color:{avg_stoi_color}">{stats['avg_stoi']:.1f}%</div>
    <div class="summary-label">全局含屎量</div>
  </div>
  <div class="summary-card green">
    <div class="summary-value" style="color:{cache_color}">{stats['avg_cache_hit']:.1f}%</div>
    <div class="summary-label">缓存命中</div>
  </div>
  <div class="summary-card blue">
    <div class="summary-value" style="color:{eff_color}">{eff_pct:.0f}%</div>
    <div class="summary-label">平均效率分</div>
  </div>
  <div class="summary-card purple">
    <div class="summary-value" style="color:{bloat_color}">{bloat_pct:.0f}%</div>
    <div class="summary-label">上下文膨胀</div>
  </div>
</div>"""

    turn_rows = _build_turn_rows(analysis.turns, session_path)
    sec_turns = f"""
<div class="section">
  <div class="section-title">
    🔁 逐轮分析
    <span class="section-sub">{analysis.total_turns} 轮 · 点击 <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:3px"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>分析 获取 LLM 分析</span>
  </div>
  <table class="turn-table">
    <thead>
      <tr>
        <th>#</th>
        <th>时间</th>
        <th>用户消息</th>
        <th>工具调用</th>
        <th style="text-align:right">Input Tokens</th>
        <th>含屎量</th>
        <th>操作</th>
      </tr>
    </thead>
    <tbody>
      {turn_rows}
    </tbody>
  </table>
</div>"""

    fix_cards = _build_fix_cards(analysis)
    sec_fixes = f"""
<div class="section">
  <div class="section-title">
    🛠️ 可操作建议
    <span class="section-sub">按影响优先级排序</span>
  </div>
  {fix_cards}
</div>"""

    sec_footer = """
<div class="footer">
  Generated by <strong>STOI Dashboard</strong> v1.0 — Shit Token On Investment
</div>"""

    # ── 读取 LLM 配置 ──────────────────────────────────────────────────────
    try:
        from .stoi_config import load_config
        cfg = load_config()
        llm_cfg  = cfg.get("llm", {})
        api_key  = llm_cfg.get("api_key", "")
        base_url = llm_cfg.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        model    = llm_cfg.get("model", "qwen-turbo")
        # 确保 base_url 以 /v1 结尾
        if base_url and not base_url.rstrip("/").endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"
    except Exception:
        api_key, base_url, model = "", "https://api.openai.com/v1", "gpt-4o-mini"

    # ── 构建每轮的数据（注入到 JS）──────────────────────────────────────────
    turn_data = {}
    for t in analysis.turns:
        tool_calls_str = "; ".join(
            f"{tc.name}({tc.input_str[:80]})" for tc in t.tool_calls
        ) or "（无工具调用）"
        tool_results_preview = "\n---\n".join(
            tr.content[:200] for tr in t.tool_results
        )[:500] or "（无工具返回）"
        turn_data[t.turn_index] = {
            "user_text":          t.user_text[:200],
            "tool_calls":         tool_calls_str[:300],
            "tool_results_preview": tool_results_preview,
            "assistant_text":     t.assistant_text[:300],
            "input_tokens":       t.total_input_tokens,
            "cache_read":         t.cache_read_tokens,
            "output_tokens":      t.usage.get("output_tokens", 0),
            "stoi_score":         t.stoi_score,
        }

    # ── JS (inject all config) ─────────────────────────────────────────────
    session_path_json = json.dumps(str(session_path))
    js_code = _JS.replace("__SESSION_PATH__", session_path_json)
    js_config = f"""
const LLM_API_KEY  = {json.dumps(api_key)};
const LLM_BASE_URL = {json.dumps(base_url.rstrip('/'))};
const LLM_MODEL    = {json.dumps(model)};
const TURN_DATA    = {json.dumps(turn_data)};
"""
    js_code = js_config + js_code

    # ── Full HTML ──────────────────────────────────────────────────────────
    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>STOI Dashboard — {_h(analysis.session_name)}</title>
<link rel="stylesheet" href="https://unpkg.com/lucide-static@latest/font/lucide.css">
<style>
{_CSS}
</style>
</head>
<body>
<div class="wrapper">
{sec_header}
{sec_summary}
{sec_turns}
{sec_fixes}
{sec_footer}
</div>
<script>
{js_code}
</script>
</body>
</html>"""

    out_dir = Path("~/.stoi").expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", analysis.session_name)[:40]
    ts_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = out_dir / f"stoi_dashboard_{safe_name}_{ts_suffix}.html"
    html_path.write_text(html_doc, encoding="utf-8")

    return html_path


# ─── LLM call ────────────────────────────────────────────────────────────────

def _call_llm_for_turn(turn_data: dict) -> str:
    """Call configured LLM to analyze a single turn."""
    from .stoi_config import load_config, PROVIDER_MODELS

    cfg      = load_config()
    llm_cfg  = cfg.get("llm", {})
    provider = llm_cfg.get("provider", "")
    model    = llm_cfg.get("model", "")
    api_key  = llm_cfg.get("api_key", "")
    base_url = llm_cfg.get("base_url", "")

    # Fall back to env vars if config is incomplete
    if not api_key:
        if provider == "anthropic" or not provider:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if api_key and not provider:
                provider = "anthropic"
        elif provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY", "")
        elif provider == "qwen":
            api_key = os.environ.get("DASHSCOPE_API_KEY", "")
        elif provider == "deepseek":
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")

    if not api_key:
        return "未配置 LLM API Key。请运行 stoi config 进行配置。"

    # Build prompt
    user_text    = turn_data.get("user_text", "")[:500]
    tool_names   = turn_data.get("tool_names", "")
    tool_inputs  = turn_data.get("tool_inputs", "")[:600]
    tool_results = turn_data.get("tool_results", "")[:800]
    asst_preview = turn_data.get("assistant_text", "")[:400]
    inp_t  = turn_data.get("input_tokens", 0)
    cr_t   = turn_data.get("cache_read_tokens", 0)
    out_t  = turn_data.get("output_tokens", 0)
    score  = turn_data.get("stoi_score", 0)

    prompt = f"""分析这一轮 Claude Code 对话的 Token 效率问题。

轮次信息：
- 用户输入: {user_text}
- 工具调用: {tool_names}
- 工具调用参数: {tool_inputs}
- 工具返回（前800字）: {tool_results}
- AI 输出（前400字）: {asst_preview}
- Token 用量: input={inp_t:,}, cache_read={cr_t:,}, output={out_t:,}
- 含屎量: {score:.1f}%

请给出：
1. 这轮最大的 token 浪费在哪里（具体定位，不是泛泛而谈）
2. 一条可立即执行的优化操作（CLAUDE.md 配置或 prompt 改法）
3. 预计节省量

格式：
**[浪费点]** 描述
**操作**: 具体配置
**收益**: 量化"""

    # ── Try Anthropic ──────────────────────────────────────────────────────
    if provider == "anthropic" or not provider:
        if not base_url:
            base_url = "https://api.anthropic.com"
        if not model:
            model = "claude-haiku-3-5"

        import urllib.request
        req_body = json.dumps({
            "model": model,
            "max_tokens": 512,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            f"{base_url}/v1/messages",
            data=req_body,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("x-api-key", api_key)
        req.add_header("anthropic-version", "2023-06-01")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        return result["content"][0]["text"]

    # ── Try OpenAI-compatible (openai / qwen / deepseek / custom) ─────────
    if not base_url:
        pinfo = PROVIDER_MODELS.get(provider, {})
        base_url = pinfo.get("base_url", "https://api.openai.com/v1")
    if not model:
        pinfo = PROVIDER_MODELS.get(provider, {})
        model = pinfo.get("default", "gpt-4o-mini")

    import urllib.request
    req_body = json.dumps({
        "model": model,
        "max_tokens": 512,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=req_body,
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    return result["choices"][0]["message"]["content"]


def _load_turn_data(session_path: Path, turn_index: int) -> dict:
    """Re-parse the session file to extract data for a specific turn index."""
    from .stoi_chain import parse_chain
    turns = parse_chain(session_path, max_turns=200)
    for t in turns:
        if t.turn_index == turn_index:
            tool_names = ", ".join(dict.fromkeys(tc.name for tc in t.tool_calls)) or "none"
            tool_inputs = "\n".join(
                f"[{tc.name}] {tc.input_str[:200]}" for tc in t.tool_calls
            ) or "none"
            tool_results = "\n".join(
                f"[{tr.output_tokens}tok] {tr.content[:300]}" for tr in t.tool_results
            ) or "none"
            return {
                "user_text":       t.user_text,
                "tool_names":      tool_names,
                "tool_inputs":     tool_inputs,
                "tool_results":    tool_results,
                "assistant_text":  t.assistant_text,
                "input_tokens":    t.total_input_tokens,
                "cache_read_tokens": t.cache_read_tokens,
                "output_tokens":   t.usage.get("output_tokens", 0),
                "stoi_score":      t.stoi_score,
            }
    return {}


# ─── HTTP Server ─────────────────────────────────────────────────────────────

_SERVER_PORT = 57018


class _DashboardHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler: serves the dashboard HTML and the LLM analysis API."""

    def log_message(self, fmt, *args):
        # Suppress noisy access log; print errors only
        pass

    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._send_cors()
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "service": "stoi-dashboard"}).encode())

    def do_POST(self):
        if self.path != "/api/analyze-turn":
            self.send_response(404)
            self.end_headers()
            return

        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)
        try:
            req_data = json.loads(body)
        except Exception:
            self._json_error("invalid JSON body", 400)
            return

        turn_index   = req_data.get("turn_index")
        session_path = req_data.get("session_path")

        if turn_index is None or not session_path:
            self._json_error("missing turn_index or session_path", 400)
            return

        sp = Path(session_path)
        if not sp.exists():
            self._json_error(f"session file not found: {session_path}", 404)
            return

        try:
            turn_data = _load_turn_data(sp, int(turn_index))
            if not turn_data:
                self._json_response({"error": f"turn #{turn_index} not found in session"})
                return
            analysis_text = _call_llm_for_turn(turn_data)
            self._json_response({"analysis": analysis_text})
        except Exception as exc:
            self._json_response({"error": f"{type(exc).__name__}: {exc}"})

    def _json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors()
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, msg: str, status: int = 400):
        self._json_response({"error": msg}, status)


def serve_dashboard(html_path: Path, open_browser: bool = True) -> None:
    """
    Start the local HTTP server for LLM analysis API, then block.

    Args:
        html_path:    Path to the generated dashboard HTML file.
        open_browser: If True, auto-open the HTML file in the default browser.
    """
    html_path = Path(html_path)

    server = HTTPServer(("localhost", _SERVER_PORT), _DashboardHandler)

    if open_browser:
        # Open browser after a short delay to let server bind
        def _open():
            import time
            time.sleep(0.4)
            try:
                import subprocess
                subprocess.Popen(["open", str(html_path)])
            except Exception:
                webbrowser.open(html_path.as_uri())
        threading.Thread(target=_open, daemon=True).start()

    from rich.console import Console
    c = Console(highlight=False)
    c.print(f"\n  [bold #FFB800]STOI Dashboard[/bold #FFB800]")
    c.print(f"  [dim]HTML:[/dim] [white]{html_path}[/white]")
    c.print(f"  [dim]API :[/dim] [white]http://localhost:{_SERVER_PORT}/api/analyze-turn[/white]")
    c.print(f"  [dim]Ctrl+C 停止服务器[/dim]\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        c.print("\n  [dim]Dashboard 服务器已停止[/dim]")
        server.server_close()


# ─── Convenience wrapper ─────────────────────────────────────────────────────

def generate_and_serve_dashboard(session_path: Optional[Path] = None) -> None:
    """
    Find (or use provided) session, generate dashboard HTML, and start server.
    Called by REPL /dashboard and CLI `stoi dashboard`.
    """
    from rich.console import Console
    c = Console(highlight=False)

    if session_path is None:
        from .stoi_core import find_claude_sessions
        files = find_claude_sessions(1)
        if not files:
            c.print("  [yellow]未找到 Claude Code session[/yellow]")
            return
        session_path = files[0]

    session_path = Path(session_path)
    c.print(f"\n  [dim]解析 session: {session_path.name}…[/dim]")

    from .stoi_chain import parse_chain, analyze_chain
    with c.status("[dim]分析链条…[/dim]", spinner="dots"):
        turns    = parse_chain(session_path, max_turns=100)
        analysis = analyze_chain(turns, session_path.parent.name[:20] + "/" + session_path.stem[:16])

    if not turns:
        c.print("  [yellow]session 无可解析的轮次数据[/yellow]")
        return

    c.print(f"  [dim]生成 Dashboard HTML…[/dim]")
    html_path = generate_dashboard(analysis, session_path)
    c.print(f"  [green]✅ HTML 已生成:[/green] {html_path}")

    serve_dashboard(html_path, open_browser=True)


# ─── CLI smoke test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    generate_and_serve_dashboard()
