#!/usr/bin/env python3
"""
创建 123 网盘分享链接。

用法:
    python3 share_link.py --file-id <文件夹/文件ID> [--expire 0|1|7|30] [--pwd <提取码>]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import fail
from netdisk import create_123_share, get_123_client


def main():
    parser = argparse.ArgumentParser(description="创建 123 网盘分享链接")
    parser.add_argument("--file-id", required=True, help="要分享的文件夹/文件 ID")
    parser.add_argument("--expire", type=int, default=7, choices=[0, 1, 7, 30], help="有效期天数，0=永久")
    parser.add_argument("--pwd", default="", help="提取码（默认无）")
    args = parser.parse_args()

    client = get_123_client()
    try:
        info = create_123_share(client, args.file_id, expiry_days=args.expire, password=args.pwd)
    except Exception as exc:
        fail(f"创建分享失败: {exc}")

    print("✅ 分享链接已创建")
    print(f"   URL: {info['url']}")
    print(f"   提取码: {info['password'] or '无'}")
    print(f"   有效期: {info['expiry']}")


if __name__ == "__main__":
    main()
