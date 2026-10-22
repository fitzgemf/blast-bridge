"""Render the deterministic fictional range-board image; run only at development time."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUTPUT = Path(__file__).resolve().parents[1] / "examples/fictional/intake/demo_range_board.png"


def main() -> None:
    image = Image.new("RGBA", (1600, 1050))
    wall = ImageDraw.Draw(image)
    for y in range(1050):
        shade = 162 - 24 * y // 1049
        wall.line((0, y, 1599, y), fill=(shade, shade - 4, shade - 12, 255))
    board = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(board)
    draw.rounded_rectangle((48, 48, 1552, 1002), radius=12, fill="#555952")
    for y in range(70, 981):
        shade = 8 * (y - 70) // 910
        draw.line((70, y, 1530, y), fill=(247 - shade, 246 - shade, 234 - shade, 255))
    lighting = Image.new("RGBA", image.size)
    light = ImageDraw.Draw(lighting)
    for x in range(70, 1531):
        shade = 10 * (x - 70) ** 2 // 1460**2
        light.line((x, 70, x, 980), fill=(0, 0, 0, shade))
    board = Image.alpha_composite(board, lighting)
    draw = ImageDraw.Draw(board)
    title = ImageFont.load_default(size=48)
    body = ImageFont.load_default(size=34)
    small = ImageFont.load_default(size=28)
    draw.text((110, 105), "FICTIONAL DEMO", font=title, fill="#a62f29")
    draw.text((110, 190), "2026-10-19 / Demo Range North", font=body, fill="#1c3440")
    draw.text((110, 245), "HIMARS / Live-fire qualification", font=body, fill="#1c3440")
    draw.line((110, 320, 1490, 320), fill="#536771", width=3)
    for top, label, count, names in (
        (365, "Launcher 1", "6", ("Avery Kestrel", "Jordan Pike", "Riley Marsh")),
        (650, "Launcher 2", "?", ("Casey Thorne", "Morgan Vale", "Taylor Brook")),
    ):
        draw.text((110, top), f"{label} - {count}", font=body, fill="#1c3440")
        for offset, role, name in zip(
            (65, 115, 165), ("Chief", "Gunner", "Driver"), names, strict=True
        ):
            draw.text((160, top + offset), f"{role}: {name}", font=body, fill="#1c3440")
    draw.text((110, 925), "FICTIONAL DEMO - training record only", font=small, fill="#a62f29")
    board = board.rotate(
        1.6, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(0, 0, 0, 0)
    )
    shadow = Image.new("RGBA", board.size, (0, 0, 0, 100))
    shadow.putalpha(board.getchannel("A").point(lambda alpha: alpha * 100 // 255))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    left = (image.width - board.width) // 2
    top = (image.height - board.height) // 2
    image.alpha_composite(shadow, dest=(left + 12, top + 16))
    image.alpha_composite(board, dest=(left, top))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(OUTPUT, format="PNG")


if __name__ == "__main__":
    main()
