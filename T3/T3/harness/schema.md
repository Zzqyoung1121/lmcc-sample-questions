# 测试 DSL 词汇表

`public_tests.json` / `hidden_tests.json` 里的每一步都是 `{"op": ..., "args": {...}}`。
`run_tests.py` 逐条执行；任一条失败即该子场景失败，两个子场景全通过才得该点 10 分。

## 动作

| op | args | 说明 |
| --- | --- | --- |
| `add` | `{text}` | 把 text 填进 `.new-todo` 后按 Enter（text 原样输入，不预先 trim） |
| `set_subject` | `{index, subject}` | 设置可见第 index 行的 `select.task-subject` |
| `set_subject_filter` | `{value}` | 设置 `select#subject-filter`：all / unassigned / chinese / math / english |
| `set_status_filter` | `{value}` | 点击 `.filters a`：all→`#/`、active→`#/active`、completed→`#/completed` |
| `toggle` | `{index}` | 点击可见第 index 行的 `.toggle` |
| `destroy` | `{index}` | 点击可见第 index 行的 `.destroy` |
| `clear_completed` | `{}` | 点击 `.clear-completed` |
| `move_up` / `move_down` | `{index}` | 点击可见第 index 行的 `button.move-up` / `button.move-down` |
| `reload` | `{}` | 刷新页面 |

## 断言

| op | args | 说明 |
| --- | --- | --- |
| `assert_rows` | `{rows}` | 可见行必须**恰好**等于 rows，逐行核对标题、完成状态、科目 |
| `assert_rows_empty` | `{}` | 可见列表为空 |
| `assert_active_count` | `{n}` | `.todo-count strong` 的数值等于 n（全清单未完成数） |
| `assert_move_buttons_boundary` | `{}` | 可见第一条的上移、最后一条的下移必须 `disabled`；其余方向必须可用 |

`rows` 的元素形如 `{"title": "数学练习", "done": false, "subject": "math"}`，
`subject` 省略时按 `unassigned` 处理。

## 关键语义

- **可见行序号从 0 开始**，只统计 `.todo-list > li` 中 `offsetParent !== null` 的行（CSS 隐藏的行不算可见）。题面允许用 CSS 隐藏代替移除。
- **`assert_rows` 是有序的**：顺序即页面实际顺序，不排序、不忽略。
- **`assert_move_buttons_boundary` 在空列表时不检查**（没有按钮）。
- 每个子场景使用**独立的浏览器 context 和空白 localStorage**，场景之间互不影响。
- 动作后立即断言，不等待动画；题面要求操作后 1 秒内可见。
