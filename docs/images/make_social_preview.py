"""Makes social-preview.png (1280x640), the image GitHub shows when the repository is linked.

The terminal on the right is not drawn: it is cut out of the last frame of demo.gif, which is a
recording of a real run (see README.md in this directory). Two pieces of that frame are put one
above the other: the error with dbt's diff, and the summary with the exit code. Nothing in them is
typed or edited. The text on the left is the tagline of the README.

Run from the root of the repository:  uvx --with pillow python docs/images/make_social_preview.py
Fonts: DejaVu Sans and DejaVu Sans Mono (the ones demo.gif was drawn with).
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageSequence

HERE = Path(__file__).parent
FONTS = Path("/usr/share/fonts/truetype/dejavu")
WIDTH, HEIGHT = 1280, 640
PANEL = (23, 27, 33)  # the background of the terminal in demo.gif, so the excerpt has no band
BACKGROUND = (13, 17, 23)
LINE = (48, 54, 61)
WHITE = (240, 246, 252)
SOFT = (201, 209, 217)
MUTED = (139, 148, 158)


def last_frame() -> Image.Image:
    gif = Image.open(HERE / "demo.gif")
    return [f.copy().convert("RGB") for f in ImageSequence.Iterator(gif)][-1]


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def terminal_excerpt(scale: float) -> Image.Image:
    frame = last_frame()
    error_and_diff = frame.crop((0, 342, 620, 502))
    summary = frame.crop((0, 633, 620, 676))  # without the cursor under the last line
    gap = 16
    excerpt = Image.new("RGB", (620, error_and_diff.height + gap + summary.height), PANEL)
    excerpt.paste(error_and_diff, (0, 0))
    excerpt.paste(summary, (0, error_and_diff.height + gap))
    size = (round(excerpt.width * scale), round(excerpt.height * scale))
    return excerpt.resize(size, Image.LANCZOS)


def main() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    left = 72
    draw.text((left, 92), "dbt-macro-test", font=font("DejaVuSansMono.ttf", 30), fill=MUTED)
    title = font("DejaVuSans-Bold.ttf", 72)
    draw.text((left, 148), "Test your", font=title, fill=WHITE)
    draw.text((left, 240), "dbt macros.", font=title, fill=WHITE)
    sub = font("DejaVuSans.ttf", 28)
    draw.text((left, 372), "Arguments in, rows out, in YAML.", font=sub, fill=SOFT)
    draw.text((left, 414), "Run by dbt's own unit tests.", font=sub, fill=SOFT)

    command = "pip install dbt-macro-test"
    mono = font("DejaVuSansMono.ttf", 28)
    box = (left, 498, left + round(draw.textlength(command, font=mono)) + 56, 498 + 68)
    draw.rounded_rectangle(box, radius=14, fill=PANEL, outline=LINE, width=2)
    draw.text((left + 28, 498 + 17), command, font=mono, fill=WHITE)

    excerpt = terminal_excerpt(scale=0.94)
    panel_x, panel_w = 624, WIDTH - 624 - 48
    panel_h = excerpt.height + 54 + 28
    panel_y = (HEIGHT - panel_h) // 2
    draw.rounded_rectangle(
        (panel_x, panel_y, panel_x + panel_w, panel_y + panel_h),
        radius=18, fill=PANEL, outline=LINE, width=2,
    )
    for i, colour in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        cx = panel_x + 30 + i * 28
        draw.ellipse((cx - 8, panel_y + 22 - 8, cx + 8, panel_y + 22 + 8), fill=colour)
    image.paste(excerpt, (panel_x + (panel_w - excerpt.width) // 2, panel_y + 54))

    image.save(HERE / "social-preview.png", optimize=True)


if __name__ == "__main__":
    main()
