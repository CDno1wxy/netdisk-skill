#!/usr/bin/env python3
"""
115 分享链接转存。

用法:
    python3 transfer_share.py <分享链接> --target-pid <目录ID>

链接格式: https://115.com/s/xxx?password=yyy
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import fail, load_cookies, resolve_cookies_path
from netdisk import transfer_115_share


def main():
    parser = argparse.ArgumentParser(description="115 分享链接转存")
    parser.add_argument("url", help="115 分享链接（含提取码）")
    parser.add_argument("--target-pid", required=True, help="目标目录 ID")
    parser.add_argument("--cookies-path", help="115 cookies 文件路径（默认 ~/.115-cookies）")
    args = parser.parse_args()

    cookies = load_cookies(resolve_cookies_path(args.cookies_path))
    print(f"📦 目标目录: {args.target_pid}")
    print(f"🔗 链接: {args.url}\n")

    ok, msg = transfer_115_share(cookies, args.url, args.target_pid)
    print(f"{'✅' if ok else '❌'} {msg}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
