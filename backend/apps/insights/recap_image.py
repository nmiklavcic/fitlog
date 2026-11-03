"""Renders the shareable 1080x1080 recap card with Pillow (no browser, no extra services)."""
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageDraw, ImageFont

SIZE = 1080
TOP_COLOR = (79, 70, 229)  # indigo
BOTTOM_COLOR = (17, 24, 39)  # near-black
KG_TO_LB = 2.20462


def _font(size):
    # Pillow ships a scalable default font (FreeType), so no font files are needed.
    return ImageFont.load_default(size=size)


def _volume_label(volume_kg, units):
    value = volume_kg * KG_TO_LB if units == "lb" else volume_kg
    return f"{value:,.0f} {units}"


def render_recap(label, stats, username, units="kg"):
    image = Image.new("RGB", (SIZE, SIZE))
    draw = ImageDraw.Draw(image)
    for y in range(SIZE):
        t = y / SIZE
        draw.line([(0, y), (SIZE, y)], fill=tuple(int(TOP_COLOR[i] * (1 - t) + BOTTOM_COLOR[i] * t) for i in range(3)))

    draw.text((80, 80), "LIFTLOG RECAP", font=_font(34), fill=(199, 210, 254))
    draw.text((80, 128), label, font=_font(78), fill="white")
    draw.text((80, 228), f"@{username}", font=_font(38), fill=(224, 231, 255))

    tiles = [
        ("Workouts", str(stats["workouts"])),
        ("Volume", _volume_label(stats["volume_kg"], units)),
        ("Personal records", str(stats["pr_count"])),
        ("Sets", str(stats["sets"])),
        ("Best weekly streak", f"{stats['longest_weekly_streak']} wk"),
        ("Most trained", (stats["most_trained_muscle"] or "-").title()),
    ]
    tile_w, tile_h, gap, top = 440, 170, 40, 330
    for index, (title, value) in enumerate(tiles):
        col, row = index % 2, index // 2
        x, y = 80 + col * (tile_w + gap), top + row * (tile_h + gap)
        draw.rounded_rectangle([x, y, x + tile_w, y + tile_h], radius=28, fill=(30, 27, 75))
        draw.text((x + 32, y + 28), title.upper(), font=_font(26), fill=(165, 180, 252))
        draw.text((x + 32, y + 72), value, font=_font(60), fill="white")

    if stats.get("top_exercise"):
        draw.text((80, 980), f"Top lift: {stats['top_exercise']}", font=_font(34), fill=(199, 210, 254))

    buffer = BytesIO()
    image.save(buffer, "PNG")
    return SimpleUploadedFile("recap.png", buffer.getvalue(), content_type="image/png")
