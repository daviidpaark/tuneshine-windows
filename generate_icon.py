import os
from PIL import Image, ImageDraw


def generate_square_icon(is_playing: bool = False, is_paused: bool = False, size: int = 64) -> Image.Image:
    """
    Generates a crisp minimalist thin-border square matching the Tuneshine hardware outline.
    The center is clean/transparent and the border dynamically reflects state.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Crisp proportional stroke width (1px at 16/24px, 2px at 32/48px, 3px at 64px, 6px at 256px)
    stroke_w = max(1, int(round(size * 0.05)))
    margin = max(1, int(round(size * 0.08)))
    radius = max(1, int(round(size * 0.06)))

    if is_playing:
        border_col = (34, 197, 94, 255)      # Emerald Green (#22c55e)
    elif is_paused:
        border_col = (245, 158, 11, 255)     # Amber (#f59e0b)
    else:
        border_col = (212, 212, 216, 255)    # Clean Zinc / Silver (#d4d4d8)

    box = [margin, margin, size - margin - 1, size - margin - 1]
    # Pure transparent interior with crisp thin border
    draw.rounded_rectangle(box, radius=radius, fill=(0, 0, 0, 0), outline=border_col, width=stroke_w)
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
    
    # Correct Pillow multi-frame ICO saving
    ico_images[0].save(
        ico_path,
        format="ICO",
        sizes=[(im.width, im.height) for im in ico_images],
        append_images=ico_images[1:],
    )
    print(f"Generated {png_path} and {ico_path}")


if __name__ == "__main__":
    export_app_icons("c:/Users/david/Documents/Git/tuneshine-windows")
