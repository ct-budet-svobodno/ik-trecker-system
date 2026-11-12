"""Branded image fallback for chats where Telegram rejects widget media."""

from collections.abc import Sequence
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


_FONT = Path(__file__).resolve().parents[1] / "assets" / "Cygre-Medium.ttf"
_BG = "#131019"
_SURFACE = "#232230"
_TEXT = "#f1f0f5"
_MUTED = "#a6a1b4"
_VIOLET = "#8b5cf6"
_PINK = "#cb77ab"
_ORANGE = "#ff9934"
_TEAL = "#2dd4bf"


def _fit(draw: ImageDraw.ImageDraw, value: str, font: ImageFont.FreeTypeFont, width: int) -> str:
    if draw.textbbox((0, 0), value, font=font)[2] <= width:
        return value
    while value and draw.textbbox((0, 0), value + "…", font=font)[2] > width:
        value = value[:-1]
    return value + "…"


def render_valyny_image(rows: Sequence[tuple[str, int]], date_label: str) -> bytes:
    """Render the same leaderboard as a PNG for unsupported group chats."""
    image = Image.new("RGB", (800, 1000), _BG)
    draw = ImageDraw.Draw(image)
    font_small = ImageFont.truetype(str(_FONT), 21)
    font_body = ImageFont.truetype(str(_FONT), 29)
    font_number = ImageFont.truetype(str(_FONT), 31)
    font_title = ImageFont.truetype(str(_FONT), 43)
    font_mark = ImageFont.truetype(str(_FONT), 37)

    draw.rounded_rectangle((22, 22, 778, 978), radius=28, fill=_SURFACE, outline="#3d3b50", width=2)
    draw.rounded_rectangle((51, 51, 113, 113), radius=17, fill=_VIOLET)
    draw.text((60, 60), "ИК", font=font_mark, fill="white")
    draw.text((132, 62), "ИНФОРМАЦИОННЫЙ", font=font_small, fill=_TEXT)
    draw.text((132, 87), "КОМИТЕТ", font=font_small, fill=_MUTED)
    draw.text((610, 72), date_label, font=font_small, fill=_MUTED)
    for x, color in ((52, _PINK), (294, _ORANGE), (536, _TEAL)):
        draw.rounded_rectangle((x, 135, x + 212, 140), radius=2, fill=color)

    draw.text((52, 157), "Топ валын ИК", font=font_title, fill=_TEXT)
    draw.text((54, 213), "Десятка лидеров по команде !метр", font=font_small, fill=_MUTED)

    for rank, (name, size) in enumerate(rows[:10], 1):
        y = 253 + (rank - 1) * 66
        border = (_VIOLET, _PINK, _ORANGE)[rank - 1] if rank <= 3 else "#302e3f"
        fill = "#302448" if rank == 1 else "#1b1a24"
        draw.rounded_rectangle((52, y, 748, y + 57), radius=13, fill=fill, outline=border, width=2)
        draw.text((69, y + 11), f"{rank:02}", font=font_body, fill=border if rank <= 3 else _MUTED)
        label = _fit(draw, name or "без имени", font_body, 445)
        draw.text((119, y + 11), label, font=font_body, fill=_TEXT)
        value = f"{int(size)} СМ"
        value_width = draw.textbbox((0, 0), value, font=font_number)[2]
        draw.text((726 - value_width, y + 9), value, font=font_number, fill=_TEAL)

    draw.text((54, 928), "РЕЙТИНГ НА МОМЕНТ ЗАПРОСА", font=font_small, fill=_MUTED)
    draw.text((641, 928), "!МЕТР ↗", font=font_small, fill=_ORANGE)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
