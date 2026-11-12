"""A compact, self-contained Telegram widget for the ИК meter leaderboard."""

import html
import zlib
from collections.abc import Sequence

from aiogram.methods import TelegramMethod
from aiogram.types import Message


class SendWidget(TelegramMethod[Message]):
    """Bot API 10.4 method, pending a typed equivalent in aiogram."""

    __returning__ = Message
    __api_method__ = "sendWidget"

    chat_id: int | str
    html: str
    width: int = 0
    height: int = 0
    caption: str | None = None
    message_thread_id: int | None = None


_STYLE = """<style>
*{box-sizing:border-box}
body{margin:0;background:#131019;color:#f1f0f5;font:14px/1.3 system-ui,sans-serif}
.card{width:100%;padding:18px;border:1px solid #3d3b50;border-radius:18px;background:linear-gradient(145deg,#232230,#131019 55%,#1b1a24)}
.top{display:flex;align-items:center;justify-content:space-between;gap:8px}
.mark{display:flex;align-items:center;gap:9px;font-weight:900;letter-spacing:.06em}
.ik{display:grid;place-items:center;width:37px;height:37px;border-radius:11px;background:#8b5cf6;color:#fff;font-size:18px}
.eyebrow{color:#a6a1b4;font-size:10px;font-weight:800;letter-spacing:.13em}
.date{color:#a6a1b4;font-size:11px}
.rule{height:3px;margin:15px 0;background:linear-gradient(90deg,#cb77ab,#ff9934,#2dd4bf);border-radius:4px}
h1{margin:0 0 3px;font-size:23px;line-height:1.1;letter-spacing:-.03em}
.sub{margin:0 0 15px;color:#a6a1b4;font-size:12px}
.list{display:grid;gap:5px}
.row{display:flex;align-items:center;gap:9px;min-height:38px;padding:6px 9px;border:1px solid #302e3f;border-radius:10px;background:#1b1a24}
.row.first{border-color:#8b5cf6;background:#302448}
.row.second{border-color:#cb77ab}
.row.third{border-color:#ff9934}
.rank{flex:0 0 25px;color:#a6a1b4;font-size:12px;font-weight:800}
.first .rank{color:#c4a9ff}.second .rank{color:#cb77ab}.third .rank{color:#ff9934}
.name{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600}
.size{flex:0 0 auto;color:#2dd4bf;font-size:17px;font-weight:900;white-space:nowrap}
.size small{font-size:10px;font-weight:700}
.foot{display:flex;justify-content:space-between;gap:8px;margin-top:14px;color:#a6a1b4;font-size:10px;font-weight:700;letter-spacing:.04em}
.foot b{color:#ff9934}
</style>"""


def render_valyny_widget(rows: Sequence[tuple[str, int]], date_label: str) -> str:
    """Render a snapshot; Telegram enforces 32 KB HTML and 4 KB zlib limits."""
    items = []
    for rank, (name, size) in enumerate(rows[:10], 1):
        short_name = name[:47] + "…" if len(name) > 48 else name
        safe_name = html.escape(short_name or "без имени", quote=True)
        cls = ("first", "second", "third")[rank - 1] if rank <= 3 else ""
        items.append(
            f'<div class="row {cls}"><span class="rank">{rank:02}</span>'
            f'<span class="name">{safe_name}</span>'
            f'<span class="size">{int(size)} <small>СМ</small></span></div>'
        )
    safe_date = html.escape(date_label, quote=True)
    document = (
        '<!doctype html><html lang="ru"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        + _STYLE
        + '<div class="card"><div class="top"><div class="mark"><span class="ik">ИК</span>'
        + '<span class="eyebrow">ИНФОРМАЦИОННЫЙ КОМИТЕТ</span></div>'
        + f'<span class="date">{safe_date}</span></div>'
        + '<div class="rule"></div><h1>Топ валын ИК</h1>'
        + '<p class="sub">Десятка лидеров по команде !метр</p>'
        + '<div class="list">' + "".join(items) + '</div>'
        + '<div class="foot"><span>РЕЙТИНГ НА МОМЕНТ ЗАПРОСА</span><b>!МЕТР ↗</b></div>'
        + '</div></html>'
    )
    source = document.encode("utf-8")
    if len(source) > 32_768 or len(zlib.compress(source, 9)) > 4_096:
        raise ValueError("Valyny widget exceeds Telegram size limits")
    return document


def valyny_caption(rows: Sequence[tuple[str, int]]) -> str:
    """Text that stays readable when a Telegram client cannot render widgets."""
    lines = ["🍆 Топ 10 валын ИК"]
    for rank, (name, size) in enumerate(rows[:10], 1):
        short_name = name or "без имени"
        if len(short_name.encode("utf-8")) > 48:
            prefix = ""
            for character in short_name:
                if len((prefix + character).encode("utf-8")) > 45:
                    break
                prefix += character
            short_name = prefix + "…"
        lines.append(f"{rank}. {short_name or 'без имени'} — {int(size)} СМ")
    return "\n".join(lines)
