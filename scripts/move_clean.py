#!/usr/bin/env python3
"""
115 网盘目录整理与清理。

用法:
    # 递归移动 source 下所有文件到 target，并清理空目录
    python3 move_clean.py --source-pid <源目录ID> --target-pid <目标目录ID>

    # 清空指定目录内容并清空回收站
    python3 move_clean.py --clean-pids <ID1,ID2,...> [--trash-password <回收站密码>]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import fail, load_cookies, resolve_cookies_path
from netdisk import clean_115_folders, move_115_tree


def main():
    parser = argparse.ArgumentParser(description="115 网盘目录整理与清理")
    parser.add_argument("--source-pid", help="源目录 ID（递归转移）")
    parser.add_argument("--target-pid", help="目标目录 ID（递归转移）")
    parser.add_argument("--clean-pids", help="要清空的目录 ID，逗号分隔")
    parser.add_argument("--trash-password", type=int, default=0, help="回收站密码（如有）")
    parser.add_argument("--cookies-path", help="115 cookies 文件路径（默认 ~/.115-cookies）")
    args = parser.parse_args()

    if not args.source_pid and not args.clean_pids:
        parser.print_help()
        sys.exit(1)
    if args.source_pid and not args.target_pid:
        fail("--source-pid 需要配合 --target-pid")

    cookies = load_cookies(resolve_cookies_path(args.cookies_path))

    if args.source_pid:
        print(f"📦 开始递归转移: {args.source_pid} -> {args.target_pid}\n")
        stats = move_115_tree(cookies, args.source_pid, args.target_pid)
        print(f"\n完成：移动 {stats['moved']} 个文件，删除空目录 {stats['deleted_dirs']} 个，失败 {stats['failed']} 个")
        sys.exit(0 if stats["failed"] == 0 else 1)

    if args.clean_pids:
        print(f"🗑️ 开始清理目录: {args.clean_pids}\n")
        stats = clean_115_folders(cookies, args.clean_pids, trash_password=args.trash_password)
        print(f"\n完成：删除 {stats['deleted']} 项")
        sys.exit(0)


if __name__ == "__main__":
    main()
