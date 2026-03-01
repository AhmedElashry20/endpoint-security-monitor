#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║     Live Monitor Dashboard - لوحة المراقبة المباشرة          ║
║     سيرفر مركزي يعرض بث مباشر من أجهزة الموظفين             ║
║     يشتغل على جهاز المسؤول (الأدمن)                          ║
╚══════════════════════════════════════════════════════════════╝

طريقة التشغيل:
    pip install flask flask-socketio
    python dashboard_server.py

ثم افتح المتصفح على: http://localhost:5000
"""

import os
import sys
import json
import time
import base64
import threading
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# ============================================
#   تثبيت المكتبات تلقائي
# ============================================
def install_deps():
    import subprocess
    deps = ["flask", "flask-socketio", "gevent", "gevent-websocket"]
    for dep in deps:
        try:
            __import__(dep.replace("-", "_"))
        except ImportError:
            print(f"[i] Installing {dep}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep, "--quiet"])

install_deps()

from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit

# ============================================
#   Server Configuration
# ============================================
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000
SECRET_KEY = "change-this-to-a-strong-secret-key"

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*", max_http_buffer_size=10 * 1024 * 1024,
                    ping_timeout=30, ping_interval=10, async_mode='threading')

# ============================================
#   Connected Agents Storage
# ============================================
connected_agents = {}  # {agent_id: {info, last_frame, last_seen, ...}}
alert_history = []     # [{timestamp, agent, app, ...}]
agent_sockets = {}     # {sid: agent_id}
access_requests = []   # [{request_id, agent_id, app_name, employee, status}]

# ============================================
#   Dashboard HTML
# ============================================
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🛡️ لوحة المراقبة المباشرة</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.4/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
            background: #0a0e17;
            color: #e0e0e0;
            min-height: 100vh;
        }

        /* Header */
        .header {
            background: linear-gradient(135deg, #1a1f35, #0d1117);
            border-bottom: 1px solid #30363d;
            padding: 15px 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header h1 {
            font-size: 20px;
            color: #58a6ff;
        }

        .header-stats {
            display: flex;
            gap: 20px;
        }

        .stat-badge {
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: bold;
        }

        .stat-online { background: rgba(46, 160, 67, 0.2); color: #3fb950; border: 1px solid #23883060; }
        .stat-alert { background: rgba(248, 81, 73, 0.2); color: #f85149; border: 1px solid #f8514960; animation: pulse 2s infinite; }
        .stat-total { background: rgba(88, 166, 255, 0.2); color: #58a6ff; border: 1px solid #58a6ff60; }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }

        /* Main Content */
        .main {
            display: flex;
            height: calc(100vh - 60px);
        }

        /* Sidebar */
        .sidebar {
            width: 300px;
            background: #0d1117;
            border-left: 1px solid #30363d;
            overflow-y: auto;
            flex-shrink: 0;
        }

        .sidebar-title {
            padding: 15px;
            font-size: 14px;
            color: #8b949e;
            border-bottom: 1px solid #21262d;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .agent-card {
            padding: 12px 15px;
            border-bottom: 1px solid #21262d;
            cursor: pointer;
            transition: background 0.2s;
        }

        .agent-card:hover { background: #161b22; }
        .agent-card.active { background: #1f2937; border-right: 3px solid #58a6ff; }
        .agent-card.alerting { background: #1c0d0d; border-right: 3px solid #f85149; }

        .agent-name {
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 4px;
        }

        .agent-info {
            font-size: 11px;
            color: #8b949e;
        }

        .agent-status {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-left: 6px;
        }

        .status-online { background: #3fb950; box-shadow: 0 0 6px #3fb95080; }
        .status-streaming { background: #f85149; box-shadow: 0 0 6px #f8514980; animation: pulse 1s infinite; }
        .status-offline { background: #484f58; }

        .alert-badge {
            display: inline-block;
            background: #f85149;
            color: white;
            font-size: 10px;
            padding: 2px 8px;
            border-radius: 10px;
            margin-right: 5px;
        }

        /* Viewer Area */
        .viewer {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: #0a0e17;
        }

        .viewer-header {
            padding: 10px 20px;
            background: #161b22;
            border-bottom: 1px solid #30363d;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .viewer-title {
            font-size: 16px;
            color: #c9d1d9;
        }

        .live-indicator {
            display: flex;
            align-items: center;
            gap: 6px;
            color: #f85149;
            font-weight: bold;
            font-size: 13px;
        }

        .live-dot {
            width: 10px;
            height: 10px;
            background: #f85149;
            border-radius: 50%;
            animation: pulse 1s infinite;
        }

        .stream-container {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 15px;
            position: relative;
        }

        #live-stream {
            max-width: 100%;
            max-height: 100%;
            border-radius: 8px;
            box-shadow: 0 0 30px rgba(0,0,0,0.5);
        }

        .no-stream {
            text-align: center;
            color: #484f58;
        }

        .no-stream-icon { font-size: 60px; margin-bottom: 15px; }
        .no-stream-text { font-size: 16px; }

        /* Activity Panel */
        .activity-panel {
            height: 200px;
            background: #0d1117;
            border-top: 1px solid #30363d;
            overflow-y: auto;
            padding: 10px 20px;
        }

        .activity-panel h3 {
            font-size: 13px;
            color: #8b949e;
            margin-bottom: 8px;
            text-transform: uppercase;
        }

        .activity-item {
            padding: 6px 0;
            border-bottom: 1px solid #21262d;
            font-size: 12px;
            display: flex;
            gap: 10px;
        }

        .activity-time { color: #484f58; min-width: 70px; }
        .activity-text { color: #c9d1d9; }

        .severity-critical { color: #f85149; }
        .severity-high { color: #d29922; }
        .severity-medium { color: #58a6ff; }

        /* Multi-view grid */
        .multi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 10px;
            padding: 15px;
            flex: 1;
            overflow-y: auto;
        }

        .grid-cell {
            background: #161b22;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #30363d;
            cursor: pointer;
            transition: border-color 0.2s;
        }

        .grid-cell:hover { border-color: #58a6ff; }
        .grid-cell.alerting { border-color: #f85149; box-shadow: 0 0 10px rgba(248,81,73,0.2); }

        .grid-cell-header {
            padding: 8px 12px;
            background: #21262d;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
        }

        .grid-cell img {
            width: 100%;
            display: block;
        }

        /* View toggle */
        .view-toggle {
            display: flex;
            gap: 5px;
        }

        .view-btn {
            padding: 5px 12px;
            border: 1px solid #30363d;
            background: transparent;
            color: #8b949e;
            border-radius: 5px;
            cursor: pointer;
            font-size: 12px;
        }

        .view-btn.active { background: #58a6ff; color: white; border-color: #58a6ff; }

        /* Sound toggle */
        .sound-btn {
            padding: 5px 10px;
            border: 1px solid #30363d;
            background: transparent;
            color: #8b949e;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }
        .sound-btn.active { color: #f85149; }
    </style>
</head>
<body>

    <!-- Header -->
    <div class="header">
        <h1>🛡️ لوحة المراقبة المباشرة - Endpoint Security Monitor</h1>
        <div class="header-stats">
            <span class="stat-badge stat-total" id="total-count">الأجهزة: 0</span>
            <span class="stat-badge stat-online" id="online-count">متصل: 0</span>
            <span class="stat-badge stat-alert" id="alert-count" style="display:none">⚠️ تنبيه: 0</span>
            <div class="view-toggle">
                <button class="view-btn active" onclick="setView('single')" id="btn-single">شاشة واحدة</button>
                <button class="view-btn" onclick="setView('multi')" id="btn-multi">عرض متعدد</button>
            </div>
            <button class="sound-btn" id="sound-btn" onclick="toggleSound()" title="صوت التنبيه">🔔</button>
        </div>
    </div>

    <!-- Access Request Modal -->
    <div id="request-modal" style="display:none; position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.8); z-index:999; display:none; align-items:center; justify-content:center;">
        <div style="background:#1a1f35; border:2px solid #f85149; border-radius:12px; padding:25px; max-width:500px; width:90%; animation: slideIn 0.3s;">
            <h2 style="color:#f85149; margin:0 0 15px; text-align:center;">🚨 طلب وصول جديد</h2>
            <div id="request-details" style="background:#0d1117; padding:15px; border-radius:8px; margin-bottom:15px;">
            </div>
            <div style="display:flex; gap:10px; margin-bottom:10px;">
                <label style="color:#8b949e; font-size:13px;">مدة الموافقة:</label>
                <select id="approve-duration" style="background:#21262d; color:white; border:1px solid #30363d; border-radius:5px; padding:5px 10px;">
                    <option value="15">15 دقيقة</option>
                    <option value="30" selected>30 دقيقة</option>
                    <option value="60">ساعة</option>
                    <option value="120">ساعتين</option>
                    <option value="480">يوم عمل (8 ساعات)</option>
                </select>
            </div>
            <div style="display:flex; gap:10px; justify-content:center; margin-top:15px;">
                <button onclick="approveRequest()" style="background:#2ea043; color:white; border:none; padding:10px 30px; border-radius:8px; cursor:pointer; font-size:15px; font-weight:bold;">✅ موافقة</button>
                <button onclick="denyRequest()" style="background:#f85149; color:white; border:none; padding:10px 30px; border-radius:8px; cursor:pointer; font-size:15px; font-weight:bold;">❌ رفض</button>
                <button onclick="closeModal()" style="background:#30363d; color:#8b949e; border:none; padding:10px 20px; border-radius:8px; cursor:pointer; font-size:13px;">إغلاق</button>
            </div>
        </div>
    </div>

    <!-- Pending Requests Bar -->
    <div id="requests-bar" style="display:none; background:linear-gradient(135deg, #1c0d0d, #2d1b1b); border-bottom:1px solid #f8514940; padding:8px 25px; position:sticky; top:60px; z-index:99;">
        <div style="display:flex; align-items:center; gap:10px; overflow-x:auto;">
            <span style="color:#f85149; font-weight:bold; white-space:nowrap;">📋 طلبات معلقة:</span>
            <div id="requests-list" style="display:flex; gap:8px; flex-wrap:nowrap;"></div>
        </div>
    </div>

    <div class="main">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-title">الأجهزة المتصلة</div>
            <div id="agents-list"></div>
        </div>

        <!-- Single View -->
        <div class="viewer" id="single-view">
            <div class="viewer-header">
                <span class="viewer-title" id="viewer-title">اختر جهاز من القائمة</span>
                <div class="live-indicator" id="live-badge" style="display:none">
                    <div class="live-dot"></div>
                    <span>LIVE</span>
                </div>
            </div>
            <div class="stream-container" id="stream-container">
                <div class="no-stream">
                    <div class="no-stream-icon">🖥️</div>
                    <div class="no-stream-text">اختر جهاز من القائمة لمشاهدة البث المباشر</div>
                    <div class="no-stream-text" style="margin-top:8px; font-size:13px; color:#30363d;">
                        البث يبدأ تلقائياً عند اكتشاف برنامج تحكم عن بُعد
                    </div>
                </div>
            </div>
            <div class="activity-panel" id="activity-panel">
                <h3>📋 سجل النشاط</h3>
                <div id="activity-log"></div>
            </div>

            <!-- Admin Tools Panel -->
            <div style="background:#0d1117; border-top:1px solid #30363d; padding:10px 15px;">
                <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">

                    <!-- إرسال رسالة -->
                    <input id="admin-msg-input" type="text" placeholder="اكتب رسالة للموظف..."
                        style="flex:1; min-width:200px; background:#21262d; border:1px solid #30363d; color:#c9d1d9; padding:7px 12px; border-radius:6px; font-size:13px;"
                        onkeydown="if(event.key==='Enter') sendMessage()">
                    <label style="color:#8b949e; font-size:11px; display:flex; align-items:center; gap:3px;">
                        <input type="checkbox" id="msg-fullscreen"> ملء الشاشة
                    </label>
                    <button onclick="sendMessage()" style="background:#58a6ff; color:white; border:none; padding:7px 14px; border-radius:6px; cursor:pointer; font-size:12px; font-weight:bold;">📩 إرسال</button>

                    <div style="width:1px; height:25px; background:#30363d;"></div>

                    <!-- تجميد -->
                    <input id="freeze-msg" type="text" placeholder="رسالة التجميد (اختياري)" style="width:160px; background:#21262d; border:1px solid #30363d; color:#c9d1d9; padding:7px 10px; border-radius:6px; font-size:12px;">
                    <button onclick="freezeDevice()" style="background:#f85149; color:white; border:none; padding:7px 12px; border-radius:6px; cursor:pointer; font-size:12px;">🔒 تجميد</button>
                    <button onclick="unfreezeDevice()" style="background:#2ea043; color:white; border:none; padding:7px 12px; border-radius:6px; cursor:pointer; font-size:12px;">🔓 فك</button>

                    <div style="width:1px; height:25px; background:#30363d;"></div>

                    <!-- وضع المسؤول -->
                    <select id="bypass-duration" style="background:#21262d; color:#c9d1d9; border:1px solid #30363d; border-radius:5px; padding:5px; font-size:12px;">
                        <option value="30">30 دقيقة</option>
                        <option value="60">ساعة</option>
                        <option value="120">ساعتين</option>
                    </select>
                    <button onclick="activateAdminBypass()" style="background:#d29922; color:white; border:none; padding:7px 12px; border-radius:6px; cursor:pointer; font-size:12px;">👑 أنا الداخل</button>
                    <button onclick="deactivateAdminBypass()" style="background:#484f58; color:white; border:none; padding:7px 12px; border-radius:6px; cursor:pointer; font-size:12px;">إيقاف</button>

                    <div style="width:1px; height:25px; background:#30363d;"></div>

                    <!-- كيبورد -->
                    <button onclick="toggleKeystrokePanel()" style="background:#6e40c9; color:white; border:none; padding:7px 12px; border-radius:6px; cursor:pointer; font-size:12px;">⌨️ الكيبورد</button>

                    <div style="width:1px; height:25px; background:#30363d;"></div>

                    <!-- إزالة عن بُعد -->
                    <button onclick="showUninstallDialog()" style="background:#6e7681; color:white; border:none; padding:7px 12px; border-radius:6px; cursor:pointer; font-size:12px;">🗑️ إزالة</button>
                </div>
            </div>

            <!-- Keystroke Panel -->
            <div id="keystroke-container" style="display:none; background:#0a0e17; border-top:1px solid #6e40c9;">
                <div style="padding:8px 15px; background:#161b22; display:flex; justify-content:space-between; align-items:center;">
                    <h3 style="font-size:13px; color:#d2a8ff; margin:0;">⌨️ الكيبورد المباشر (كل ضغطة + الباسوردات)</h3>
                    <span style="font-size:11px; color:#f85149;">🔴 مباشر</span>
                </div>
                <div id="keystroke-log" style="height:150px; overflow-y:auto; padding:10px 15px; font-family:monospace;">
                    <div style="color:#484f58; padding:10px;">اختر جهاز لمشاهدة الكيبورد</div>
                </div>
            </div>
        </div>

        <!-- Multi View -->
        <div class="multi-grid" id="multi-view" style="display:none">
        </div>
    </div>

    <!-- Alert Sound -->
    <audio id="alert-sound" preload="auto">
        <source src="data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQ==" type="audio/wav">
    </audio>

    <script>
        const socket = io();
        let agents = {};
        let selectedAgent = null;
        let currentView = 'single';
        let soundEnabled = true;
        let alertCount = 0;

        // ════════════════════════════════
        //   Socket Events
        // ════════════════════════════════

        socket.on('connect', () => {
            console.log('Connected to dashboard server');
            addActivity('متصل بالسيرفر', 'medium');
        });

        // وصول فريم جديد من الوكيل
        socket.on('screen_frame', (data) => {
            const agentId = data.agent_id;

            // تحديث بيانات الوكيل
            if (!agents[agentId]) {
                agents[agentId] = {};
            }
            agents[agentId].lastFrame = data.frame;
            agents[agentId].lastSeen = new Date();
            agents[agentId].streaming = true;
            agents[agentId].detected_app = data.detected_app || '';
            agents[agentId].hostname = data.hostname || agentId;
            agents[agentId].os = data.os || '';
            agents[agentId].user = data.user || '';
            agents[agentId].active_window = data.active_window || '';

            // تحديث العرض
            if (currentView === 'single' && selectedAgent === agentId) {
                updateSingleView(data);
            }
            updateMultiView(agentId, data);
            updateAgentsList();
        });

        // تسجيل وكيل جديد
        socket.on('agent_connected', (data) => {
            const agentId = data.agent_id;
            agents[agentId] = {
                hostname: data.hostname,
                os: data.os,
                user: data.user,
                ip: data.ip,
                streaming: false,
                lastSeen: new Date()
            };
            updateAgentsList();
            addActivity(`جهاز متصل: ${data.hostname} (${data.ip})`, 'medium');
        });

        // نبض حياة من الوكيل (يحدّث آخر ظهور)
        socket.on('agent_heartbeat', (data) => {
            const agentId = data.agent_id;
            if (agents[agentId]) {
                agents[agentId].lastSeen = new Date();
            }
            updateAgentsList();
        });

        // وكيل قطع الاتصال
        socket.on('agent_disconnected', (data) => {
            if (agents[data.agent_id]) {
                agents[data.agent_id].streaming = false;
            }
            updateAgentsList();
            addActivity(`جهاز انقطع: ${data.agent_id}`, 'high');
        });

        // تنبيه جديد
        socket.on('alert', (data) => {
            alertCount++;
            updateAlertBadge();
            addActivity(`🚨 ${data.message}`, 'critical');
            playAlertSound();

            // إضافة تنبيه بصري
            if (agents[data.agent_id]) {
                agents[data.agent_id].alerting = true;
                setTimeout(() => {
                    if (agents[data.agent_id]) agents[data.agent_id].alerting = false;
                    updateAgentsList();
                }, 30000);
            }
            updateAgentsList();
        });

        // نشاط النافذة
        socket.on('window_activity', (data) => {
            if (selectedAgent === data.agent_id) {
                addActivity(`🖥️ ${data.hostname}: ${data.window_title}`, 'medium');
            }
        });

        // ════════════════════════════════
        //   UI Functions
        // ════════════════════════════════

        function updateSingleView(data) {
            const container = document.getElementById('stream-container');
            let img = document.getElementById('live-stream');

            if (!img) {
                container.innerHTML = '<img id="live-stream" />';
                img = document.getElementById('live-stream');
            }

            img.src = 'data:image/jpeg;base64,' + data.frame;

            document.getElementById('viewer-title').textContent =
                `${data.hostname} - ${data.detected_app || 'متصل'} | ${data.active_window || ''}`;
            document.getElementById('live-badge').style.display = 'flex';
        }

        function updateMultiView(agentId, data) {
            const grid = document.getElementById('multi-view');
            let cell = document.getElementById('grid-' + agentId);

            if (!cell) {
                cell = document.createElement('div');
                cell.id = 'grid-' + agentId;
                cell.className = 'grid-cell';
                cell.onclick = () => { selectAgent(agentId); setView('single'); };
                cell.innerHTML = `
                    <div class="grid-cell-header">
                        <span class="cell-name"></span>
                        <span class="cell-app"></span>
                    </div>
                    <img class="cell-img" />
                `;
                grid.appendChild(cell);
            }

            cell.querySelector('.cell-img').src = 'data:image/jpeg;base64,' + data.frame;
            cell.querySelector('.cell-name').textContent = data.hostname || agentId;
            cell.querySelector('.cell-app').innerHTML =
                data.detected_app ? `<span class="alert-badge">${data.detected_app}</span>` : '🟢 متصل';

            if (agents[agentId]?.alerting) {
                cell.classList.add('alerting');
            } else {
                cell.classList.remove('alerting');
            }
        }

        function updateAgentsList() {
            const list = document.getElementById('agents-list');
            let html = '';
            let onlineCount = 0;
            let streamingCount = 0;

            for (const [id, agent] of Object.entries(agents)) {
                const isOnline = agent.lastSeen && (new Date() - agent.lastSeen < 30000);
                const isStreaming = agent.streaming && isOnline;
                const isAlerting = agent.alerting;

                if (isOnline) onlineCount++;
                if (isStreaming) streamingCount++;

                let statusClass = 'status-offline';
                if (isStreaming) statusClass = 'status-streaming';
                else if (isOnline) statusClass = 'status-online';

                let cardClass = 'agent-card';
                if (selectedAgent === id) cardClass += ' active';
                if (isAlerting) cardClass += ' alerting';

                html += `
                    <div class="${cardClass}" onclick="selectAgent('${id}')">
                        <div class="agent-name">
                            <span class="agent-status ${statusClass}"></span>
                            ${agent.hostname || id}
                            ${agent.detected_app ? `<span class="alert-badge">${agent.detected_app}</span>` : ''}
                        </div>
                        <div class="agent-info">
                            ${agent.os || ''} | ${agent.user || ''} | ${agent.ip || ''}
                            ${agent.active_window ? '<br>📱 ' + (agent.active_window || '').substring(0, 40) : ''}
                        </div>
                    </div>
                `;
            }

            if (!html) {
                html = '<div style="padding:20px; text-align:center; color:#484f58;">لا توجد أجهزة متصلة<br><br><span style="font-size:12px;">شغّل الوكيل على أجهزة الموظفين</span></div>';
            }

            list.innerHTML = html;

            document.getElementById('total-count').textContent = `الأجهزة: ${Object.keys(agents).length}`;
            document.getElementById('online-count').textContent = `متصل: ${onlineCount}`;
        }

        function selectAgent(agentId) {
            selectedAgent = agentId;
            updateAgentsList();

            if (agents[agentId]?.lastFrame) {
                updateSingleView({
                    frame: agents[agentId].lastFrame,
                    hostname: agents[agentId].hostname,
                    detected_app: agents[agentId].detected_app,
                    active_window: agents[agentId].active_window
                });
            }

            // طلب بث من هذا الوكيل
            socket.emit('request_stream', { agent_id: agentId });
        }

        function setView(view) {
            currentView = view;
            document.getElementById('single-view').style.display = view === 'single' ? 'flex' : 'none';
            document.getElementById('multi-view').style.display = view === 'multi' ? 'grid' : 'none';
            document.getElementById('btn-single').className = 'view-btn' + (view === 'single' ? ' active' : '');
            document.getElementById('btn-multi').className = 'view-btn' + (view === 'multi' ? ' active' : '');
        }

        function addActivity(text, severity) {
            const log = document.getElementById('activity-log');
            const time = new Date().toLocaleTimeString('ar-SA');
            const item = document.createElement('div');
            item.className = 'activity-item';
            item.innerHTML = `
                <span class="activity-time">${time}</span>
                <span class="activity-text severity-${severity}">${text}</span>
            `;
            log.insertBefore(item, log.firstChild);
            if (log.children.length > 100) log.removeChild(log.lastChild);
        }

        function updateAlertBadge() {
            const badge = document.getElementById('alert-count');
            badge.style.display = alertCount > 0 ? 'inline' : 'none';
            badge.textContent = `⚠️ تنبيه: ${alertCount}`;
        }

        function toggleSound() {
            soundEnabled = !soundEnabled;
            document.getElementById('sound-btn').className = 'sound-btn' + (soundEnabled ? ' active' : '');
            document.getElementById('sound-btn').textContent = soundEnabled ? '🔔' : '🔕';
        }

        function playAlertSound() {
            if (!soundEnabled) return;
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.frequency.value = 800;
                gain.gain.value = 0.3;
                osc.start();
                osc.frequency.linearRampToValueAtTime(400, ctx.currentTime + 0.5);
                gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.5);
                setTimeout(() => osc.stop(), 600);
            } catch(e) {}
        }

        // تحديث الحالة كل 5 ثواني
        setInterval(updateAgentsList, 5000);

        // ════════════════════════════════
        //   Access Control
        // ════════════════════════════════
        let pendingRequests = {};
        let currentRequestId = null;
        let currentRequestAgentId = null;
        let currentRequestApp = null;

        socket.on('new_access_request', (data) => {
            pendingRequests[data.request_id] = data;
            showRequestNotification(data);
            updateRequestsBar();
            playAlertSound();
            alertCount++;
            updateAlertBadge();
        });

        socket.on('request_updated', (data) => {
            if (pendingRequests[data.request_id]) {
                pendingRequests[data.request_id].status = data.status;
                if (data.status !== 'pending') {
                    delete pendingRequests[data.request_id];
                }
            }
            updateRequestsBar();
            closeModal();
        });

        function showRequestNotification(data) {
            currentRequestId = data.request_id;
            currentRequestAgentId = data.agent_id;
            currentRequestApp = data.app_name;

            const modal = document.getElementById('request-modal');
            const details = document.getElementById('request-details');

            details.innerHTML = `
                <table style="width:100%; color:#c9d1d9;">
                    <tr><td style="padding:6px; color:#8b949e; width:110px;">الموظف:</td><td style="font-weight:bold; color:#58a6ff;">${data.employee_name}</td></tr>
                    <tr><td style="padding:6px; color:#8b949e;">الرقم الوظيفي:</td><td>${data.employee_id}</td></tr>
                    <tr><td style="padding:6px; color:#8b949e;">القسم:</td><td>${data.department}</td></tr>
                    <tr><td style="padding:6px; color:#8b949e;">الجهاز:</td><td>${data.hostname}</td></tr>
                    <tr><td style="padding:6px; color:#8b949e;">البرنامج:</td><td style="color:#f85149; font-weight:bold;">${data.app_name}</td></tr>
                    <tr><td style="padding:6px; color:#8b949e;">الوقت:</td><td>${new Date(data.timestamp).toLocaleString('ar-SA')}</td></tr>
                </table>
            `;

            modal.style.display = 'flex';
        }

        function approveRequest() {
            const duration = document.getElementById('approve-duration').value;
            socket.emit('approve_access', {
                request_id: currentRequestId,
                agent_id: currentRequestAgentId,
                app_name: currentRequestApp,
                duration_minutes: parseInt(duration)
            });
            addActivity(`✅ تمت الموافقة: ${currentRequestApp} (${duration} دقيقة)`, 'medium');
            closeModal();
        }

        function denyRequest() {
            socket.emit('deny_access', {
                request_id: currentRequestId,
                agent_id: currentRequestAgentId,
                app_name: currentRequestApp
            });
            addActivity(`❌ تم الرفض: ${currentRequestApp}`, 'critical');
            closeModal();
        }

        function closeModal() {
            document.getElementById('request-modal').style.display = 'none';
        }

        function updateRequestsBar() {
            const bar = document.getElementById('requests-bar');
            const list = document.getElementById('requests-list');
            const pending = Object.values(pendingRequests).filter(r => r.status === 'pending');

            if (pending.length === 0) {
                bar.style.display = 'none';
                return;
            }

            bar.style.display = 'block';
            list.innerHTML = pending.map(r => `
                <button onclick='showRequestNotification(${JSON.stringify(r).replace(/'/g, "\\'")})'
                    style="background:#21262d; border:1px solid #f85149; color:#f85149; padding:5px 12px; border-radius:15px; cursor:pointer; white-space:nowrap; font-size:12px;">
                    ⏳ ${r.employee_name} → ${r.app_name} (${r.hostname})
                </button>
            `).join('');
        }

        function revokeAccess(agentId, appName) {
            if (confirm('هل تريد سحب الموافقة وإيقاف البرنامج فوراً؟')) {
                socket.emit('revoke_access', { agent_id: agentId, app_name: appName });
                addActivity(`🔴 تم سحب الموافقة: ${appName}`, 'critical');
            }
        }

        // ════════════════════════════════
        //   Admin Tools (رسائل، تجميد، كيبورد)
        // ════════════════════════════════
        let liveKeystrokes = {};  // {agent_id: [{time, key, window}]}

        // استقبال الكيبورد المباشر
        socket.on('live_keystrokes', (data) => {
            const agentId = data.agent_id;
            if (!liveKeystrokes[agentId]) liveKeystrokes[agentId] = [];
            data.keystrokes.forEach(k => liveKeystrokes[agentId].push(k));
            // إبقاء آخر 500
            if (liveKeystrokes[agentId].length > 500) {
                liveKeystrokes[agentId] = liveKeystrokes[agentId].slice(-500);
            }
            if (selectedAgent === agentId) updateKeystrokePanel();
        });

        // استقبال تقرير الأدلة
        socket.on('evidence_report', (data) => {
            addActivity(`📋 تقرير أدلة من ${data.hostname}: ${data.screenshot_count} صورة، ${data.keystrokes?.length || 0} ضغطة`, 'critical');
            playAlertSound();
        });

        function sendMessage() {
            if (!selectedAgent) { alert('اختر جهاز أولاً'); return; }
            const msg = document.getElementById('admin-msg-input').value.trim();
            if (!msg) return;
            const fullscreen = document.getElementById('msg-fullscreen').checked;
            socket.emit('admin_message_to_agent', {
                agent_id: selectedAgent,
                message: msg,
                fullscreen: fullscreen
            });
            document.getElementById('admin-msg-input').value = '';
            addActivity(`📩 رسالة مرسلة: ${msg.substring(0, 40)}...`, 'medium');
        }

        function freezeDevice() {
            if (!selectedAgent) { alert('اختر جهاز أولاً'); return; }
            const agentName = agents[selectedAgent]?.hostname || selectedAgent;
            if (!confirm(`هل تريد تجميد جهاز ${agentName}؟\\nسيتم إيقاف الماوس والكيبورد.`)) return;
            const msg = document.getElementById('freeze-msg').value || 'تم تجميد الجهاز بواسطة المسؤول';
            socket.emit('freeze_device_cmd', { agent_id: selectedAgent, message: msg });
            addActivity(`🔒 تم تجميد: ${agentName}`, 'critical');
        }

        function unfreezeDevice() {
            if (!selectedAgent) return;
            socket.emit('unfreeze_device_cmd', { agent_id: selectedAgent });
            addActivity(`🔓 تم فك تجميد: ${agents[selectedAgent]?.hostname || selectedAgent}`, 'medium');
        }

        function activateAdminBypass() {
            if (!selectedAgent) { alert('اختر جهاز أولاً'); return; }
            const duration = document.getElementById('bypass-duration').value;
            socket.emit('admin_bypass_cmd', {
                agent_id: selectedAgent,
                app_name: 'ALL',
                duration_minutes: parseInt(duration),
                activate: true
            });
            addActivity(`👑 وضع المسؤول: مفعّل (${duration} دقيقة)`, 'medium');
        }

        function deactivateAdminBypass() {
            if (!selectedAgent) return;
            socket.emit('admin_bypass_cmd', {
                agent_id: selectedAgent,
                app_name: 'ALL',
                activate: false
            });
            addActivity(`👑 وضع المسؤول: متوقف`, 'medium');
        }

        function updateKeystrokePanel() {
            const panel = document.getElementById('keystroke-log');
            if (!panel || !selectedAgent) return;
            const keys = liveKeystrokes[selectedAgent] || [];
            if (keys.length === 0) {
                panel.innerHTML = '<div style="color:#484f58; padding:10px;">لا توجد ضغطات مسجلة</div>';
                return;
            }
            let html = '';
            let currentWindow = '';
            keys.slice(-100).forEach(k => {
                if (k.window && k.window !== currentWindow) {
                    currentWindow = k.window;
                    html += `<div style="color:#58a6ff; font-size:11px; margin-top:8px; padding:3px 6px; background:#0d1117; border-radius:3px;">📱 ${currentWindow}</div>`;
                }
                let keyDisplay = k.key || '';
                if (keyDisplay === 'Key.space') keyDisplay = ' ';
                else if (keyDisplay === 'Key.enter') keyDisplay = '<span style="color:#f85149;"> ⏎\\n</span>';
                else if (keyDisplay === 'Key.backspace') keyDisplay = '<span style="color:#d29922;">⌫</span>';
                else if (keyDisplay === 'Key.tab') keyDisplay = '<span style="color:#8b949e;"> ⇥ </span>';
                else if (keyDisplay.startsWith('Key.')) keyDisplay = `<span style="color:#484f58;">[${keyDisplay.replace('Key.','')}]</span>`;
                else if (keyDisplay.startsWith('[CLIPBOARD]')) keyDisplay = `<span style="color:#d29922;">${keyDisplay}</span>`;
                html += keyDisplay;
            });
            panel.innerHTML = `<div style="font-family:monospace; font-size:14px; line-height:1.8; word-wrap:break-word; direction:ltr; text-align:left;">${html}</div>`;
            panel.scrollTop = panel.scrollHeight;
        }

        function toggleKeystrokePanel() {
            const panel = document.getElementById('keystroke-container');
            panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
            if (panel.style.display !== 'none') updateKeystrokePanel();
        }

        // ════════════════════════════════
        //   Remote Uninstall
        // ════════════════════════════════
        socket.on('uninstall_result', (data) => {
            if (data.success) {
                alert('✅ تمت إزالة البرنامج من ' + data.hostname);
                addActivity(`🗑️ تمت الإزالة: ${data.hostname}`, 'critical');
            } else {
                alert('❌ فشلت الإزالة: ' + (data.error || 'كلمة المرور خاطئة'));
            }
        });

        function showUninstallDialog() {
            if (!selectedAgent) { alert('اختر جهاز أولاً'); return; }
            const agentName = agents[selectedAgent]?.hostname || selectedAgent;
            const pwd = prompt(`🔐 إزالة البرنامج من: ${agentName}\n\nأدخل كلمة مرور الإزالة:`);
            if (!pwd) return;
            if (!confirm(`⚠️ هل أنت متأكد من إزالة البرنامج نهائياً من ${agentName}؟\nلا يمكن التراجع!`)) return;
            socket.emit('remote_uninstall_cmd', {
                agent_id: selectedAgent,
                password: pwd
            });
            addActivity(`🗑️ طلب إزالة: ${agentName}`, 'critical');
        }

        // ════════════════════════════════
        //   Intruder IP Tracker
        // ════════════════════════════════
        socket.on('intruder_detected', (data) => {
            playAlertSound();

            const isPrivate = data.is_private;
            const locText = isPrivate
                ? 'شبكة محلية'
                : `${data.city || '?'}, ${data.country || '?'}`;

            const msg = `🚨 مخترق! IP: ${data.intruder_ip} | ${locText} | ISP: ${data.isp || '?'} | عبر: ${data.app_name || '?'} | جهاز: ${data.hostname || '?'}`;
            addActivity(msg, 'critical');

            // عرض تنبيه كبير
            const alertDiv = document.createElement('div');
            alertDiv.style.cssText = 'position:fixed; top:0; left:0; right:0; z-index:10000; background:linear-gradient(135deg, #d32f2f, #b71c1c); color:white; padding:15px 25px; font-family:Arial; direction:rtl; animation:slideDown 0.3s; box-shadow:0 4px 20px rgba(211,47,47,0.5);';
            alertDiv.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                    <div>
                        <span style="font-size:20px;">🚨</span>
                        <strong style="font-size:16px;"> تم رصد اتصال خارجي!</strong>
                    </div>
                    <div style="display:flex; gap:20px; flex-wrap:wrap; font-size:14px;">
                        <span>📡 <strong>${data.intruder_ip}</strong></span>
                        <span>🌍 ${locText}</span>
                        <span>🏢 ${data.isp || '?'}</span>
                        <span>💻 ${data.app_name || '?'}</span>
                        <span>🖥️ ${data.hostname || '?'}</span>
                        ${data.org ? `<span>🏭 ${data.org}</span>` : ''}
                    </div>
                    <button onclick="this.parentElement.parentElement.remove()" style="background:rgba(255,255,255,0.2); color:white; border:1px solid rgba(255,255,255,0.3); padding:5px 15px; border-radius:5px; cursor:pointer; font-size:13px;">✕ إغلاق</button>
                </div>
            `;
            document.body.appendChild(alertDiv);

            // إزالة تلقائية بعد 30 ثانية
            setTimeout(() => { if (alertDiv.parentElement) alertDiv.remove(); }, 30000);

            alertCount++;
            document.getElementById('alert-count').textContent = alertCount;
        });
    </script>
</body>
</html>
"""


# ============================================
#   Flask Routes
# ============================================
@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@app.route("/api/agents")
def api_agents():
    result = {}
    for agent_id, info in connected_agents.items():
        result[agent_id] = {
            "hostname": info.get("hostname"),
            "os": info.get("os"),
            "user": info.get("user"),
            "ip": info.get("ip"),
            "streaming": info.get("streaming", False),
            "detected_app": info.get("detected_app"),
            "last_seen": info.get("last_seen"),
        }
    return jsonify(result)

@app.route("/api/alerts")
def api_alerts():
    return jsonify(alert_history[-50:])


# ============================================
#   SocketIO Events
# ============================================
@socketio.on("connect")
def handle_connect():
    print(f"[+] Client connected: {request.sid}")
    # إرسال قائمة الأجهزة المتصلة حالياً للمتصفح الجديد
    for agent_id, info in connected_agents.items():
        emit("agent_connected", {
            "agent_id": agent_id,
            "hostname": info.get("hostname", "Unknown"),
            "os": info.get("os", ""),
            "user": info.get("user", ""),
            "ip": info.get("ip", ""),
        })

@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    if sid in agent_sockets:
        agent_id = agent_sockets[sid]
        if agent_id in connected_agents:
            connected_agents[agent_id]["streaming"] = False
        socketio.emit("agent_disconnected", {"agent_id": agent_id})
        del agent_sockets[sid]
        print(f"[-] Agent disconnected: {agent_id}")

# وكيل يسجل نفسه
@socketio.on("register_agent")
def handle_register(data):
    agent_id = data.get("agent_id", request.sid)
    connected_agents[agent_id] = {
        "hostname": data.get("hostname", "Unknown"),
        "os": data.get("os", ""),
        "user": data.get("user", ""),
        "ip": request.remote_addr,
        "streaming": False,
        "last_seen": datetime.now().isoformat(),
        "sid": request.sid,
    }
    agent_sockets[request.sid] = agent_id
    socketio.emit("agent_connected", {
        "agent_id": agent_id,
        "hostname": data.get("hostname"),
        "os": data.get("os"),
        "user": data.get("user"),
        "ip": request.remote_addr,
    })
    print(f"[+] Agent registered: {agent_id} ({data.get('hostname')})")

# وكيل يرسل heartbeat (نبض حياة)
@socketio.on("heartbeat")
def handle_heartbeat(data):
    agent_id = data.get("agent_id")
    if agent_id in connected_agents:
        connected_agents[agent_id]["last_seen"] = datetime.now().isoformat()
    # تمرير للمتصفحات
    socketio.emit("agent_heartbeat", data)

# وكيل يرسل فريم
@socketio.on("screen_frame")
def handle_frame(data):
    agent_id = data.get("agent_id")
    if agent_id in connected_agents:
        connected_agents[agent_id]["streaming"] = True
        connected_agents[agent_id]["last_seen"] = datetime.now().isoformat()
        connected_agents[agent_id]["detected_app"] = data.get("detected_app", "")

    # إرسال الفريم لكل المتصفحات (الأدمن)
    socketio.emit("screen_frame", data)

# وكيل يرسل نشاط النافذة
@socketio.on("window_activity")
def handle_window_activity(data):
    socketio.emit("window_activity", data)

# وكيل يرسل تنبيه
@socketio.on("agent_alert")
def handle_alert(data):
    alert = {
        "timestamp": datetime.now().isoformat(),
        "agent_id": data.get("agent_id"),
        "hostname": data.get("hostname"),
        "message": data.get("message"),
        "severity": data.get("severity", "HIGH"),
    }
    alert_history.append(alert)
    socketio.emit("alert", {
        "agent_id": data.get("agent_id"),
        "message": f"{data.get('hostname')}: {data.get('message')}",
    })
    print(f"[!] ALERT: {alert['message']}")

# الأدمن يطلب بث من وكيل
@socketio.on("request_stream")
def handle_request_stream(data):
    agent_id = data.get("agent_id")
    if agent_id in connected_agents:
        target_sid = connected_agents[agent_id].get("sid")
        if target_sid:
            socketio.emit("start_stream", {}, to=target_sid)

# ── طلبات الوصول (Access Requests) ──

@socketio.on("access_request")
def handle_access_request(data):
    """وكيل يرسل طلب موافقة"""
    request = {
        "request_id": data.get("request_id"),
        "agent_id": data.get("agent_id"),
        "app_name": data.get("app_name"),
        "employee_name": data.get("employee_name"),
        "employee_id": data.get("employee_id"),
        "department": data.get("department"),
        "hostname": data.get("hostname"),
        "timestamp": data.get("timestamp", datetime.now().isoformat()),
        "status": "pending",
    }
    access_requests.append(request)
    # إرسال للأدمن
    socketio.emit("new_access_request", request)
    print(f"[!] ACCESS REQUEST: {data.get('employee_name')} wants to use {data.get('app_name')} on {data.get('hostname')}")

@socketio.on("approve_access")
def handle_approve(data):
    """الأدمن يوافق"""
    request_id = data.get("request_id")
    duration = data.get("duration_minutes", 30)
    agent_id = data.get("agent_id")

    # تحديث الطلب
    for req in access_requests:
        if req["request_id"] == request_id:
            req["status"] = "approved"
            req["approved_at"] = datetime.now().isoformat()
            req["duration"] = duration
            break

    # إرسال الموافقة للوكيل
    if agent_id in connected_agents:
        target_sid = connected_agents[agent_id].get("sid")
        if target_sid:
            socketio.emit("access_approved", {
                "request_id": request_id,
                "app_name": data.get("app_name"),
                "duration_minutes": duration,
            }, to=target_sid)

    socketio.emit("request_updated", {"request_id": request_id, "status": "approved", "duration": duration})
    print(f"[✓] APPROVED: {request_id} for {duration} minutes")

@socketio.on("deny_access")
def handle_deny(data):
    """الأدمن يرفض"""
    request_id = data.get("request_id")
    agent_id = data.get("agent_id")

    for req in access_requests:
        if req["request_id"] == request_id:
            req["status"] = "denied"
            break

    if agent_id in connected_agents:
        target_sid = connected_agents[agent_id].get("sid")
        if target_sid:
            socketio.emit("access_denied", {
                "request_id": request_id,
                "app_name": data.get("app_name"),
            }, to=target_sid)

    socketio.emit("request_updated", {"request_id": request_id, "status": "denied"})
    print(f"[✗] DENIED: {request_id}")

@socketio.on("revoke_access")
def handle_revoke(data):
    """الأدمن يسحب الموافقة"""
    agent_id = data.get("agent_id")
    app_name = data.get("app_name")

    if agent_id in connected_agents:
        target_sid = connected_agents[agent_id].get("sid")
        if target_sid:
            socketio.emit("revoke_access", {"app_name": app_name}, to=target_sid)

    print(f"[!] REVOKED: {app_name} from {agent_id}")

# ── أدوات المسؤول (رسائل، تجميد، وضع المسؤول) ──

@socketio.on("admin_message_to_agent")
def handle_admin_message(data):
    """المسؤول يرسل رسالة لجهاز"""
    agent_id = data.get("agent_id")
    if agent_id in connected_agents:
        target_sid = connected_agents[agent_id].get("sid")
        if target_sid:
            socketio.emit("admin_message", {
                "message": data.get("message", ""),
                "fullscreen": data.get("fullscreen", False),
            }, to=target_sid)
    print(f"[>] MESSAGE to {agent_id}: {data.get('message', '')[:50]}")

@socketio.on("freeze_device_cmd")
def handle_freeze_cmd(data):
    """المسؤول يجمّد جهاز"""
    agent_id = data.get("agent_id")
    if agent_id in connected_agents:
        target_sid = connected_agents[agent_id].get("sid")
        if target_sid:
            socketio.emit("freeze_device", {
                "message": data.get("message", "تم تجميد الجهاز بواسطة المسؤول"),
            }, to=target_sid)
    print(f"[!] FREEZE: {agent_id}")

@socketio.on("unfreeze_device_cmd")
def handle_unfreeze_cmd(data):
    """المسؤول يفك تجميد جهاز"""
    agent_id = data.get("agent_id")
    if agent_id in connected_agents:
        target_sid = connected_agents[agent_id].get("sid")
        if target_sid:
            socketio.emit("unfreeze_device", {}, to=target_sid)
    print(f"[!] UNFREEZE: {agent_id}")

@socketio.on("admin_bypass_cmd")
def handle_bypass_cmd(data):
    """المسؤول يفعّل/يلغي وضع الباي باس"""
    agent_id = data.get("agent_id")
    activate = data.get("activate", True)

    if agent_id in connected_agents:
        target_sid = connected_agents[agent_id].get("sid")
        if target_sid:
            if activate:
                socketio.emit("admin_bypass_activate", {
                    "app_name": data.get("app_name", "ALL"),
                    "admin_id": "admin",
                    "duration_minutes": data.get("duration_minutes", 60),
                }, to=target_sid)
            else:
                socketio.emit("admin_bypass_deactivate", {
                    "app_name": data.get("app_name", "ALL"),
                }, to=target_sid)

    status = "activated" if activate else "deactivated"
    print(f"[!] ADMIN BYPASS {status}: {agent_id}")

@socketio.on("live_keystrokes")
def handle_live_keystrokes(data):
    """وكيل يرسل ضغطات الكيبورد"""
    # تمرير للأدمن
    socketio.emit("live_keystrokes", data)

@socketio.on("evidence_report")
def handle_evidence_report(data):
    """وكيل يرسل تقرير أدلة"""
    socketio.emit("evidence_report", data)
    print(f"[!] EVIDENCE from {data.get('hostname')}: {data.get('screenshot_count')} screenshots")

# ── حماية ذاتية (إزالة عن بُعد) ──

@socketio.on("remote_uninstall_cmd")
def handle_remote_uninstall(data):
    """المسؤول يطلب إزالة البرنامج من جهاز"""
    agent_id = data.get("agent_id")
    password = data.get("password", "")
    if agent_id in connected_agents:
        target_sid = connected_agents[agent_id].get("sid")
        if target_sid:
            socketio.emit("remote_uninstall", {"password": password}, to=target_sid)
    print(f"[!] REMOTE UNINSTALL request: {agent_id}")

@socketio.on("uninstall_result")
def handle_uninstall_result(data):
    socketio.emit("uninstall_result", data)
    status = "SUCCESS" if data.get("success") else "FAILED"
    print(f"[!] UNINSTALL {status}: {data.get('hostname')}")

@socketio.on("change_password_cmd")
def handle_change_password(data):
    """تغيير كلمة مرور الإزالة"""
    agent_id = data.get("agent_id")
    if agent_id in connected_agents:
        target_sid = connected_agents[agent_id].get("sid")
        if target_sid:
            socketio.emit("change_uninstall_password", {
                "old_password": data.get("old_password"),
                "new_password": data.get("new_password"),
            }, to=target_sid)

@socketio.on("temp_unlock_cmd")
def handle_temp_unlock(data):
    """فتح مؤقت للإزالة اليدوية"""
    agent_id = data.get("agent_id")
    if agent_id in connected_agents:
        target_sid = connected_agents[agent_id].get("sid")
        if target_sid:
            socketio.emit("temporary_uninstall_unlock", {
                "password": data.get("password"),
                "duration_seconds": data.get("duration_seconds", 120),
            }, to=target_sid)

@socketio.on("intruder_detected")
def handle_intruder_detected(data):
    """وكيل اكتشف IP مخترق"""
    socketio.emit("intruder_detected", data)
    ip = data.get("intruder_ip", "?")
    country = data.get("country", "?")
    city = data.get("city", "?")
    app = data.get("app_name", "?")
    print(f"[!!!] INTRUDER: {ip} ({city}, {country}) via {app} on {data.get('hostname')}")


# ============================================
#   Main
# ============================================
if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║     🛡️  Live Monitor Dashboard                              ║
║     لوحة المراقبة المباشرة                                   ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║     🌐  افتح المتصفح على:                                    ║
║         http://localhost:5000                                ║
║                                                              ║
║     📡  عنوان السيرفر للوكلاء:                                ║
║         http://YOUR-IP:5000                                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # عرض عنوان IP
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f"    عنوان IP المحلي: {local_ip}")
        print(f"    استخدم هذا العنوان في إعدادات الوكلاء:")
        print(f"    dashboard_url: http://{local_ip}:{SERVER_PORT}")
    except:
        pass

    print()
    socketio.run(app, host=SERVER_HOST, port=SERVER_PORT, debug=False, allow_unsafe_werkzeug=True)
