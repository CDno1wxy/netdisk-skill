#!/usr/bin/env python3
"""
按 TMDB 识别结果整理 115 网盘影视目录。

默认只演练并显示匹配结果；增加 --apply 才会执行移动和清理。
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from identify import resolve_api_key
from lib import get_client_from_cookies, load_cookies, resolve_cookies_path
from netdisk import TMDBHelper, _normalize_115_item
from p115client.client import check_response

DEFAULT_SOURCE_PIDS = {
    "云下载": "3439867362963758303",
    "转存": "3439810345100254376",
}
DEFAULT_CATEGORY_PIDS = {
    "电影": "3440501979228019840",
    "剧集": "3441689709559553356",
    "动漫": "3455547294947613986",
    "纪录片": "3456821792988601632",
}
JUNK_NAMES = {"thumbs.db", "desktop.ini", ".ds_store"}
JUNK_SUFFIXES = (".torrent", ".url", ".webloc", ".html", ".htm", ".sfv", ".md5")
JUNK_MARKERS = (
    "发布页",
    "更多无水印",
    "更多高清",
    "更多电视剧集",
    "更多剧集",
    "访问 www",
    "网站宣传",
    "广告",
)


def list_children(client, parent_id):
    payload = {"cid": parent_id, "limit": 1000, "offset": 0, "show_dir": 1}
    errors = []
    for method_name in ("fs_files_app", "fs_files_aps", "fs_files"):
        method = getattr(client, method_name, None)
        if not callable(method):
            continue
        try:
            response = method(payload)
            check_response(response)
            return response.get("data") or []
        except Exception as exc:
            errors.append(f"{method_name}: {exc}")
    raise RuntimeError("无法读取目录: " + " | ".join(errors))


def normalized_item(item):
    return _normalize_115_item(item)


def is_directory(item):
    normalized = normalized_item(item)
    if normalized.get("is_dir") is not None:
        return bool(normalized.get("is_dir"))
    if "fc" in normalized:
        return str(normalized.get("fc")) == "0"
    return "fn" in normalized and "fid" in normalized and "fs" not in normalized


def normalized_name(item):
    normalized = normalized_item(item)
    return normalized.get("name") or normalized.get("fn") or normalized.get("n") or ""


def normalized_id(item):
    normalized = normalized_item(item)
    return normalized.get("id") or normalized.get("fid") or normalized.get("cid")


def classify(metadata):
    genre_ids = set(metadata.get("genre_ids") or [])
    if 99 in genre_ids:
        return "纪录片"
    if 16 in genre_ids:
        return "动漫"
    return "剧集" if metadata.get("media_type") == "tv" else "电影"


def build_target_index(client):
    index = {}
    for category, parent_id in DEFAULT_CATEGORY_PIDS.items():
        for item in list_children(client, parent_id):
            if not is_directory(item):
                continue
            name = normalized_name(item)
            target_id = normalized_id(item)
            match = re.search(r"(?:tmdb|tmdbid)[=-](\d+)", name, re.IGNORECASE)
            if match and target_id:
                index[(category, match.group(1))] = (target_id, name)
    return index


def is_junk_file(name):
    lowered = name.lower().strip()
    if lowered in JUNK_NAMES or lowered.endswith(JUNK_SUFFIXES):
        return True
    return lowered.startswith("sample.") or any(marker.lower() in lowered for marker in JUNK_MARKERS)


def find_media_name(client, parent_id):
    video_suffixes = (".mkv", ".mp4", ".avi", ".m2ts", ".ts", ".mov", ".flv", ".wmv", ".rmvb")
    for item in list_children(client, parent_id):
        item_name = normalized_name(item)
        if is_directory(item):
            nested = find_media_name(client, normalized_id(item))
            if nested:
                return nested
        elif item_name.lower().endswith(video_suffixes):
            return item_name
    return ""


def move_file(client, item_id, target_id):
    response = client.fs_move_app({"ids": item_id, "to_cid": target_id}, app="android")
    check_response(response)


def delete_item(client, item_id):
    response = client.fs_delete_app(item_id)
    check_response(response)


def move_contents(client, source_id, target_id, dry_run):
    stats = {"moved_files": 0, "deleted_junk": 0, "deleted_dirs": 0, "failed": 0}

    def walk(parent_id, depth=0):
        children = list_children(client, parent_id)
        directories = [item for item in children if is_directory(item)]
        files = [item for item in children if not is_directory(item)]
        remaining = False

        for item in files:
            item_id = normalized_id(item)
            item_name = normalized_name(item)
            if not item_id or not item_name:
                continue
            if is_junk_file(item_name):
                if dry_run:
                    print(f"   🗑️ 可清理垃圾: {item_name}")
                else:
                    try:
                        delete_item(client, item_id)
                        stats["deleted_junk"] += 1
                        print(f"   🗑️ 已删除垃圾: {item_name}")
                    except Exception as exc:
                        stats["failed"] += 1
                        remaining = True
                        print(f"   ❌ 删除垃圾失败: {item_name} - {exc}")
                continue
            if dry_run:
                print(f"   📄 可移动内容: {item_name}")
                continue
            try:
                move_file(client, item_id, target_id)
                stats["moved_files"] += 1
                print(f"   📦 已移动内容: {item_name}")
            except Exception as exc:
                stats["failed"] += 1
                remaining = True
                print(f"   ❌ 移动失败: {item_name} - {exc}")

        for directory in directories:
            directory_id = normalized_id(directory)
            directory_name = normalized_name(directory)
            if not directory_id:
                continue
            child_stats = walk(directory_id, depth + 1)
            for key in stats:
                stats[key] += child_stats[key]
            if dry_run:
                print(f"   📁 可清理空目录: {directory_name}")
            else:
                try:
                    if not list_children(client, directory_id):
                        delete_item(client, directory_id)
                        stats["deleted_dirs"] += 1
                        print(f"   🗑️ 已删除空目录: {directory_name}")
                    else:
                        remaining = True
                except Exception as exc:
                    stats["failed"] += 1
                    remaining = True
                    print(f"   ❌ 清理目录失败: {directory_name} - {exc}")

        if dry_run:
            return stats
        if files and any(not is_junk_file(normalized_name(item)) for item in files):
            remaining = remaining or bool(list_children(client, parent_id))
        stats["remaining"] = int(remaining)
        return stats

    result = walk(source_id)
    if not dry_run:
        try:
            if not list_children(client, source_id):
                delete_item(client, source_id)
                result["deleted_dirs"] += 1
                print("   🗑️ 已删除空的来源目录")
        except Exception as exc:
            result["failed"] += 1
            print(f"   ⚠️ 来源目录保留: {exc}")
    return result


def organize(args):
    cookies = load_cookies(resolve_cookies_path(args.cookies_path))
    client = get_client_from_cookies(cookies)
    helper = TMDBHelper(resolve_api_key(args.api_key))
    target_index = build_target_index(client)
    candidates = []
    for source_name, source_id in DEFAULT_SOURCE_PIDS.items():
        for item in list_children(client, source_id):
            item_id = normalized_id(item)
            item_name = normalized_name(item)
            if not item_id or not item_name or not is_directory(item):
                continue
            result = helper.identify(item_name)
            if not result or result.get("error") or not result.get("tmdb_id"):
                media_name = find_media_name(client, item_id)
                if media_name:
                    result = helper.identify(media_name, media_name)
            if not result or result.get("error") or not result.get("tmdb_id"):
                print(f"⚠️ 未识别，保留: {source_name}/{item_name}")
                continue
            category = classify(result)
            target = target_index.get((category, str(result["tmdb_id"])))
            if not target:
                print(f"⚠️ 未找到整理目录，保留: {item_name} -> {category} / {result.get('title')} ({result.get('tmdb_id')})")
                continue
            candidates.append((source_name, item_id, item_name, category, target[0], target[1]))
            print(f"✅ 匹配: {source_name}/{item_name}")
            print(f"   -> 整理/{category}/{target[1]}")

    if not candidates:
        print("没有找到可移动的明确匹配项。")
        return
    if not args.apply:
        print(f"\n演练完成：{len(candidates)} 项可整理。加 --apply 才会移动内容并清理垃圾。")
        return

    totals = {"moved_files": 0, "deleted_junk": 0, "deleted_dirs": 0, "failed": 0}
    for source_name, source_id, source_item_name, category, target_id, target_name in candidates:
        print(f"\n📂 整理: {source_name}/{source_item_name} -> 整理/{category}/{target_name}")
        result = move_contents(client, source_id, target_id, dry_run=False)
        for key in totals:
            totals[key] += result.get(key, 0)
    print(
        f"\n完成：移动内容 {totals['moved_files']} 项，删除垃圾 {totals['deleted_junk']} 项，"
        f"删除空目录 {totals['deleted_dirs']} 个，失败 {totals['failed']} 项。"
    )
    if totals["failed"]:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="按 TMDB 识别结果整理 115 云下载和转存目录")
    parser.add_argument("--apply", action="store_true", help="执行实际移动和清理；默认只演练")
    parser.add_argument("--api-key", default="", help="TMDB API Key（默认读取环境变量或 ~/.tmdb-api-key）")
    parser.add_argument("--cookies-path", help="115 cookies 文件路径（默认 ~/.115-cookies）")
    organize(parser.parse_args())


if __name__ == "__main__":
    main()
