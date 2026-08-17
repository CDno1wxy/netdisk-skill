#!/usr/bin/env python3
"""
测试网盘连接状态（115 / 123）。

用法:
    python3 test_connection.py              # 测试 115
    python3 test_connection.py --disk 123   # 测试 123
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (
    FILE_LOGIN_HINT,
    concise_error,
    get_client,
    get_list_data,
    list_115_files_app,
    load_basic_info,
    looks_like_login_error,
    print_basic_summary,
    print_item,
    require_success,
)
from netdisk import get_123_client, list_123_files, print_123_item


def test_115():
    print("🔌 正在连接 115 网盘...\n")
    client = get_client()
    summary = load_basic_info(client=client)
    print_basic_summary(summary)

    print("\n═══ 根目录预览 ═══")
    try:
        response = list_115_files_app(client, cid=0, limit=10)
        if isinstance(response, dict) and response.get("state") is False:
            print(f"  ⚠️ 获取根目录预览失败: {response.get('error') or response.get('message') or response.get('errno')}")
            if looks_like_login_error(response):
                print(f"  {FILE_LOGIN_HINT}")
        else:
            items = get_list_data(response, "获取根目录预览")
            for item in items:
                print_item(item)
    except Exception as exc:
        print(f"  ⚠️ 获取根目录预览失败: {concise_error(exc)}")
        if looks_like_login_error(exc):
            print(f"  {FILE_LOGIN_HINT}")

    print("\n═══ 离线下载 ═══")
    try:
        quota = require_success(client.offline_quota_info(), "获取离线配额")
        if isinstance(quota.get("data"), dict):
            quota = quota["data"]
        print(f"  配额: {quota.get('quota', '?')} / {quota.get('total', '?')}")
    except Exception as e:
        print(f"  ⚠️ 获取离线配额失败: {concise_error(e)}")

    print("\n✅ 115 网盘基础信息读取完成!")


def test_123():
    print("🔌 正在连接 123 网盘...\n")
    client = get_123_client()
    print("✅ 连接成功!")
    print("\n═══ 根目录预览 ═══")
    try:
        items = list_123_files(client.token, parent_file_id=0, limit=10)
        if not items:
            print("  (空目录)")
        for item in items:
            print_123_item(item)
    except Exception as exc:
        print(f"  ⚠️ 获取根目录预览失败: {concise_error(exc)}")
    print("\n✅ 123 网盘基础信息读取完成!")


def main():
    if "--disk" in sys.argv:
        disk_idx = sys.argv.index("--disk")
        disk = sys.argv[disk_idx + 1].lower()
    else:
        disk = "115"
    if disk == "123":
        test_123()
    else:
        test_115()


if __name__ == "__main__":
    main()
