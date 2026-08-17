#!/usr/bin/env python3
"""
扫描 Telegram 频道中的网盘分享链接（115 / 123）。

用法:
    python3 monitor.py --channel https://t.me/s/xxx [--limit 20] [--transfer] [--target-pid <ID>]

默认只列出频道最新消息和其中发现的分享链接；
加 --transfer 会把发现的链接转存到 --target-pid 指定目录。
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import fail, load_cookies, resolve_cookies_path
from netdisk import get_123_client, scan_telegram_channel, transfer_115_share, transfer_123_share


def main():
    parser = argparse.ArgumentParser(description="扫描 Telegram 频道中的网盘分享链接")
    parser.add_argument("--channel", required=True, help="Telegram 频道链接，如 https://t.me/s/xxx 或 https://t.me/xxx")
    parser.add_argument("--limit", type=int, default=20, help="扫描最新消息条数")
    parser.add_argument("--transfer", action="store_true", help="把发现的分享链接转存")
    parser.add_argument("--target-pid", help="转存目标目录 ID（--transfer 时必填）")
    parser.add_argument("--cookies-path", help="115 cookies 文件路径（默认 ~/.115-cookies）")
    args = parser.parse_args()

    if args.transfer and not args.target_pid:
        fail("--transfer 需要 --target-pid")

    print(f"📡 扫描频道: {args.channel} (最新 {args.limit} 条)\n")
    try:
        messages = scan_telegram_channel(args.channel, limit=args.limit)
    except Exception as exc:
        fail(f"扫描失败: {exc}")

    if not messages:
        print("(未获取到消息，频道可能不存在或需要代理访问)")
        sys.exit(0)

    total_115 = 0
    total_123 = 0
    for msg in messages:
        links_115 = msg["links"]["115"]
        links_123 = msg["links"]["123"]
        if not links_115 and not links_123:
            continue
        total_115 += len(links_115)
        total_123 += len(links_123)
        print(f"--- 消息 {msg['id']} ({msg['date']}) ---")
        print(f"    文本: {msg['text'][:120]}")
        for link in links_115:
            print(f"    🅰️ 115: {link}")
        for link in links_123:
            print(f"    🅱️ 123: {link.split(chr(25552)+chr(21462))[0].strip() or link}")
        print()

    if not total_115 and not total_123:
        print("(频道最新消息中未发现 115 / 123 分享链接)")
        sys.exit(0)

    if not args.transfer:
        print(f"共发现 {total_115} 个 115 链接、{total_123} 个 123 链接。加 --transfer --target-pid <ID> 可自动转存。")
        sys.exit(0)

    print(f"开始转存到目录 {args.target_pid} ...\n")
    ok_count = 0
    fail_count = 0
    for msg in messages:
        for link in msg["links"]["115"]:
            cookies = load_cookies(resolve_cookies_path(args.cookies_path))
            ok, msg_text = transfer_115_share(cookies, link, args.target_pid)
            print(f"{'✅' if ok else '❌'} [115] {link} -> {msg_text}")
            ok_count += 1 if ok else 0
            fail_count += 0 if ok else 1
        for link in msg["links"]["123"]:
            client = get_123_client()
            ok, msg_text = transfer_123_share(client, link, args.target_pid)
            print(f"{'✅' if ok else '❌'} [123] {link} -> {msg_text}")
            ok_count += 1 if ok else 0
            fail_count += 0 if ok else 1

    print(f"\n完成：成功 {ok_count}，失败 {fail_count}")
    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
