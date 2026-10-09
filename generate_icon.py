import os
import sys
from functools import lru_cache

from PIL import Image

# icon.svg is Lucide "square-play" (lucide-static v1.54.0, ISC), unmodified.
# icon.png is that file rendered at 256px with resvg; only its alpha channel is used here.
_RESOURCE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
_MASTER_PATH = os.path.join(_RESOURCE_DIR, "icon.png")

_PLAYING = (34, 197, 94)     # Emerald Green (#22c55e)
_PAUSED = (245, 158, 11)     # Amber (#f59e0b)
_IDLE = (212, 212, 216)      # Clean Zinc / Silver (#d4d4d8)


@lru_cache(maxsize=8)
def _icon_alpha(size: int) -> Image.Image:
    with Image.open(_MASTER_PATH) as master:
        alpha = master.convert("RGBA").getchannel("A")
    if alpha.size != (size, size):
        alpha = alpha.resize((size, size), Image.LANCZOS)
    return alpha


def generate_square_icon(is_playing: bool = False, is_paused: bool = False, size: int = 64) -> Image.Image:
    """Returns the app icon tinted for the playback state."""
    if is_playing:
        colour = _PLAYING
    elif is_paused:
        colour = _PAUSED
    else:
        colour = _IDLE

    img = Image.new("RGBA", (size, size), colour + (0,))
    img.putalpha(_icon_alpha(size))
    return img


def export_app_icons(output_dir: str):
    """Saves multi-resolution icon.ico and icon.png."""
    os.makedirs(output_dir, exist_ok=True)

    # Master 256x256 PNG
    master = generate_square_icon(is_playing=True, size=256)
    png_path = os.path.join(output_dir, "icon.png")
    master.save(png_path, format="PNG")

    # Multi-resolution ICO (16, 24, 32, 48, 64, 128, 256)
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_images = [generate_square_icon(is_playing=True, size=s[0]) for s in ico_sizes]
    ico_path = os.path.join(output_dir, "icon.ico")

    # Pillow drops sizes larger than the base image, so save from the largest frame
    ico_images[-1].save(
        ico_path,
        format="ICO",
        sizes=[(im.width, im.height) for im in ico_images],
        append_images=ico_images[:-1],
    )
    print(f"Generated {png_path} and {ico_path}")


if __name__ == "__main__":
    export_app_icons(os.path.dirname(os.path.abspath(__file__)))
