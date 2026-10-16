#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T3 测试运行器。

用法：
    python run_tests.py                        # 跑公开点 P01–P05（对 ./project）
    python run_tests.py --project <目录>        # 指定项目目录
    python run_tests.py --set public           # 只跑公开点（默认）
    python run_tests.py --json                 # 额外输出机器可读结果
    python run_tests.py --only P03             # 只跑某个点

每个测试点含两个子场景；两个子场景都通过才得该点 10 分。
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from playwright.sync_api import sync_playwright  # noqa: E402

from steps import LocalServer, PageSession, StepFailure  # noqa: E402

POINT_SCORE = 10


def run_scenario(browser, base_url: str, scenario: dict) -> tuple[bool, str]:
    """跑一个子场景。返回 (是否通过, 失败说明)。"""
    session = PageSession(browser, base_url)
    try:
        for i, step in enumerate(scenario["steps"], 1):
            try:
                from steps import run_step

                run_step(session, step)
            except StepFailure as exc:
                return False, "第 %d 步失败：%s\n        步骤：%s" % (
                    i, exc, json.dumps(step, ensure_ascii=False))
            except Exception as exc:  # noqa: BLE001
                return False, "第 %d 步异常：%s: %s\n        步骤：%s" % (
                    i, type(exc).__name__, str(exc)[:200], json.dumps(step, ensure_ascii=False))
        if session.errors:
            return False, "页面报错：%s" % session.errors[:3]
        return True, ""
    finally:
        session.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=str(HERE.parent / "project"),
                    help="待测项目目录（默认 ../../project）")
    ap.add_argument("--tests", default=str(HERE / "public_tests.json"))
    ap.add_argument("--only", default="", help="只跑指定点，如 P03")
    ap.add_argument("--set", choices=["public", "hidden", "all"], default="public",
                    help="跑哪一套：public / hidden / all")
    ap.add_argument("--with-score", action="store_true",
                    help="结合 agent/usage.json 的用量，按题面公式给出最终得分")
    ap.add_argument("--json", action="store_true", help="输出机器可读结果")
    args = ap.parse_args()

    project = Path(args.project).resolve()
    if not (project / "index.html").exists():
        sys.exit("在 %s 找不到 index.html" % project)

    # --set 决定测试集；显式给了 --tests 就以它为准
    if args.tests == str(HERE / "public_tests.json") and args.set != "public":
        names = {"hidden": ["hidden_tests.json"], "all": ["public_tests.json", "hidden_tests.json"]}[args.set]
        specs = [json.loads((HERE / n).read_text(encoding="utf-8")) for n in names]
    else:
        specs = [json.loads(Path(args.tests).read_text(encoding="utf-8"))]

    spec = specs[0]
    points = []
    for sp in specs:
        points.extend(p for p in sp["points"] if not args.only or p["id"] == args.only)
    if not points:
        sys.exit("没有匹配的测试点")

    print("=" * 74)
    print("T3 测试运行：%s" % spec.get("problem", ""))
    print("项目目录：%s" % project)
    print("测试集：%s（%d 个点）" % (Path(args.tests).name, len(points)))
    print("=" * 74)

    results = []
    total = 0
    with LocalServer(project) as server, sync_playwright() as pw:
        browser = pw.chromium.launch()
        for point in points:
            print("\n%s %s（%d 分）" % (point["id"], point["title"], POINT_SCORE))
            subs = []
            for scenario in point["scenarios"]:
                ok, why = run_scenario(browser, server.url, scenario)
                subs.append(ok)
                print("  [%s] %s" % ("PASS" if ok else "FAIL", scenario["id"]))
                if not ok:
                    for line in why.splitlines():
                        print("         " + line)
            passed = all(subs)
            score = POINT_SCORE if passed else 0
            total += score
            results.append({"id": point["id"], "passed": passed, "score": score})
            print("  -> %s  %d/%d" % ("通过" if passed else "未通过", score, POINT_SCORE))
        browser.close()

    label = {"public": "公开点", "hidden": "隐藏点", "all": "公开 + 隐藏"}[args.set]
    print("\n" + "=" * 74)
    raw_score = total
    print("%s功能分（原分 S）：%d / %d" % (label, raw_score, len(points) * POINT_SCORE))
    print("=" * 74)
    if args.with_score:
        usage_file = HERE.parent / "agent" / "usage.json"
        if usage_file.exists():
            usage = json.loads(usage_file.read_text(encoding="utf-8"))
            t = int(usage.get("tokens", 0))
            if t <= 100_000:
                factor = 1.0
            elif t >= 160_000:
                factor = 0.5
            else:
                factor = 1.0 - 0.5 * (t - 100_000) / 60_000
            print("累计用量 T = %d Token，用量系数 = %.4f" % (t, factor))
            print("最终得分 = %d × %.4f = %.2f" % (raw_score, factor, round(raw_score * factor, 2)))
        else:
            print("（未找到 agent/usage.json，跳过用量换算）")

    if args.json:
        print(json.dumps({"results": results, "rawScore": total,
                          "max": len(points) * POINT_SCORE}, ensure_ascii=False))
    return 0 if total == len(points) * POINT_SCORE else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(130)
