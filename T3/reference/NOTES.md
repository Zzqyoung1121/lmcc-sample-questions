# 参考实现说明（T3 · 第一批）

本目录是 **参考答案**，用途只有一个：**校验测试转录是否正确**。
它不是考生文件，考生工作区是 `T3/T3/project/`。

## 起点

从 `T3/T3/project/` 复制，然后实现题面要求的四项新功能：

| 文件 | 改动 |
| --- | --- |
| `src/store.js` | 内存 `MemoryStorage` → `localStorage` 后端（键 `todos-lmcc`）；新增 `saveAll`；启动时把 ID 推到已有数据之后，避免刷新后新条目与旧条目 ID 冲突 |
| `src/model.js` | 新增 `readAll`（读全清单）、`swap`（交换两条在全清单中的位置）、`rewrite` |
| `src/controller.js` | 新增 `_visible`（科目+完成状态联合筛选）、`showEntries`、`changeSubject`、`moveItem`；`_filter` 改为总是重绘；**路由名归一化为 All/Active/Completed** |
| `src/view.js` | 绑定 `itemSubject` / `subjectFilter` / `itemMoveUp` / `itemMoveDown`；新增渲染命令 `updateMoveButtons`（按可见顺序设置原生 `disabled`） |

## 实现过程中的两个坑（本地复现平台行为时值得注意）

1. **路由大小写**：上游 `_filter` 里把 `_activeRoute` 转成首字母大写再派发 `show*`，
   但 `_updateFilterState` 存的是小写（`"completed"`）。原来的筛选逻辑只做路由名匹配，
   所以没暴露；一旦筛选条件依赖 `_activeRoute` 本身，就必须在存的时候归一化。
   → 已在 `_updateFilterState` 里统一成 `All` / `Active` / `Completed`。

2. **`.destroy` 之类的隐藏控件点不动**：TodoMVC 的删除按钮靠 CSS 悬停显示，实际是 0 尺寸，
   Playwright 的合成点击会因“元素不可见”超时。本地测试用 `force=True` 或直接派发 DOM click。

## 验收证据

对 `reference/project/` 跑 `harness/run_tests.py`：

```text
P01 独立科目与联合筛选下完成  [PASS] P01-1  [PASS] P01-2  -> 10/10
P02 删除清理保存与逐条选科目  [PASS] P02-1  [PASS] P02-2  -> 10/10
P03 联合筛选与全清单移动边界  [PASS] P03-1  [PASS] P03-2  -> 10/10
P04 可见移动、隐藏位置与完成变化 [PASS] P04-1 [PASS] P04-2  -> 10/10
P05 刷新追加与移动后修改一致  [PASS] P05-1  [PASS] P05-2  -> 10/10
公开点功能分：50 / 50
```

对未实现的 `T3/T3/project/` 跑同一套测试：

```text
P01..P05 全部子场景 FAIL
公开点功能分：0 / 50
```

**这两个结果同时成立，才说明测试既不是空转、也没有超出题面要求。**

## 第二批：隐藏点 H01–H05

`harness/hidden_tests.json` 是**自造**的，只覆盖题面已写明、而 P01–P05 未覆盖的行为：

| 点 | 覆盖的题面要求 |
| --- | --- |
| H01 | 要求 1「清理已完成删除全清单中的已完成条目，包括当前筛选看不到的」 |
| H02 | 要求 2「即使正在只看数学，也不把新作业自动归为数学」 |
| H03 | 要求 4「切换任何筛选都不改变作业或全清单顺序」 |
| H04 | 要求 6「只有一条时两个都禁用」及各筛选下的边界收敛 |
| H05 | 要求 7「刷新后恢复标题、完成情况、科目与顺序」 |

全量验收（公开 + 隐藏）：

```text
参考答案 reference/project/  -> 100 / 100（20 个子场景全通过）
起步项目 project/（未实现）   -> 0 / 100（20 个子场景全失败）
```

## Agent

`T3/T3/agent/` 是**自造**的本地复刻（考场用 Qwen3.5-35B-A3B + 平台自研 Agent）。
经 mock 端点验证的工具链路：`read_file → bash → write_file → 文本回复`。
沙箱拒绝工作区外路径与固定文件写入；用量记入 `agent/usage.json`。
