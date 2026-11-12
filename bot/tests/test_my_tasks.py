"""Private task widget and account scoping."""

import os
import sqlite3
import tempfile
import unittest
import zlib
from datetime import date
from unittest.mock import patch

from utils.my_tasks import MyTask, load_my_tasks, my_tasks_caption, render_my_tasks_widget


class MyTasksTests(unittest.TestCase):
    def test_loads_only_exact_telegram_users_assignments_and_own_status(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "tracker.db")
            with sqlite3.connect(path) as db:
                db.executescript("""
                    CREATE TABLE users (id INTEGER, telegram_id INTEGER, is_active INTEGER, full_name TEXT);
                    CREATE TABLE tasks (id INTEGER, title TEXT, status TEXT, due_date TEXT,
                                        is_checklist INTEGER, assignee_id INTEGER);
                    CREATE TABLE task_assignees (task_id INTEGER, user_id INTEGER, status TEXT);
                    INSERT INTO users VALUES (1, 111, 1, 'Анна ИК'), (2, 222, 1, 'Борис ИК'),
                                             (3, 333, 0, 'Неактивный');
                    INSERT INTO tasks VALUES
                      (1, 'Моя задача', 'TODO', '2026-11-13', 1, 1),
                      (2, 'Чужая задача', 'TODO', NULL, 0, 2),
                      (3, 'Общее поручение', 'TODO', NULL, 0, 1),
                      (4, 'Старое назначение', 'TODO', NULL, 0, 1);
                    INSERT INTO task_assignees VALUES (3, 1, 'IN_PROGRESS'),
                                                      (3, 2, 'DONE'),
                                                      (4, 2, 'TODO');
                """)
            with patch.dict(os.environ, {"TRACKER_DB_PATH": path}):
                name, tasks = load_my_tasks(111)
                self.assertEqual(name, "Анна ИК")
                self.assertEqual({task.id for task in tasks}, {1, 3})
                self.assertEqual(next(task.status for task in tasks if task.id == 3), "in_progress")
                self.assertEqual(load_my_tasks(333), (None, []))
                self.assertEqual(load_my_tasks(999), (None, []))

    def test_widget_escapes_titles_paginates_and_stays_in_telegram_limits(self):
        tasks = [MyTask(i, f"Задача {i}", "todo", None, False) for i in range(11)]
        tasks[0] = MyTask(0, "<script>secret</script>", "in_progress", "2026-11-01", True)
        source = render_my_tasks_widget("<Анна>", tasks, date(2026, 11, 12))
        self.assertIn("&lt;script&gt;secret&lt;/script&gt;", source)
        self.assertNotIn("<script>secret", source)
        self.assertIn("Просрочено", source)
        self.assertIn("Чек-лист", source)
        self.assertIn("'Unbounded'", source)
        self.assertIn("'Golos Text'", source)
        self.assertIn("'JetBrains Mono'", source)
        self.assertIn("#e0a85e", source)
        self.assertIn('class="ik" alt="ИК" src="data:image/png;base64,', source)
        self.assertIn("#df4b51,#e8863c,#18b1ad", source)
        self.assertNotIn('<span class="ik">ИК</span>', source)
        self.assertEqual(source.count('class="page active"'), 1)
        self.assertEqual(source.count('class="page"'), 2)
        self.assertIn('class="title">Задача 1</div>', source)
        self.assertLess(source.index('id="next"'), source.index('class="page active"'))
        self.assertLessEqual(len(source.encode()), 32_768)
        self.assertLessEqual(len(zlib.compress(source.encode(), 9)), 4_096)

    def test_text_fallback(self):
        self.assertIn("Мои задачи", my_tasks_caption([MyTask(1, "Отчёт", "todo", None, False)]))
