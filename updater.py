import asyncio
import logging
import re
import webbrowser
from typing import Optional, Dict, Any, Tuple
import httpx

logger = logging.getLogger("tuneshine-windows.updater")

APP_VERSION = "0.1.0"
GITHUB_REPO = "daviidpaark/tuneshine-windows"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def parse_version(ver_str: str) -> Tuple[int, ...]:
    """Parses semver string like 'v1.2.3' or '1.2' into a comparable tuple of integers."""
    clean = re.sub(r"^[^\d]*", "", ver_str.strip())
    parts = []
    for piece in clean.split("."):
        nums = re.findall(r"\d+", piece)
        if nums:
            parts.append(int(nums[0]))
        else:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


async def check_for_updates() -> Optional[Dict[str, Any]]:
    """
    Checks the GitHub Releases API for a newer version than APP_VERSION.
    Returns release info dict if an update is available, otherwise None.
    """
    headers = {
        "User-Agent": f"TuneshineWindows/{APP_VERSION}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(RELEASES_API_URL, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                tag_name = data.get("tag_name", "")
                latest_ver = parse_version(tag_name)
                current_ver = parse_version(APP_VERSION)

                if latest_ver > current_ver:
                    clean_tag = tag_name.lstrip("v")
                    html_url = data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases")
                    
                    # Look for standalone executable asset
                    exe_url = None
                    for asset in data.get("assets", []):
                        if asset.get("name", "").endswith(".exe"):
                            exe_url = asset.get("browser_download_url")
                            break

                    logger.info(f"Update available: v{clean_tag} (current: v{APP_VERSION})")
                    return {
                        "version": clean_tag,
                        "tag": tag_name,
                        "html_url": html_url,
                        "download_url": exe_url or html_url,
                        "body": data.get("body", ""),
                    }
                else:
                    logger.debug(f"Application is up to date (current: v{APP_VERSION}, latest: {tag_name})")
            elif resp.status_code == 404:
                logger.debug("No releases found on GitHub repository")
            else:
                logger.debug(f"GitHub Releases API returned status {resp.status_code}")
    except Exception as e:
        logger.debug(f"Failed to check for updates: {e}")

    return None


def open_release_page(url: Optional[str] = None):
    """Opens the GitHub release page in the user's default browser."""
    target_url = url or f"https://github.com/{GITHUB_REPO}/releases/latest"
    webbrowser.open(target_url)
