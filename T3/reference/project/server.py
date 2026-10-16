#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本题固定的启动脚本（请勿修改）。

在本地起一个静态文件服务，让浏览器能以 http:// 而不是 file:// 打开页面，
这样 localStorage 的行为与考场一致。

用法：
    python server.py            # 默认 8000 端口
    python server.py --port 0   # 随机空闲端口
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
from pathlib import Path

HERE = Path(__file__).resolve().parent


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):  # 静默，避免刷屏
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    handler = functools.partial(Handler, directory=str(HERE))
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        port = httpd.server_address[1]
        print("http://127.0.0.1:%d/index.html" % port, flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
