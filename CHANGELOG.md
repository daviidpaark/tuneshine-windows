# Changelog

All notable changes to the `tuneshine-windows` desktop companion will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.0] - 2026-08-29

### Added
- **Streamlined Program Filtering (Allow & Block):** Introduced customizable program filtering with three operation modes:
  - `Off (Allow All)`: All detected media players sync without restriction.
  - `Block Mode`: Disables synchronization for blocked programs (e.g. `chrome.exe`, `msedge.exe`, Discord, games) while allowing all other media players.
  - `Allow Mode`: Strict mode. Only permits explicitly approved media players (e.g. `Spotify.exe`, `Apple Music`).
- **Dynamic Program Discovery:** Automatically detects active media players on Windows in real-time and registers them in the dashboard with clean human-readable names and timestamps.
- **Dedicated Allow / Block Toggles:** 1-click `[ Allow ]` and `[ Block ]` pills per program with immediate status reflection.
- **Smart Session Fallback:** When Windows' currently focused session is blocked by a filter rule, Tuneshine automatically inspects background media sessions to keep music syncing uninterrupted.
- **Real-Time Hero Card Status:** Displays `BLOCKED` (red) status and app details whenever active playback is filtered out.
- **Automated Installer Rebuild:** Installer automatically detects modified Python source code and recompiles `dist\TuneshineWindows.exe` prior to installation.

---

## [0.2.0] - 2026-08-29

### Added
- **Start in System Tray:** Companion now starts quietly in the system tray by default without popping up the dashboard window.
- **"Start Minimized to Tray" Setting:** Added preferences toggle switch to easily configure whether the dashboard opens on launch.
- **Command Line Flags:** Added `--show` / `--dashboard` (force visible) and `--tray` / `--minimized` / `--hidden` (force hidden) launch options.
- **Config Location Indicator:** Added active configuration file indicator in the dashboard footer with one-click opening of the config folder in Windows File Explorer.

### Fixed
- **Default Service Name:** Set default service name to `Spotify` across hub and standalone payloads.
- **Settings Persistence to File:** Guaranteed immediate `config.json` file saving across all inputs (text inputs auto-save on change/blur/Enter; toggles auto-save on switch).
- **Configuration Property Setters:** Added complete setters with type casting and auto-save for `clear_delay`, `service_name`, `start_in_tray`, and `autostart`.
- **Portable & Local Config Support:** Added resolution of local `config.json` in working/application directory before falling back to `%APPDATA%\tuneshine-windows\config.json`.
- **Windows Autostart Registry for Frozen Executables:** Fixed startup registry entry command to properly point to compiled `TuneshineWindows.exe` without appending `main.py`.

---

## [0.1.0] - 2026-08-28

### Added
- **Native Windows SMTC Integration:** Hooks directly into Windows 10/11 WinRT `GlobalSystemMediaTransportControlsSessionManager` to capture real-time playback metadata and high-res cover art.
- **Universal Player Support:** Out-of-the-box support for Spotify, Apple Music, Tidal, YouTube (Chrome/Firefox/Edge), Foobar2000, VLC, and local media.
- **Dual Operation Modes:**
  - `Tuneshine Hub (Offload)`: Forwards raw artwork and metadata to a `tuneshine-hub` Docker instance.
  - `Direct to Device (Standalone)`: Encodes 64×64 lossless WebP locally via Pillow and sends directly to physical Tuneshine hardware.
- **System Tray Interface:**
  - Minimalist dynamic thin-border square tray icon reflecting playback state (Emerald Green = Playing, Amber = Paused, Silver = Idle).
  - Target host & operation mode configuration popup.
  - Sync pause/resume toggle.
  - Auto-launch on Windows Startup toggle.
- **Artwork Hash Deduplication:** Computes SHA256 checksums of artwork & metadata to eliminate redundant network transmissions.
- **1-Click Packaging & Installer:** Bundled standalone executable (`TuneshineWindows.exe`) with `Install.bat` and `Uninstall.bat`.
