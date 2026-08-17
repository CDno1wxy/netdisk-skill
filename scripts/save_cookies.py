#!/usr/bin/env python3
"""
保存 115 网盘 Cookies 到标准路径并验证有效性。

用法:
    python3 save_cookies.py --stdin     # 从标准输入读取 cookies
    python3 save_cookies.py --env       # 从 P115_COOKIES 读取 cookies
    python3 save_cookies.py              # 交互式输入
    python3 save_cookies.py 'UID=xxx; CID=xxx; SEID=xxx; KID=xxx'
    python3 save_cookies.py --test       # 仅测试已有 cookies 是否有效
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import COOKIES_PATH, format_size, import_p115client, load_cookies, require_success


def validate_cookies_format(cookies: str) -> bool:
    """校验 115 cookies 是否包含 4 个关键字段。"""
    if not cookies:
        return False
    required = ["UID=", "CID=", "SEID=", "KID="]
    return all(key in cookies for key in required)


def test_connection(cookies: str) -> bool:
    """测试 115 cookies 有效性。"""
    try:
        P115Client = import_p115client()
        client = P115Client(cookies)
        info = require_success(client.user_info(), "验证 Cookies")
        user = info.get("data", {})
        print("✅ 连接成功!")
        print(f"   用户: {user.get('user_name')} (ID: {user.get('user_id')})")
        print(f"   VIP:  {user.get('is_vip')}")
        space = client.fs_storage_info()
        for type_id, info in space.items():
            total = format_size(info.get("total", 0))
            used = format_size(info.get("used", 0))
            print(f"   空间: {used} / {total}")
            break
        return True
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="保存并验证 115 网盘 Cookies")
    parser.add_argument("cookies", nargs="?", help="115 cookies 字符串；不推荐，可能进入 shell 历史")
    parser.add_argument("--stdin", action="store_true", help="从标准输入读取 cookies")
    parser.add_argument("--env", action="store_true", help="从 P115_COOKIES 环境变量读取 cookies")
    parser.add_argument("--test", action="store_true", help="仅测试已有 cookies 是否有效")
    args = parser.parse_args()

    if args.test:
        cookies = load_cookies(COOKIES_PATH)
        print(f"📂 读取 cookies: {COOKIES_PATH}")
        ok = test_connection(cookies)
        sys.exit(0 if ok else 1)

    if args.stdin:
        cookies = sys.stdin.read().strip()
    elif args.env:
        cookies = os.environ.get("P115_COOKIES", "").strip()
    elif args.cookies:
        print("⚠️ 不建议通过命令行参数传入 cookies，可能进入 shell 历史。", file=sys.stderr)
        cookies = args.cookies.strip()
    else:
        print("请输入 115 网盘 Cookies（格式: UID=xxx; CID=xxx; SEID=xxx; KID=xxx）:")
        cookies = input("> ").strip()

    if not validate_cookies_format(cookies):
        print("\n格式示例:")
        print("  UID=309340478_I1_xxx; CID=bf8c61a3xxx; SEID=ad0e6a3bxxx; KID=c371f1d5xxx")
        print("\n获取方式: 浏览器登录 115.com → F12 → Application → Cookies → 复制上述 4 个字段")
        sys.exit(1)

    print("🔌 测试连接...")
    if not test_connection(cookies):
        sys.exit(1)

    with COOKIES_PATH.open("w", encoding="utf-8") as f:
        f.write(cookies.strip())
    os.chmod(COOKIES_PATH, 0o600)
    print(f"✅ Cookies 已保存到: {COOKIES_PATH}")
    print("\n🎉 完成! 后续可直接使用 browse.py / offline_download.py 等工具。")


if __name__ == "__main__":
    main()
