#!/usr/bin/env python3
"""
网盘分享链接转存（115 / 123）。

用法:
    python3 transfer_share.py <分享链接> --target-pid <目录ID> [--disk auto|115|123]

按链接域名自动识别网盘（115.com -> 115，123pan.com -> 123），也可用 --disk 指定。
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import fail, load_cookies, resolve_cookies_path
from netdisk import get_123_client, transfer_115_share, transfer_123_share


def detect_disk(url: str) -> str:
    if "115.com" in url or "115cdn.com" in url or "anxia.com" in url:
        return "115"
    if "123pan.com" in url or "123684.com" in url or "123912.com" in url:
        return "123"
    return "unknown"


def main():
    parser = argparse.ArgumentParser(description="网盘分享链接转存（115 / 123）")
    parser.add_argument("url", help="分享链接（115 或 123）")
    parser.add_argument("--target-pid", required=True, help="目标目录 ID")
    parser.add_argument("--disk", choices=["auto", "115", "123"], default="auto", help="网盘类型，默认自动识别")
    parser.add_argument("--cookies-path", help="115 cookies 文件路径（默认 ~/.115-cookies）")
    args = parser.parse_args()

    disk = detect_disk(args.url) if args.disk == "auto" else args.disk
    if disk == "unknown":
        fail(f"无法识别网盘类型，请用 --disk 指定: {args.url}")

    print(f"📦 网盘: {disk} | 目标目录: {args.target_pid}")
    print(f"🔗 链接: {args.url}\n")

    if disk == "115":
        cookies = load_cookies(resolve_cookies_path(args.cookies_path))
        ok, msg = transfer_115_share(cookies, args.url, args.target_pid)
    else:
        client = get_123_client()
        ok, msg = transfer_123_share(client, args.url, args.target_pid)

    print(f"{'✅' if ok else '❌'} {msg}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
