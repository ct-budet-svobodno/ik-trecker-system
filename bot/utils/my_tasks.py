"""Read the linked user's tracker assignments and render a private widget."""

import html
import os
import sqlite3
import zlib
from base64 import b64encode
from dataclasses import dataclass
from datetime import date
from pathlib import Path


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


_LOGO_DATA = b64encode(Path(__file__).with_name("ik_logo_widget.png").read_bytes()).decode("ascii")


_STYLE = """<style>
*{box-sizing:border-box}body{margin:0;background:#131019;color:#f1f0f5;font:14px/1.5 'Golos Text',system-ui,'Segoe UI',sans-serif}
.card{padding:18px;border:1px solid #3d3b50;border-radius:0px;background:radial-gradient(65% 85% at -5% 55%,rgba(201,51,54,.55) 0%,transparent 60%),radial-gradient(62% 68% at 42% 108%,rgba(232,134,60,.52) 0%,transparent 60%),radial-gradient(65% 90% at 105% 60%,rgba(38,176,150,.50) 0%,transparent 62%),#131019}
.top{display:flex;align-items:center;justify-content:space-between;gap:8px}.mark{display:flex;align-items:center;gap:9px;font-weight:900;letter-spacing:.06em}
.ik{display:block;width:64px;height:51px;flex:none;object-fit:contain}
.eyebrow{color:#a6a1b4;font:500 10px/1.4 'JetBrains Mono',ui-monospace,monospace;letter-spacing:.08em}.date{color:#a6a1b4;font:11px 'JetBrains Mono',ui-monospace,monospace}
.rule{height:3px;margin:15px 0;background:linear-gradient(90deg,#df4b51,#e8863c,#18b1ad);border-radius:4px}
h1{margin:0 0 3px;font:500 21px/1.3 'Unbounded','Golos Text',system-ui,sans-serif;letter-spacing:-.01em}.sub{margin:0 0 14px;color:#a6a1b4;font-size:12px}
.stats{display:flex;gap:7px;margin-bottom:13px}.stat{flex:1;padding:8px;border:1px solid #302e3f;border-radius:12px;background:#1b1a24;text-align:center}
.stat b{display:block;font:500 18px 'JetBrains Mono',ui-monospace,monospace;color:#8b5cf6}.stat.progress b{color:#e0a85e}.stat.done-count b{color:#45c4a0}.stat small{font-size:10px;color:#a6a1b4}
.nav{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:11px}
.nav button{padding:8px 10px;border:1px solid #8b5cf6;border-radius:8px;background:#302448;color:#f1f0f5;font:600 12px 'Golos Text',system-ui,sans-serif}
.nav button:disabled{border-color:#302e3f;background:#1b1a24;color:#726e82}.nav span{color:#a6a1b4;font:500 12px 'JetBrains Mono',ui-monospace,monospace}
.page{display:none;gap:8px}.page.active{display:grid}.task{position:relative;overflow:hidden;padding:10px 11px 10px 14px;border:1px solid #302e3f;border-radius:12px;background:#1b1a24}
.task:before{content:'';position:absolute;inset:0 auto 0 0;width:4px;background:#8b5cf6}.task.overdue{border-color:#f87171}.task.done .title{color:#a6a1b4;text-decoration:line-through;text-decoration-color:#726e82}
.task-head{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:5px}.kind{padding:2px 6px;border-radius:6px;background:#302448;color:#f1f0f5;font-size:10px;font-weight:600}
.status{display:inline-flex;align-items:center;gap:5px;color:#a6a1b4;font-size:10px;white-space:nowrap}.dot{width:7px;height:7px;border-radius:50%;background:#908ca0}
.status.in_progress .dot{background:#e0a85e}.status.in_review .dot{background:#a78bfa}.status.done .dot{background:#45c4a0}
.title{font-size:14px;font-weight:600;line-height:1.35;overflow-wrap:anywhere}.due{margin-top:5px;color:#a6a1b4;font:11px 'JetBrains Mono',ui-monospace,monospace}
.overdue .due{color:#f87171}.empty{padding:22px 12px;border:1px solid #302e3f;border-radius:12px;background:#1b1a24;text-align:center;color:#a6a1b4}
.foot{margin-top:13px;color:#a6a1b4;font:500 10px/1.4 'JetBrains Mono',ui-monospace,monospace;letter-spacing:.04em}
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
        kind = "Чек-лист" if task.is_checklist else "Задача"
        status = task.status if task.status in _STATUS else "todo"
        cards.append(
            f'<div class="task{" overdue" if overdue else ""}{" done" if task.status == "done" else ""}">'
            f'<div class="task-head"><span class="kind">{kind}</span>'
            f'<span class="status {status}"><span class="dot"></span>{_STATUS[status]}</span></div>'
            f'<div class="title">{html.escape(task.title[:160], quote=True)}</div>'
            f'<div class="due">{due}</div></div>'
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
        + '<div class="card"><div class="top"><div class="mark"><img class="ik" alt="ИК" src="data:image/png;base64,' + _LOGO_DATA + '">'
        + '<span class="eyebrow">ИНФОРМАЦИОННЫЙ КОМИТЕТ</span></div>'
        + f'<span class="date">{today:%d.%m.%Y}</span></div><div class="rule"></div>'
        + '<h1>Мои задачи</h1>'
        + f'<p class="sub">{first_name}, вот что тебе назначено</p>'
        + f'<div class="stats"><div class="stat"><b>{active}</b><small>Активные</small></div>'
        + f'<div class="stat progress"><b>{progress}</b><small>В работе</small></div>'
        + f'<div class="stat done-count"><b>{done}</b><small>Сделано</small></div></div>'
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
