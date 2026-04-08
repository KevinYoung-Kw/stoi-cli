#!/usr/bin/env python3
"""
STOI Web GUI - Apple Design Style
简约、现代、优雅的苹果风格界面
"""

import sys
import socket
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import json
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

from config import ConfigManager, get_openai_client
from importers import get_importer
from importers.claude import ClaudeImporter
from stoi import STOIDatabase, STOIAnalyzer, LLMJudge, Speaker

app = Flask(__name__)
app.config["TRUSTED_HOSTS"] = ["127.0.0.1", "localhost", "::1", "[::1]"]

# 苹果风格 HTML 模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STOI - Token Efficiency</title>
    <style>
        :root {
            --bg-primary: #f5f5f7;
            --bg-secondary: #ffffff;
            --bg-tertiary: rgba(255, 255, 255, 0.72);
            --text-primary: #1d1d1f;
            --text-secondary: #86868b;
            --text-tertiary: #a1a1a6;
            --accent-blue: #0071e3;
            --accent-green: #34c759;
            --accent-orange: #ff9500;
            --accent-red: #ff3b30;
            --accent-purple: #af52de;
            --border: rgba(0, 0, 0, 0.08);
            --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.04);
            --shadow-md: 0 4px 24px rgba(0, 0, 0, 0.08);
            --shadow-lg: 0 12px 48px rgba(0, 0, 0, 0.12);
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 18px;
            --radius-xl: 24px;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }

        /* Header */
        .header {
            background: rgba(255, 255, 255, 0.72);
            backdrop-filter: saturate(180%) blur(20px);
            -webkit-backdrop-filter: saturate(180%) blur(20px);
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header-content {
            max-width: 1200px;
            margin: 0 auto;
            padding: 16px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-icon {
            font-size: 28px;
        }

        .logo-text {
            font-size: 21px;
            font-weight: 600;
            letter-spacing: -0.02em;
        }

        .logo-subtitle {
            font-size: 12px;
            color: var(--text-secondary);
            font-weight: 400;
        }

        /* Main Layout */
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 32px 24px;
        }

        .main-grid {
            display: grid;
            grid-template-columns: 360px 1fr;
            gap: 24px;
        }

        /* Card Style */
        .card {
            background: var(--bg-secondary);
            border-radius: var(--radius-xl);
            box-shadow: var(--shadow-md);
            border: 1px solid var(--border);
            overflow: hidden;
        }

        .card-header {
            padding: 20px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .card-title {
            font-size: 17px;
            font-weight: 600;
            color: var(--text-primary);
        }

        .card-content {
            padding: 20px 24px;
        }

        /* Session List */
        .session-list {
            max-height: 600px;
            overflow-y: auto;
        }

        .session-item {
            padding: 16px;
            border-radius: var(--radius-md);
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            border: 1px solid transparent;
        }

        .session-item:hover {
            background: rgba(0, 113, 227, 0.04);
        }

        .session-item.selected {
            background: rgba(0, 113, 227, 0.08);
            border-color: rgba(0, 113, 227, 0.2);
        }

        .session-id {
            font-family: 'SF Mono', monospace;
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }

        .session-meta {
            display: flex;
            gap: 12px;
            font-size: 13px;
            color: var(--text-tertiary);
        }

        .session-badge {
            background: rgba(0, 0, 0, 0.04);
            padding: 2px 8px;
            border-radius: 100px;
            font-size: 12px;
            font-weight: 500;
        }

        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 80px 40px;
            color: var(--text-secondary);
        }

        .empty-icon {
            font-size: 48px;
            margin-bottom: 16px;
            opacity: 0.4;
        }

        .empty-title {
            font-size: 17px;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--text-primary);
        }

        .empty-text {
            font-size: 14px;
        }

        /* Result Section */
        .result-header {
            display: flex;
            gap: 16px;
            margin-bottom: 32px;
        }

        .grade-card {
            width: 140px;
            height: 140px;
            border-radius: var(--radius-lg);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            box-shadow: var(--shadow-sm);
        }

        .grade-s { background: linear-gradient(135deg, #0071e3 0%, #42a5f5 100%); }
        .grade-a { background: linear-gradient(135deg, #34c759 0%, #66bb6a 100%); }
        .grade-b { background: linear-gradient(135deg, #ff9500 0%, #ffb74d 100%); }
        .grade-c { background: linear-gradient(135deg, #ff3b30 0%, #ef5350 100%); }
        .grade-d { background: linear-gradient(135deg, #af52de 0%, #ba68c8 100%); }
        .grade-f { background: linear-gradient(135deg, #5856d6 0%, #7c4dff 100%); }

        .grade-letter {
            font-size: 56px;
            line-height: 1;
            margin-bottom: 4px;
        }

        .grade-label {
            font-size: 13px;
            opacity: 0.9;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .stats-row {
            flex: 1;
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }

        .stat-box {
            background: rgba(0, 0, 0, 0.02);
            border-radius: var(--radius-md);
            padding: 20px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        .stat-value {
            font-size: 32px;
            font-weight: 600;
            color: var(--text-primary);
            letter-spacing: -0.02em;
        }

        .stat-value.positive { color: var(--accent-green); }
        .stat-value.negative { color: var(--accent-red); }

        .stat-label {
            font-size: 13px;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        /* Dimensions */
        .dimensions-title {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 16px;
        }

        .dimension-item {
            margin-bottom: 16px;
        }

        .dimension-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }

        .dimension-name {
            font-size: 14px;
            color: var(--text-primary);
        }

        .dimension-score {
            font-size: 14px;
            font-weight: 600;
            color: var(--text-secondary);
        }

        .progress-bar {
            height: 6px;
            background: rgba(0, 0, 0, 0.04);
            border-radius: 100px;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            border-radius: 100px;
            transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .progress-fill.excellent { background: var(--accent-blue); }
        .progress-fill.good { background: var(--accent-green); }
        .progress-fill.warning { background: var(--accent-orange); }
        .progress-fill.poor { background: var(--accent-red); }

        /* Quote Block */
        .quote-block {
            background: rgba(0, 0, 0, 0.02);
            border-radius: var(--radius-md);
            padding: 20px 24px;
            margin-top: 24px;
            border-left: 3px solid var(--accent-blue);
        }

        .quote-text {
            font-size: 15px;
            line-height: 1.6;
            color: var(--text-primary);
            font-style: italic;
        }

        .quote-author {
            font-size: 13px;
            color: var(--text-secondary);
            margin-top: 12px;
        }

        /* Buttons */
        .button-group {
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
        }

        .btn {
            padding: 12px 24px;
            border-radius: var(--radius-sm);
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            border: none;
            outline: none;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        .btn-primary {
            background: var(--accent-blue);
            color: white;
        }

        .btn-primary:hover {
            background: #0077ed;
            transform: translateY(-1px);
            box-shadow: var(--shadow-sm);
        }

        .btn-secondary {
            background: rgba(0, 0, 0, 0.04);
            color: var(--text-primary);
        }

        .btn-secondary:hover {
            background: rgba(0, 0, 0, 0.08);
        }

        /* Loading */
        .loading-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 80px 40px;
            color: var(--text-secondary);
        }

        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid rgba(0, 113, 227, 0.1);
            border-top-color: var(--accent-blue);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-bottom: 16px;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* Error */
        .error-state {
            background: rgba(255, 59, 48, 0.04);
            border: 1px solid rgba(255, 59, 48, 0.1);
            border-radius: var(--radius-md);
            padding: 20px 24px;
            color: var(--accent-red);
            font-size: 14px;
        }

        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
        }

        ::-webkit-scrollbar-track {
            background: transparent;
        }

        ::-webkit-scrollbar-thumb {
            background: rgba(0, 0, 0, 0.15);
            border-radius: 100px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: rgba(0, 0, 0, 0.25);
        }

        /* Responsive */
        @media (max-width: 900px) {
            .main-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <div class="logo">
                <span class="logo-icon">💩</span>
                <div>
                    <div class="logo-text">STOI</div>
                    <div class="logo-subtitle">Shit Token On Investment</div>
                </div>
            </div>
        </div>
    </header>

    <main class="container">
        <div class="main-grid">
            <!-- Session List -->
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">Sessions</h2>
                    <button class="btn btn-secondary" onclick="loadSessions()">Refresh</button>
                </div>
                <div class="card-content">
                    <div class="session-list" id="sessionList">
                        <div class="loading-state">
                            <div class="spinner"></div>
                            <span>Loading sessions...</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Analysis Result -->
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">Analysis</h2>
                    <div class="button-group" style="margin: 0;">
                        <button class="btn btn-primary" onclick="analyze(false)">Analyze</button>
                        <button class="btn btn-secondary" onclick="analyze(true)">Analyze + Speak</button>
                    </div>
                </div>
                <div class="card-content">
                    <div id="resultArea">
                        <div class="empty-state">
                            <div class="empty-icon">📊</div>
                            <div class="empty-title">Select a session</div>
                            <div class="empty-text">Choose a conversation from the list to analyze its token efficiency.</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <script>
        let selectedSession = null;
        let sessions = [];

        async function loadSessions() {
            const listDiv = document.getElementById('sessionList');
            listDiv.innerHTML = `
                <div class="loading-state">
                    <div class="spinner"></div>
                    <span>Loading...</span>
                </div>
            `;

            try {
                const res = await fetch('/api/sessions');
                sessions = await res.json();

                if (sessions.length === 0) {
                    listDiv.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-icon">📭</div>
                            <div class="empty-title">No sessions</div>
                            <div class="empty-text">No conversation history found.</div>
                        </div>
                    `;
                    return;
                }

                listDiv.innerHTML = sessions.map((s, i) => `
                    <div class="session-item" onclick="selectSession(${i})" data-index="${i}">
                        <div class="session-id">${s.id.substring(0, 20)}...</div>
                        <div class="session-meta">
                            <span>${s.time}</span>
                            <span class="session-badge">${s.messages} msgs</span>
                        </div>
                    </div>
                `).join('');
            } catch (e) {
                listDiv.innerHTML = `
                    <div class="error-state">
                        Failed to load: ${e.message}
                    </div>
                `;
            }
        }

        function selectSession(index) {
            selectedSession = sessions[index];
            document.querySelectorAll('.session-item').forEach(el => {
                el.classList.remove('selected');
            });
            document.querySelector(`[data-index="${index}"]`).classList.add('selected');
        }

        async function analyze(dramatic) {
            if (!selectedSession) {
                document.getElementById('resultArea').innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">👆</div>
                        <div class="empty-title">No session selected</div>
                        <div class="empty-text">Please select a session from the list first.</div>
                    </div>
                `;
                return;
            }

            const resultDiv = document.getElementById('resultArea');
            resultDiv.innerHTML = `
                <div class="loading-state">
                    <div class="spinner"></div>
                    <span>Analyzing...</span>
                </div>
            `;

            try {
                const res = await fetch(`/api/analyze/${selectedSession.id}?dramatic=${dramatic}`);
                const data = await res.json();

                if (data.error) {
                    resultDiv.innerHTML = `<div class="error-state">${data.error}</div>`;
                    return;
                }

                displayResult(data);
            } catch (e) {
                resultDiv.innerHTML = `<div class="error-state">Analysis failed: ${e.message}</div>`;
            }
        }

        function displayResult(data) {
            const gradeColors = {
                'S': 'grade-s', 'A': 'grade-a', 'B': 'grade-b',
                'C': 'grade-c', 'D': 'grade-d', 'F': 'grade-f'
            };

            const scoreLevel = (score) => {
                if (score >= 4) return 'excellent';
                if (score >= 3) return 'good';
                if (score >= 2) return 'warning';
                return 'poor';
            };

            document.getElementById('resultArea').innerHTML = `
                <div class="result-header">
                    <div class="grade-card ${gradeColors[data.grade] || 'grade-b'}">
                        <div class="grade-letter">${data.grade}</div>
                        <div class="grade-label">Grade</div>
                    </div>
                    <div class="stats-row">
                        <div class="stat-box">
                            <div class="stat-value">${data.stoi_index.toFixed(0)}</div>
                            <div class="stat-label">Purity Score / 100</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value ${data.waste_ratio > 0.5 ? 'negative' : 'positive'}">
                                ${(data.waste_ratio * 100).toFixed(1)}%
                            </div>
                            <div class="stat-label">Waste Ratio</div>
                        </div>
                    </div>
                </div>

                <div class="dimensions-title">Dimensions</div>
                ${renderDimension('Problem Solving', data.problem_solving, scoreLevel(data.problem_solving))}
                ${renderDimension('Code Quality', data.code_quality, scoreLevel(data.code_quality))}
                ${renderDimension('Information Density', data.information_density, scoreLevel(data.information_density))}
                ${renderDimension('Context Efficiency', data.context_efficiency, scoreLevel(data.context_efficiency))}

                <div class="quote-block">
                    <div class="quote-text">"${data.summary}"</div>
                    <div class="quote-author">— AI Evaluation</div>
                </div>

                <div class="quote-block" style="border-left-color: ${data.waste_ratio > 0.5 ? 'var(--accent-red)' : 'var(--accent-green)'};">
                    <div class="quote-text">${data.advice}</div>
                    <div class="quote-author">— Recommendation</div>
                </div>
            `;
        }

        function renderDimension(name, score, level) {
            return `
                <div class="dimension-item">
                    <div class="dimension-header">
                        <span class="dimension-name">${name}</span>
                        <span class="dimension-score">${score}/5</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill ${level}" style="width: ${(score/5)*100}%"></div>
                    </div>
                </div>
            `;
        }

        loadSessions();
    </script>
</body>
</html>
"""


def get_advice(waste_ratio: float) -> str:
    if waste_ratio < 0.2:
        return "Excellent work! Your code is clean and efficient. Keep it up!"
    elif waste_ratio < 0.4:
        return "Good job! There's some room for improvement, but overall solid."
    elif waste_ratio < 0.6:
        return "Getting bloated. Consider removing unnecessary verbosity."
    elif waste_ratio < 0.8:
        return "High waste detected. Significant optimization needed."
    else:
        return "Critical waste levels! Immediate refactoring recommended."


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/sessions')
def api_sessions():
    try:
        importer = ClaudeImporter()
        conversations = importer.get_conversations(limit=20)
        result = []
        for conv in conversations:
            time_str = conv.updated_at.strftime("%b %d, %H:%M") if conv.updated_at else "N/A"
            result.append({
                'id': conv.id,
                'time': time_str,
                'messages': conv.message_count,
                'project': Path(conv.title).name if conv.title else "Unknown"
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze/<session_id>')
def api_analyze(session_id: str):
    dramatic = request.args.get('dramatic', 'false').lower() == 'true'

    try:
        db = STOIDatabase()
        importer = ClaudeImporter()
        importer.import_to_stoi(session_id, db)

        client, model = get_openai_client()
        judge = LLMJudge(client, model)
        speaker = Speaker()
        analyzer = STOIAnalyzer(db, judge, speaker, use_rich=False)

        analyzer.analyze_session(session_id, dramatic=dramatic, dashboard=False)

        session = db.get_session(session_id)
        if session and session.messages:
            user_query = ""
            assistant_output = ""
            for msg in reversed(session.messages):
                if msg["role"] == "assistant" and not assistant_output:
                    assistant_output = msg["content"]
                elif msg["role"] == "user" and not user_query:
                    user_query = msg["content"]

            evaluation = judge.evaluate(user_query, assistant_output)

            if dramatic:
                speaker.speak(f"Analysis complete! Grade {evaluation.grade}")

            return jsonify({
                'grade': evaluation.grade,
                'stoi_index': evaluation.stoi_index,
                'waste_ratio': evaluation.waste_ratio,
                'problem_solving': evaluation.problem_solving,
                'code_quality': evaluation.code_quality,
                'information_density': evaluation.information_density,
                'context_efficiency': evaluation.context_efficiency,
                'summary': evaluation.summary,
                'advice': get_advice(evaluation.waste_ratio)
            })

        return jsonify({'error': 'No messages found'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _pick_gui_port(host: str, preferred_port: int | None = None) -> int:
    candidates = []
    if preferred_port is not None:
        candidates.append(preferred_port)

    # 5000 在 macOS 上常被系统服务占用，默认避开它。
    candidates.extend([8765, 5001, 5050, 8080])

    for port in candidates:
        if _is_port_available(host, port):
            return port

    raise RuntimeError("找不到可用的本地端口，请使用 --port 指定")


def main(port: int | None = None):
    host = "127.0.0.1"
    actual_port = _pick_gui_port(host, port)
    print("🌐 Starting STOI Web GUI (Apple Design)...")
    print(f"Open: http://{host}:{actual_port}")
    app.run(host=host, port=actual_port, debug=False)


if __name__ == '__main__':
    main()
