#!/usr/bin/env python3
"""
按 TMDB 识别结果整理 115 网盘影视目录。

默认只演练并显示匹配结果；增加 --apply 才会执行整体移动。
"""

import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from identify import resolve_api_key
from download_metadata import load_metadata, metadata_matches_name
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


def is_noisy_name(name):
    markers = ("发布", "首发", "梦幻天堂", "龙网", "飞鸟娱乐", "6v电影", "阳光电影", "UIndex", "www.")
    return bool(re.search(r"[\u4e00-\u9fff][A-Za-z]{1,}[\u4e00-\u9fff]", name)) or any(
        marker.lower() in name.lower() for marker in markers
    )


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


def move_item(client, item_id, target_id):
    for attempt in range(4):
        try:
            response = client.fs_move_app({"ids": item_id, "to_cid": target_id}, app="android")
            check_response(response)
            return
        except Exception:
            if attempt == 3:
                raise
            time.sleep(5)


def rename_item(client, item_id, name):
    response = client.fs_rename_app((item_id, name), app="android")
    check_response(response)


def delete_item(client, item_id):
    response = client.fs_delete_app(item_id)
    check_response(response)


VIDEO_SUFFIXES = (".mkv", ".mp4", ".avi", ".m2ts", ".ts", ".mov", ".flv", ".wmv", ".rmvb")
SIDEcar_SUFFIXES = (".srt", ".ass", ".ssa", ".sup", ".vtt", ".nfo", ".ac3", ".dts", ".flac", ".mp3")
JUNK_DIR_MARKERS = ("发布页", "地址", "6v电影", "uindex", "更多无水印", "下载地址")


def is_media_or_sidecar(name):
    return name.lower().endswith(VIDEO_SUFFIXES + SIDEcar_SUFFIXES)


def is_junk_dir_name(name):
    lowered = name.lower()
    return any(marker.lower() in lowered for marker in JUNK_DIR_MARKERS)


def contains_media(client, parent_id):
    for item in list_children(client, parent_id):
        if is_directory(item):
            if contains_media(client, normalized_id(item)):
                return True
        elif is_media_or_sidecar(normalized_name(item)):
            return True
    return False


def cleanup_residue(client, parent_id, dry_run=False):
    """Remove empty directories and clearly promotional directories left behind."""
    removed = 0
    for item in list_children(client, parent_id):
        if not is_directory(item):
            continue
        item_id = normalized_id(item)
        item_name = normalized_name(item)
        removed += cleanup_residue(client, item_id, dry_run)
        children = list_children(client, item_id)
        if children and not contains_media(client, item_id):
            if is_junk_dir_name(item_name):
                if dry_run:
                    print(f"   🧹 可清理垃圾目录: {item_name}")
                else:
                    delete_item(client, item_id)
                    print(f"   🧹 已清理垃圾目录: {item_name}")
                removed += 1
                continue
        if not children:
            if dry_run:
                print(f"   🧹 可清理空目录: {item_name}")
            else:
                delete_item(client, item_id)
                print(f"   🧹 已清理空目录: {item_name}")
            removed += 1
    return removed


def move_contents(client, source_id, target_id, dry_run):
    stats = {"moved_items": 0, "deleted_files": 0, "deleted_dirs": 0, "failed": 0}
    children = list_children(client, source_id)
    for item in children:
        item_id = normalized_id(item)
        item_name = normalized_name(item)
        if not item_id or not item_name:
            continue
        if dry_run:
            print(f"   📦 可整体移动: {item_name}")
            continue
        try:
            move_item(client, item_id, target_id)
            stats["moved_items"] += 1
            print(f"   📦 已整体移动: {item_name}")
        except Exception as exc:
            stats["failed"] += 1
            print(f"   ❌ 移动失败: {item_name} - {exc}")
    stats["deleted_dirs"] += cleanup_residue(client, source_id, dry_run)

    result = stats
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
    saved_metadata = list(load_metadata().values())
    target_index = build_target_index(client)
    candidates = []
    seen = 0
    inspected = 0
    for source_name, source_id in DEFAULT_SOURCE_PIDS.items():
        for item in list_children(client, source_id):
            if args.offset and seen < args.offset:
                seen += 1
                continue
            if args.limit and inspected >= args.limit:
                break
            seen += 1
            inspected += 1
            item_id = normalized_id(item)
            item_name = normalized_name(item)
            if not item_id or not item_name or not is_directory(item):
                continue
            result = {}
            for saved in saved_metadata:
                if saved.get("tmdb_id") and metadata_matches_name(saved, item_name):
                    result = saved
                    break
            if not result:
                result = helper.identify(item_name)
            if result and result.get("tmdb_id"):
                parsed_title = helper.parse_metadata(item_name).get("title") or ""
                result_title = result.get("title") or ""
                original_title = result.get("original_title") or ""
                saved_match = any(
                    saved.get("tmdb_id") == result.get("tmdb_id")
                    and metadata_matches_name(saved, item_name)
                    for saved in saved_metadata
                )
                if (
                    parsed_title
                    and not saved_match
                    and not helper._related_title(parsed_title, result_title)
                    and not helper._related_title(parsed_title, original_title)
                ):
                    print(f"⚠️ 片名与 TMDB 结果不相关，保留: {source_name}/{item_name}")
                    continue
            noisy_title = is_noisy_name(item_name)
            if not result or result.get("error") or not result.get("tmdb_id") or noisy_title:
                media_name = find_media_name(client, item_id)
                if media_name:
                    media_noisy = is_noisy_name(media_name)
                    if not media_noisy:
                        media_result = helper.identify(media_name, media_name)
                        if media_result and not media_result.get("error") and media_result.get("tmdb_id"):
                            if result and result.get("tmdb_id") and str(result["tmdb_id"]) != str(media_result["tmdb_id"]):
                                result = {}
                            else:
                                result = media_result
                    elif noisy_title:
                        result = {}
                elif noisy_title:
                    result = {}
            if not result or result.get("error") or not result.get("tmdb_id"):
                print(f"⚠️ 未识别，保留: {source_name}/{item_name}")
                continue
            category = classify(result)
            target = target_index.get((category, str(result["tmdb_id"])))
            if target:
                target_title = re.sub(r"\s*\{tmdb-\d+\}\s*$", "", target[1], flags=re.IGNORECASE).strip()
                result_title = result.get("title") or result.get("original_title") or ""
                if target_title and result_title and not helper._related_title(target_title, result_title):
                    print(f"⚠️ 目标目录与识别结果不一致，保留: {source_name}/{item_name}")
                    continue
            target_id = target[0] if target else ""
            target_name = target[1] if target else f"{result.get('title')} ({result.get('year')}) {{tmdb-{result.get('tmdb_id')}}}"
            category_parent_id = DEFAULT_CATEGORY_PIDS[category]
            candidates.append((source_name, item_id, item_name, category, category_parent_id, target_id, target_name))
            print(f"✅ 匹配: {source_name}/{item_name}")
            print(f"   -> 整理/{category}/{target_name}")

    if not candidates:
        print("没有找到可移动的明确匹配项。")
        return
    if not args.apply:
        print(f"\n演练完成：{len(candidates)} 项可整理。加 --apply 才会整体移动目录内容。")
        return

    totals = {"moved_items": 0, "deleted_files": 0, "deleted_dirs": 0, "failed": 0}
    prepared = []
    print("\n📝 第一阶段：统一重命名源目录")
    for candidate in candidates:
        source_name, source_id, source_item_name, category, category_parent_id, target_id, target_name = candidate
        try:
            rename_item(client, source_id, target_name)
            prepared.append(candidate)
            print(f"   ✅ {source_item_name} -> {target_name}")
        except Exception as exc:
            totals["failed"] += 1
            print(f"   ❌ 重命名失败: {source_item_name} - {exc}")
    if prepared:
        time.sleep(5)

    print("\n📦 第二阶段：统一整体移动目录")
    for source_name, source_id, source_item_name, category, category_parent_id, target_id, target_name in prepared:
        print(f"\n📂 整理: {target_name} -> 整理/{category}")
        if target_id:
            result = move_contents(client, source_id, target_id, dry_run=False)
        else:
            result = {"moved_items": 0, "deleted_files": 0, "deleted_dirs": 0, "failed": 0}
            try:
                move_item(client, source_id, category_parent_id)
                result["moved_items"] = 1
                print(f"   📦 已整体移动目录: {target_name}")
            except Exception as exc:
                result["failed"] = 1
                print(f"   ❌ 目录整体移动失败: {exc}")
        for key in totals:
            totals[key] += result.get(key, 0)
    print(
        f"\n完成：整体移动 {totals['moved_items']} 项，未删除任何文件，"
        f"删除空源目录 {totals['deleted_dirs']} 个，失败 {totals['failed']} 项。"
    )
    if totals["failed"]:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="按 TMDB 识别结果整理 115 云下载和转存目录")
    parser.add_argument("--apply", action="store_true", help="执行实际移动和清理；默认只演练")
    parser.add_argument("--api-key", default="", help="TMDB API Key（默认读取环境变量或 ~/.tmdb-api-key）")
    parser.add_argument("--cookies-path", help="115 cookies 文件路径（默认 ~/.115-cookies）")
    parser.add_argument("--limit", type=int, default=0, help="本次最多处理多少个源目录；0 表示不限制")
    parser.add_argument("--offset", type=int, default=0, help="跳过前多少个源目录")
    organize(parser.parse_args())


if __name__ == "__main__":
    main()
