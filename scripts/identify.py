#!/usr/bin/env python3
"""
TMDB 影视识别（电影 / 剧集）。

用法:
    python3 identify.py --name "侠医 (2025) {tmdb-298444}" [--file "侠医.S01E01.mkv"] [--api-key xxx]

--name 是文件夹名/影视名；--file 是其中的文件名（用于判断剧集）；
TMDB API Key 读取优先级: --api-key > ENV_TMDB_API_KEY > ~/.tmdb-api-key。
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from netdisk import TMDBHelper


def resolve_api_key(cli_key: str = "") -> str:
    """API Key 优先级: --api-key > ENV_TMDB_API_KEY > ~/.tmdb-api-key。"""
    if cli_key:
        return cli_key
    env_key = os.getenv("ENV_TMDB_API_KEY", "").strip()
    if env_key:
        return env_key
    key_file = Path("~/.tmdb-api-key").expanduser()
    if key_file.exists():
        try:
            return key_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return ""


def main():
    parser = argparse.ArgumentParser(description="TMDB 影视识别")
    parser.add_argument("--name", required=True, help="影视文件夹名/名称")
    parser.add_argument("--file", default="", help="影视文件名（用于判断剧集）")
    parser.add_argument("--api-key", default="", help="TMDB API Key（默认读取环境变量或 ~/.tmdb-api-key）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    helper = TMDBHelper(resolve_api_key(args.api_key))
    result = helper.identify(args.name, args.file)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    if "error" in result:
        print(f"❌ {result['error']}")
        sys.exit(1)
    if not result:
        print("❌ 未识别到 TMDB 元数据")
        sys.exit(1)

    media = "剧集" if result.get("media_type") == "tv" else "电影"
    print(f"✅ 识别结果（{media}）")
    print(f"   标题: {result.get('title')} ({result.get('original_title')})")
    print(f"   年份: {result.get('year')}")
    print(f"   TMDB ID: {result.get('tmdb_id')}")
    print(f"   评分: {result.get('vote_average')}")
    overview = result.get("overview", "")
    if overview:
        print(f"   简介: {overview[:150]}")


if __name__ == "__main__":
    main()
