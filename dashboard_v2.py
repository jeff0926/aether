#!/usr/bin/env python3
"""
AETHER Dashboard - Operational Diagnostics, KG Explorer, AEC Lab, Orchestrator
Single-file dashboard using Python stdlib only.
Run: python dashboard.py [--port 8864]
"""

import json
import subprocess
import sys
import os
import argparse
import webbrowser
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# Add project root to path for imports
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from aether import Capsule, validate_folder, get_required_files
from kg import load_kg, get_nodes, stats as kg_stats
from aec import verify as aec_verify
from education import get_queue, queue_stats

EXAMPLES_DIR = ROOT / "examples"

# Capsule categories for inventory display
CAPSULE_CATEGORIES = {
    "Aether Core": ["aether-alpha", "aether_alpha"],
    "Scholars": ["jefferson", "scholar-buffett", "algorithmic-art"],
    "Validators": ["aether-validator"],
    "Domain Experts": ["brand-guidelines", "domain-sap-cap", "frontend-design", "doc-coauthoring"],
    "Anthropic Skills": ["claude-api", "mcp-builder", "skill-creator", "xlsx", "pptx", "slack-gif", "canvas-design"],
    "Executive Roles": ["ceo-engine", "cto-engine", "cpo-product", "cfo-capital", "clo-governance", "ciso-resilience", "agent-owner", "lead-dev"],
    "Infrastructure": ["domain-agent-builder", "orchestrator", "test-agent"],
}

def get_capsule_category(folder_name):
    """Determine category for a capsule based on folder name."""
    folder_lower = folder_name.lower()
    for category, prefixes in CAPSULE_CATEGORIES.items():
        for prefix in prefixes:
            if prefix in folder_lower:
                return category
    return "Other"

# =============================================================================
# HTML TEMPLATE
# =============================================================================

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AETHER Dashboard</title>
<script src="https://unpkg.com/vis-network/dist/vis-network.min.js"></script>
<style>
:root {
  --bg-dark: #0d1117;
  --bg-panel: #161b22;
  --bg-card: #1c2128;
  --border: #30363d;
  --text: #c9d1d9;
  --text-dim: #8b949e;
  --accent: #58a6ff;
  --green: #3fb950;
  --orange: #d29922;
  --red: #f85149;
  --purple: #a371f7;
  --cyan: #56d4dd;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: "Cascadia Code", "Fira Code", "JetBrains Mono", monospace;
  background: var(--bg-dark);
  color: var(--text);
  font-size: 12px;
  line-height: 1.5;
}
.header {
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border);
  padding: 12px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header h1 {
  font-size: 16px;
  font-weight: 600;
  color: var(--accent);
  letter-spacing: 2px;
}
.header .subtitle {
  font-size: 10px;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-top: 2px;
}
.header-stats {
  display: flex;
  gap: 20px;
  font-size: 10px;
  text-transform: uppercase;
}
.header-stats .stat {
  display: flex;
  align-items: center;
  gap: 6px;
}
.header-stats .stat-value {
  font-weight: 700;
  color: var(--cyan);
  font-size: 14px;
}
.container {
  display: flex;
  height: calc(100vh - 60px);
}
.sidebar {
  width: 220px;
  background: var(--bg-panel);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  padding: 12px;
}
.sidebar-title {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-dim);
  margin-bottom: 10px;
  padding-left: 4px;
}
.capsule-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: border-color 0.15s;
}
.capsule-card:hover { border-color: var(--accent); }
.capsule-card.selected { border-color: var(--accent); background: rgba(88,166,255,0.1); }
.capsule-card .name { font-weight: 600; font-size: 11px; margin-bottom: 4px; }
.capsule-card .version { font-size: 9px; color: var(--text-dim); }
.capsule-card .stats {
  display: flex;
  gap: 12px;
  margin-top: 8px;
  font-size: 9px;
  color: var(--text-dim);
}
.capsule-card .stats span { display: flex; align-items: center; gap: 3px; }
.capsule-card .stats .num { color: var(--cyan); font-weight: 700; }
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.tabs {
  display: flex;
  flex-wrap: wrap;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border);
}
.tab {
  padding: 10px 20px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-dim);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
}
.tab:hover { color: var(--text); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.panel { display: none; }
.panel.active { display: block; }
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 16px;
}
.card-title {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-dim);
  margin-bottom: 12px;
}
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
}
.badge-green { background: rgba(63,185,80,0.2); color: var(--green); }
.badge-red { background: rgba(248,81,73,0.2); color: var(--red); }
.badge-orange { background: rgba(210,153,34,0.2); color: var(--orange); }
.badge-blue { background: rgba(88,166,255,0.2); color: var(--accent); }
.badge-purple { background: rgba(163,113,247,0.2); color: var(--purple); }
.badge-cyan { background: rgba(86,212,221,0.2); color: var(--cyan); }
.origin-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}
.origin-core { background: var(--accent); }
.origin-acquired { background: var(--green); }
.origin-updated { background: var(--orange); }
.origin-deprecated { background: var(--red); }
.origin-provenance { background: var(--purple); }
.btn {
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-card);
  color: var(--text);
  cursor: pointer;
  font-family: inherit;
  font-size: 11px;
  transition: all 0.15s;
}
.btn:hover { border-color: var(--accent); color: var(--accent); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: var(--accent); border-color: var(--accent); color: var(--bg-dark); }
.btn-primary:hover { background: #79b8ff; }
.btn-green { background: var(--green); border-color: var(--green); color: var(--bg-dark); }
.btn-green:hover { background: #56d364; }
input, textarea, select {
  background: var(--bg-dark);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text);
  font-family: inherit;
  font-size: 11px;
  padding: 8px 12px;
}
textarea { resize: vertical; width: 100%; min-height: 120px; }
select { cursor: pointer; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); font-size: 11px; }
th { font-size: 9px; text-transform: uppercase; letter-spacing: 1px; color: var(--text-dim); }
.text-dim { color: var(--text-dim); }
.text-green { color: var(--green); }
.text-red { color: var(--red); }
.text-orange { color: var(--orange); }
.text-accent { color: var(--accent); }
.text-purple { color: var(--purple); }
.text-cyan { color: var(--cyan); }
.flex { display: flex; }
.flex-between { justify-content: space-between; }
.flex-center { align-items: center; }
.gap-8 { gap: 8px; }
.gap-16 { gap: 16px; }
.mb-8 { margin-bottom: 8px; }
.mb-16 { margin-bottom: 16px; }
.mt-16 { margin-top: 16px; }

/* KG Explorer */
.kg-layout { display: flex; gap: 16px; height: calc(100vh - 180px); }
.kg-graph { flex-grow: 1; background: #0d1117; border: 1px solid var(--border); border-radius: 6px; position: relative; }
#kg-network { width: 100%; height: 100%; }
.kg-detail { width: 280px; flex-shrink: 0; display: flex; flex-direction: column; gap: 12px; }
.kg-legend { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 12px; font-size: 10px; }
.kg-legend-item { display: flex; align-items: center; gap: 4px; }
.kg-search { position: absolute; top: 10px; left: 10px; z-index: 10; }
.kg-search input { width: 180px; background: var(--bg-panel); border: 1px solid var(--border); border-radius: 4px; padding: 8px 12px; color: var(--text); font-size: 11px; }
.kg-search input::placeholder { color: var(--text-dim); }
.node-list { flex: 1; overflow-y: auto; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; padding: 8px; }
.node-list-item { padding: 6px 8px; cursor: pointer; border-radius: 4px; font-size: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.node-list-item:hover { background: rgba(88,166,255,0.1); }
.node-list-item.selected { background: rgba(88,166,255,0.2); }

/* AEC Lab */
.aec-result { margin-top: 16px; }
.score-bar { height: 24px; background: var(--bg-dark); border-radius: 4px; position: relative; overflow: hidden; margin-bottom: 8px; }
.score-fill { height: 100%; transition: width 0.3s; }
.score-threshold { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--text-dim); }
.statement-row { padding: 8px 12px; border-left: 3px solid; margin-bottom: 4px; background: var(--bg-dark); border-radius: 0 4px 4px 0; font-size: 11px; display: flex; justify-content: space-between; align-items: center; }
.statement-grounded { border-color: var(--green); }
.statement-ungrounded { border-color: var(--red); }
.statement-persona { border-color: var(--purple); }
.statement-method { font-size: 9px; padding: 2px 6px; border-radius: 3px; background: var(--bg-panel); color: var(--text-dim); white-space: nowrap; margin-left: 8px; }

/* Force Test */
.test-summary { display: flex; gap: 16px; margin-bottom: 20px; }
.test-stat { background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; padding: 16px 24px; text-align: center; }
.test-stat .value { font-size: 28px; font-weight: 700; }
.test-stat .label { font-size: 9px; text-transform: uppercase; color: var(--text-dim); margin-top: 4px; }
.spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Queue */
.queue-item { background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; padding: 12px; margin-bottom: 8px; cursor: pointer; }
.queue-item:hover { border-color: var(--accent); }
.queue-item.expanded { border-color: var(--accent); }
.queue-item-header { display: flex; justify-content: space-between; align-items: center; }
.queue-item-details { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: none; }
.queue-item.expanded .queue-item-details { display: block; }

/* Orchestrator */
.orchestrator-input { width: 100%; padding: 12px; font-size: 14px; }
.candidate-row { padding: 10px 12px; background: var(--bg-dark); border-radius: 4px; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center; }
.candidate-row.selected { background: rgba(63,185,80,0.2); border: 1px solid var(--green); }
.candidate-score { font-weight: 700; font-size: 14px; }
.gap-alert { background: rgba(248,81,73,0.1); border: 1px solid var(--red); border-radius: 6px; padding: 16px; margin-top: 16px; }

/* Category headers */
.category-header { font-size: 11px; font-weight: 600; color: var(--accent); margin: 16px 0 8px 0; padding-bottom: 4px; border-bottom: 1px solid var(--border); }
.category-header:first-child { margin-top: 0; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>AETHER DASHBOARD</h1>
    <div class="subtitle">Operational Diagnostics | KG Explorer | AEC Lab | Orchestrator</div>
  </div>
  <div class="header-stats">
    <div class="stat"><span>CAPSULES</span><span class="stat-value" id="stat-capsules">-</span></div>
    <div class="stat"><span>KG NODES</span><span class="stat-value" id="stat-nodes">-</span></div>
    <div class="stat"><span>PENDING</span><span class="stat-value" id="stat-pending">-</span></div>
  </div>
</div>

<div class="container">
  <div class="sidebar">
    <div class="sidebar-title">Capsule Registry</div>
    <div id="capsule-list"></div>
  </div>

  <div class="main">
    <div class="tabs">
      <div class="tab active" data-tab="overview">Overview</div>
      <div class="tab" data-tab="kg">KG Explorer</div>
      <div class="tab" data-tab="aec">AEC Lab</div>
      <div class="tab" data-tab="test">Force Test</div>
      <div class="tab" data-tab="queue">Education Queue</div>
      <div class="tab" data-tab="orchestrator">Orchestrator</div>
      <div class="tab" data-tab="psi">PSI Layer</div>
      <div class="tab" data-tab="chat">Chat</div>
    </div>

    <div class="tab-content">
      <!-- Overview Panel -->
      <div id="panel-overview" class="panel active">
        <div class="card">
          <div class="card-title">Capsule Inventory</div>
          <div id="inventory-grid"></div>
        </div>
        <div class="card">
          <div class="card-title">Codebase Metrics</div>
          <div id="metrics-content"></div>
        </div>
      </div>

      <!-- KG Explorer Panel -->
      <div id="panel-kg" class="panel">
        <div class="flex flex-between flex-center mb-16">
          <div class="kg-legend">
            <div class="kg-legend-item"><span class="origin-dot origin-core"></span>Core</div>
            <div class="kg-legend-item"><span class="origin-dot origin-acquired"></span>Acquired</div>
            <div class="kg-legend-item"><span class="origin-dot origin-updated"></span>Updated</div>
            <div class="kg-legend-item"><span class="origin-dot origin-deprecated"></span>Deprecated</div>
            <div class="kg-legend-item"><span class="origin-dot origin-provenance"></span>Provenance</div>
            <div class="kg-legend-item" style="margin-left:20px;"><span style="color:var(--cyan);">---</span> avoids</div>
            <div class="kg-legend-item"><span style="color:var(--green);">---</span> enables</div>
            <div class="kg-legend-item"><span style="color:var(--orange);">---</span> requires</div>
            <div class="kg-legend-item"><span style="color:var(--red);">---</span> contradicts</div>
          </div>
          <div id="kg-stats" class="text-dim"></div>
        </div>
        <div class="kg-layout">
          <div class="kg-graph"><div class="kg-search"><input type="text" id="kg-search" placeholder="Search nodes..."></div><div id="kg-network"></div></div>
          <div class="kg-detail">
            <div class="card" style="flex:0 0 auto;">
              <div class="card-title">Node Details</div>
              <div id="node-detail">Select a node to view details</div>
            </div>
            <div class="node-list" id="node-list"></div>
          </div>
        </div>
      </div>

      <!-- AEC Lab Panel -->
      <div id="panel-aec" class="panel">
        <div class="card">
          <div class="card-title">AEC Verification Lab</div>
          <div class="flex gap-16 mb-16">
            <div style="flex:1;">
              <label class="text-dim" style="font-size:9px;text-transform:uppercase;display:block;margin-bottom:6px;">Capsule</label>
              <select id="aec-capsule" style="width:100%;"></select>
            </div>
          </div>
          <div class="mb-16">
            <label class="text-dim" style="font-size:9px;text-transform:uppercase;display:block;margin-bottom:6px;">Text to Verify</label>
            <textarea id="aec-text" placeholder="Enter response text to verify against the capsule's knowledge graph..."></textarea>
          </div>
          <div class="flex gap-8 mb-16">
            <button class="btn btn-primary" onclick="runAEC()">Verify</button>
            <button class="btn" onclick="fillExample('pass')">Example: Pass</button>
            <button class="btn" onclick="fillExample('fail')">Example: Fail</button>
            <button class="btn" onclick="fillExample('persona')">Example: Persona</button>
          </div>
          <div id="aec-result" class="aec-result"></div>
        </div>
      </div>

      <!-- Force Test Panel -->
      <div id="panel-test" class="panel">
        <div class="card">
          <div class="card-title">Exhaustive System Test</div>
          <div class="mb-16">
            <button class="btn btn-green" onclick="runTests()" id="run-test-btn">Run Tests</button>
            <span id="test-status" class="text-dim" style="margin-left:12px;"></span>
          </div>
          <div id="test-results"></div>
        </div>
      </div>

      <!-- Queue Panel -->
      <div id="panel-queue" class="panel">
        <div class="card">
          <div class="card-title">Education Queue: <span id="queue-capsule-name">-</span></div>
          <div id="queue-stats" class="flex gap-16 mb-16"></div>
          <div id="queue-items"></div>
        </div>
      </div>

      <!-- Orchestrator Panel -->
      <div id="panel-orchestrator" class="panel">
        <div class="card">
          <div class="card-title">Query Orchestrator</div>
          <div class="mb-16">
            <label class="text-dim" style="font-size:9px;text-transform:uppercase;display:block;margin-bottom:6px;">Query</label>
            <input type="text" id="orchestrator-query" class="orchestrator-input" placeholder="Enter a query to route to the best capsule...">
          </div>
          <div class="flex gap-8 mb-16">
            <button class="btn btn-primary" onclick="runOrchestrate(true)" id="route-btn">Route (Dry Run)</button>
            <button class="btn btn-green" onclick="runOrchestrate(false)" id="execute-btn">Route & Execute</button>
            <span id="orchestrator-status" class="text-dim" style="margin-left:12px;"></span>
          </div>
          <div id="orchestrator-result"></div>
        </div>
      </div>

      <!-- PSI Layer Demo Panel -->
      <div id="panel-psi" class="panel">
        <link rel="stylesheet" href="/static/aether-sliver.css">
        <div class="card">
          <div class="card-title">PSI Layer Demo</div>
          <p class="text-dim mb-16" style="font-size:11px;">
            The PSI layer projects agent cognitive state as CSS variables. Pipeline stages map to visual phases:
            <span class="badge badge-blue">reflex</span>
            <span class="badge badge-cyan">deliberation</span>
            <span class="badge badge-green">complete</span>
            <span class="badge badge-orange">ghost</span>
          </p>
          <div class="flex gap-16 mb-16">
            <div style="flex:1;">
              <label class="text-dim" style="font-size:9px;text-transform:uppercase;display:block;margin-bottom:6px;">Capsule</label>
              <select id="psi-capsule" style="width:100%;"></select>
            </div>
          </div>
          <div class="mb-16">
            <label class="text-dim" style="font-size:9px;text-transform:uppercase;display:block;margin-bottom:6px;">Query</label>
            <input type="text" id="psi-query" style="width:100%;padding:12px;" placeholder="Enter a query to trigger the pipeline...">
          </div>
          <div class="flex gap-8 mb-16">
            <button class="btn btn-primary" onclick="runPsiDemo()">Run Pipeline</button>
            <span id="psi-status" class="text-dim" style="margin-left:12px;"></span>
          </div>
        </div>

        <div class="flex gap-16 mt-16">
          <!-- Live Sliver Preview -->
          <div class="card" style="flex:1;">
            <div class="card-title">Live Sliver Preview</div>
            <div id="psi-sliver-container">
              <div data-aether-agent="demo"
                   data-aether-phase="idle"
                   data-aether-autoconnect="false"
                   class="aether-sliver"
                   id="psi-demo-sliver"
                   style="--aether-state:idle; --aether-view-complexity:0; --aether-confidence:0; --aether-sentiment:neutral;">
                <header class="aether-header">
                  <span data-aether-slot="agent-name">Select a capsule</span>
                </header>
                <main class="aether-content">
                  <p data-aether-slot="answer">Waiting for query...</p>
                </main>
                <footer class="aether-meta">
                  <span data-aether-slot="status">Ready</span>
                  <span class="aether-confidence" data-aether-slot="confidence"></span>
                </footer>
              </div>
            </div>
          </div>

          <!-- CSS Variable State -->
          <div class="card" style="width:300px;">
            <div class="card-title">CSS Variable State</div>
            <div id="psi-vars-display" style="font-family:monospace;font-size:11px;">
              <div class="mb-8"><span class="text-dim">--aether-state:</span> <span id="psi-var-state">idle</span></div>
              <div class="mb-8"><span class="text-dim">--aether-view-complexity:</span> <span id="psi-var-complexity">0</span></div>
              <div class="mb-8"><span class="text-dim">--aether-confidence:</span> <span id="psi-var-confidence">0</span></div>
              <div class="mb-8"><span class="text-dim">--aether-sentiment:</span> <span id="psi-var-sentiment">neutral</span></div>
            </div>
            <div class="mt-16">
              <div class="card-title">Event Log</div>
              <div id="psi-event-log" style="max-height:200px;overflow-y:auto;font-size:10px;"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Chat Panel -->
      <div id="panel-chat" class="panel">
        <div class="card">
          <div class="card-title">Aether Chat</div>
          <div class="flex gap-16 mb-16">
            <div style="flex:1;">
              <label class="text-dim" style="font-size:9px;text-transform:uppercase;display:block;margin-bottom:6px;">Capsule</label>
              <select id="chat-capsule" style="width:100%;"></select>
            </div>
          </div>
          <div id="chat-history" style="height: 400px; overflow-y: auto; background: var(--bg-dark); border: 1px solid var(--border); border-radius: 6px; padding: 12px; margin-bottom: 16px; display: flex; flex-direction: column; gap: 8px;">
            <div class="text-dim">Select a capsule and start chatting...</div>
          </div>
          <div class="flex gap-8">
            <input type="text" id="chat-input" style="flex:1;" placeholder="Type your message...">
            <button class="btn btn-primary" onclick="sendChatMessage()">Send</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
// Suppress benign ResizeObserver error from vis-network
window.addEventListener('error', e => {
  if (e.message === 'ResizeObserver loop completed with undelivered notifications.' ||
      e.message === 'ResizeObserver loop limit exceeded') {
    e.stopImmediatePropagation();
  }
});

let capsules = [];
let selectedCapsule = null;
let kgData = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  loadCapsules();
  loadMetrics();

  // Tab switching
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      const panel = document.getElementById('panel-' + tab.dataset.tab);
      if (panel) panel.classList.add('active');
    });
  });

  // Enter key for orchestrator
  document.getElementById('orchestrator-query').addEventListener('keypress', e => {
    if (e.key === 'Enter') runOrchestrate(true);
  });
  
  // Enter key for chat
  document.getElementById('chat-input').addEventListener('keypress', e => {
    if (e.key === 'Enter') sendChatMessage();
  });
});

async function loadCapsules() {
  const res = await fetch('/api/capsules');
  capsules = await res.json();

  // Update header stats
  let totalNodes = 0, totalPending = 0;
  capsules.forEach(c => {
    totalNodes += c.kg_nodes || 0;
    totalPending += c.queue_pending || 0;
  });
  document.getElementById('stat-capsules').textContent = capsules.length;
  document.getElementById('stat-nodes').textContent = totalNodes;
  document.getElementById('stat-pending').textContent = totalPending;

  // Group capsules by category
  const categories = {};
  capsules.forEach(c => {
    const cat = c.category || 'Other';
    if (!categories[cat]) categories[cat] = [];
    categories[cat].push(c);
  });

  // Render sidebar with categories
  const list = document.getElementById('capsule-list');
  let sidebarHtml = '';
  const categoryOrder = ['Aether Core', 'Scholars', 'Validators', 'Domain Experts', 'Anthropic Skills', 'Executive Roles', 'Infrastructure', 'Other'];
  categoryOrder.forEach(cat => {
    if (categories[cat] && categories[cat].length > 0) {
      sidebarHtml += `<div class="sidebar-title" style="margin-top:12px;">${cat}</div>`;
      categories[cat].forEach(c => {
        sidebarHtml += `
          <div class="capsule-card" data-folder="${c.folder}" onclick="selectCapsule('${c.folder}')">
            <div class="name">${c.name}</div>
            <div class="version">v${c.version}</div>
            <div class="stats">
              <span><span class="num">${c.kg_nodes}</span> nodes</span>
              <span><span class="num">${c.queue_pending}</span> pending</span>
            </div>
          </div>
        `;
      });
    }
  });
  list.innerHTML = sidebarHtml;

  // Render inventory grid grouped by category
  const grid = document.getElementById('inventory-grid');
  let gridHtml = '';
  categoryOrder.forEach(cat => {
    if (categories[cat] && categories[cat].length > 0) {
      gridHtml += `<div class="category-header" style="grid-column: 1 / -1;">${cat} (${categories[cat].length})</div>`;
      categories[cat].forEach(c => {
        const health = c.queue_pending > 5 ? 'red' : c.queue_pending > 2 ? 'orange' : 'green';
        gridHtml += `
          <div class="card" style="margin:0;">
            <div class="flex flex-between flex-center mb-8">
              <div class="name" style="font-weight:600;">${c.name}</div>
              <span class="badge badge-${health}">${health === 'green' ? 'HEALTHY' : health === 'orange' ? 'WARN' : 'ALERT'}</span>
            </div>
            <div class="text-dim mb-8" style="font-size:9px;">${c.id}</div>
            <div class="flex gap-16" style="font-size:10px;">
              <div><span class="text-dim">KB:</span> ${c.kb_size.toLocaleString()} chars</div>
              <div><span class="text-dim">KG:</span> ${c.kg_nodes} nodes</div>
            </div>
            <div class="flex gap-16 mt-16" style="font-size:10px;">
              <div><span class="origin-dot origin-core"></span>${c.kg_core || 0}</div>
              <div><span class="origin-dot origin-acquired"></span>${c.kg_acquired || 0}</div>
              <div><span class="origin-dot origin-deprecated"></span>${c.kg_deprecated || 0}</div>
            </div>
            <div class="mt-16" style="font-size:10px;">
              <span class="text-dim">Queue:</span> ${c.queue_total} total, ${c.queue_pending} pending, ${c.queue_integrated || 0} integrated
            </div>
          </div>
        `;
      });
    }
  });
  grid.innerHTML = gridHtml;

  // Populate AEC and Chat dropdowns
  const aecSelect = document.getElementById('aec-capsule');
  aecSelect.innerHTML = capsules.map(c => `<option value="${c.folder}">${c.name}</option>`).join('');
  
  const chatSelect = document.getElementById('chat-capsule');
  chatSelect.innerHTML = capsules.map(c => `<option value="${c.folder}">${c.name}</option>`).join('');

  // Select first capsule
  if (capsules.length > 0) {
    await selectCapsule(capsules[0].folder);
  }
}

async function selectCapsule(folder) {
  console.log('selectCapsule called with:', folder);
  selectedCapsule = folder;

  // Update sidebar selection
  document.querySelectorAll('.capsule-card').forEach(el => {
    el.classList.toggle('selected', el.dataset.folder === folder);
  });

  // Update AEC and Chat dropdowns
  document.getElementById('aec-capsule').value = folder;
  document.getElementById('chat-capsule').value = folder;

  // Load KG and Queue (await to ensure completion)
  try {
    await loadKG(folder);
    await loadQueue(folder);
  } catch (e) {
    console.error('Error loading capsule data:', e);
  }
}

async function sendChatMessage() {
  const capsule = document.getElementById('chat-capsule').value;
  const query = document.getElementById('chat-input').value.trim();
  if (!query) return;

  const history = document.getElementById('chat-history');
  if (history.innerHTML.includes('Select a capsule')) history.innerHTML = '';
  
  history.innerHTML += `<div style="align-self: flex-end; background: var(--accent); color: var(--bg-dark); padding: 8px 12px; border-radius: 12px 12px 0 12px; max-width: 80%; font-size: 11px; margin-top: 8px;">${query}</div>`;
  document.getElementById('chat-input').value = '';
  history.scrollTop = history.scrollHeight;

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({capsule, query})
    });
    const result = await res.json();

    const response = result.generated || '[No response]';
    const review = result.review || {};
    const aecScore = review.aec?.score || 0;
    const passed = review.passed;
    const isGhost = review.ghost;
    
    history.innerHTML += `
      <div style="align-self: flex-start; background: var(--bg-panel); border: 1px solid ${isGhost ? 'var(--red)' : 'var(--border)'}; padding: 8px 12px; border-radius: 12px 12px 12px 0; max-width: 80%; font-size: 11px; margin-top: 8px;">
        <div style="white-space: pre-wrap;">${response}</div>
        <div class="text-dim" style="font-size: 9px; margin-top: 4px; display: flex; justify-content: space-between;">
          <span>AEC: ${Math.round(aecScore * 100)}% | ${passed ? '<span class="text-green">PASSED</span>' : '<span class="text-red">FAILED</span>'}</span>
          ${isGhost ? '<span class="badge badge-red">GHOST</span>' : ''}
        </div>
      </div>
    `;
    history.scrollTop = history.scrollHeight;
  } catch (e) {
    history.innerHTML += `<div style="align-self: flex-start; color: var(--red); font-size: 10px; margin-top: 4px;">Error: ${e.message}</div>`;
  }
}


async function loadKG(folder) {
  console.log('loadKG fetching:', '/api/kg/' + folder);
  const res = await fetch('/api/kg/' + folder);
  kgData = await res.json();
  console.log('loadKG received:', kgData.nodes ? kgData.nodes.length : 0, 'nodes,', kgData.edges ? kgData.edges.length : 0, 'edges');

  // Update stats
  const stats = kgData.stats || {};
  const edgeCount = (kgData.edges || []).length;
  document.getElementById('kg-stats').textContent =
    `Nodes: ${stats.total || 0} | Edges: ${edgeCount} | Core: ${stats.core || 0} | Acquired: ${stats.acquired || 0} | Updated: ${stats.updated || 0} | Deprecated: ${stats.deprecated || 0}`;

  // Render node list
  const nodeList = document.getElementById('node-list');
  nodeList.innerHTML = (kgData.nodes || []).map((n, i) => {
    const origin = n.origin || 'core';
    const label = n.label || n.id || 'Unknown';
    return `<div class="node-list-item" data-index="${i}" onclick="selectNode(${i})"><span class="origin-dot origin-${origin}"></span>${label}</div>`;
  }).join('');

  // Render graph with force-directed layout
  renderKGGraph(kgData);
}

// vis-network state
let network = null;
let visNodes = null;
let visEdges = null;

function renderKGGraph(data) {
  const container = document.getElementById('kg-network');

  // Destroy previous network
  if (network) {
    network.destroy();
    network = null;
  }

  // Create DataSets
  visNodes = new vis.DataSet();
  visEdges = new vis.DataSet();

  // Map nodes - store original data for click handler lookup
  (data.nodes || []).forEach((n, i) => {
    visNodes.add({
      id: n.id || `node-${i}`,
      label: n.label || n.id || 'Unknown',
      group: n.origin || 'core',
      title: n.label || n.id,
      _index: i
    });
  });

  // Edge colors by predicate type
  const edgeColors = {
    'skill:avoids': '#56d4dd',
    'skill:enables': '#3fb950',
    'skill:requires': '#d29922',
    'skill:contradicts': '#f85149',
    'skill:contains': '#a371f7',
    'avoids': '#56d4dd',
    'enables': '#3fb950',
    'requires': '#d29922',
    'contradicts': '#f85149',
    'contains': '#a371f7',
  };

  // Map edges
  (data.edges || []).forEach((e, i) => {
    const sourceNode = data.nodes[e.source];
    const targetNode = data.nodes[e.target];
    if (sourceNode && targetNode) {
      const predicate = e.predicate || '';
      const predicateShort = predicate.replace('skill:', '');
      const edgeColor = edgeColors[predicate] || edgeColors[predicateShort] || '#30363d';
      visEdges.add({
        from: sourceNode.id || `node-${e.source}`,
        to: targetNode.id || `node-${e.target}`,
        label: predicateShort,
        color: { color: edgeColor, highlight: edgeColor },
        font: { color: edgeColor, size: 9, strokeWidth: 0 }
      });
    }
  });

  // Network options
  const options = {
    groups: {
      core: { shape: 'dot', size: 20, color: '#58a6ff' },
      acquired: { shape: 'dot', size: 20, color: '#3fb950' },
      updated: { shape: 'dot', size: 18, color: '#d29922' },
      deprecated: { shape: 'diamond', size: 15, color: '#f85149' },
      provenance: { shape: 'dot', size: 16, color: '#a371f7' }
    },
    nodes: {
      font: { color: '#c9d1d9', size: 12 }
    },
    edges: {
      font: { size: 9, color: '#8b949e', strokeWidth: 0, align: 'middle' },
      arrows: { to: { enabled: true, scaleFactor: 0.5 } },
      smooth: { type: 'curvedCW', roundness: 0.2 }
    },
    physics: {
      forceAtlas2Based: { gravitationalConstant: -80, centralGravity: 0.01, springLength: 120 },
      solver: 'forceAtlas2Based',
      stabilization: { iterations: 100 }
    }
  };

  // Create network
  network = new vis.Network(container, { nodes: visNodes, edges: visEdges }, options);

  // Click handler
  network.on('click', (params) => {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0];
      const visNode = visNodes.get(nodeId);
      if (visNode) {
        const node = (data.nodes || [])[visNode._index];
        if (node) {
          selectNode(visNode._index, node);
        }
      }
    } else {
      document.querySelectorAll('.node-list-item').forEach(el => el.classList.remove('selected'));
      document.getElementById('node-detail').innerHTML = 'Select a node to view details';
    }
  });

  // Search handler
  const searchInput = document.getElementById('kg-search');
  searchInput.value = '';
  searchInput.onkeyup = () => {
    const query = searchInput.value.toLowerCase().trim();
    if (!query) return;
    const filtered = visNodes.get({ filter: n => n.label.toLowerCase().includes(query) });
    if (filtered.length > 0) {
      network.focus(filtered[0].id, { scale: 1.2, animation: true });
      network.selectNodes([filtered[0].id]);
    }
  };

  // Resize handler
  window.addEventListener('resize', () => {
    if (network) network.redraw();
  });
}

function selectNode(index, node) {
  if (!node) {
    node = kgData.nodes[index];
  }
  if (!node) return;

  // Update list selection
  document.querySelectorAll('.node-list-item').forEach(el => {
    el.classList.toggle('selected', parseInt(el.dataset.index) === index);
  });

  // Show details including edges
  const detail = document.getElementById('node-detail');
  const origin = node.origin || 'core';
  let propsHtml = '';
  for (const [k, v] of Object.entries(node.properties || {})) {
    propsHtml += `<div style="margin-bottom:4px;"><span class="text-dim">${k}:</span> ${JSON.stringify(v)}</div>`;
  }

  // Find edges for this node
  let edgesHtml = '';
  if (kgData.edges) {
    const nodeEdges = kgData.edges.filter(e =>
      kgData.nodes[e.source]?.id === node.id || kgData.nodes[e.target]?.id === node.id
    );
    if (nodeEdges.length > 0) {
      edgesHtml = '<div style="margin-top:8px;"><strong>Edges:</strong></div>';
      nodeEdges.forEach(e => {
        const source = kgData.nodes[e.source];
        const target = kgData.nodes[e.target];
        const isOutgoing = source?.id === node.id;
        const other = isOutgoing ? target : source;
        const direction = isOutgoing ? '→' : '←';
        edgesHtml += `<div style="font-size:10px;margin-top:2px;"><span class="text-cyan">${e.predicate}</span> ${direction} ${other?.label || 'unknown'}</div>`;
      });
    }
  }

  detail.innerHTML = `
    <div class="mb-8"><span class="badge badge-${origin === 'core' ? 'blue' : origin === 'acquired' ? 'green' : origin === 'deprecated' ? 'red' : 'purple'}">${origin.toUpperCase()}</span></div>
    <div class="mb-8"><strong>@id:</strong> ${node.id}</div>
    <div class="mb-8"><strong>Label:</strong> ${node.label || '-'}</div>
    <div style="font-size:10px;">${propsHtml || '<span class="text-dim">No properties</span>'}</div>
    ${edgesHtml}
  `;
}

async function runAEC() {
  const capsule = document.getElementById('aec-capsule').value;
  const text = document.getElementById('aec-text').value;
  if (!text.trim()) return;

  const res = await fetch('/api/aec', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({capsule, text})
  });
  const result = await res.json();

  const scorePercent = Math.round((result.score || 0) * 100);
  const thresholdPercent = Math.round((result.threshold || 0.8) * 100);
  const passed = result.passed;

  // Method badge colors
  const methodColors = {
    'persona': 'purple',
    'deterministic_number': 'green',
    'deterministic_date': 'green',
    'deterministic_percentage': 'green',
    'concept:Rule': 'cyan',
    'concept:Technique': 'cyan',
    'concept:AntiPattern': 'red',
    'antipattern_violation': 'red',
    'llm_grounded': 'blue',
    'llm_violation': 'red',
  };

  function getMethodColor(method) {
    if (!method) return 'text-dim';
    for (const [key, color] of Object.entries(methodColors)) {
      if (method.includes(key)) return color;
    }
    if (method.startsWith('concept:')) return 'cyan';
    if (method.startsWith('deterministic')) return 'green';
    return 'text-dim';
  }

  let statementsHtml = '';
  (result.statements || []).forEach(s => {
    const cat = s.category || 'persona';
    const method = s.method || '';
    const methodColor = getMethodColor(method);
    const methodDisplay = method.replace('deterministic_', 'factual:').replace('concept:', 'L1:');
    statementsHtml += `
      <div class="statement-row statement-${cat}">
        <span>${s.text}</span>
        <span class="statement-method" style="color:var(--${methodColor});">${methodDisplay}</span>
      </div>`;
  });

  document.getElementById('aec-result').innerHTML = `
    <div class="score-bar">
      <div class="score-fill" style="width:${scorePercent}%;background:${passed ? 'var(--green)' : 'var(--red)'};"></div>
      <div class="score-threshold" style="left:${thresholdPercent}%;"></div>
    </div>
    <div class="flex flex-between flex-center mb-16">
      <div>
        <span style="font-size:24px;font-weight:700;">${scorePercent}%</span>
        <span class="text-dim" style="margin-left:8px;">threshold: ${thresholdPercent}%</span>
      </div>
      <span class="badge ${passed ? 'badge-green' : 'badge-red'}">${passed ? 'PASS' : 'FAIL'}</span>
    </div>
    <div class="text-dim mb-8" style="font-size:10px;">
      ${result.grounded_statements || 0} grounded, ${result.ungrounded_statements || 0} ungrounded, ${result.persona_statements || 0} persona
      ${result.concept_applied ? ' | <span class="text-cyan">Concept matching applied</span>' : ''}
    </div>
    <div class="mb-8" style="font-size:10px;">
      <span class="text-dim">Verification layers:</span>
      <span class="badge badge-green" style="margin-left:4px;">factual</span>
      <span class="badge badge-cyan" style="margin-left:4px;">L1:type</span>
      <span class="badge badge-blue" style="margin-left:4px;">L2:llm</span>
      <span class="badge badge-purple" style="margin-left:4px;">persona</span>
    </div>
    <div>${statementsHtml}</div>
    ${result.gaps && result.gaps.length ? '<div class="mt-16 text-dim" style="font-size:10px;">Gaps: ' + result.gaps.map(g => g.text).join('; ') + '</div>' : ''}
  `;
}

function fillExample(type) {
  const examples = {
    pass: 'Jefferson was born on April 13, 1743 in Virginia. He authored the Declaration of Independence in 1776.',
    fail: 'Jefferson was born in 1750 in New York. He wrote the Magna Carta in 1800.',
    persona: 'He was a brilliant thinker and visionary leader. His ideas continue to inspire millions around the world.'
  };
  document.getElementById('aec-text').value = examples[type] || '';
  // Select jefferson capsule for examples
  const select = document.getElementById('aec-capsule');
  for (let opt of select.options) {
    if (opt.value.includes('jefferson')) { select.value = opt.value; break; }
  }
}

async function runOrchestrate(dryRun) {
  const query = document.getElementById('orchestrator-query').value.trim();
  if (!query) return;

  const status = document.getElementById('orchestrator-status');
  const routeBtn = document.getElementById('route-btn');
  const executeBtn = document.getElementById('execute-btn');

  routeBtn.disabled = true;
  executeBtn.disabled = true;
  status.innerHTML = '<span class="spinner"></span> Routing...';

  try {
    const res = await fetch('/api/orchestrate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({query, dry_run: dryRun})
    });
    const result = await res.json();

    status.textContent = dryRun ? 'Dry run complete' : 'Execution complete';

    let html = '<div class="mb-16"><strong>Query:</strong> ' + query + '</div>';

    // Show candidates
    if (result.candidates && result.candidates.length > 0) {
      html += '<div class="card-title">Candidates</div>';
      result.candidates.forEach(c => {
        const isSelected = c.capsule_id === result.routed_to;
        html += `
          <div class="candidate-row ${isSelected ? 'selected' : ''}">
            <div>
              <strong>${c.capsule_name}</strong>
              <div class="text-dim" style="font-size:10px;">${c.capsule_id}</div>
            </div>
            <div class="flex gap-8 flex-center">
              <span class="candidate-score ${isSelected ? 'text-green' : ''}">${(c.score * 100).toFixed(1)}%</span>
              ${isSelected ? '<span class="badge badge-green">SELECTED</span>' : ''}
            </div>
          </div>
        `;
      });
    }

    // Gap detection
    if (result.gap) {
      html += `
        <div class="gap-alert">
          <div class="flex flex-between flex-center mb-8">
            <strong class="text-red">GAP DETECTED</strong>
            <span class="badge badge-red">NO MATCH</span>
          </div>
          <div class="mb-8"><span class="text-dim">Topic:</span> ${result.gap.topic || 'unknown'}</div>
          ${result.gap.closest_capsule ? `<div class="mb-8"><span class="text-dim">Closest:</span> ${result.gap.closest_capsule} (${(result.gap.closest_score * 100).toFixed(1)}%)</div>` : ''}
          <div class="text-dim">${result.gap.recommendation || ''}</div>
        </div>
      `;
    } else if (result.routed_to) {
      html += `
        <div class="card mt-16" style="background:rgba(63,185,80,0.1);border-color:var(--green);">
          <div class="flex flex-between flex-center">
            <div>
              <div class="text-dim" style="font-size:9px;text-transform:uppercase;">Routed To</div>
              <div style="font-size:14px;font-weight:600;">${result.routed_name}</div>
            </div>
            <div style="font-size:24px;font-weight:700;color:var(--green);">${(result.match_score * 100).toFixed(1)}%</div>
          </div>
        </div>
      `;

      // Show pipeline result if executed
      if (!dryRun && result.result) {
        const pipelineResult = result.result;
        const response = pipelineResult.generated || '';
        const review = pipelineResult.review || {};
        const aec = review.aec || {};

        html += '<div class="card-title mt-16">Pipeline Result</div>';

        if (response) {
          html += `<div class="card" style="max-height:200px;overflow-y:auto;"><pre style="white-space:pre-wrap;font-size:11px;">${response.substring(0, 1000)}${response.length > 1000 ? '...' : ''}</pre></div>`;
        }

        if (aec.score !== undefined) {
          const aecScore = Math.round((aec.score || 0) * 100);
          const aecPassed = aec.passed;
          html += `
            <div class="flex gap-16 mt-16">
              <div><span class="text-dim">AEC Score:</span> <strong class="${aecPassed ? 'text-green' : 'text-red'}">${aecScore}%</strong></div>
              <div><span class="text-dim">Threshold:</span> ${Math.round((aec.threshold || 0.8) * 100)}%</div>
              <div><span class="badge ${aecPassed ? 'badge-green' : 'badge-red'}">${aecPassed ? 'PASS' : 'FAIL'}</span></div>
            </div>
          `;
          if (review.ghost) {
            html += '<div class="mt-16"><span class="badge badge-orange">GHOST</span> <span class="text-dim">Unverifiable response</span></div>';
          }
        }
      }
    }

    document.getElementById('orchestrator-result').innerHTML = html;
  } catch (e) {
    status.textContent = 'Error: ' + e.message;
    document.getElementById('orchestrator-result').innerHTML = '<div class="text-red">Error: ' + e.message + '</div>';
  }

  routeBtn.disabled = false;
  executeBtn.disabled = false;
}

async function runTests() {
  const btn = document.getElementById('run-test-btn');
  const status = document.getElementById('test-status');
  btn.disabled = true;
  status.innerHTML = '<span class="spinner"></span> Running tests...';

  try {
    const res = await fetch('/api/test');
    const data = await res.json();

    status.textContent = 'Last run: ' + new Date().toLocaleTimeString();

    const total = data.total || 0;
    const passed = data.passed || 0;
    const failed = total - passed;
    const rate = total > 0 ? Math.round(passed / total * 100) : 0;

    let resultsHtml = `
      <div class="test-summary">
        <div class="test-stat"><div class="value">${total}</div><div class="label">Total</div></div>
        <div class="test-stat"><div class="value text-green">${passed}</div><div class="label">Passed</div></div>
        <div class="test-stat"><div class="value text-red">${failed}</div><div class="label">Failed</div></div>
        <div class="test-stat"><div class="value ${rate >= 90 ? 'text-green' : rate >= 70 ? 'text-orange' : 'text-red'}">${rate}%</div><div class="label">Pass Rate</div></div>
      </div>
    `;

    // Group tests by category
    const categories = {};
    (data.tests || []).forEach(t => {
      const cat = t.category || 'other';
      if (!categories[cat]) categories[cat] = [];
      categories[cat].push(t);
    });

    for (const [cat, tests] of Object.entries(categories)) {
      resultsHtml += `<div class="card-title mt-16">${cat.toUpperCase()}</div><table><tr><th>Test</th><th>Expected</th><th>Actual</th><th>Status</th></tr>`;
      tests.sort((a,b) => (a.status === 'PASS' ? 1 : -1) - (b.status === 'PASS' ? 1 : -1));
      tests.forEach(t => {
        const color = t.status === 'PASS' ? 'text-green' : 'text-red';
        resultsHtml += `<tr><td>${t.name}</td><td class="text-dim">${(t.expected||'').substring(0,30)}</td><td class="text-dim">${(t.actual||'').substring(0,30)}</td><td class="${color}">${t.status}</td></tr>`;
      });
      resultsHtml += '</table>';
    }

    document.getElementById('test-results').innerHTML = resultsHtml;
  } catch (e) {
    status.textContent = 'Error: ' + e.message;
  }
  btn.disabled = false;
}

async function loadQueue(folder) {
  const cap = capsules.find(c => c.folder === folder);
  document.getElementById('queue-capsule-name').textContent = cap ? cap.name : folder;

  const res = await fetch('/api/queue/' + folder);
  const data = await res.json();

  const stats = data.stats || {};
  document.getElementById('queue-stats').innerHTML = `
    <div><span class="text-dim">Total:</span> ${stats.total || 0}</div>
    <div><span class="text-dim">Pending:</span> <span class="text-orange">${stats.pending || 0}</span></div>
    <div><span class="text-dim">Researching:</span> ${stats.researching || 0}</div>
    <div><span class="text-dim">Integrated:</span> <span class="text-green">${stats.integrated || 0}</span></div>
    <div><span class="text-dim">Failed:</span> <span class="text-red">${stats.failed || 0}</span></div>
  `;

  const items = data.items || [];
  document.getElementById('queue-items').innerHTML = items.length === 0 ? '<div class="text-dim">No items in queue</div>' :
    items.map((item, i) => {
      const scoreColor = item.aec_score < 0.5 ? 'text-red' : item.aec_score < 0.8 ? 'text-orange' : 'text-green';
      const statusBadge = item.status === 'pending' ? 'badge-orange' : item.status === 'integrated' ? 'badge-green' : item.status === 'failed' ? 'badge-red' : 'badge-blue';
      return `
        <div class="queue-item" onclick="this.classList.toggle('expanded')">
          <div class="queue-item-header">
            <div>
              <span class="text-dim" style="font-size:9px;">${item.id || ''}</span>
              <div style="margin-top:4px;">${(item.query || '').substring(0, 60)}...</div>
            </div>
            <div class="flex gap-8 flex-center">
              <span class="${scoreColor}" style="font-weight:700;">${Math.round((item.aec_score || 0) * 100)}%</span>
              <span class="badge ${statusBadge}">${item.status}</span>
            </div>
          </div>
          <div class="queue-item-details">
            <div class="mb-8"><strong>Query:</strong> ${item.query || '-'}</div>
            <div class="mb-8"><strong>Response:</strong> ${(item.response || '').substring(0, 200)}...</div>
            <div><strong>Gaps:</strong> ${(item.gaps || []).map(g => g.text || g).join('; ') || 'None'}</div>
          </div>
        </div>
      `;
    }).join('');
}

async function loadMetrics() {
  const res = await fetch('/api/metrics');
  const data = await res.json();

  let html = `
    <div class="flex gap-16 mb-16">
      <div><span class="text-dim">Files:</span> <strong>${data.total_files || 0}</strong></div>
      <div><span class="text-dim">Lines:</span> <strong>${data.total_lines || 0}</strong></div>
      <div><span class="text-dim">Python:</span> 3.11+</div>
      <div><span class="text-dim">Dependencies:</span> anthropic (optional), openai (optional)</div>
    </div>
    <table><tr><th>File</th><th>Lines</th></tr>
  `;
  const files = data.files || {};
  Object.entries(files).sort((a,b) => b[1] - a[1]).forEach(([f, lines]) => {
    html += `<tr><td>${f}</td><td>${lines}</td></tr>`;
  });
  html += '</table>';
  document.getElementById('metrics-content').innerHTML = html;
}

// =============================================================================
// PSI LAYER DEMO
// =============================================================================

async function loadPsiCapsules() {
  const res = await fetch('/api/psi-capsules');
  const data = await res.json();

  const select = document.getElementById('psi-capsule');
  select.innerHTML = data.map(c =>
    `<option value="${c.folder}">${c.name} ${c.psi_enabled ? '(PSI)' : ''}</option>`
  ).join('');

  // Update sliver agent name
  if (data.length > 0) {
    document.querySelector('#psi-demo-sliver [data-aether-slot="agent-name"]').textContent = data[0].name;
  }

  select.addEventListener('change', () => {
    const selected = data.find(c => c.folder === select.value);
    if (selected) {
      document.querySelector('#psi-demo-sliver [data-aether-slot="agent-name"]').textContent = selected.name;
    }
  });
}

function applyPsiDelta(data) {
  const sliver = document.getElementById('psi-demo-sliver');

  // Apply CSS variables
  if (data.vars) {
    for (const [k, v] of Object.entries(data.vars)) {
      sliver.style.setProperty(k, v);

      // Update display
      if (k === '--aether-state') document.getElementById('psi-var-state').textContent = v;
      if (k === '--aether-view-complexity') document.getElementById('psi-var-complexity').textContent = v;
      if (k === '--aether-confidence') document.getElementById('psi-var-confidence').textContent = v;
      if (k === '--aether-sentiment') document.getElementById('psi-var-sentiment').textContent = v;
    }
  }

  // Apply phase
  if (data.phase) {
    sliver.dataset.aetherPhase = data.phase;
  }

  // Apply content
  if (data.content) {
    sliver.querySelector('[data-aether-slot="answer"]').textContent = data.content;
  }

  // Update confidence display
  if (data.meta && data.meta.aec_score !== null) {
    sliver.querySelector('[data-aether-slot="confidence"]').textContent = Math.round(data.meta.aec_score * 100) + '%';
  }

  // Log event
  const log = document.getElementById('psi-event-log');
  const logEntry = document.createElement('div');
  logEntry.className = 'mb-8';
  logEntry.innerHTML = `<span class="text-cyan">${data.phase}</span> <span class="text-dim">${new Date().toLocaleTimeString()}</span>`;
  log.insertBefore(logEntry, log.firstChild);
}

async function runPsiDemo() {
  const capsule = document.getElementById('psi-capsule').value;
  const query = document.getElementById('psi-query').value.trim();
  if (!query) {
    document.getElementById('psi-status').textContent = 'Enter a query';
    return;
  }

  const status = document.getElementById('psi-status');
  status.innerHTML = '<span class="spinner"></span> Running pipeline...';

  // Clear previous state
  const sliver = document.getElementById('psi-demo-sliver');
  sliver.dataset.aetherPhase = 'reflex';
  sliver.querySelector('[data-aether-slot="answer"]').textContent = 'Processing...';
  document.getElementById('psi-event-log').innerHTML = '';

  try {
    const res = await fetch(`/api/stream/${capsule}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse SSE events
      const lines = buffer.split('\\n');
      buffer = lines.pop(); // Keep incomplete line in buffer

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.substring(6));
            applyPsiDelta(data);
          } catch (e) {
            console.warn('PSI parse error:', e);
          }
        }
      }
    }

    status.textContent = 'Complete';
  } catch (e) {
    status.textContent = 'Error: ' + e.message;
  }
}

// Load PSI capsules when page loads
document.addEventListener('DOMContentLoaded', loadPsiCapsules);
</script>
</body>
</html>'''


# =============================================================================
# API HANDLERS
# =============================================================================

# Edge predicates to detect in KG
EDGE_PREDICATES = ['skill:avoids', 'skill:requires', 'skill:contradicts', 'skill:enables', 'skill:contains']

def get_capsules():
    """Get all capsules with metadata."""
    result = []
    if not EXAMPLES_DIR.exists():
        return result

    for capsule_dir in EXAMPLES_DIR.iterdir():
        if not capsule_dir.is_dir():
            continue
        # Skip staging directory
        if capsule_dir.name == 'staging':
            continue
        try:
            cap = Capsule(capsule_dir)
            kg = cap.files.get("kg", {})
            nodes = kg.get("@graph", [])
            qs = queue_stats(capsule_dir)
            kstats = kg_stats(kg)

            result.append({
                "folder": capsule_dir.name,
                "id": cap.id,
                "name": cap.name,
                "version": cap.version,
                "kb_size": len(cap.files.get("kb", "")),
                "kg_nodes": len(nodes),
                "kg_core": kstats.get("core", 0),
                "kg_acquired": kstats.get("acquired", 0),
                "kg_deprecated": kstats.get("deprecated", 0),
                "queue_total": qs.get("total", 0),
                "queue_pending": qs.get("pending", 0),
                "queue_integrated": qs.get("integrated", 0),
                "category": get_capsule_category(capsule_dir.name),
            })
        except Exception as e:
            result.append({"folder": capsule_dir.name, "error": str(e), "category": "Other"})

    return result


def get_kg_data(folder):
    """Get KG nodes, edges, and stats for visualization."""
    capsule_dir = EXAMPLES_DIR / folder
    if not capsule_dir.exists():
        return {"error": "Not found", "nodes": [], "edges": [], "stats": {}}

    try:
        files = get_required_files(folder)
        kg_path = capsule_dir / files["kg"]
        kg = load_kg(kg_path)
        nodes_raw = get_nodes(kg)
        stats = kg_stats(kg)

        # Build lookup tables for edge detection
        id_to_index = {}

        nodes = []
        for i, n in enumerate(nodes_raw):
            origin = n.get("aether:origin", "core")
            if origin not in ["core", "acquired", "updated", "deprecated", "provenance"]:
                origin = "core"

            node_id = n.get("@id", "")
            label = n.get("rdfs:label", node_id)
            props = {k: v for k, v in n.items() if not k.startswith("@") and not k.startswith("aether:")}

            nodes.append({
                "id": node_id,
                "label": label,
                "origin": origin,
                "properties": props,
            })

            if node_id:
                id_to_index[node_id] = i

        # Detect edges using skill: predicates
        edges = []
        seen_edges = set()

        def resolve_target(value):
            """Resolve a value to a node index."""
            if isinstance(value, str):
                if value in id_to_index:
                    return id_to_index[value]
            elif isinstance(value, dict) and "@id" in value:
                if value["@id"] in id_to_index:
                    return id_to_index[value["@id"]]
            return None

        for i, n in enumerate(nodes_raw):
            for pred in EDGE_PREDICATES:
                if pred in n:
                    targets = n[pred]
                    if not isinstance(targets, list):
                        targets = [targets]
                    for target in targets:
                        target_idx = resolve_target(target)
                        if target_idx is not None and target_idx != i:
                            edge_key = (i, target_idx, pred)
                            if edge_key not in seen_edges:
                                seen_edges.add(edge_key)
                                edges.append({
                                    "source": i,
                                    "target": target_idx,
                                    "predicate": pred
                                })

        return {"nodes": nodes, "edges": edges, "stats": stats}
    except Exception as e:
        return {"error": str(e), "nodes": [], "edges": [], "stats": {}}


def run_aec_verify(data):
    """Run AEC verification."""
    capsule_folder = data.get("capsule", "")
    text = data.get("text", "")

    capsule_dir = EXAMPLES_DIR / capsule_folder
    if not capsule_dir.exists():
        return {"error": "Capsule not found", "score": 0, "passed": False}

    try:
        files = get_required_files(capsule_folder)
        kg_path = capsule_dir / files["kg"]
        kg = load_kg(kg_path)
        nodes = get_nodes(kg)

        # Import concept matching for typed KGs
        from aec_concept import compile_kg, has_typed_nodes
        compiled_kg = compile_kg(nodes) if has_typed_nodes(nodes) else None

        result = aec_verify(text, nodes, threshold=0.8, compiled_kg=compiled_kg)

        # Format statements with method info for display
        statements = []
        for detail in result.get("details", []):
            statements.append({
                "text": detail.get("text", ""),
                "category": detail.get("category", "persona"),
                "method": detail.get("method", ""),
                "grounded": detail.get("grounded"),
            })

        return {
            "score": result.get("score", 0),
            "threshold": result.get("threshold", 0.8),
            "passed": result.get("passed", False),
            "grounded_statements": result.get("grounded_statements", 0),
            "ungrounded_statements": result.get("ungrounded_statements", 0),
            "persona_statements": result.get("persona_statements", 0),
            "concept_applied": result.get("concept_applied", False),
            "statements": statements,
            "gaps": result.get("gaps", []),
        }
    except Exception as e:
        return {"error": str(e), "score": 0, "passed": False}


def run_orchestrate(data):
    """Run query orchestration."""
    from habitat import orchestrate
    from llm import make_llm_fn

    query = data.get("query", "")
    registry = data.get("registry", "./examples")
    dry_run = data.get("dry_run", True)

    if not query:
        return {"error": "No query provided"}

    try:
        # Create LLM function if not dry run
        llm_fn = None
        if not dry_run:
            llm_fn = make_llm_fn(provider="stub")

        result = orchestrate(
            query=query,
            registry_path=registry,
            llm_fn=llm_fn,
            dry_run=dry_run
        )
        return result
    except Exception as e:
        return {"error": str(e)}


def get_queue_data(folder):
    """Get education queue for capsule."""
    capsule_dir = EXAMPLES_DIR / folder
    if not capsule_dir.exists():
        return {"error": "Not found", "items": [], "stats": {}}

    try:
        items = get_queue(capsule_dir)
        stats = queue_stats(capsule_dir)
        return {"items": items, "stats": stats}
    except Exception as e:
        return {"error": str(e), "items": [], "stats": {}}


def get_psi_capsules():
    """Get list of capsules that can be used with PSI (all capsules for demo)."""
    result = []
    if not EXAMPLES_DIR.exists():
        return result

    for capsule_dir in EXAMPLES_DIR.iterdir():
        if not capsule_dir.is_dir() or capsule_dir.name == 'staging':
            continue
        try:
            cap = Capsule(capsule_dir)
            result.append({
                "folder": capsule_dir.name,
                "id": cap.id,
                "name": cap.name,
                "psi_enabled": cap.psi_enabled,
                "has_psi_file": cap.psi is not None,
            })
        except Exception:
            pass

    return result


def run_tests():
    """Run exhaustive tests and return results."""
    test_script = ROOT / "tests" / "test_exhaustive.py"
    if not test_script.exists():
        return {"error": "Test script not found", "total": 0, "passed": 0, "tests": []}

    try:
        result = subprocess.run(
            [sys.executable, str(test_script)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(ROOT)
        )

        # Parse output
        output = result.stdout + result.stderr
        total = 0
        passed = 0

        # Extract counts from output
        for line in output.split('\n'):
            if line.startswith('Total:'):
                try:
                    total = int(line.split(':')[1].strip().split()[0])
                except:
                    pass
            if line.startswith('Passed:'):
                try:
                    passed = int(line.split(':')[1].strip())
                except:
                    pass

        # Try to read report file
        report_path = ROOT / "IGNORE" / "daily" / f"AETHER_SYSTEM_REPORT_{datetime.now().strftime('%Y-%m-%d')}.md"
        tests = []

        if report_path.exists():
            content = report_path.read_text(encoding="utf-8")
            current_category = "other"

            for line in content.split('\n'):
                if line.startswith('### ') and 'Tests' in line:
                    current_category = line.replace('###', '').replace('Tests', '').strip().lower()
                elif '|' in line and 'PASS' in line or 'FAIL' in line:
                    parts = [p.strip() for p in line.split('|') if p.strip()]
                    if len(parts) >= 4:
                        tests.append({
                            "name": parts[0],
                            "expected": parts[1] if len(parts) > 1 else "",
                            "actual": parts[2] if len(parts) > 2 else "",
                            "status": parts[3] if len(parts) > 3 else "",
                            "category": current_category,
                        })

        return {"total": total, "passed": passed, "tests": tests, "output": output[:2000]}
    except subprocess.TimeoutExpired:
        return {"error": "Test timeout", "total": 0, "passed": 0, "tests": []}
    except Exception as e:
        return {"error": str(e), "total": 0, "passed": 0, "tests": []}


def get_metrics():
    """Get codebase metrics."""
    files = {}
    total_lines = 0

    for f in ROOT.glob("*.py"):
        lines = len(f.read_text(encoding="utf-8").splitlines())
        files[f.name] = lines
        total_lines += lines

    tests_dir = ROOT / "tests"
    if tests_dir.exists():
        for f in tests_dir.glob("*.py"):
            lines = len(f.read_text(encoding="utf-8").splitlines())
            files[f"tests/{f.name}"] = lines
            total_lines += lines

    return {
        "total_files": len(files),
        "total_lines": total_lines,
        "files": files,
    }


# =============================================================================
# HTTP SERVER
# =============================================================================

STATIC_DIR = ROOT / "static"

# MIME types for static files
MIME_TYPES = {
    ".js": "application/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".json": "application/json",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"  {args[0]}")  # Log requests

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def send_html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def send_static(self, filepath):
        """Serve a static file."""
        if not filepath.exists():
            self.send_response(404)
            self.end_headers()
            return
        ext = filepath.suffix.lower()
        mime = MIME_TYPES.get(ext, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(filepath.read_bytes())

    def send_sse_headers(self):
        """Send headers for SSE streaming."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path.rstrip('/')

        if path == "/" or path == "":
            self.send_html(HTML_TEMPLATE)
        elif path.startswith("/static/"):
            # Serve static files
            filename = path.replace("/static/", "")
            filepath = STATIC_DIR / filename
            self.send_static(filepath)
        elif path == "/api/capsules":
            self.send_json(get_capsules())
        elif path.startswith("/api/kg/"):
            folder = path.replace("/api/kg/", "").strip('/')
            print(f"[API] GET /api/kg/{folder}")
            self.send_json(get_kg_data(folder))
        elif path.startswith("/api/queue/"):
            folder = path.replace("/api/queue/", "").strip('/')
            self.send_json(get_queue_data(folder))
        elif path.startswith("/api/stream/") and "/query" not in path:
            # SSE stream endpoint
            agent_id = path.replace("/api/stream/", "").strip('/')
            self.handle_sse_stream(agent_id)
        elif path == "/api/test":
            self.send_json(run_tests())
        elif path == "/api/metrics":
            self.send_json(get_metrics())
        elif path == "/api/psi-capsules":
            # List PSI-enabled capsules
            self.send_json(get_psi_capsules())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/aec":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            try:
                data = json.loads(body)
                self.send_json(run_aec_verify(data))
            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON"}, 400)
        elif path == "/api/orchestrate":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            try:
                data = json.loads(body)
                self.send_json(run_orchestrate(data))
            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON"}, 400)
        elif path == "/api/chat":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            try:
                data = json.loads(body)
                capsule_folder = data.get("capsule", "")
                query = data.get("query", "")
                
                capsule_dir = EXAMPLES_DIR / capsule_folder
                if not capsule_dir.exists():
                    self.send_json({"error": "Capsule not found"}, 404)
                    return
                
                from llm import make_llm_fn
                # Fallback to stub if no key
                api_key = os.environ.get("ANTHROPIC_API_KEY")
                provider = "anthropic" if api_key else "stub"
                llm_fn = make_llm_fn(provider=provider)
                
                cap = Capsule(capsule_dir, llm_fn=llm_fn)
                result = cap.run(query)
                self.send_json(result)
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
        elif "/api/stream/" in path and "/query" in path:
            # PSI query endpoint - run pipeline and stream events
            agent_id = path.replace("/api/stream/", "").replace("/query", "").strip('/')
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            try:
                data = json.loads(body)
                self.handle_psi_query(agent_id, data)
            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON"}, 400)
        else:
            self.send_response(404)
            self.end_headers()

    def handle_sse_stream(self, agent_id):
        """Handle SSE stream connection for an agent."""
        # Find capsule
        capsule_dir = None
        for item in EXAMPLES_DIR.iterdir():
            if item.is_dir() and agent_id in item.name:
                capsule_dir = item
                break

        if not capsule_dir:
            self.send_json({"error": "Agent not found"}, 404)
            return

        try:
            cap = Capsule(capsule_dir)
            if not cap.psi_enabled:
                self.send_json({"error": "Agent not PSI-enabled"}, 400)
                return

            # Send SSE headers
            self.send_sse_headers()

            # Send initial snapshot if reconnecting
            last_event_id = self.headers.get("Last-Event-ID")
            if last_event_id and cap._emitter:
                self.wfile.write(cap._emitter.snapshot().encode())
                self.wfile.flush()

            # Send heartbeat (single event for now - real impl would loop)
            if cap._emitter:
                self.wfile.write(cap._emitter.heartbeat().encode())
                self.wfile.flush()

        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def handle_psi_query(self, agent_id, data):
        """Handle PSI query - run pipeline and stream events in real-time."""
        import time
        query = data.get("query", "")
        if not query:
            self.send_json({"error": "No query provided"}, 400)
            return

        # Find capsule
        capsule_dir = None
        for item in EXAMPLES_DIR.iterdir():
            if item.is_dir() and agent_id in item.name:
                capsule_dir = item
                break

        if not capsule_dir:
            self.send_json({"error": "Agent not found"}, 404)
            return

        try:
            from llm import make_llm_fn
            from psi import AetherEmitter, _detect_sentiment

            llm_fn = make_llm_fn(provider="stub")
            cap = Capsule(capsule_dir, llm_fn=llm_fn)

            # Create emitter for streaming
            emitter = AetherEmitter(cap.name, f"#aether-{cap.path.name}")

            # Send SSE headers FIRST (before pipeline runs)
            self.send_sse_headers()

            # Initialize context
            ctx = {
                "input": query,
                "distilled": {},
                "augmented": {},
                "generated": "",
                "review": {},
                "meta": {"capsule_id": cap.id, "version": cap.version},
                "telemetry": {"start": time.time(), "stages": {}},
            }

            cfg = cap.files["definition"].get("pipeline", {})

            # Stage 1: Distill → emit reflex immediately
            if cfg.get("distill", {}).get("enabled", True):
                ctx = cap.distill(ctx)
                event = emitter.pulse(
                    "reflex",
                    {"--aether-view-complexity": "0.2", "--aether-confidence": "0"}
                )
                self.wfile.write(event.encode())
                self.wfile.flush()

            # Stage 2: Augment → emit deliberation immediately
            if cfg.get("augment", {}).get("enabled", True):
                ctx = cap.augment(ctx)
                event = emitter.pulse(
                    "deliberation",
                    {"--aether-view-complexity": "0.4"}
                )
                self.wfile.write(event.encode())
                self.wfile.flush()

            # Stage 3: Generate → emit deliberation (mid) immediately
            if cfg.get("generate", {}).get("enabled", True):
                ctx = cap.generate(ctx)
                event = emitter.pulse(
                    "deliberation",
                    {"--aether-view-complexity": "0.7"}
                )
                self.wfile.write(event.encode())
                self.wfile.flush()

            # Stage 4: Review → emit complete/ghost immediately
            if cfg.get("review", {}).get("enabled", True):
                ctx = cap.review(ctx)
                review = ctx.get("review", {})
                aec_data = review.get("aec", {})
                aec_score = aec_data.get("score", 0)
                aec_passed = review.get("passed", False)
                is_ghost = review.get("ghost", False)
                response = ctx.get("generated", "")

                if aec_passed and not is_ghost:
                    event = emitter.pulse(
                        "complete",
                        {
                            "--aether-view-complexity": "1.0",
                            "--aether-confidence": str(round(aec_score, 2)),
                            "--aether-sentiment": _detect_sentiment(response),
                        },
                        content=response,
                        aec_score=aec_score,
                    )
                else:
                    event = emitter.pulse(
                        "ghost",
                        {
                            "--aether-view-complexity": "0.1",
                            "--aether-confidence": "0",
                            "--aether-sentiment": "negative",
                        },
                        content=None,
                        aec_score=aec_score,
                        reason=f"AEC score {aec_score:.2f} below threshold" if aec_score else "Verification failed",
                    )
                self.wfile.write(event.encode())
                self.wfile.flush()

            # Send completion event
            completion = f"event: aether.complete\ndata: {json.dumps({'status': 'done', 'response': ctx.get('generated', ''), 'aec_score': aec_score, 'passed': aec_passed})}\n\n"
            self.wfile.write(completion.encode())
            self.wfile.flush()

        except Exception as e:
            # If headers already sent, emit error as SSE event
            try:
                error_event = f"event: aether.error\ndata: {json.dumps({'error': str(e)})}\n\n"
                self.wfile.write(error_event.encode())
                self.wfile.flush()
            except:
                self.send_json({"error": str(e)}, 500)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def main():
    parser = argparse.ArgumentParser(description="AETHER Dashboard")
    parser.add_argument("--port", type=int, default=8864, help="Port (default: 8864)")
    args = parser.parse_args()

    server = HTTPServer(("", args.port), DashboardHandler)
    url = f"http://localhost:{args.port}"

    print(f"\n  AETHER DASHBOARD")
    print(f"  ================")
    print(f"  Running at: {url}")
    print(f"  Press Ctrl+C to stop\n")

    # Open browser
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
