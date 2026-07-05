"""Generate a simple icon for the app and tray."""

from PIL import Image, ImageDraw


def main() -> None:
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    bg_color = (30, 30, 35, 255)
    caret_color = (80, 220, 120, 255)

    draw.rounded_rectangle((8, 8, size - 8, size - 8), radius=48, fill=bg_color)
    cx, cy = size // 2, size // 2
    points = [(cx, cy - 50), (cx - 60, cy + 40), (cx + 60, cy + 40)]
    draw.polygon(points, fill=caret_color)

    img.save(
        r"assets\icon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (256, 256)],
    )
    print("Created assets/icon.ico")


if __name__ == "__main__":
    main()
