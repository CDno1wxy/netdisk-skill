#!/usr/bin/env python3
"""
浏览 / 搜索 115 网盘目录。

用法:
    python3 browse.py                  # 浏览根目录
    python3 browse.py <目录ID>         # 浏览指定目录
    python3 browse.py --search <关键词>  # 搜索文件
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import FILE_LOGIN_HINT, concise_error, fail, get_client, get_list_data, list_115_files_app, looks_like_login_error, print_item


def browse_dir(client, cid: int = 0, page: int = 1, limit: int = 50):
    try:
        result = list_115_files_app(client, cid=cid, limit=limit, offset=(page - 1) * limit)
    except Exception as exc:
        hint = f"\n   {FILE_LOGIN_HINT}" if looks_like_login_error(exc) else ""
        fail(f"浏览目录失败: {concise_error(exc)}{hint}")
    items = get_list_data(result, "浏览目录")
    if not items:
        print("  (空目录)")
        return
    for item in items:
        print_item(item)


def search_files(client, keyword: str, limit: int = 30):
    try:
        result = client.fs_search({"search_value": keyword, "limit": limit})
    except Exception as exc:
        hint = f"\n   {FILE_LOGIN_HINT}" if looks_like_login_error(exc) else ""
        fail(f"搜索文件失败: {concise_error(exc)}{hint}")
    items = get_list_data(result, "搜索文件")
    if not items:
        print(f"  未找到包含「{keyword}」的文件")
        return
    for item in items:
        print_item(item)


def main():
    args = sys.argv[1:]
    client = get_client()

    if "--search" in args:
        idx = args.index("--search")
        keyword = args[idx + 1] if idx + 1 < len(args) else ""
        if not keyword:
            fail("用法: python3 browse.py --search <关键词>")
        print(f"🔍 搜索: {keyword}\n")
        search_files(client, keyword)
    else:
        cid = 0
        for a in args:
            if a.isdigit():
                cid = int(a)
                break
        print(f"📂 目录 {cid}:\n")
        browse_dir(client, cid)


if __name__ == "__main__":
    main()
