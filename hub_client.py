import asyncio
import hashlib
import io
import json
import logging
from typing import Optional, Dict, Any
import httpx
from PIL import Image

logger = logging.getLogger("tuneshine-windows.client")


def convert_to_tuneshine_webp(raw_image_bytes: bytes) -> bytes:
    """Converts any input image to 64x64 lossless WebP for physical Tuneshine hardware."""
    with Image.open(io.BytesIO(raw_image_bytes)) as img:
        img = img.convert("RGBA")
        img = img.resize((64, 64), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="WEBP", lossless=True)
        return out.getvalue()


class HubClient:
    def __init__(self, hub_url: str, mode: str = "hub"):
        self.hub_url = hub_url.rstrip("/")
        self.mode = mode.lower()  # "hub" or "direct"
        self.client = httpx.AsyncClient(timeout=10.0)
        self.last_sent_hash: Optional[str] = None
        self.is_currently_playing = False
        self.last_error: Optional[str] = None

    def update_url(self, hub_url: str, mode: Optional[str] = None):
        self.hub_url = hub_url.rstrip("/")
        if mode:
            self.mode = mode.lower()
        self.last_sent_hash = None
        logger.info(f"Target URL updated to: {self.hub_url} (mode: {self.mode})")

    async def close(self):
        await self.client.aclose()

    @staticmethod
    def _compute_hash(image_bytes: bytes, metadata: Dict[str, Any]) -> str:
        meta_str = json.dumps(metadata, sort_keys=True)
        h = hashlib.sha256()
        h.update(meta_str.encode("utf-8"))
        h.update(image_bytes)
        return h.hexdigest()

    async def send_playing(
        self,
        image_bytes: bytes,
        title: str,
        artist: str,
        album: str,
        service_name: str = "Windows Media",
        item_id: Optional[str] = None,
    ) -> bool:
        """Pushes playing track art and metadata to Tuneshine Hub or physical device."""
        if not image_bytes:
            logger.warning("Attempted to send playing state without image bytes")
            return False

        metadata = {
            "artistName": artist or "Unknown Artist",
            "albumName": album or title or "Unknown Album",
            "serviceName": service_name,
            "itemId": item_id or f"{artist}-{title}",
        }

        payload_hash = self._compute_hash(image_bytes, metadata)
        if payload_hash == self.last_sent_hash and self.is_currently_playing:
            # Identical payload already sent
            return True

        try:
            if self.mode == "direct":
                # Convert locally to 64x64 lossless WebP for physical Tuneshine hardware
                webp_bytes = convert_to_tuneshine_webp(image_bytes)
                files = {
                    "image": ("cover.webp", webp_bytes, "image/webp"),
                    "metadata": (None, json.dumps(metadata), "application/json"),
                }
            else:
                # Hub mode: offload conversion to Hub Docker container
                files = {"image": ("cover.png", image_bytes, "image/png")}
                data = {"metadata": json.dumps(metadata)}

            url = f"{self.hub_url}/image"
            if self.mode == "direct":
                resp = await self.client.post(url, files=files)
            else:
                resp = await self.client.post(url, files=files, data=data)

            if 200 <= resp.status_code < 300:
                self.last_sent_hash = payload_hash
                self.is_currently_playing = True
                self.last_error = None
                target_label = "Tuneshine" if self.mode == "direct" else "Hub"
                logger.info(f"Successfully pushed to {target_label}: '{title}' by '{artist}' ({len(image_bytes)} bytes)")
                return True
            else:
                self.last_error = f"HTTP {resp.status_code}: {resp.text}"
                logger.warning(f"Target responded with status {resp.status_code}: {resp.text}")
                return False
        except httpx.RequestError as e:
            self.last_error = f"Connection error: {e}"
            logger.warning(f"Failed to push to target ({self.hub_url}): {e}")
            return False

    async def send_stopped(self) -> bool:
        """Notifies Tuneshine Hub that playback has stopped/paused."""
        if not self.is_currently_playing:
            return True

        try:
            resp = await self.client.delete(f"{self.hub_url}/image")
            if resp.status_code == 200:
                self.is_currently_playing = False
                self.last_sent_hash = None
                self.last_error = None
                logger.info("Successfully sent STOP to Hub")
                return True
            else:
                self.last_error = f"HTTP {resp.status_code}: {resp.text}"
                logger.warning(f"Hub responded to DELETE with {resp.status_code}: {resp.text}")
                return False
        except httpx.RequestError as e:
            self.last_error = f"Connection error: {e}"
            logger.warning(f"Failed to send DELETE to Hub ({self.hub_url}): {e}")
            return False

    async def check_health(self) -> Dict[str, Any]:
        """Queries the Hub's /health or /state endpoint."""
        try:
            resp = await self.client.get(f"{self.hub_url}/health")
            if resp.status_code == 200:
                return {"online": True, "data": resp.json()}
            return {"online": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"online": False, "error": str(e)}
