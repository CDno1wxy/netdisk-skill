#!/usr/bin/env python3
"""
TMDB 影视识别（电影 / 剧集）。

用法:
    python3 identify.py --name "侠医 (2025) {tmdb-298444}" [--file "侠医.S01E01.mkv"] [--api-key xxx]

--name 是文件夹名/影视名；--file 是其中的文件名（用于判断剧集）；
TMDB API Key 也可通过环境变量 ENV_TMDB_API_KEY 提供。
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from netdisk import TMDBHelper


def main():
    parser = argparse.ArgumentParser(description="TMDB 影视识别")
    parser.add_argument("--name", required=True, help="影视文件夹名/名称")
    parser.add_argument("--file", default="", help="影视文件名（用于判断剧集）")
    parser.add_argument("--api-key", default=os.getenv("ENV_TMDB_API_KEY", ""), help="TMDB API Key")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    helper = TMDBHelper(args.api_key)
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
