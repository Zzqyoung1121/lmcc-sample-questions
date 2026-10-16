#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T3 测试步骤 DSL 执行器。

把 public_tests.json 里的每一步翻成浏览器操作 + 断言。
所有可交互/可断言的东西都走题面「控件定位约定」里给出的选择器，不依赖内部实现。
"""

from __future__ import annotations

import functools
import http.server
import json
import socketserver
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------- 常量
SUBJECT_LABEL = {
    "unassigned": "未分类",
    "chinese": "语文",
    "math": "数学",
    "english": "英语",
}
STATUS_HREF = {"all": "#/", "active": "#/active", "completed": "#/completed"}
STEP_TIMEOUT_MS = 1000  # 题面：每次正常操作后的界面变化在 1 秒内可见


class StepFailure(AssertionError):
    """某一步没通过。带上足以定位的上下文。"""


# ---------------------------------------------------------------- 本地服务
class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D102
        pass


class LocalServer:
    def __init__(self, directory: Path):
        self._srv = socketserver.TCPServer(
            ("127.0.0.1", 0), functools.partial(_QuietHandler, directory=str(directory))
        )
        self.port = self._srv.server_address[1]
        self._thread = threading.Thread(target=self._srv.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._srv.shutdown()
        self._srv.server_close()

    @property
    def url(self) -> str:
        return "http://127.0.0.1:%d/index.html" % self.port


# ---------------------------------------------------------------- 执行器
class PageSession:
    """一个子场景 = 一个独立浏览器上下文 = 一份空白存储。"""

    def __init__(self, browser, base_url: str):
        self._ctx = browser.new_context()
        self.page = self._ctx.new_page()
        self._errors: list[str] = []
        self.page.on("pageerror", lambda e: self._errors.append("pageerror: %s" % e))
        self.page.on(
            "console",
            lambda m: self._errors.append("console.error: %s" % m.text) if m.type == "error" else None,
        )
        self.base_url = base_url
        self.page.goto(base_url, wait_until="domcontentloaded")

    # -------- 生命周期
    def close(self):
        self._ctx.close()

    @property
    def errors(self) -> list[str]:
        return list(self._errors)

    # -------- 读取
    def _rows(self) -> list[dict]:
        return self.page.eval_on_selector_all(
            ".todo-list > li",
            """els => els.map(e => ({
                id: e.getAttribute('data-id'),
                title: e.querySelector('label') ? e.querySelector('label').textContent : null,
                subject: e.querySelector('select.task-subject') ? e.querySelector('select.task-subject').value : null,
                done: !!e.querySelector('input.toggle') && e.querySelector('input.toggle').checked,
                visible: e.offsetParent !== null,
            }))""",
        )

    def visible_rows(self) -> list[dict]:
        return [r for r in self._rows() if r["visible"]]

    def _row(self, index: int):
        rows = self.visible_rows()
        if index < 0 or index >= len(rows):
            raise StepFailure("可见行序号 %d 越界，当前可见 %d 行" % (index, len(rows)))
        return rows[index]

    # -------- 动作
    def add(self, text: str):
        self.page.fill(".new-todo", text)
        self.page.press(".new-todo", "Enter")

    def set_subject(self, index: int, subject: str):
        row = self._row(index)
        sel = ".todo-list > li[data-id='%s'] select.task-subject" % row["id"]
        if self.page.locator(sel).count() == 0:
            raise StepFailure("第 %d 行找不到 select.task-subject" % index)
        self.page.select_option(sel, subject)

    def set_subject_filter(self, value: str):
        if self.page.locator("select#subject-filter").count() == 0:
            raise StepFailure("找不到 select#subject-filter")
        self.page.select_option("select#subject-filter", value)

    def set_status_filter(self, value: str):
        href = STATUS_HREF[value]
        if self.page.locator(".filters a[href='%s']" % href).count() == 0:
            raise StepFailure("找不到完成筛选链接 %s" % href)
        self._dom_click(".filters a[href='%s']" % href)

    def toggle(self, index: int):
        row = self._row(index)
        self.page.click(".todo-list > li[data-id='%s'] input.toggle" % row["id"], force=True)

    def destroy(self, index: int):
        row = self._row(index)
        self._dom_click(".todo-list > li[data-id='%s'] button.destroy" % row["id"])

    def _dom_click(self, selector: str):
        """对视觉隐藏但仍可用的控件派发真实 DOM click。

        TodoMVC 的 .destroy 是靠 CSS 悬停显示的 0 尺寸按钮，
        Playwright 的合成点击会因「元素不可见」超时；这里直接派发事件。
        """
        found = self.page.evaluate(
            """(sel) => {
                const el = document.querySelector(sel);
                if (!el) return false;
                el.click();
                return true;
            }""",
            selector,
        )
        if not found:
            raise StepFailure("找不到可点击的控件：%s" % selector)

    def clear_completed(self):
        self.page.click(".clear-completed", force=True)

    def move_up(self, index: int):
        row = self._row(index)
        self.page.click(".todo-list > li[data-id='%s'] button.move-up" % row["id"], force=True)

    def move_down(self, index: int):
        row = self._row(index)
        self.page.click(".todo-list > li[data-id='%s'] button.move-down" % row["id"], force=True)

    def reload(self):
        self.page.reload(wait_until="domcontentloaded")

    # -------- 断言
    def assert_rows(self, expected: list[dict]):
        got = self.visible_rows()
        if len(got) != len(expected):
            raise StepFailure("可见行数不符：期望 %d 行，实际 %d 行\n  期望 %s\n  实际 %s"
                              % (len(expected), len(got), _fmt(expected), _fmt(got)))
        for i, (g, e) in enumerate(zip(got, expected)):
            if g["title"] != e["title"]:
                raise StepFailure("第 %d 行标题不符：期望 %r，实际 %r" % (i, e["title"], g["title"]))
            if bool(g["done"]) != bool(e.get("done", False)):
                raise StepFailure("第 %d 行（%r）完成状态不符：期望 %s，实际 %s"
                                  % (i, e["title"], "已完成" if e.get("done") else "未完成",
                                     "已完成" if g["done"] else "未完成"))
            exp_sub = e.get("subject", "unassigned")
            if g["subject"] != exp_sub:
                raise StepFailure("第 %d 行（%r）科目不符：期望 %s，实际 %s"
                                  % (i, e["title"], SUBJECT_LABEL.get(exp_sub, exp_sub),
                                     SUBJECT_LABEL.get(g["subject"], g["subject"])))

    def assert_rows_empty(self):
        got = self.visible_rows()
        if got:
            raise StepFailure("期望可见列表为空，实际 %d 行：%s" % (len(got), _fmt(got)))

    def assert_active_count(self, n: int):
        el = self.page.locator(".todo-count strong")
        if el.count() == 0:
            raise StepFailure("找不到 .todo-count strong")
        text = el.first.text_content().strip()
        try:
            got = int(text)
        except ValueError:
            raise StepFailure(".todo-count strong 不是数字：%r" % text)
        if got != n:
            raise StepFailure("全清单未完成数不符：期望 %d，实际 %d" % (n, got))

    def assert_move_buttons_boundary(self):
        rows = self.visible_rows()
        if not rows:
            return  # 空列表时无按钮需检查
        for i, row in enumerate(rows):
            up = self.page.locator(".todo-list > li[data-id='%s'] button.move-up" % row["id"])
            dn = self.page.locator(".todo-list > li[data-id='%s'] button.move-down" % row["id"])
            if up.count() == 0 or dn.count() == 0:
                raise StepFailure("第 %d 行缺少 button.move-up / button.move-down" % i)
            up_disabled = up.first.is_disabled()
            dn_disabled = dn.first.is_disabled()
            if i == 0 and not up_disabled:
                raise StepFailure("可见第一条的上移按钮应禁用，实际可用")
            if i > 0 and up_disabled:
                raise StepFailure("可见第 %d 行的上移按钮不应禁用" % i)
            if i == len(rows) - 1 and not dn_disabled:
                raise StepFailure("可见最后一条的下移按钮应禁用，实际可用")
            if i < len(rows) - 1 and dn_disabled:
                raise StepFailure("可见第 %d 行的下移按钮不应禁用" % i)


def _fmt(rows: list[dict]) -> str:
    return "[" + ", ".join(
        "%r(%s/%s)" % (r["title"], "已完成" if r["done"] else "未完成",
                       SUBJECT_LABEL.get(r["subject"], r["subject"]))
        for r in rows
    ) + "]"


# ---------------------------------------------------------------- 步骤派发
def run_step(session: PageSession, step: dict):
    action = step["op"]
    args = step.get("args", {})
    handler = {
        "add": lambda: session.add(args["text"]),
        "set_subject": lambda: session.set_subject(args["index"], args["subject"]),
        "set_subject_filter": lambda: session.set_subject_filter(args["value"]),
        "set_status_filter": lambda: session.set_status_filter(args["value"]),
        "toggle": lambda: session.toggle(args["index"]),
        "destroy": lambda: session.destroy(args["index"]),
        "clear_completed": lambda: session.clear_completed(),
        "move_up": lambda: session.move_up(args["index"]),
        "move_down": lambda: session.move_down(args["index"]),
        "reload": lambda: session.reload(),
        "assert_rows": lambda: session.assert_rows(args["rows"]),
        "assert_rows_empty": lambda: session.assert_rows_empty(),
        "assert_active_count": lambda: session.assert_active_count(args["n"]),
        "assert_move_buttons_boundary": lambda: session.assert_move_buttons_boundary(),
    }.get(action)
    if handler is None:
        raise StepFailure("未知的步骤类型：%s" % action)
    return handler()
