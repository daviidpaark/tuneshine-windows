# Tuneshine Windows Desktop Companion

[![CI](https://github.com/daviidpaark/tuneshine-windows/actions/workflows/ci.yml/badge.svg)](https://github.com/daviidpaark/tuneshine-windows/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%20%7C%203.13%20%7C%203.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6?logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A lightweight Windows System Tray desktop companion for [Tuneshine Hub](https://github.com/daviidpaark/tuneshine-hub) and [Tuneshine](https://www.tuneshine.rocks/) LED displays.

Hooks directly into Windows 10/11's native **System Media Transport Controls (SMTC)** to capture real-time playback metadata and high-resolution album artwork from **any** Windows music or video player, pushing updates directly to Tuneshine Hub (or physical Tuneshine hardware) with zero setup and zero API rate limits.

---

## The Tuneshine Ecosystem

- **[tuneshine-windows](https://github.com/daviidpaark/tuneshine-windows)** *(This repository)*: Standalone Windows System Tray desktop companion. Hooks into Windows Media Controls (SMTC) to capture and stream real-time playback from Spotify, Apple Music, YouTube, Tidal, and local players to Tuneshine Hub (or directly to a physical Tuneshine device).
- **[tuneshine-hub](https://github.com/daviidpaark/tuneshine-hub)**: Central Docker hub service. Manages 24/7 background Spotify tracking, converts raw artwork to 64×64 WebP, arbitrates multi-source priority, and drives your physical Tuneshine device.
- **[tuneshine-navidrome](https://github.com/daviidpaark/tuneshine-navidrome)**: Official Navidrome plugin. Streams live playback and cover art from your Navidrome music server to Tuneshine Hub (or directly to a physical Tuneshine device).

---

## Supported Music Players

Works out-of-the-box with any application that integrates with Windows Media Controls:
- **Spotify Desktop**
- **Apple Music (Windows Preview / Electron)**
- **Tidal**
- **YouTube / YouTube Music** (in Chrome, Edge, Firefox, Brave)
- **Foobar2000, MusicBee, AIMP, VLC**
- **Local audio files & video players**

---

## Features

- **Dual Operation Modes:**
  - **Tuneshine Hub (Offload Processing):** Passes raw cover art and metadata to a `tuneshine-hub` Docker instance, offloading WebP compression and multi-source arbitration.
  - **Direct to Device (Standalone):** Converts cover art to 64×64 lossless WebP locally via Pillow and speaks directly to physical Tuneshine hardware without requiring Docker.
- **Zero-Config Setup:** No Spotify Developer API keys, client secrets, or OAuth tokens needed.
- **Instant Event-Driven Sync:** Pushes updates the moment a track starts, changes, or pauses (similar to Discord Music Presence engines).
- **Artwork Hash Deduplication:** Eliminates redundant network calls for identical tracks or consecutive plays.
- **Clean System Tray Interface:**
  - Minimalist thin-border square icon dynamically reflecting playback state (Emerald Green = Playing, Amber = Paused, Silver = Idle).
  - One-click Target Host & Operation Mode configuration.
  - Sync pause / resume toggle.
  - Launch on Windows Startup toggle (runs silently on boot).
- **Ultra-Lightweight:** Uses `<25 MB` RAM and `0.0%` idle CPU.

---

## Operation Modes

| Mode | Target | Description |
| :--- | :--- | :--- |
| **`Tuneshine Hub`** *(Recommended)* | Tuneshine Hub (e.g. `http://unraid:8585` or `<hub-ip>:8585`) | Forwards raw cover art and playback events to the Hub Docker container for centralized arbitration and multi-device coordination. |
| **`Direct to Device`** *(Standalone)* | Physical Tuneshine (e.g. `http://192.168.1.100` or `http://tuneshine.local`) | Converts cover art to 64×64 lossless WebP locally with Pillow and uploads directly to the physical Tuneshine device. |

---

## Installation & Quick Start

### Option A: Standalone Executable (Recommended - No Python Required)

1. Download the latest `TuneshineWindows.exe` and `Install.bat` from the [Releases](https://github.com/daviidpaark/tuneshine-windows/releases) page.
2. Double-click **`Install.bat`**. This will:
   - Copy the executable to `%LOCALAPPDATA%\TuneshineWindows\`
   - Create Start Menu & Desktop shortcuts
   - Enable automatic Windows startup
   - Launch the application immediately

### Option B: Running from Source

1. Clone the repository:
   ```powershell
   git clone https://github.com/daviidpaark/tuneshine-windows.git
   cd tuneshine-windows
   ```

2. Create virtual environment and install dependencies:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Launch:
   - **With Console (for testing/logs):** Double-click `run.bat` or run:
     ```powershell
     .\.venv\Scripts\python.exe main.py
     ```
   - **Silent Background Mode:** Double-click `run_silent.vbs` or run:
     ```powershell
     .\.venv\Scripts\pythonw.exe main.py
     ```

---

## Configuration

Right-click the square **Tuneshine** icon in your Windows System Tray (near the clock):

- **Configure Target Host...** — Set the IP/URL of your Hub or physical Tuneshine (e.g. `http://unraid:8585`).
- **Operation Mode** — Switch between `Tuneshine Hub (Offload)` and `Direct to Device (Standalone)`.
- **Sync Enabled** — Pause or resume syncing.
- **Start Minimized to Tray** — Launch quietly in the system tray without opening the dashboard window.
- **Launch on Windows Startup** — Toggle automatic background start on Windows login.

Settings are saved automatically to `config.json` (in `%APPDATA%\tuneshine-windows\config.json` or local folder):

```json
{
  "hub_url": "http://localhost:8585",
  "mode": "hub",
  "enabled": true,
  "start_in_tray": true,
  "clear_delay": 2.0,
  "service_name": "Spotify",
  "autostart": false
}
```

---

## Building from Source

To compile the standalone `.exe` using PyInstaller:

```powershell
.\.venv\Scripts\python.exe build_exe.py
```

The output binary will be created at `dist/TuneshineWindows.exe`.

---

## Testing

Run unit tests with:
```powershell
.\.venv\Scripts\python.exe test_components.py
```

---

## AI Disclosure & Personal Project Note

> [!NOTE]
> This project was developed as a personal home lab tool with the assistance of **Google Antigravity (Gemini Flash)** AI pair programming. It is shared publicly for the benefit of the community and other Tuneshine owners. Contributions, feedback, and issue reports are always welcome!

---

## License

MIT License. See [LICENSE](LICENSE) for details.
