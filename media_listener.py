import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable, List
import winrt.windows.media.control as wmc
import winrt.windows.storage.streams as wss

try:
    import winrt.windows.foundation.collections  # Required for IVectorView enumeration
except ImportError:
    pass

from config import Config

logger = logging.getLogger("tuneshine-windows.listener")

# WinRT Playback Status
STATUS_PLAYING = wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING


@dataclass
class TrackInfo:
    is_playing: bool
    title: str = ""
    artist: str = ""
    album: str = ""
    app_id: str = ""
    app_name: str = ""
    thumbnail_bytes: Optional[bytes] = None
    is_blocked: bool = False

    @property
    def summary(self) -> str:
        name = self.app_name or self.app_id
        if self.is_blocked:
            return f"Blocked: {name}" if name else "Blocked by filter"
        if not self.is_playing:
            if self.artist and self.title:
                return f"[Paused] {self.title} - {self.artist}"
            if self.title:
                return f"[Paused] {self.title}"
            return "Idle / Paused"
        if self.artist and self.title:
            return f"{self.title} - {self.artist}"
        return self.title or "Playing"


class MediaListener:
    def __init__(
        self,
        on_update: Callable[[TrackInfo], Awaitable[None]],
        config: Optional[Config] = None,
        on_detected_apps_changed: Optional[Callable[[], None]] = None,
    ):
        self.on_update = on_update
        self.config = config
        self.on_detected_apps_changed = on_detected_apps_changed
        self.manager: Optional[wmc.GlobalSystemMediaTransportControlsSessionManager] = None
        self.current_session: Optional[wmc.GlobalSystemMediaTransportControlsSession] = None
        self._attached_session_ids: set = set()
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._last_state_key: Optional[str] = None
        self.current_track: TrackInfo = TrackInfo(is_playing=False)
        self._check_lock: Optional[asyncio.Lock] = None

    async def start(self):
        """Initializes WinRT session manager and begins listening."""
        self._running = True
        self._loop = asyncio.get_running_loop()
        self._check_lock = asyncio.Lock()
        try:
            self.manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
            self.manager.add_current_session_changed(self._on_current_session_changed)
            try:
                self.manager.add_sessions_changed(self._on_sessions_changed)
            except Exception:
                pass
            logger.info("WinRT Media Session Manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WinRT Session Manager: {e}")

        # Start the background sync loop (handles active polling & event fallbacks)
        asyncio.create_task(self._sync_loop())

    def stop(self):
        self._running = False
        self.current_session = None
        self._attached_session_ids.clear()

    def invalidate_state(self):
        """Forces the next check_current_media call to re-evaluate and emit state."""
        self._last_state_key = None

    def _is_allowed(self, app_id: str) -> bool:
        if not self.config:
            return True
        return self.config.is_app_allowed(app_id)

    def _register_app_if_new(self, app_id: str):
        if not app_id or not self.config:
            return
        if self.config.is_app_ignored(app_id):
            return
        is_new = self.config.register_detected_app(app_id)
        if is_new and self.on_detected_apps_changed:
            try:
                self.on_detected_apps_changed()
            except Exception as e:
                logger.debug(f"Error in on_detected_apps_changed: {e}")

    def _scan_all_sessions(self) -> List[wmc.GlobalSystemMediaTransportControlsSession]:
        """Discovers all active media sessions and registers their app IDs dynamically."""
        sessions = []
        if not self.manager:
            return sessions
        try:
            raw_sessions = self.manager.get_sessions()
            if raw_sessions:
                for s in raw_sessions:
                    try:
                        app_id = s.source_app_user_model_id or ""
                        if app_id and not (self.config and self.config.is_app_ignored(app_id)):
                            # Only register if session is active (playing or paused)
                            try:
                                pb = s.get_playback_info()
                                st = pb.playback_status if pb else None
                                if st in (STATUS_PLAYING, wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus.PAUSED):
                                    self._register_app_if_new(app_id)
                            except Exception:
                                pass
                        self._attach_session_events(s)
                        sessions.append(s)
                    except Exception as e:
                        logger.debug(f"Error inspecting individual session: {e}")
        except Exception as e:
            logger.debug(f"Could not enumerate all sessions: {e}")
            # If session enumeration failed due to COM disconnect, trigger re-request
            err_str = str(e).lower()
            if "disconnected" in err_str or "closed" in err_str:
                self.manager = None
        return sessions

    def _on_sessions_changed(self, sender, args):
        """WinRT event handler for session list changed."""
        if self._loop and self._running:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.check_current_media(trigger="sessions_changed"))
            )

    def _on_current_session_changed(self, sender, args):
        """WinRT event handler for active media session change."""
        if self._loop and self._running:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.check_current_media(trigger="session_changed"))
            )

    def _on_media_properties_changed(self, sender, args):
        """WinRT event handler for title/artist/album/art changes."""
        if self._loop and self._running:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.check_current_media(trigger="props_changed"))
            )

    def _on_playback_info_changed(self, sender, args):
        """WinRT event handler for play/pause/stop changes."""
        if self._loop and self._running:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.check_current_media(trigger="playback_changed"))
            )

    def _attach_session_events(self, session: wmc.GlobalSystemMediaTransportControlsSession):
        if not session:
            return
        try:
            session_id = str(id(session))
            if session_id in self._attached_session_ids:
                return
            session.add_media_properties_changed(self._on_media_properties_changed)
            session.add_playback_info_changed(self._on_playback_info_changed)
            self._attached_session_ids.add(session_id)
        except Exception as e:
            logger.debug(f"Could not attach session event listeners: {e}")

    async def _read_thumbnail(self, thumbnail_ref) -> Optional[bytes]:
        """Reads the IRandomAccessStreamReference into bytes safely."""
        if not thumbnail_ref:
            return None
        try:
            stream = await thumbnail_ref.open_read_async()
            if not stream or stream.size == 0:
                return None
            reader = wss.DataReader(stream)
            await reader.load_async(stream.size)
            buf = bytearray(stream.size)
            reader.read_bytes(buf)
            return bytes(buf)
        except Exception as e:
            logger.debug(f"Error reading thumbnail stream: {e}")
            return None

    async def check_current_media(self, trigger: str = "poll"):
        """Inspects media sessions with filter awareness and multi-tier priority selection."""
        if not self._running:
            return

        if self._check_lock is None:
            self._check_lock = asyncio.Lock()

        # Prevent overlapping concurrent evaluations
        async with self._check_lock:
            await self._check_current_media_unlocked(trigger=trigger)

    async def _check_current_media_unlocked(self, trigger: str = "poll"):
        if not self.manager:
            try:
                self.manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
                self._attached_session_ids.clear()
            except Exception:
                return

        try:
            # 1. Discover all active sessions on Windows
            all_sessions = self._scan_all_sessions()
            
            try:
                current_session = self.manager.get_current_session()
            except Exception:
                current_session = None

            if current_session:
                try:
                    curr_id = current_session.source_app_user_model_id or ""
                    if curr_id and not (self.config and self.config.is_app_ignored(curr_id)):
                        self._register_app_if_new(curr_id)
                    self._attach_session_events(current_session)
                except Exception:
                    pass

            # Build candidate list with current_session prioritized at head
            candidate_sessions = []
            if current_session:
                candidate_sessions.append(current_session)
            for s in all_sessions:
                if s not in candidate_sessions:
                    candidate_sessions.append(s)

            # Score each candidate session
            # Higher score = higher priority
            best_allowed_session = None
            best_allowed_score = -1

            best_blocked_session = None
            best_blocked_score = -1

            for s in candidate_sessions:
                try:
                    app_id = s.source_app_user_model_id or ""
                    if not app_id:
                        continue
                    if self.config and self.config.is_app_ignored(app_id):
                        continue
                    is_allowed = self._is_allowed(app_id)
                    pb = s.get_playback_info()
                    status = pb.playback_status if pb else None

                    # Playback status mappings
                    is_playing = bool(status == STATUS_PLAYING)
                    is_paused = bool(status == wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus.PAUSED)
                    is_stopped = bool(status == wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus.STOPPED)
                    is_closed = bool(status == wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus.CLOSED)

                    if is_closed:
                        continue

                    # Prioritization scoring
                    score = 0
                    if is_allowed:
                        if is_playing:
                            score = 100
                        elif is_paused:
                            score = 50
                        elif not is_stopped:
                            score = 30
                        else:
                            score = 10

                        # OS active session gets preference bonus
                        if s == current_session:
                            score += 5

                        if score > best_allowed_score:
                            best_allowed_score = score
                            best_allowed_session = s
                    else:
                        if is_playing:
                            score = 20
                            if s == current_session:
                                score += 5
                            if score > best_blocked_score:
                                best_blocked_score = score
                                best_blocked_session = s
                except Exception as e:
                    logger.debug(f"Error evaluating candidate session: {e}")

            # 2. Select chosen session based on priority:
            # - If an allowed session exists (playing or paused), use it
            # - If only blocked playing sessions exist, display blocked status
            # - Otherwise, idle

            chosen_session = best_allowed_session

            if chosen_session:
                self.current_session = chosen_session
                try:
                    pb = chosen_session.get_playback_info()
                    is_playing = bool(pb and pb.playback_status == STATUS_PLAYING)
                except Exception:
                    is_playing = False

                app_id = chosen_session.source_app_user_model_id or "Unknown"
                title = ""
                artist = ""
                album = ""
                thumbnail_ref = None

                try:
                    props = await chosen_session.try_get_media_properties_async()
                    if props:
                        title = props.title or ""
                        artist = props.artist or ""
                        album = props.album_title or ""
                        thumbnail_ref = props.thumbnail
                except Exception as e:
                    logger.debug(f"Error retrieving media properties: {e}")

                state_key = f"{'playing' if is_playing else 'paused'}:{app_id}:{artist}:{title}:{album}"

                thumbnail_bytes = None
                if thumbnail_ref:
                    # Fetch thumbnail if track changed or if previous thumbnail was missing
                    if state_key != self._last_state_key or self.current_track.thumbnail_bytes is None:
                        thumbnail_bytes = await self._read_thumbnail(thumbnail_ref)
                    else:
                        thumbnail_bytes = self.current_track.thumbnail_bytes

                from config import get_friendly_app_name
                app_name = get_friendly_app_name(app_id)

                track = TrackInfo(
                    is_playing=is_playing,
                    is_blocked=False,
                    title=title,
                    artist=artist,
                    album=album,
                    app_id=app_id,
                    app_name=app_name,
                    thumbnail_bytes=thumbnail_bytes,
                )

                # Send update if state changed OR if thumbnail arrived asynchronously
                needs_update = (
                    state_key != self._last_state_key
                    or (is_playing and thumbnail_bytes is not None and self.current_track.thumbnail_bytes is None)
                )

                if needs_update:
                    self._last_state_key = state_key
                    self.current_track = track
                    await self.on_update(track)
                return

            # If no allowed session, check if there is an active blocked session playing
            if best_blocked_session:
                self.current_session = best_blocked_session
                curr_app = best_blocked_session.source_app_user_model_id or "Unknown"
                from config import get_friendly_app_name
                app_name = get_friendly_app_name(curr_app)

                title = "Blocked Playback"
                artist = ""
                album = ""
                try:
                    props = await best_blocked_session.try_get_media_properties_async()
                    if props:
                        title = props.title or "Blocked Playback"
                        artist = props.artist or ""
                        album = props.album_title or ""
                except Exception:
                    pass

                blocked_track = TrackInfo(
                    is_playing=False,
                    is_blocked=True,
                    title=title,
                    artist=artist,
                    album=album,
                    app_id=curr_app,
                    app_name=app_name,
                    thumbnail_bytes=None,
                )
                state_key = f"blocked:{curr_app}:{artist}:{title}:{album}"
                if state_key != self._last_state_key:
                    self._last_state_key = state_key
                    self.current_track = blocked_track
                    await self.on_update(blocked_track)
                return

            # No sessions active -> IDLE
            self.current_session = None
            idle_track = TrackInfo(is_playing=False, is_blocked=False)
            state_key = "idle"
            if state_key != self._last_state_key:
                self._last_state_key = state_key
                self.current_track = idle_track
                await self.on_update(idle_track)

        except Exception as e:
            logger.debug(f"Exception checking media ({trigger}): {e}")
            err_str = str(e).lower()
            if "disconnected" in err_str or "closed" in err_str or "0x80010108" in err_str:
                logger.info("WinRT session manager connection dropped, will re-request on next cycle")
                self.manager = None
                self._attached_session_ids.clear()

    async def _sync_loop(self):
        """Adaptive periodic sync loop to ensure display stays in sync."""
        while self._running:
            try:
                await self.check_current_media(trigger="loop")
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")

            # Sleep 1.5s when playing, 3.0s when idle
            delay = 1.5 if self.current_track.is_playing else 3.0
            await asyncio.sleep(delay)
