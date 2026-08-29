import asyncio
import base64
import json
import logging
import os
import threading
from typing import Optional, Callable
import webview

from config import Config
from hub_client import HubClient
from media_listener import TrackInfo
import updater

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
      padding: 16px;
      height: 100vh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    /* Cards */
    .card {
      background: #16161a;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      padding: 14px;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
    }

    /* Now Playing Hero */
    .player-card {
      display: flex;
      align-items: center;
      gap: 14px;
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

    .badge-idle {
      background: rgba(255, 255, 255, 0.08);
      color: #a1a1aa;
      border: 1px solid rgba(255, 255, 255, 0.12);
    }
    .badge-idle .badge-dot { background: #71717a; }

    .source-text {
      font-size: 11px;
      color: #71717a;
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
      margin-bottom: 12px;
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
      font-size: 12.5px;
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
      font-size: 12px;
      font-weight: 600;
      padding: 7px 14px;
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

    /* Segmented Mode Switcher */
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
      padding: 6px 10px;
      font-size: 11.5px;
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
    }
    .version-link {
      font-size: 11px;
      color: #71717a;
      text-decoration: none;
      cursor: pointer;
    }
    .version-link:hover {
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

  <!-- 2. Connection Settings -->
  <div class="card">
    <div class="form-group">
      <label class="form-label">Target Hub Address</label>
      <div class="input-row">
        <input type="text" id="hubUrl" placeholder="http://unraid:8585">
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

  <!-- 3. Preferences -->
  <div class="card">
    <div class="setting-row">
      <span class="setting-label">Sync Playback</span>
      <label class="switch">
        <input type="checkbox" id="chkSync" onchange="autoSave()">
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

  <!-- 4. Footer -->
  <div class="footer">
    <a class="version-link" id="verLabel" onclick="checkUpdates()">v1.0.0 • Check updates</a>
    <span id="toastMsg" class="toast">Saved ✓</span>
    <button class="btn-primary" onclick="manualSave()">Save Settings</button>
  </div>

  <script>
    let currentMode = "hub";
    let delayVal = 2.0;

    // Default 1x1 black square fallback
    const DEFAULT_ART = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAQAAAAAYLlVAAAAOUlEQVR42u3OQQ0AAAgEILV/Z2nhexswCegqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKg8W+yEA95gZ154AAAAASUVORK5CYII=";
    document.getElementById('coverArt').src = DEFAULT_ART;

    function setMode(mode) {
      currentMode = mode;
      document.getElementById('modeHub').className = 'segmented-btn ' + (mode === 'hub' ? 'active' : '');
      document.getElementById('modeDirect').className = 'segmented-btn ' + (mode === 'direct' ? 'active' : '');
      autoSave();
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
        enabled: document.getElementById('chkSync').checked,
        autostart: document.getElementById('chkAutostart').checked,
        clear_delay: delayVal
      };
    }

    async function autoSave() {
      if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.save_settings(getFormData());
        showToast("Saved ✓");
      }
    }

    async function manualSave() {
      if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.save_settings(getFormData());
        showToast("Saved ✓");
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

    async function checkUpdates() {
      const link = document.getElementById('verLabel');
      link.innerText = 'Checking...';
      if (window.pywebview && window.pywebview.api) {
        const res = await window.pywebview.api.check_updates();
        if (res.has_update) {
          link.innerText = 'Update available (v' + res.version + ')';
          link.style.color = '#22c55e';
        } else {
          link.innerText = 'Up to date (v' + res.version + ')';
          setTimeout(() => { link.innerText = 'v' + res.version + ' • Check updates'; }, 3000);
        }
      }
    }

    // Called from Python on SMTC playback update
    window.updateTrackInfo = function(track) {
      const badge = document.getElementById('statusBadge');
      const badgeText = document.getElementById('statusText');
      const sourceApp = document.getElementById('sourceApp');
      const title = document.getElementById('trackTitle');
      const artist = document.getElementById('trackArtist');
      const art = document.getElementById('coverArt');

      if (track.is_playing) {
        badge.className = 'badge badge-syncing';
        badgeText.innerText = 'SYNCING';
        sourceApp.innerText = track.app_id ? 'via ' + track.app_id.replace('.exe', '') : '';
        title.innerText = track.title || 'Unknown Title';
        artist.innerText = track.artist + (track.album ? ' • ' + track.album : '');
        if (track.art_b64) {
          art.src = 'data:image/png;base64,' + track.art_b64;
        } else {
          art.src = DEFAULT_ART;
        }
      } else {
        const isPaused = Boolean(track.title);
        badge.className = isPaused ? 'badge badge-paused' : 'badge badge-idle';
        badgeText.innerText = isPaused ? 'PAUSED' : 'IDLE';
        sourceApp.innerText = '';
        title.innerText = isPaused ? track.title : 'No Active Playback';
        artist.innerText = isPaused ? track.artist : 'Waiting for media session...';
        if (!isPaused) {
          art.src = DEFAULT_ART;
        }
      }
    };

    // Initialize state on load
    window.addEventListener('pywebviewready', async () => {
      if (window.pywebview && window.pywebview.api) {
        const init = await window.pywebview.api.get_initial_state();
        document.getElementById('hubUrl').value = init.config.hub_url;
        document.getElementById('chkSync').checked = init.config.enabled;
        document.getElementById('chkAutostart').checked = init.config.autostart;
        delayVal = init.config.clear_delay || 2.0;
        document.getElementById('clearDelay').value = delayVal.toFixed(1) + 's';
        setMode(init.config.mode || 'hub');
        document.getElementById('verLabel').innerText = 'v' + init.version + ' • Check updates';

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
                "autostart": self.config.autostart,
                "clear_delay": self.config.clear_delay,
            },
            "version": updater.APP_VERSION,
            "current_track": self.latest_track_dict,
        }

    def save_settings(self, data: dict):
        if not data:
            return {"success": False}
        self.config.hub_url = data.get("hub_url", self.config.hub_url).rstrip("/")
        self.config.mode = data.get("mode", self.config.mode)
        self.config.enabled = bool(data.get("enabled", self.config.enabled))
        self.config.autostart = bool(data.get("autostart", self.config.autostart))
        self.config.data["clear_delay"] = float(data.get("clear_delay", self.config.clear_delay))
        self.config.save()

        self.hub_client.update_url(self.config.hub_url, mode=self.config.mode)
        self.on_config_changed()
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

    def check_updates(self):
        loop = asyncio.new_event_loop()
        try:
            info = loop.run_until_complete(updater.check_for_updates())
            if info:
                return {"has_update": True, "version": info["version"], "url": info["html_url"]}
            return {"has_update": False, "version": updater.APP_VERSION}
        except Exception as e:
            return {"has_update": False, "version": updater.APP_VERSION, "error": str(e)}
        finally:
            loop.close()


class WebviewDashboard:
    def __init__(self, config: Config, hub_client: HubClient, on_config_changed: Callable[[], None]):
        self.config = config
        self.hub_client = hub_client
        self.on_config_changed = on_config_changed
        self.api = WebViewApi(config, hub_client, on_config_changed)
        self.window: Optional[webview.Window] = None

    def create_window(self):
        self.window = webview.create_window(
            title="Tuneshine Windows",
            html=HTML_TEMPLATE,
            js_api=self.api,
            width=390,
            height=510,
            resizable=False,
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

    def update_media(self, track: TrackInfo):
        art_b64 = ""
        if track.thumbnail_bytes:
            art_b64 = base64.b64encode(track.thumbnail_bytes).decode("utf-8")

        track_dict = {
            "is_playing": track.is_playing,
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "app_id": track.app_id,
            "art_b64": art_b64,
        }
        self.api.latest_track_dict = track_dict

        if self.window:
            try:
                js_code = f"if (window.updateTrackInfo) {{ window.updateTrackInfo({json.dumps(track_dict)}); }}"
                self.window.evaluate_js(js_code)
            except Exception as e:
                logger.debug(f"Could not push to webview: {e}")
