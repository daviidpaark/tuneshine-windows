import asyncio
import base64
import json
import logging
import os
import threading
from typing import Optional, Callable
import webview

from config import Config, APP_VERSION
from hub_client import HubClient
from media_listener import TrackInfo

logger = logging.getLogger("tuneshine-windows.ui")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tuneshine Windows</title>
  <style>
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      user-select: none;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI Variable Text", "Segoe UI", Inter, Roboto, sans-serif;
    }
    body {
      background-color: #0d0d10;
      color: #fafafa;
      padding: 14px;
      height: 100vh;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    body::-webkit-scrollbar {
      width: 6px;
    }
    body::-webkit-scrollbar-track {
      background: transparent;
    }
    body::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.15);
      border-radius: 3px;
    }
    body::-webkit-scrollbar-thumb:hover {
      background: rgba(255, 255, 255, 0.25);
    }

    /* Cards */
    .card {
      background: #16161a;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      padding: 13px;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
    }
    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
    }
    .card-title {
      font-size: 12.5px;
      font-weight: 700;
      color: #f4f4f5;
      letter-spacing: 0.2px;
    }

    /* Now Playing Hero */
    .player-card {
      display: flex;
      align-items: center;
      gap: 13px;
      background: linear-gradient(135deg, #18181f 0%, #121216 100%);
      border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .cover-art {
      width: 64px;
      height: 64px;
      border-radius: 8px;
      background: #09090b;
      border: 1px solid rgba(255, 255, 255, 0.12);
      object-fit: cover;
      flex-shrink: 0;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
    }
    .player-info {
      display: flex;
      flex-direction: column;
      gap: 3px;
      min-width: 0;
      flex: 1;
    }
    .status-row {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.5px;
      padding: 2px 7px;
      border-radius: 999px;
      text-transform: uppercase;
    }
    .badge-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
    }
    .badge-syncing {
      background: rgba(34, 197, 94, 0.15);
      color: #22c55e;
      border: 1px solid rgba(34, 197, 94, 0.3);
    }
    .badge-syncing .badge-dot { background: #22c55e; box-shadow: 0 0 6px #22c55e; }
    
    .badge-paused {
      background: rgba(245, 158, 11, 0.15);
      color: #f59e0b;
      border: 1px solid rgba(245, 158, 11, 0.3);
    }
    .badge-paused .badge-dot { background: #f59e0b; }

    .badge-blocked {
      background: rgba(239, 68, 68, 0.15);
      color: #ef4444;
      border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .badge-blocked .badge-dot { background: #ef4444; }

    .badge-idle {
      background: rgba(255, 255, 255, 0.08);
      color: #a1a1aa;
      border: 1px solid rgba(255, 255, 255, 0.12);
    }
    .badge-idle .badge-dot { background: #71717a; }

    .source-text {
      font-size: 11px;
      color: #71717a;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 150px;
    }
    .track-title {
      font-size: 13.5px;
      font-weight: 600;
      color: #ffffff;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .track-artist {
      font-size: 11.5px;
      color: #a1a1aa;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    /* Form rows */
    .form-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin-bottom: 11px;
    }
    .form-group:last-child {
      margin-bottom: 0;
    }
    .form-label {
      font-size: 11.5px;
      font-weight: 600;
      color: #d4d4d8;
    }
    .input-row {
      display: flex;
      gap: 8px;
    }
    input[type="text"] {
      flex: 1;
      background: #0d0d10;
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 8px;
      color: #fafafa;
      font-size: 12px;
      padding: 7px 10px;
      outline: none;
      transition: border-color 0.15s;
    }
    input[type="text"]:focus {
      border-color: #22c55e;
    }

    /* Buttons */
    button {
      cursor: pointer;
      border: none;
      border-radius: 8px;
      font-size: 11.5px;
      font-weight: 600;
      padding: 6px 12px;
      transition: all 0.15s;
    }
    .btn-secondary {
      background: rgba(255, 255, 255, 0.08);
      color: #e4e4e7;
      border: 1px solid rgba(255, 255, 255, 0.12);
    }
    .btn-secondary:hover {
      background: rgba(255, 255, 255, 0.14);
      color: #ffffff;
    }
    .btn-primary {
      background: #22c55e;
      color: #ffffff;
      box-shadow: 0 2px 8px rgba(34, 197, 94, 0.3);
    }
    .btn-primary:hover {
      background: #16a34a;
    }
    .btn-primary:active {
      transform: scale(0.98);
    }

    /* Segmented Switcher */
    .segmented {
      display: flex;
      background: #0d0d10;
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 8px;
      padding: 3px;
      gap: 3px;
    }
    .segmented-btn {
      flex: 1;
      text-align: center;
      padding: 5px 8px;
      font-size: 11px;
      font-weight: 500;
      color: #a1a1aa;
      border-radius: 6px;
      background: transparent;
      transition: all 0.15s;
    }
    .segmented-btn.active {
      background: #27272a;
      color: #fafafa;
      font-weight: 600;
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
    }

    /* Program Filtering Card Elements */
    .filter-guide {
      font-size: 11px;
      color: #71717a;
      line-height: 1.35;
      margin-top: 3px;
    }
    .apps-section {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-top: 10px;
    }
    .apps-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 11px;
      color: #a1a1aa;
      padding-bottom: 2px;
    }
    .apps-list {
      display: flex;
      flex-direction: column;
      gap: 6px;
      max-height: 185px;
      overflow-y: auto;
      padding-right: 2px;
    }
    .apps-list::-webkit-scrollbar {
      width: 5px;
    }
    .apps-list::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.12);
      border-radius: 3px;
    }
    .app-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: #0d0d10;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 8px;
      padding: 7px 10px;
      gap: 8px;
      transition: border-color 0.15s;
    }
    .app-item:hover {
      border-color: rgba(255, 255, 255, 0.18);
    }
    .app-info {
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 0;
      flex: 1;
    }
    .app-name {
      font-size: 12px;
      font-weight: 600;
      color: #fafafa;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .app-id-sub {
      font-size: 10px;
      color: #71717a;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .app-actions {
      display: flex;
      align-items: center;
      gap: 5px;
      flex-shrink: 0;
    }
    .tag-btn {
      padding: 3px 9px;
      font-size: 11px;
      font-weight: 600;
      border-radius: 6px;
      border: 1px solid rgba(255, 255, 255, 0.1);
      background: rgba(255, 255, 255, 0.05);
      color: #a1a1aa;
      cursor: pointer;
      transition: all 0.12s;
    }
    .tag-btn:hover {
      background: rgba(255, 255, 255, 0.12);
      color: #ffffff;
    }
    .tag-btn.tag-allow-active {
      background: rgba(34, 197, 94, 0.2);
      color: #22c55e;
      border-color: rgba(34, 197, 94, 0.45);
    }
    .tag-btn.tag-allow-active:hover {
      background: rgba(34, 197, 94, 0.3);
    }
    .tag-btn.tag-block-active {
      background: rgba(239, 68, 68, 0.2);
      color: #ef4444;
      border-color: rgba(239, 68, 68, 0.45);
    }
    .tag-btn.tag-block-active:hover {
      background: rgba(239, 68, 68, 0.3);
    }
    .btn-delete {
      background: transparent;
      color: #52525b;
      padding: 3px 6px;
      font-size: 12px;
      border-radius: 4px;
    }
    .btn-delete:hover {
      color: #ef4444;
      background: rgba(239, 68, 68, 0.1);
    }
    .empty-apps {
      text-align: center;
      padding: 14px 8px;
      font-size: 11px;
      color: #71717a;
      line-height: 1.4;
    }
    .add-app-row {
      display: flex;
      gap: 6px;
      margin-top: 4px;
    }

    /* Settings List Rows */
    .setting-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 6px 0;
    }
    .setting-row:not(:last-child) {
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    .setting-label {
      font-size: 12px;
      color: #e4e4e7;
    }

    /* Toggle Switch */
    .switch {
      position: relative;
      display: inline-block;
      width: 36px;
      height: 20px;
    }
    .switch input {
      opacity: 0;
      width: 0;
      height: 0;
    }
    .slider {
      position: absolute;
      cursor: pointer;
      top: 0; left: 0; right: 0; bottom: 0;
      background-color: #27272a;
      border: 1px solid rgba(255, 255, 255, 0.1);
      transition: .2s;
      border-radius: 20px;
    }
    .slider:before {
      position: absolute;
      content: "";
      height: 14px;
      width: 14px;
      left: 2px;
      bottom: 2px;
      background-color: #d4d4d8;
      transition: .2s;
      border-radius: 50%;
    }
    input:checked + .slider {
      background-color: #22c55e;
      border-color: #22c55e;
    }
    input:checked + .slider:before {
      transform: translateX(16px);
      background-color: #ffffff;
    }

    /* Number Stepper */
    .stepper {
      display: flex;
      align-items: center;
      background: #0d0d10;
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 6px;
      overflow: hidden;
    }
    .stepper input {
      width: 48px;
      background: transparent;
      border: none;
      color: #fafafa;
      text-align: center;
      font-size: 12px;
      font-weight: 600;
      padding: 4px 0;
      outline: none;
    }
    .stepper-btn {
      background: rgba(255, 255, 255, 0.05);
      color: #a1a1aa;
      padding: 4px 8px;
      font-size: 11px;
      border-radius: 0;
    }
    .stepper-btn:hover {
      background: rgba(255, 255, 255, 0.12);
      color: #fff;
    }

    /* Footer */
    .footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-top: auto;
      padding-top: 4px;
      padding-bottom: 2px;
    }
    .footer-left {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .version-label {
      font-size: 11px;
      color: #71717a;
    }
    .config-link {
      font-size: 10px;
      color: #52525b;
      text-decoration: none;
      cursor: pointer;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 170px;
    }
    .config-link:hover {
      color: #a1a1aa;
      text-decoration: underline;
    }
    .toast {
      font-size: 11px;
      color: #22c55e;
      opacity: 0;
      transition: opacity 0.2s;
    }
    .toast.show {
      opacity: 1;
    }
  </style>
</head>
<body>

  <!-- 1. Now Playing Hero -->
  <div class="card player-card">
    <img id="coverArt" class="cover-art" src="" alt="Album Art">
    <div class="player-info">
      <div class="status-row">
        <div id="statusBadge" class="badge badge-idle">
          <span class="badge-dot"></span>
          <span id="statusText">IDLE</span>
        </div>
        <span id="sourceApp" class="source-text"></span>
      </div>
      <div id="trackTitle" class="track-title">No Active Playback</div>
      <div id="trackArtist" class="track-artist">Waiting for media session...</div>
    </div>
  </div>

  <!-- 2. Program Filtering (Allow / Block) -->
  <div class="card">
    <div class="card-header">
      <div class="card-title">Program Filtering</div>
      <span id="filterStatusBadge" class="badge badge-idle">ALLOW ALL (OFF)</span>
    </div>

    <div class="form-group">
      <label class="form-label">Filter Mode</label>
      <div class="segmented">
        <button id="modeFilterOff" class="segmented-btn active" onclick="setFilterMode('off')">Off (Allow All)</button>
        <button id="modeFilterBlock" class="segmented-btn" onclick="setFilterMode('block')">Block Mode</button>
        <button id="modeFilterAllow" class="segmented-btn" onclick="setFilterMode('allow')">Allow Mode</button>
      </div>
      <div id="filterGuideText" class="filter-guide">All detected media programs are currently allowed to sync.</div>
    </div>

    <div class="apps-section">
      <div class="apps-header">
        <span id="appsCountLabel">Detected Programs (0)</span>
      </div>

      <div id="appsList" class="apps-list">
        <div class="empty-apps">No media programs detected yet.<br>Play audio in any app or add one manually below.</div>
      </div>

      <div class="add-app-row">
        <input type="text" id="manualAppInput" placeholder="Add exe (e.g. cider.exe)" onkeydown="if(event.key==='Enter'){addManualApp();}">
        <button class="btn-secondary" onclick="addManualApp()">+ Add</button>
      </div>
    </div>
  </div>

  <!-- 3. Connection Settings -->
  <div class="card">
    <div class="form-group">
      <label class="form-label">Target Hub Address</label>
      <div class="input-row">
        <input type="text" id="hubUrl" placeholder="http://unraid:8585" onchange="autoSave()" onkeydown="if(event.key==='Enter'){manualSave();}">
        <button id="btnTest" class="btn-secondary" onclick="testConnection()">Ping</button>
      </div>
    </div>

    <div class="form-group">
      <label class="form-label">Operation Mode</label>
      <div class="segmented">
        <button id="modeHub" class="segmented-btn active" onclick="setMode('hub')">Tuneshine Hub</button>
        <button id="modeDirect" class="segmented-btn" onclick="setMode('direct')">Direct Device</button>
      </div>
    </div>
  </div>

  <!-- 4. Preferences -->
  <div class="card">
    <div class="setting-row">
      <span class="setting-label">Sync Playback</span>
      <label class="switch">
        <input type="checkbox" id="chkSync" onchange="autoSave()">
        <span class="slider"></span>
      </label>
    </div>

    <div class="setting-row">
      <span class="setting-label">Start Minimized to Tray</span>
      <label class="switch">
        <input type="checkbox" id="chkStartInTray" onchange="autoSave()">
        <span class="slider"></span>
      </label>
    </div>

    <div class="setting-row">
      <span class="setting-label">Launch with Windows</span>
      <label class="switch">
        <input type="checkbox" id="chkAutostart" onchange="autoSave()">
        <span class="slider"></span>
      </label>
    </div>

    <div class="setting-row">
      <span class="setting-label">Clear / Pause Delay</span>
      <div class="stepper">
        <button class="stepper-btn" onclick="stepDelay(-0.5)">-</button>
        <input type="text" id="clearDelay" value="2.0s" readonly>
        <button class="stepper-btn" onclick="stepDelay(0.5)">+</button>
      </div>
    </div>
  </div>

  <!-- 5. Footer -->
  <div class="footer">
    <div class="footer-left">
      <span class="version-label" id="verLabel">v0.3.3</span>
      <a class="config-link" id="configPathLabel" onclick="openConfigFolder()" title="Click to open config folder">Config: config.json</a>
    </div>
    <span id="toastMsg" class="toast">Saved ✓</span>
    <button class="btn-primary" onclick="manualSave()">Save Settings</button>
  </div>

  <script>
    let currentMode = "hub";
    let currentFilterMode = "off";
    let currentAllowedList = [];
    let currentBlockedList = [];
    let currentDetectedApps = {};
    let delayVal = 2.0;

    // Default 1x1 black square fallback
    const DEFAULT_ART = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAQAAAAAYLlVAAAAOUlEQVR42u3OQQ0AAAgEILV/Z2nhexswCegqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKg8W+yEA95gZ154AAAAASUVORK5CYII=";
    document.getElementById('coverArt').src = DEFAULT_ART;

    function setMode(mode, save = true) {
      currentMode = mode;
      document.getElementById('modeHub').className = 'segmented-btn ' + (mode === 'hub' ? 'active' : '');
      document.getElementById('modeDirect').className = 'segmented-btn ' + (mode === 'direct' ? 'active' : '');
      if (save) {
        autoSave();
      }
    }

    function setFilterMode(mode, save = true) {
      if (mode === 'blacklist') mode = 'block';
      if (mode === 'whitelist') mode = 'allow';
      currentFilterMode = mode;

      document.getElementById('modeFilterOff').className = 'segmented-btn ' + (mode === 'off' ? 'active' : '');
      document.getElementById('modeFilterBlock').className = 'segmented-btn ' + (mode === 'block' ? 'active' : '');
      document.getElementById('modeFilterAllow').className = 'segmented-btn ' + (mode === 'allow' ? 'active' : '');

      const badge = document.getElementById('filterStatusBadge');
      const guide = document.getElementById('filterGuideText');

      if (mode === 'block') {
        badge.className = 'badge badge-paused';
        badge.innerText = 'BLOCK MODE';
        guide.innerText = 'Programs marked as "Block" will be prevented from syncing.';
      } else if (mode === 'allow') {
        badge.className = 'badge badge-syncing';
        badge.innerText = 'ALLOW MODE';
        guide.innerText = 'Only programs marked as "Allow" will be permitted to sync.';
      } else {
        badge.className = 'badge badge-idle';
        badge.innerText = 'ALLOW ALL (OFF)';
        guide.innerText = 'All detected media programs are currently allowed to sync.';
      }

      if (save && window.pywebview && window.pywebview.api) {
        window.pywebview.api.set_filter_mode(mode);
      }
      renderAppsList();
    }

    function isAppInList(appId, list) {
      if (!appId || !list) return false;
      const lower = appId.toLowerCase();
      return list.some(item => {
        const itemLower = item.toLowerCase();
        return itemLower === lower || lower.includes(itemLower) || itemLower.includes(lower);
      });
    }

    function renderAppsList() {
      const container = document.getElementById('appsList');
      const keys = Object.keys(currentDetectedApps);
      document.getElementById('appsCountLabel').innerText = `Detected Programs (${keys.length})`;

      if (keys.length === 0) {
        container.innerHTML = '<div class="empty-apps">No media programs detected yet.<br>Play audio in any app or add one manually below.</div>';
        return;
      }

      let html = '';
      keys.forEach(appId => {
        const info = currentDetectedApps[appId];
        const dispName = (info && info.display_name) || appId;
        const isAllowed = isAppInList(appId, currentAllowedList);
        const isBlocked = isAppInList(appId, currentBlockedList);

        const allowBtnClass = isAllowed ? 'tag-btn tag-allow-active' : 'tag-btn';
        const blockBtnClass = isBlocked ? 'tag-btn tag-block-active' : 'tag-btn';

        const nextAllowState = isAllowed ? 'neutral' : 'allow';
        const nextBlockState = isBlocked ? 'neutral' : 'block';

        html += `
          <div class="app-item">
            <div class="app-info">
              <div class="app-name">${escapeHtml(dispName)}</div>
              <div class="app-id-sub" title="${escapeHtml(appId)}">${escapeHtml(appId)}</div>
            </div>
            <div class="app-actions">
              <button class="${allowBtnClass}" title="Mark as Allowed" onclick="setAppFilter('${escapeHtml(appId)}', '${nextAllowState}')">Allow</button>
              <button class="${blockBtnClass}" title="Mark as Blocked" onclick="setAppFilter('${escapeHtml(appId)}', '${nextBlockState}')">Block</button>
              <button class="btn-delete" title="Remove program" onclick="removeApp('${escapeHtml(appId)}')">✕</button>
            </div>
          </div>
        `;
      });

      container.innerHTML = html;
    }

    function escapeHtml(text) {
      if (!text) return '';
      return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    async function setAppFilter(appId, state) {
      if (window.pywebview && window.pywebview.api) {
        const res = await window.pywebview.api.set_app_filter_state(appId, state);
        if (res && res.success) {
          currentAllowedList = res.whitelist || res.allowed_apps || [];
          currentBlockedList = res.blacklist || res.blocked_apps || [];
          currentDetectedApps = res.detected_apps || currentDetectedApps;
          renderAppsList();
          showToast(`Updated ${appId}`);
        }
      }
    }

    async function addManualApp() {
      const input = document.getElementById('manualAppInput');
      const val = input.value.trim();
      if (!val) return;
      if (window.pywebview && window.pywebview.api) {
        const res = await window.pywebview.api.add_custom_app(val);
        if (res && res.success) {
          currentDetectedApps = res.detected_apps || currentDetectedApps;
          currentAllowedList = res.whitelist || res.allowed_apps || currentAllowedList;
          currentBlockedList = res.blacklist || res.blocked_apps || currentBlockedList;
          input.value = '';
          renderAppsList();
          showToast(`Added ${val}`);
        }
      }
    }

    async function removeApp(appId) {
      if (window.pywebview && window.pywebview.api) {
        const res = await window.pywebview.api.remove_app(appId);
        if (res && res.success) {
          currentDetectedApps = res.detected_apps || {};
          currentAllowedList = res.whitelist || res.allowed_apps || [];
          currentBlockedList = res.blacklist || res.blocked_apps || [];
          renderAppsList();
          showToast(`Removed ${appId}`);
        }
      }
    }

    function stepDelay(delta) {
      delayVal = Math.max(0.0, Math.min(10.0, delayVal + delta));
      document.getElementById('clearDelay').value = delayVal.toFixed(1) + 's';
      autoSave();
    }

    function showToast(text, isError = false) {
      const t = document.getElementById('toastMsg');
      t.innerText = text;
      t.style.color = isError ? '#ef4444' : '#22c55e';
      t.className = 'toast show';
      setTimeout(() => { t.className = 'toast'; }, 2200);
    }

    function getFormData() {
      return {
        hub_url: document.getElementById('hubUrl').value.trim(),
        mode: currentMode,
        filter_mode: currentFilterMode,
        enabled: document.getElementById('chkSync').checked,
        start_in_tray: document.getElementById('chkStartInTray').checked,
        autostart: document.getElementById('chkAutostart').checked,
        clear_delay: delayVal
      };
    }

    async function autoSave() {
      if (window.pywebview && window.pywebview.api) {
        const res = await window.pywebview.api.save_settings(getFormData());
        if (res && res.success) {
          showToast("Saved ✓");
        } else {
          showToast("Save failed", true);
        }
      }
    }

    async function manualSave() {
      if (window.pywebview && window.pywebview.api) {
        const res = await window.pywebview.api.save_settings(getFormData());
        if (res && res.success) {
          showToast("Saved ✓");
        } else {
          showToast("Save failed", true);
        }
      }
    }

    async function openConfigFolder() {
      if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.open_config_folder();
      }
    }

    async function testConnection() {
      const btn = document.getElementById('btnTest');
      btn.innerText = '...';
      const url = document.getElementById('hubUrl').value.trim();
      if (window.pywebview && window.pywebview.api) {
        const res = await window.pywebview.api.test_connection(url);
        if (res.online) {
          btn.innerText = 'OK (200)';
          btn.style.color = '#22c55e';
          showToast('Connected to Hub!');
        } else {
          btn.innerText = 'Failed';
          btn.style.color = '#ef4444';
          showToast('Connection failed: ' + (res.error || 'unreachable'), true);
        }
        setTimeout(() => {
          btn.innerText = 'Ping';
          btn.style.color = '#e4e4e7';
        }, 3000);
      }
    }

    // Called dynamically from Python when new apps are discovered
    window.updateDetectedApps = function(data) {
      if (!data) return;
      if (data.detected_apps) currentDetectedApps = data.detected_apps;
      if (data.whitelist) currentAllowedList = data.whitelist;
      if (data.allowed_apps) currentAllowedList = data.allowed_apps;
      if (data.blacklist) currentBlockedList = data.blacklist;
      if (data.blocked_apps) currentBlockedList = data.blocked_apps;
      if (data.filter_mode) currentFilterMode = data.filter_mode;
      renderAppsList();
    };

    // Called from Python on SMTC playback update
    window.updateTrackInfo = function(track) {
      const badge = document.getElementById('statusBadge');
      const badgeText = document.getElementById('statusText');
      const sourceApp = document.getElementById('sourceApp');
      const title = document.getElementById('trackTitle');
      const artist = document.getElementById('trackArtist');
      const art = document.getElementById('coverArt');

      const appLabel = track.app_name || (track.app_id ? track.app_id.replace('.exe', '') : '');

      if (track.is_playing) {
        badge.className = 'badge badge-syncing';
        badgeText.innerText = 'SYNCING';
        sourceApp.innerText = appLabel ? 'via ' + appLabel : '';
        title.innerText = track.title || 'Unknown Title';
        artist.innerText = track.artist + (track.album ? ' • ' + track.album : '');
        if (track.art_b64) {
          art.src = 'data:image/png;base64,' + track.art_b64;
        } else {
          art.src = DEFAULT_ART;
        }
      } else if (track.is_blocked) {
        badge.className = 'badge badge-blocked';
        badgeText.innerText = 'BLOCKED';
        sourceApp.innerText = appLabel ? 'via ' + appLabel + ' (Blocked)' : 'Blocked';
        title.innerText = track.title || 'Playback Blocked';
        artist.innerText = (track.artist ? track.artist + ' • ' : '') + 'Blocked by filter rules';
        art.src = DEFAULT_ART;
      } else {
        const isPaused = Boolean(track.title);
        badge.className = isPaused ? 'badge badge-paused' : 'badge badge-idle';
        badgeText.innerText = isPaused ? 'PAUSED' : 'IDLE';
        sourceApp.innerText = (isPaused && appLabel) ? 'via ' + appLabel : '';
        title.innerText = isPaused ? track.title : 'No Active Playback';
        artist.innerText = isPaused ? (track.artist + (track.album ? ' • ' + track.album : '')) : 'Waiting for media session...';
        if (isPaused && track.art_b64) {
          art.src = 'data:image/png;base64,' + track.art_b64;
        } else if (!isPaused) {
          art.src = DEFAULT_ART;
        }
      }
    };

    // Initialize state on load
    window.addEventListener('pywebviewready', async () => {
      if (window.pywebview && window.pywebview.api) {
        const init = await window.pywebview.api.get_initial_state();
        currentFilterMode = init.config.filter_mode || 'off';
        currentAllowedList = init.config.allowed_apps || init.config.whitelist || [];
        currentBlockedList = init.config.blocked_apps || init.config.blacklist || [];
        currentDetectedApps = init.config.detected_apps || {};
        currentMode = init.config.mode || 'hub';
        delayVal = init.config.clear_delay || 2.0;

        document.getElementById('hubUrl').value = init.config.hub_url || '';
        document.getElementById('chkSync').checked = Boolean(init.config.enabled);
        document.getElementById('chkStartInTray').checked = Boolean(init.config.start_in_tray);
        document.getElementById('chkAutostart').checked = Boolean(init.config.autostart);
        document.getElementById('clearDelay').value = delayVal.toFixed(1) + 's';
        document.getElementById('verLabel').innerText = 'v' + init.version;

        setMode(currentMode, false);
        setFilterMode(currentFilterMode, false);
        renderAppsList();

        if (init.config_path) {
          document.getElementById('configPathLabel').innerText = 'Config: ' + (init.config_filename || 'config.json');
          document.getElementById('configPathLabel').title = init.config_path + ' (Click to open folder)';
        }

        if (init.current_track) {
          window.updateTrackInfo(init.current_track);
        }
      }
    });
  </script>
</body>
</html>
"""


class WebViewApi:
    """Exposed Python API callable from JavaScript."""

    def __init__(self, config: Config, hub_client: HubClient, on_config_changed: Callable[[], None]):
        self.config = config
        self.hub_client = hub_client
        self.on_config_changed = on_config_changed
        self.latest_track_dict = {}

    def get_initial_state(self):
        return {
            "config": {
                "hub_url": self.config.hub_url,
                "mode": self.config.mode,
                "enabled": self.config.enabled,
                "start_in_tray": self.config.start_in_tray,
                "autostart": self.config.autostart,
                "clear_delay": self.config.clear_delay,
                "filter_mode": self.config.filter_mode,
                "blacklist": self.config.blacklist,
                "whitelist": self.config.whitelist,
                "blocked_apps": self.config.blocked_apps,
                "allowed_apps": self.config.allowed_apps,
                "detected_apps": self.config.detected_apps,
            },
            "config_path": str(self.config.config_path),
            "config_filename": self.config.config_path.name,
            "version": APP_VERSION,
            "current_track": self.latest_track_dict,
        }

    def save_settings(self, data: dict):
        if not data:
            return {"success": False}
        if "hub_url" in data:
            self.config.hub_url = data.get("hub_url", self.config.hub_url).rstrip("/")
        if "mode" in data:
            self.config.mode = data.get("mode", self.config.mode)
        if "enabled" in data:
            self.config.enabled = bool(data.get("enabled", self.config.enabled))
        if "start_in_tray" in data:
            self.config.start_in_tray = bool(data.get("start_in_tray", self.config.start_in_tray))
        if "autostart" in data:
            self.config.autostart = bool(data.get("autostart", self.config.autostart))
        if "clear_delay" in data:
            self.config.clear_delay = float(data.get("clear_delay", self.config.clear_delay))
        if "filter_mode" in data:
            self.config.filter_mode = str(data.get("filter_mode", self.config.filter_mode))

        self.config.save()

        self.hub_client.update_url(self.config.hub_url, mode=self.config.mode)
        self.on_config_changed()
        return {"success": True, "path": str(self.config.config_path)}

    def set_filter_mode(self, mode: str):
        self.config.filter_mode = mode
        self.on_config_changed()
        return {"success": True, "filter_mode": self.config.filter_mode}

    def set_app_filter_state(self, app_id: str, state: str):
        self.config.set_app_filter_state(app_id, state)
        self.on_config_changed()
        return {
            "success": True,
            "whitelist": self.config.whitelist,
            "blacklist": self.config.blacklist,
            "allowed_apps": self.config.allowed_apps,
            "blocked_apps": self.config.blocked_apps,
            "detected_apps": self.config.detected_apps,
        }

    def add_custom_app(self, app_id: str):
        clean_id = app_id.strip()
        if clean_id:
            self.config.register_detected_app(clean_id)
            self.on_config_changed()
        return {
            "success": True,
            "detected_apps": self.config.detected_apps,
            "whitelist": self.config.whitelist,
            "blacklist": self.config.blacklist,
            "allowed_apps": self.config.allowed_apps,
            "blocked_apps": self.config.blocked_apps,
        }

    def remove_app(self, app_id: str):
        self.config.remove_detected_app(app_id)
        self.on_config_changed()
        return {
            "success": True,
            "detected_apps": self.config.detected_apps,
            "whitelist": self.config.whitelist,
            "blacklist": self.config.blacklist,
            "allowed_apps": self.config.allowed_apps,
            "blocked_apps": self.config.blocked_apps,
        }

    def open_config_folder(self):
        self.config.open_config_folder()
        return {"success": True}

    def test_connection(self, url: str):
        target = (url or self.config.hub_url).strip().rstrip("/")
        loop = asyncio.new_event_loop()
        try:
            client = HubClient(target, mode="hub")
            res = loop.run_until_complete(client.check_health())
            loop.run_until_complete(client.close())
            return res
        except Exception as e:
            return {"online": False, "error": str(e)}
        finally:
            loop.close()


class WebviewDashboard:
    def __init__(self, config: Config, hub_client: HubClient, on_config_changed: Callable[[], None]):
        self.config = config
        self.hub_client = hub_client
        self.on_config_changed = on_config_changed
        self.api = WebViewApi(config, hub_client, on_config_changed)
        self.window: Optional[webview.Window] = None

    def create_window(self, hidden: bool = False):
        self.window = webview.create_window(
            title="Tuneshine Windows",
            html=HTML_TEMPLATE,
            js_api=self.api,
            width=420,
            height=660,
            resizable=True,
            hidden=hidden,
            background_color="#0d0d10",
        )
        self.window.events.closing += self._on_closing

    def _on_closing(self):
        # Hide window instead of terminating application
        if self.window:
            self.window.hide()
            return False

    def show(self):
        if self.window:
            self.window.show()
            self.window.restore()

    def update_detected_apps(self):
        if self.window:
            try:
                data = {
                    "detected_apps": self.config.detected_apps,
                    "filter_mode": self.config.filter_mode,
                    "whitelist": self.config.whitelist,
                    "blacklist": self.config.blacklist,
                    "allowed_apps": self.config.allowed_apps,
                    "blocked_apps": self.config.blocked_apps,
                }
                js_code = f"if (window.updateDetectedApps) {{ window.updateDetectedApps({json.dumps(data)}); }}"
                self.window.evaluate_js(js_code)
            except Exception as e:
                logger.debug(f"Could not push detected apps to webview: {e}")

    def update_media(self, track: TrackInfo):
        art_b64 = ""
        if track.thumbnail_bytes:
            art_b64 = base64.b64encode(track.thumbnail_bytes).decode("utf-8")

        track_dict = {
            "is_playing": track.is_playing,
            "is_blocked": getattr(track, "is_blocked", False),
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "app_id": track.app_id,
            "app_name": getattr(track, "app_name", "") or track.app_id,
            "art_b64": art_b64,
        }
        self.api.latest_track_dict = track_dict

        if self.window:
            try:
                js_code = f"if (window.updateTrackInfo) {{ window.updateTrackInfo({json.dumps(track_dict)}); }}"
                self.window.evaluate_js(js_code)
            except Exception as e:
                logger.debug(f"Could not push to webview: {e}")
