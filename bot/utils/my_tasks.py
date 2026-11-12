"""Read the linked user's tracker assignments and render a private widget."""

import html
import os
import sqlite3
import zlib
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MyTask:
    id: int
    title: str
    status: str
    due_date: str | None
    is_checklist: bool


def load_my_tasks(telegram_id: int) -> tuple[str | None, list[MyTask]]:
    """Only assignments for the exact linked Telegram account are returned."""
    path = os.getenv("TRACKER_DB_PATH", "/tracker-data/ik_tracker.db")
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5) as db:
        db.row_factory = sqlite3.Row
        user = db.execute(
            "SELECT id, full_name FROM users WHERE telegram_id = ? AND is_active = 1",
            (telegram_id,),
        ).fetchone()
        if user is None:
            return None, []
        rows = db.execute(
            """SELECT t.id, t.title, COALESCE(a.status, t.status) AS status,
                      t.due_date, t.is_checklist
               FROM tasks AS t
               LEFT JOIN task_assignees AS a ON a.task_id = t.id AND a.user_id = ?
               WHERE a.user_id IS NOT NULL OR (t.assignee_id = ? AND NOT EXISTS
                     (SELECT 1 FROM task_assignees AS other WHERE other.task_id = t.id))
               ORDER BY t.id DESC""",
            (user["id"], user["id"]),
        ).fetchall()
    tasks = [MyTask(int(row["id"]), row["title"], row["status"].lower(),
                    row["due_date"], bool(row["is_checklist"])) for row in rows]
    tasks.sort(key=lambda task: (task.status == "done", task.due_date or "9999-99-99", -task.id))
    return user["full_name"], tasks


_STYLE = """<style>
*{box-sizing:border-box}body{margin:0;background:#131019;color:#f1f0f5;font:14px/1.3 system-ui,sans-serif}
.card{padding:18px;border:1px solid #3d3b50;border-radius:18px;background:linear-gradient(145deg,#232230,#131019 60%,#1b1a24)}
.top{display:flex;align-items:center;justify-content:space-between;gap:8px}.mark{display:flex;align-items:center;gap:9px;font-weight:900;letter-spacing:.06em}
.ik{display:grid;place-items:center;width:37px;height:37px;border-radius:11px;background:#8b5cf6;color:white;font-size:18px}
.eyebrow{color:#a6a1b4;font-size:10px;font-weight:800;letter-spacing:.13em}.date{color:#a6a1b4;font-size:11px}
.rule{height:3px;margin:15px 0;background:linear-gradient(90deg,#cb77ab,#ff9934,#2dd4bf);border-radius:4px}
h1{margin:0 0 3px;font-size:23px;letter-spacing:-.03em}.sub{margin:0 0 14px;color:#a6a1b4;font-size:12px}
.stats{display:flex;gap:7px;margin-bottom:13px}.stat{flex:1;padding:8px;border:1px solid #353244;border-radius:10px;background:#1b1a24;text-align:center}
.stat b{display:block;font-size:18px;color:#c4a9ff}.stat small{font-size:10px;color:#a6a1b4}
.nav{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:11px}
.nav button{padding:8px 10px;border:1px solid #8b5cf6;border-radius:9px;background:#302448;color:#f1f0f5;font:700 12px system-ui,sans-serif}
.nav button:disabled{border-color:#302e3f;background:#1b1a24;color:#726e82}.nav span{color:#a6a1b4;font-size:12px;font-weight:700}
.page{display:none;gap:7px}.page.active{display:grid}.task{padding:10px;border:1px solid #353244;border-radius:11px;background:#1b1a24}
.task.overdue{border-color:#a94f62}.task.done{opacity:.67}.title{font-weight:750;overflow-wrap:anywhere}
.meta{display:flex;justify-content:space-between;gap:6px;margin-top:6px;color:#aaa5b8;font-size:11px}
.status{color:#c4a9ff}.overdue .due{color:#ff8794}.done .status{color:#2dd4bf}
.empty{padding:22px 12px;border:1px solid #353244;border-radius:11px;background:#1b1a24;text-align:center;color:#a6a1b4}
.foot{margin-top:13px;color:#a6a1b4;font-size:10px;font-weight:700;letter-spacing:.04em}
</style>"""

_SCRIPT = """<script>(function(){var p=document.querySelectorAll('.page'),i=0,a=document.getElementById('prev'),b=document.getElementById('next'),c=document.getElementById('counter');function show(n){p[i].classList.remove('active');i=n;p[i].classList.add('active');a.disabled=i===0;b.disabled=i===p.length-1;c.textContent=(i+1)+' / '+p.length}a.onclick=function(){if(i>0)show(i-1)};b.onclick=function(){if(i<p.length-1)show(i+1)}})();</script>"""

_STATUS = {"todo": "Не начато", "in_progress": "В работе", "in_review": "На проверке", "done": "Сделано"}


def render_my_tasks_widget(name: str, tasks: list[MyTask], today: date | None = None) -> str:
    today = today or date.today()
    active = sum(task.status != "done" for task in tasks)
    progress = sum(task.status == "in_progress" for task in tasks)
    done = len(tasks) - active
    cards = []
    for task in tasks:
        overdue = bool(task.due_date and task.due_date < today.isoformat() and task.status != "done")
        due = task.due_date[8:10] + "." + task.due_date[5:7] if task.due_date else "Без срока"
        if overdue:
            due = "Просрочено · " + due
        kind = "Чеклист · " if task.is_checklist else ""
        cards.append(
            f'<div class="task{" overdue" if overdue else ""}{" done" if task.status == "done" else ""}">'
            f'<div class="title">{html.escape(task.title[:160], quote=True)}</div>'
            f'<div class="meta"><span class="status">{kind}{_STATUS.get(task.status, "Не начато")}</span>'
            f'<span class="due">{due}</span></div></div>'
        )
    pages = [cards[i:i + 5] for i in range(0, len(cards), 5)] or [[
        '<div class="empty">Пока нет назначенных задач ✨</div>'
    ]]
    page_html = "".join(
        f'<div class="page{" active" if i == 0 else ""}">{"".join(page)}</div>'
        for i, page in enumerate(pages)
    )
    nav = ('<div class="nav"><button id="prev" disabled>← Назад</button>'
           f'<span id="counter">1 / {len(pages)}</span>'
           '<button id="next">Далее →</button></div>') if len(pages) > 1 else ""
    first_name = html.escape(name.split()[0][:30] if name.split() else "друг", quote=True)
    source = (
        '<!doctype html><html lang="ru"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">' + _STYLE
        + '<div class="card"><div class="top"><div class="mark"><span class="ik">ИК</span>'
        + '<span class="eyebrow">ИНФОРМАЦИОННЫЙ КОМИТЕТ</span></div>'
        + f'<span class="date">{today:%d.%m.%Y}</span></div><div class="rule"></div>'
        + '<h1>Мои задачи</h1>'
        + f'<p class="sub">{first_name}, вот что тебе назначено</p>'
        + f'<div class="stats"><div class="stat"><b>{active}</b><small>Активные</small></div>'
        + f'<div class="stat"><b>{progress}</b><small>В работе</small></div>'
        + f'<div class="stat"><b>{done}</b><small>Сделано</small></div></div>'
        + nav + page_html + '<div class="foot">АКТУАЛЬНО НА МОМЕНТ ЗАПРОСА · ОТКРОЙ ТРЕКЕР ДЛЯ ДЕЙСТВИЙ</div>'
        + '</div>' + (_SCRIPT if len(pages) > 1 else "") + '</html>'
    )
    raw = source.encode("utf-8")
    if len(raw) > 32_768 or len(zlib.compress(raw, 9)) > 4_096:
        raise ValueError("My tasks widget exceeds Telegram size limits")
    return source


def my_tasks_caption(tasks: list[MyTask]) -> str:
    if not tasks:
        return "📋 Назначенных задач пока нет."
    lines = [f"📋 Мои задачи · {len(tasks)}"]
    for task in tasks[:8]:
        lines.append(f"• {task.title[:65]} — {_STATUS.get(task.status, 'Не начато')}")
    if len(tasks) > 8:
        lines.append(f"И ещё {len(tasks) - 8} в трекере")
    return "\n".join(lines)[:980]
