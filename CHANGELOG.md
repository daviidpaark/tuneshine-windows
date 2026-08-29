# Changelog

All notable changes to the `tuneshine-windows` desktop companion will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
