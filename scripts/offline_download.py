#!/usr/bin/env python3
"""
115 网盘离线下载管理。

用法:
    python3 offline_download.py 'magnet:?xt=urn:btih:xxx'     # 添加磁力下载
    python3 offline_download.py 'ed2k://|file|xxx|...'        # 添加 ed2k 下载
    python3 offline_download.py 'https://example.com/file.zip' # 添加 HTTP 下载
    python3 offline_download.py --list                         # 查看离线任务
    python3 offline_download.py --quota                        # 查看配额
    python3 offline_download.py --path                         # 查看下载目录
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 在 import 第三方依赖前先切到 skill 私有 .venv（如已安装）
from lib import maybe_reexec_in_skill_venv

maybe_reexec_in_skill_venv()

import requests

from lib import (
    fail,
    format_size,
    get_client,
    load_cookies,
    require_success,
)

LIXIAN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
}


def _lixian_headers():
    return {**LIXIAN_HEADERS, "Cookie": load_cookies()}


def response_payload(response: dict, action: str) -> dict:
    """Return the nested data object when an API wraps its payload."""
    response = require_success(response, action)
    data = response.get("data")
    return data if isinstance(data, dict) else response


def add_download(client, url: str, save_path: str = None):
    """添加 115 离线任务：优先 SDK，缺失时使用网页 lixian API。"""
    add = getattr(client, "offline_add_url", None)
    if callable(add):
        params = {"url": url}
        if save_path:
            params["savepath"] = save_path
        result = add(params)
        require_success(result, "添加离线下载")
        print("✅ 下载任务已添加!")
        task = result.get("result") or result.get("data") or {}
        if isinstance(task, dict):
            print(f"   文件: {task.get('name', task.get('file_name', '?'))}")
            print(f"   大小: {format_size(task.get('size', task.get('file_size', 0)))}")
        return result

    # 网页 API 兜底
    payload = {"url": url}
    if save_path:
        payload["savepath"] = save_path
    response = requests.post(
        "https://115.com/web/lixian/?ct=lixian&ac=add_task_url",
        data=payload,
        headers=_lixian_headers(),
        timeout=20,
    )
    data = response.json()
    if data.get("state") is False:
        raise RuntimeError(data.get("error") or data)
    info = data.get("data") or {}
    print("✅ 下载任务已添加!")
    print(f"   文件: {info.get('name', url[:60])}")
    print(f"   大小: {format_size(info.get('size', 0))}")


def list_tasks(client):
    """列出 115 离线任务。"""
    offline_list = getattr(client, "offline_list", None)
    if callable(offline_list):
        tasks = response_payload(offline_list(), "获取离线任务")
        count = tasks.get("count", tasks.get("total_count", tasks.get("total", 0)))
        quota = tasks.get("quota", "?")
        total = tasks.get("total", tasks.get("quota_total", "?"))
        print(f"📊 离线配额: {quota} / {total}")
        print(f"📋 任务数量: {count}")
        task_list = tasks.get("tasks") or tasks.get("list") or []
        if not isinstance(task_list, list):
            fail(f"获取离线任务失败: 任务列表字段不是列表\n   原始响应: {tasks}")
        if not task_list:
            print("  (无任务)")
            return
        print()
        for t in task_list:
            name = t.get("name", t.get("file_name", "?"))
            size = format_size(t.get("size", t.get("file_size", 0)))
            status = t.get("status", "?")
            pct = t.get("percentDone", t.get("progress", "?"))
            status_icon = "✅" if status == 2 else "⏳" if status == 1 else "❌"
            print(f"  {status_icon} {name} ({size}) - {pct}%")
        return

    # 网页 API 兜底
    data = requests.get(
        "https://115.com/web/lixian/?ct=lixian&ac=task_lists",
        headers=_lixian_headers(),
        timeout=20,
    ).json()
    quota = data.get("quota", "?")
    total = data.get("total", "?")
    count = data.get("count", 0)
    task_list = data.get("tasks") or []
    print(f"📊 离线配额: {quota} / {total}")
    print(f"📋 任务数量: {count}")
    if not task_list:
        print("  (无任务)")
        return
    print()
    for t in task_list[:30]:
        name = t.get("name", "?")
        size = format_size(t.get("size", 0))
        pct = t.get("display_percent", t.get("percentDone", "?"))
        status_text = t.get("status_text", t.get("display_status", "?"))
        icon = "✅" if t.get("status") == 2 else "⏳" if t.get("status") == 1 else "❌"
        print(f"  {icon} {name} ({size}) - {pct:.1f}% [{status_text}]")


def show_quota(client):
    """显示 115 离线配额。"""
    offline_quota = getattr(client, "offline_quota_info", None)
    if callable(offline_quota):
        quota = response_payload(offline_quota(), "获取离线配额")
        print(f"📊 离线下载配额: {quota.get('quota', '?')} / {quota.get('total', '?')}")
        return
    data = requests.get(
        "https://115.com/web/lixian/?ct=lixian&ac=task_lists",
        headers=_lixian_headers(),
        timeout=20,
    ).json()
    print(f"📊 离线下载配额: {data.get('quota', '?')} / {data.get('total', '?')}")


def show_paths(client):
    """显示 115 离线下载目录。"""
    offline_path = getattr(client, "offline_download_path", None)
    if callable(offline_path):
        paths = require_success(offline_path(), "获取离线下载目录")
        dirs = paths.get("data", [])
        if isinstance(dirs, dict):
            dirs = dirs.get("list") or dirs.get("paths") or []
        if not isinstance(dirs, list):
            fail(f"获取离线下载目录失败: 目录字段不是列表\n   原始响应: {paths}")
        if not dirs:
            print("  (未配置下载目录)")
            return
        for d in dirs:
            selected = "⭐" if d.get("is_selected") == "1" else "  "
            print(f"  {selected} {d.get('file_name', '?')} (ID: {d.get('file_id', '?')})")
        return
    print("当前 p115client 版本未提供下载目录接口。")
    print("添加任务时可直接指定保存目录：python3 offline_download.py <URL> <目录ID>")


def main():
    args = sys.argv[1:]
    client = get_client()

    if "--list" in args:
        list_tasks(client)
    elif "--quota" in args:
        show_quota(client)
    elif "--path" in args:
        print("📂 离线下载目录:")
        show_paths(client)
    elif len(args) > 0:
        url = args[0]
        save_path = args[1] if len(args) > 1 else None
        print(f"⬇️ 添加离线下载: {url[:80]}{'...' if len(url) > 80 else ''}")
        add_download(client, url, save_path)
    else:
        print("用法:")
        print("  python3 offline_download.py <URL> [保存目录]")
        print("  python3 offline_download.py --list")
        print("  python3 offline_download.py --quota")
        print("  python3 offline_download.py --path")


if __name__ == "__main__":
    main()
