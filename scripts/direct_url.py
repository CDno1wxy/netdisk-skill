#!/usr/bin/env python3
"""
获取 123 网盘下载直链（302 直链，供 Emby 等播放）。

用法:
    python3 direct_url.py --file-id <文件ID>
    python3 direct_url.py --path "/影视/侠医/Season 1/侠医.S01E01.mkv"
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import fail
from netdisk import get_123_client, get_123_direct_url_by_path, get_123_download_url_by_file_id


def main():
    parser = argparse.ArgumentParser(description="获取 123 网盘下载直链")
    parser.add_argument("--file-id", help="文件 ID，直接获取直链")
    parser.add_argument("--path", help="网盘内完整路径，按文件名搜索匹配（取最大匹配文件）")
    args = parser.parse_args()

    if not args.file_id and not args.path:
        parser.print_help()
        sys.exit(1)

    client = get_123_client()

    if args.file_id:
        url = get_123_download_url_by_file_id(client, args.file_id)
        if not url:
            fail(f"获取直链失败 (file_id={args.file_id})")
        print(url)
        return

    url = get_123_direct_url_by_path(client, args.path)
    if not url:
        fail(f"未找到匹配文件: {args.path}")
    print(url)


if __name__ == "__main__":
    main()
