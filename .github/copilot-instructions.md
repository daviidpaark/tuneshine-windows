# TuneShine Windows Instructions

## Repository Role & Architecture
- Windows companion app for TuneShine that captures active OS media playback and album art via WinRT `GlobalSystemMediaTransportControlsSessionManager`, displays a local webview dashboard (`pywebview`), runs in the Windows system tray (`pystray`), and pushes metadata updates to TuneShine Hub via HTTP (`httpx`).
- Written in Python 3.12+ for Windows (uses `winsdk` for WinRT APIs).

## Development & Validation
- Use the virtual environment at `.venv\Scripts\python.exe`.
- Run unit and regression tests:
  ```powershell
  & ".\.venv\Scripts\python.exe" -m unittest discover -s . -p "test_*.py"
  ```
  or directly:
  ```powershell
  & ".\.venv\Scripts\python.exe" test_components.py
  ```
- All automated checks and tests should pass before concluding changes.

## Releases & CI
- Releases are published as standalone Windows executables (`TuneshineWindows.exe`) built with PyInstaller via `python build_exe.py`.
- Triggered by semantic version tags `v*` (e.g. `v0.3.7`) or manual `workflow_dispatch` with a `tag` input in `.github/workflows/release.yml`.
- Always keep `CHANGELOG.md` and `config.py` (`APP_VERSION`) synchronized before tagging.
- CI tests run across Python 3.12, 3.13, and 3.14 via `.github/workflows/ci.yml`.

## Git Workflow
- Do not commit or push unless explicitly requested by the user.
- Keep commits focused and scoped to this repository.

## Performance, Resource Lifecycle & Memory Hygiene
- **Explicit Handle & Stream Disposal:**
  - In `media_listener.py` and `hub_client.py`, never rely on garbage collection for COM streams (`IRandomAccessStreamWithContentType`, `DataReader`) or Pillow `Image` buffers.
  - Always wrap stream and image operations in `try ... finally` blocks and call `.close()`.
- **WinRT Session Event Token Tracking:**
  - WinRT projections allocate fresh Python proxy objects on every enumeration (`manager.get_sessions()`).
  - **Never use `id(session)`** or object memory addresses to deduplicate event subscriptions.
  - Track session tokens in `_attached_sessions: Dict[Any, Tuple[EventRegistrationToken, EventRegistrationToken]]`.
  - Always remove listeners via `remove_media_properties_changed` and `remove_playback_info_changed` when sessions terminate or when stopping the listener.
- **Event Debouncing & Task Coalescing:**
  - Windows OS media session changes fire in rapid bursts (e.g., track changes, playback state transitions, volume adjustments).
  - Never schedule unthrottled asyncio tasks directly into the event loop.
  - Coalesce rapid bursts using debounced scheduling (e.g., 50ms window) with non-blocking re-run flags to prevent queuing runaway coroutines behind locks.
- **Background / Idle Power & Memory Efficiency:**
  - Suppress high-cost operations (base64 image serialization, IPC message pushing, webview DOM manipulation) when the dashboard window is hidden/minimized in the system tray (`is_visible == False`).
  - Use `window.run_js(...)` for one-way webview notifications rather than `window.evaluate_js(...)` to avoid leaking callback dictionaries in `pywebview`.
  - Cache rendered state in tray `update_state()` to skip redundant PIL icon and menu regenerations when playback status is unchanged.
- **Connection & Resource Pooling:**
  - Reuse a single persistent `httpx.AsyncClient` in `hub_client.py` across background workers, and ensure `aclose()` is called upon shutdown.
