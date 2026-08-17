#!/usr/bin/env python3
"""
浏览 / 搜索网盘目录（115 / 123）。

用法:
    python3 browse.py                       # 浏览 115 根目录
    python3 browse.py <目录ID>              # 浏览 115 指定目录
    python3 browse.py --search <关键词>      # 115 搜索文件
    python3 browse.py --disk 123            # 浏览 123 根目录
    python3 browse.py --disk 123 <目录ID>   # 浏览 123 指定目录
    python3 browse.py --disk 123 --search <关键词>
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import FILE_LOGIN_HINT, concise_error, fail, get_client, get_list_data, list_115_files_app, looks_like_login_error, print_item
from netdisk import get_123_client, list_123_files, print_123_item


def browse_115(client, cid: int = 0, page: int = 1, limit: int = 50):
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


def search_115(client, keyword: str, limit: int = 30):
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
    disk = "115"
    args = sys.argv[1:]
    if "--disk" in args:
        idx = args.index("--disk")
        if idx + 1 >= len(args):
            fail("用法: python3 browse.py --disk <115|123>")
        disk = args[idx + 1].lower()
        # 去掉 --disk 及其后面的值，保留其余参数
        args = args[:idx] + args[idx + 2:]

    if disk not in ("115", "123"):
        fail(f"不支持的网盘类型: {disk}")

    if disk == "123":
        client = get_123_client()
        token = client.token
        if "--search" in args:
            idx = args.index("--search")
            keyword = args[idx + 1] if idx + 1 < len(args) else ""
            if not keyword:
                fail("用法: python3 browse.py --disk 123 --search <关键词>")
            print(f"🔍 搜索: {keyword}\n")
            try:
                items = list_123_files(token, keyword=keyword)
            except Exception as exc:
                fail(f"搜索失败: {concise_error(exc)}")
            if not items:
                print(f"  未找到包含「{keyword}」的文件")
                return
            for item in items:
                print_123_item(item)
            return
        cid = 0
        for a in args:
            if a.isdigit():
                cid = int(a)
                break
        print(f"📂 123 目录 {cid}:\n")
        try:
            items = list_123_files(token, parent_file_id=cid)
        except Exception as exc:
            fail(f"浏览失败: {concise_error(exc)}")
        if not items:
            print("  (空目录)")
            return
        for item in items:
            print_123_item(item)
        return

    # 115 默认路径
    client = get_client()
    if "--search" in args:
        idx = args.index("--search")
        keyword = args[idx + 1] if idx + 1 < len(args) else ""
        if not keyword:
            fail("用法: python3 browse.py --search <关键词>")
        print(f"🔍 搜索: {keyword}\n")
        search_115(client, keyword)
    else:
        cid = 0
        for a in args:
            if a.isdigit():
                cid = int(a)
                break
        print(f"📂 目录 {cid}:\n")
        browse_115(client, cid)


if __name__ == "__main__":
    main()

