#!/usr/bin/env python3
"""
netdisk-skill 扩展操作库。

合并自:
- 115-netdisk-skill: 115 扫码登录 / cookies / 浏览 / 搜索 / 离线下载
- TgtoDrive (v6.6.4): 115 / 123 分享链接转存、123 直链与分享创建、115 目录整理与清理、
  Telegram 频道监控、TMDB 影视识别

本模块不直接可执行，作为各 CLI 脚本的公共库使用。
"""

import os
import re
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple, Union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 在 import 第三方依赖前先切到 skill 私有 .venv（如已安装）
from lib import maybe_reexec_in_skill_venv

maybe_reexec_in_skill_venv()

import requests
from bs4 import BeautifulSoup

from lib import (
    HTTP_JSON_HEADERS,
    concise_error,
    ensure_supported_python,
    fail,
    format_size,
)

# ============================ 123 云盘 ============================

P123_TOKEN_PATH = Path("~/.123-token").expanduser()
P123_COOKIES_PATH = Path("~/.123-cookies").expanduser()

# 123 网页版文件列表 API（与 TgtoDrive get_download_url_by_path.py 一致）
P123_LIST_URL = "https://www.123pan.com/b/api/file/list/new"
# 123 开放平台 API
P123_OPEN_HOST = "https://open-api.123pan.com"
# 123 分享转存 API（TgtoDrive 使用）
P123_COPY_SAVE_URL = "https://www.123pan.com/b/api/restful/goapi/v1/file/copy/save"


def import_p123client():
    """Import p123client with a clear remediation message for agents."""
    maybe_reexec_in_skill_venv()
    ensure_supported_python()
    try:
        from p123client.client import P123Client, check_response
    except ModuleNotFoundError as exc:
        if exc.name != "p123client":
            raise
        fail(
            "缺少依赖: p123client，请重新运行 skill 安装器（会创建 .venv 并安装依赖）。"
        )
    return P123Client, check_response


def resolve_123_token_path(token_path=None) -> Path:
    """Resolve the 123 token file path used by all 123 helper scripts."""
    return Path(token_path).expanduser() if token_path else P123_TOKEN_PATH


def load_123_token(token_path=None) -> str:
    """读取 123 网盘 token 文件，不存在则报错退出。"""
    path = resolve_123_token_path(token_path)
    if not path.exists():
        fail(
            f"123 token 文件不存在: {path}\n"
            "请先运行: python3 scripts/save_cookies.py --disk 123 --token <token>\n"
            "或配置 ENV_123_CLIENT_ID / ENV_123_CLIENT_SECRET 后运行 123 相关脚本自动获取。"
        )
    with path.open(encoding="utf-8") as f:
        token = f.read().strip()
    if not token:
        fail(f"123 token 文件为空: {path}")
    return token


def save_123_token(token: str, token_path=None) -> Path:
    """把 123 token 持久化到标准路径。"""
    path = resolve_123_token_path(token_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token.strip(), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def get_123_client(
    token: Optional[str] = None,
    token_path=None,
    cookies: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
):
    """
    初始化 P123Client。

    凭据优先级:
    1. 显式传入的 token
    2. ~/.123-token 持久化 token
    3. cookies（123 网盘网页 Cookie）
    4. client_id + client_secret（123 开放平台应用凭据，可自动换取 token）

    成功后校验 token，并把 token 持久化到 ~/.123-token。
    """
    P123Client, check_response = import_p123client()
    path = resolve_123_token_path(token_path)

    resolved = token or None
    if not resolved and path.exists():
        try:
            resolved = path.read_text(encoding="utf-8").strip()
        except OSError:
            resolved = None
    if not resolved and cookies:
        try:
            client = P123Client(cookies=cookies)
            client.user_info()
            resolved = getattr(client, "token", None)
        except Exception:
            resolved = None
    if not resolved and client_id and client_secret:
        try:
            client = P123Client(client_id, client_secret)
            resolved = client.token
        except Exception as exc:
            fail(f"使用开放平台凭据获取 123 token 失败: {concise_error(exc)}")

    if not resolved:
        fail(
            "未找到 123 网盘凭据\n"
            "请先运行: python3 scripts/save_cookies.py --disk 123 --token <token>\n"
            "或设置环境变量 ENV_123_CLIENT_ID / ENV_123_CLIENT_SECRET（123 开放平台应用）"
        )

    try:
        client = P123Client(token=resolved)
        res = client.user_info()
        if isinstance(res, dict):
            ok = res.get("code") in (0, None) and res.get("message") in (None, "ok")
            if not ok:
                fail(f"123 token 无效: {res}")
    except Exception as exc:
        fail(f"123 token 校验失败: {concise_error(exc)}")

    if not path.exists():
        save_123_token(getattr(client, "token", resolved), path)
    return client


def request_123_json(url: str, token: str, platform: str = "web", method: str = "GET", payload: Optional[dict] = None) -> dict:
    """调用 123 网盘 JSON API（web 或 open_platform）。"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Platform": platform,
        "User-Agent": HTTP_JSON_HEADERS["User-Agent"],
        "Accept": "application/json,text/plain,*/*",
    }
    try:
        if method.upper() == "POST":
            headers["Content-Type"] = "application/json"
            response = requests.post(url, json=payload, headers=headers, timeout=20)
        else:
            response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"请求失败: {concise_error(exc)}") from exc


def list_123_files(token: str, parent_file_id: int = 0, keyword: str = "", limit: int = 100, page: int = 1) -> list:
    """浏览/搜索 123 网盘目录（返回 InfoList）。"""
    query = (
        f"driveId=0&limit={limit}&next=0&orderBy=update_time&orderDirection=desc"
        f"&parentFileId={parent_file_id}&trashed=false&SearchData={keyword}"
        f"&Page={page}&OnlyLookAbnormalFile=0&event=homeListFile&operateType=2&inDirectSpace=false"
    )
    data = request_123_json(f"{P123_LIST_URL}?{query}", token)
    if data.get("code") != 0:
        raise RuntimeError(data.get("message") or str(data))
    return (data.get("data") or {}).get("InfoList") or []


def print_123_item(item: dict):
    """格式化打印一个 123 文件/文件夹条目。"""
    name = item.get("FileName") or "?"
    if item.get("Type") == 1:  # 目录
        print(f"  📁 {name}/ (ID: {item.get('FileId')})")
    else:
        size = format_size(item.get("Size", 0))
        print(f"  📄 {name} ({size}) (ID: {item.get('FileId')})")


# -------------------- 123 分享链接转存 --------------------

def parse_123_share_url(target_url: str) -> Optional[Tuple[str, str]]:
    """解析 123 分享链接，返回 (share_key, share_pwd)。"""
    from urllib.parse import parse_qs, urlsplit

    parsed_url = urlsplit(target_url)
    share_key = None
    if "/s/" in parsed_url.path:
        after_s = parsed_url.path.split("/s/")[-1]
        temp_key = after_s.split("/")[0]
        pwd_sep_index = re.search(r"提取码[:：]", temp_key)
        share_key = temp_key[:pwd_sep_index.start()].strip() if pwd_sep_index else temp_key
    if not share_key:
        return None

    share_pwd = parse_qs(parsed_url.query).get("pwd", [None])[0]
    if not share_pwd:
        pwd_match = re.search(r"提取码\s*[:：]\s*(\w+)", target_url, re.IGNORECASE)
        share_pwd = pwd_match.group(1) if pwd_match else ""
    return share_key, share_pwd


def transfer_123_share(client, share_url: str, target_pid) -> Tuple[bool, str]:
    """
    转存 123 分享链接到目标目录（移植自 TgtoDrive tgto123.py transfer_shared_link）。
    返回 (是否成功, 说明)。
    """
    P123Client, check_response = import_p123client()
    parsed = parse_123_share_url(share_url)
    if not parsed:
        return False, f"无效的 123 分享链接: {share_url}"
    share_key, share_pwd = parsed

    all_items = []

    def recursive_fetch(parent_file_id: int = 0) -> None:
        page = 1
        while True:
            resp = client.share_fs_list({
                "ShareKey": share_key,
                "SharePwd": share_pwd,
                "parentFileId": parent_file_id,
                "limit": 100,
                "Page": page,
            })
            check_response(resp)
            data = resp.get("data") or {}
            info_list = data.get("InfoList") or []
            for item in info_list:
                all_items.append({
                    "file_id": item.get("FileId"),
                    "name": item.get("FileName"),
                    "etag": item.get("Etag", ""),
                    "parent_dir_id": parent_file_id,
                    "size": item.get("Size", 0),
                    "Type": item.get("Type"),
                })
            if len(info_list) < 100:
                break
            page += 1

    try:
        recursive_fetch()
        file_count = sum(1 for item in all_items if item.get("Type") != 1)
        dir_count = sum(1 for item in all_items if item.get("Type") == 1)
    except Exception as exc:
        return False, f"获取分享资源结构失败: {concise_error(exc)}"

    if not all_items:
        return False, "分享中没有可转存的项目"

    file_list = [
        {
            "fileID": item["file_id"],
            "size": item["size"],
            "etag": item["etag"],
            "type": item["Type"],
            "parentFileID": int(target_pid),
            "fileName": item["name"],
            "driveID": 0,
        }
        for item in all_items
    ]
    try:
        data = request_123_json(
            P123_COPY_SAVE_URL,
            getattr(client, "token", ""),
            platform="web",
            method="POST",
            payload={
                "fileList": file_list,
                "shareKey": share_key,
                "sharePwd": share_pwd,
                "currentLevel": 0,
            },
        )
        if data.get("message") == "ok" or data.get("code") == 0:
            return True, f"转存成功（{file_count} 个文件，{dir_count} 个目录）"
        return False, f"转存失败: {data.get('message') or data}"
    except Exception as exc:
        return False, f"转存过程中发生错误: {concise_error(exc)}"


# -------------------- 123 直链与分享创建 --------------------

def get_123_file_detail(client, file_id) -> dict:
    """获取 123 文件/文件夹详情。"""
    try:
        data = request_123_json(
            f"{P123_OPEN_HOST}/api/v1/file/detail?fileID={file_id}",
            client.token,
            platform="open_platform",
        )
        if data.get("code") != 0:
            return {}
        return data.get("data") or {}
    except Exception:
        return {}


def get_123_download_url_by_file_id(client, file_id) -> Optional[str]:
    """按文件 ID 获取 123 下载直链。"""
    try:
        data = request_123_json(
            f"{P123_OPEN_HOST}/api/v1/file/download_info?fileId={file_id}",
            client.token,
            platform="open_platform",
        )
        if data.get("code") != 0:
            return None
        return (data.get("data") or {}).get("downloadUrl")
    except Exception:
        return None


def search_123_exact_file(client, file_path: str) -> Optional[dict]:
    """
    按完整路径的文件名搜索 123 网盘，返回与文件名匹配且体积最大的文件。
    移植自 TgtoDrive get_download_url_by_path.py。
    """
    file_name_with_ext = os.path.basename(file_path)
    if not file_name_with_ext:
        return None
    token = client.token

    def search_and_match(keyword: str) -> Optional[dict]:
        try:
            items = list_123_files(token, keyword=keyword, limit=100)
        except Exception:
            return None
        exact_matches = []
        file_name_no_ext = file_name_with_ext.rsplit(".", 1)[0] if "." in file_name_with_ext else file_name_with_ext
        target_ext = file_name_with_ext.rsplit(".", 1)[1].lower() if "." in file_name_with_ext else ""
        for item in items:
            if not isinstance(item, dict) or item.get("Type") != 0:
                continue
            item_name = item.get("FileName") or ""
            item_ext = item_name.rsplit(".", 1)[1].lower() if "." in item_name else ""
            if file_name_no_ext in item_name and item_ext == target_ext and not item.get("Trashed"):
                exact_matches.append(item)
        if not exact_matches:
            return None
        return max(exact_matches, key=lambda x: x.get("Size", x.get("BaseSize", 0)))

    match = search_and_match(file_name_with_ext)
    if match:
        return match

    # 兜底：用 guessit 提取标题再搜一次
    try:
        import guessit
        guess = guessit.guessit(file_name_with_ext)
        first_part = None
        if "title" not in guess:
            if " " in file_name_with_ext:
                first_part = file_name_with_ext.split(" ")[0]
            elif "." in file_name_with_ext:
                first_part = file_name_with_ext.split(".")[0]
            else:
                first_part = file_name_with_ext
        elif guess.get("type") == "episode":
            season_episode_match = re.search(r"S\d+E\d+", file_path, re.IGNORECASE)
            season_episode = season_episode_match.group() if season_episode_match else ""
            first_part = guess.get("title") + season_episode
        else:
            first_part = guess.get("title")
        if first_part:
            match = search_and_match(first_part)
    except Exception:
        match = None
    return match


def get_123_direct_url_by_path(client, file_path: str) -> Optional[str]:
    """按文件路径获取 123 302 直链（无匹配返回 None）。"""
    match = search_123_exact_file(client, file_path)
    if not match:
        return None
    return get_123_download_url_by_file_id(client, match.get("FileId"))


def create_123_share(client, file_id, expiry_days: int = 7, password: str = "") -> dict:
    """
    创建 123 分享链接（移植自 TgtoDrive create_share_link）。
    返回 {url, password, expiry}。
    """
    if expiry_days not in (0, 1, 7, 30):
        expiry_days = 7
    detail = get_123_file_detail(client, file_id)
    folder_name = detail.get("filename") or f"分享文件夹_{file_id}"
    data = request_123_json(
        f"{P123_OPEN_HOST}/api/v1/share/create",
        client.token,
        platform="open_platform",
        method="POST",
        payload={
            "shareName": folder_name,
            "shareExpire": expiry_days,
            "fileIDList": file_id,
            "sharePwd": password,
        },
    )
    if data.get("code") != 0:
        raise RuntimeError(data.get("message") or f"创建分享失败 (ID: {file_id})")
    share_info = data.get("data") or {}
    url = f"https://www.123pan.com/s/{share_info.get('shareKey')}"
    if password:
        url += f"?pwd={password}"
    expiry_str = "永久有效" if expiry_days == 0 else f"{expiry_days} 天"
    return {"url": url, "password": share_info.get("sharePwd") or password, "expiry": expiry_str}


# ============================ 115 扩展（移植自 TgtoDrive） ============================

class Fake115Client:
    """
    115 分享链接转存客户端（移植自 TgtoDrive tgto115.py）。
    使用 webapi.115.com/share/snap + share/receive 完成转存。
    """

    def __init__(self, cookies: str):
        self.cookies = cookies
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        self.header = {
            "User-Agent": self.ua,
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": self.cookies,
        }
        self.user_id = self.get_userid()

    def get_userid(self) -> str:
        try:
            resp = requests.get("https://my.115.com/?ct=ajax&ac=get_user_aq", headers=self.header, timeout=15)
            root = resp.json()
            if not root.get("state"):
                fail(f"获取 UID 错误：{root.get('error_msg')}")
            return root.get("data", {}).get("uid", "")
        except Exception as exc:
            fail(f"获取 115 UID 失败: {concise_error(exc)}")
        return ""

    def request_datalist(self, share_code: str, receive_code: str) -> Tuple[dict, list]:
        url = (
            f"https://webapi.115.com/share/snap?share_code={share_code}"
            f"&offset=0&limit=20&receive_code={receive_code}&cid="
        )
        share_info: dict = {}
        data_list: list = []
        try:
            response = requests.get(url, headers=self.header, timeout=15)
            response_json = response.json()
            share_info = response_json.get("data", {}).get("shareinfo") or {}
            if response_json.get("state") is False:
                raise RuntimeError(response_json.get("error", "unknown"))
            count = response_json.get("data", {}).get("count", 0)
            data_list.extend(response_json.get("data", {}).get("list", []))
            while len(data_list) < count:
                offset = len(data_list)
                page = requests.get(f"{url}&offset={offset}", headers=self.header, timeout=15).json()
                data_list.extend(page.get("data", {}).get("list", []))
        except Exception:
            data_list = []
        return share_info, data_list

    def post_save(self, share_code: str, receive_code: str, file_ids, pid: str = "") -> bool:
        time.sleep(2)
        file_id_str = ",".join(str(fid) for fid in file_ids)
        payload = {
            "user_id": self.user_id,
            "share_code": share_code,
            "receive_code": receive_code,
            "file_id": file_id_str,
        }
        if pid:
            payload["cid"] = pid
        try:
            response = requests.post(
                "https://webapi.115.com/share/receive",
                data=payload,
                headers=self.header,
                timeout=15,
            )
            result = response.json()
        except Exception as exc:
            raise RuntimeError(f"转存失败: {concise_error(exc)}") from exc
        if not result.get("state"):
            error_msg = result.get("error", "")
            if "无需重复接收" in error_msg:
                return True
            raise RuntimeError(f"115 转存失败：{error_msg}")
        return True

    def share_link_parser(self, link: str) -> Optional[Tuple[str, str]]:
        match = re.search(
            r"https?://(115|115cdn|anxia)\.com/s/(\w+)\?password=(\w+)",
            link,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None
        return match.group(2), match.group(3)

    def save_link(self, share_item: Tuple[str, str], pid: str = "") -> Tuple[bool, str]:
        share_code, receive_code = share_item
        _, data_list = self.request_datalist(share_code, receive_code)
        if not data_list:
            return False, "分享目录为空或链接已失效"
        file_ids = [data.get("fid", data.get("cid")) for data in data_list]
        self.post_save(share_code=share_code, receive_code=receive_code, file_ids=file_ids, pid=pid)
        return True, f"转存成功（{len(file_ids)} 项）"


def transfer_115_share(cookies: str, share_url: str, target_pid) -> Tuple[bool, str]:
    """
    转存 115 分享链接到指定目录（移植自 TgtoDrive transfer_shared_link）。
    返回 (是否成功, 说明)。
    """
    try:
        fake_client = Fake115Client(cookies=cookies)
        share_item = fake_client.share_link_parser(share_url)
        if not share_item:
            return False, f"链接格式错误，应为 https://115.com/s/xxx?password=yyy 形式: {share_url}"
        return fake_client.save_link(share_item, str(target_pid))
    except Exception as exc:
        return False, concise_error(exc)


def _import_p115client():
    try:
        from p115client import P115Client
        return P115Client
    except ModuleNotFoundError as exc:
        if exc.name != "p115client":
            raise
        fail("缺少依赖: p115client，请重新运行 skill 安装器。")
    return None


def _normalize_115_item(item: dict) -> dict:
    try:
        from p115client.client import normalize_attr_simple
        return normalize_attr_simple(item)
    except Exception:
        return item


def move_115_tree(cookies: str, source_pid, target_pid) -> dict:
    """
    递归把 source_pid 下所有文件移动到 target_pid，并清理空目录。
    移植自 TgtoDrive transfer_and_clean。返回统计信息。
    """
    P115Client = _import_p115client()
    client = P115Client(cookies=cookies)
    stats = {"moved": 0, "deleted_dirs": 0, "failed": 0}

    def recursive_transfer(current_pid, depth=0):
        try:
            dir_info = client.fs_get_info(current_pid)
            dir_name = dir_info.get("name", f"目录#{current_pid}")
        except Exception:
            dir_name = f"目录#{current_pid}"
        print(f"{'  ' * depth}扫描目录: {dir_name} ({current_pid})")

        items = []
        offset = 0
        while True:
            try:
                resp = client.fs_files_app({"cid": current_pid, "limit": 1000, "offset": offset})
                check_response(resp)
                page_items = resp.get("data") or []
                items.extend(page_items)
                if len(page_items) < 1000:
                    break
                offset += 1000
            except Exception as exc:
                print(f"{'  ' * (depth + 1)}获取目录内容失败: {concise_error(exc)}")
                break

        files = [item for item in items if not _normalize_115_item(item).get("is_dir")]
        dirs = [item for item in items if _normalize_115_item(item).get("is_dir")]

        for i, file in enumerate(files, 1):
            normalized = _normalize_115_item(file)
            file_name = normalized.get("name", f"文件#{normalized.get('id')}")
            try:
                move_resp = client.fs_move_app({"ids": normalized["id"], "to_cid": target_pid}, app="android")
                check_response(move_resp)
                stats["moved"] += 1
                print(f"{'  ' * (depth + 1)}移动: {file_name} ({i}/{len(files)})")
            except Exception as exc:
                stats["failed"] += 1
                print(f"{'  ' * (depth + 1)}移动失败: {file_name} - {concise_error(exc)}")
            time.sleep(0.2)

        for directory in dirs:
            dir_id = _normalize_115_item(directory).get("id")
            if str(dir_id) == str(target_pid):
                continue
            recursive_transfer(dir_id, depth + 1)

        try:
            after = client.fs_files_app(current_pid)
            check_response(after)
            if not after.get("data") and str(current_pid) not in (str(source_pid), str(target_pid)):
                del_resp = client.fs_delete_app(current_pid)
                check_response(del_resp)
                stats["deleted_dirs"] += 1
                print(f"{'  ' * depth}删除空目录: {dir_name} ({current_pid})")
                time.sleep(1)
        except Exception:
            pass

    recursive_transfer(source_pid)
    client.close()
    return stats


def clean_115_folders(cookies: str, target_pids: str, trash_password=0) -> dict:
    """
    清空指定 115 目录内容并清空回收站。target_pids 为逗号分隔的目录 ID。
    移植自 TgtoDrive clean_task。返回统计信息。
    """
    P115Client = _import_p115client()
    client = P115Client(cookies=cookies)
    stats = {"deleted": 0}

    pids = [pid.strip() for pid in str(target_pids).split(",") if pid.strip()]
    if not pids:
        raise RuntimeError("未提供有效的目标目录 ID")

    for cid in pids:
        offset = 0
        limit = 100
        while True:
            try:
                resp = client.fs_files_app({"cid": cid, "limit": limit, "offset": offset, "show_dir": 1})
                check_response(resp)
                contents = resp.get("data") or []
                if not contents:
                    print(f"文件夹 {cid} 无内容，清理完成")
                    break
                for item in contents:
                    normalized = _normalize_115_item(item)
                    item_id = normalized.get("id")
                    item_name = normalized.get("name", "未知名称")
                    if not item_id:
                        continue
                    try:
                        client.fs_delete_app(item_id)
                        stats["deleted"] += 1
                        print(f"删除: {item_name} (ID: {item_id})")
                        time.sleep(0.5)
                    except Exception as exc:
                        print(f"删除 {item_name} 失败: {concise_error(exc)}")
                if len(contents) < limit:
                    break
                offset += limit
            except Exception as exc:
                print(f"获取文件夹 {cid} 内容失败: {concise_error(exc)}")
                break

    print("开始清空回收站...")
    try:
        client.recyclebin_clean(password=trash_password)
        print("回收站清空完成")
    except Exception as exc:
        print(f"清空回收站失败: {concise_error(exc)}")
    client.close()
    return stats


# ============================ Telegram 频道监控 ============================

TG_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
]


def extract_115_share_urls(text: str) -> List[str]:
    pattern = r"https?://(?:115|115cdn|anxia)\.com/s/\w+\?password=\w+"
    return list(dict.fromkeys(re.findall(pattern, text, re.IGNORECASE | re.DOTALL)))


def extract_123_share_urls(text: str) -> List[str]:
    pattern = r"https?://www\.123(?:\d+|pan)\.\w+/s/[\w-]+(?:\?pwd=\w+|(?:\s*提取码\s*[:：]\s*\w+))?"
    return list(dict.fromkeys(re.findall(pattern, text, re.IGNORECASE | re.DOTALL)))


def scan_telegram_channel(channel_url: str, limit: int = 20, timeout: int = 15) -> List[dict]:
    """
    单次扫描 Telegram 公开频道（t.me/s/ 网页版），返回最新消息列表。
    每条消息: {id, date, url, text, links: {115: [...], 123: [...]}}
    移植自 TgtoDrive get_latest_messages。
    """
    if channel_url.startswith("https://t.me/") and "/s/" not in channel_url:
        channel_name = channel_url.split("https://t.me/")[-1]
        channel_url = f"https://t.me/s/{channel_name}"

    session = requests.Session()
    headers = {"User-Agent": TG_USER_AGENTS[int(time.time()) % len(TG_USER_AGENTS)]}
    response = session.get(channel_url, headers=headers, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    message_divs = soup.find_all("div", class_="tgme_widget_message")
    if not message_divs:
        return []

    messages = []
    for msg in message_divs[-limit:]:
        data_post = msg.get("data-post", "")
        message_id = data_post.split("/")[-1] if data_post else "?"
        time_elem = msg.find("time")
        date_str = time_elem.get("datetime") if time_elem else ""
        link_elem = msg.find("a", class_="tgme_widget_message_date")
        message_url = link_elem.get("href", "").lstrip("/") if link_elem else ""
        text_elem = msg.find("div", class_="tgme_widget_message_text")
        text = text_elem.get_text(" ", strip=True) if text_elem else ""
        messages.append({
            "id": message_id,
            "date": date_str,
            "url": message_url,
            "text": text,
            "links": {
                "115": extract_115_share_urls(text),
                "123": extract_123_share_urls(text),
            },
        })
    return messages


# ============================ TMDB 识别（移植自 TgtoDrive share.py） ============================

TV_KEYWORDS = {
    "patterns": [
        r"S\d{1,3}E\d{1,3}",
        r"[Ee][Pp]?\d{1,3}",
        r"第[0-9一二三四五六七八九十]+集",
        r"[第].[季]",
    ],
    "folder_keywords": ["season", "seasons", "季", "多季", "第.季", r"\bs\d\b"],
}


class TMDBHelper:
    """TMDB 影视识别（移植自 TgtoDrive share.py）。"""

    def __init__(self, api_key: str):
        if not api_key:
            fail("缺少 TMDB API Key，请设置环境变量 ENV_TMDB_API_KEY 或使用 --api-key 参数")
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"
        self.session = requests.Session()

    def _request(self, path: str, params: dict) -> dict:
        params = {**params, "api_key": self.api_key}
        response = self.session.get(f"{self.base_url}{path}", params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    def parse_metadata(self, folder_name: str) -> dict:
        """从文件夹名中提取 title / year / tmdb_id。"""
        tmdb_id_pattern = r"[{\[](?:tmdb(?:id)?)(?:=|-)(\d+)[}\]]"
        tmdb_match = re.search(tmdb_id_pattern, folder_name)
        tmdb_id = tmdb_match.group(1) if tmdb_match else None

        cleaned = folder_name.replace("（", "(").replace("）", ")")
        cleaned = re.sub(r"[\s\-_]+", " ", cleaned).strip()
        cleaned = re.sub(r"\[.*?\]|\{.*?\}", "", cleaned).strip()
        format_patterns = [
            r"\d{3,4}p", r"\d{3,4}i", r"HD", r"4K", r"8K", r"WEB[-_.]?DL", r"BD[-_.]?REMUX",
            r"BD[-_.]?RIP", r"DVDRIP", r"CAM", r"HDTV", r"Blu[-_.]?ray",
            r"x264", r"x265", r"H\.264", r"H\.265", r"DDP\d+\.\d+", r"AC3", r"DTS", r"FLAC",
        ]
        for pattern in format_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        if tmdb_match:
            cleaned = re.sub(re.escape(tmdb_match.group(0)), "", cleaned).strip()

        title = None
        year = None
        try:
            import guessit
            guess = guessit.guessit(cleaned)
            title = guess.get("title")
            year = guess.get("year")
        except Exception:
            pass

        if not title:
            match = re.match(r"(.+?)[^\d]*(?:\b(\d{4})\b)?.*", cleaned.strip())
            if match and match.group(1):
                title = match.group(1).strip()
            if not year and match and match.group(2):
                year = match.group(2)

        if not title and not tmdb_id:
            return {}
        return {"title": title, "year": year, "tmdb_id": tmdb_id}

    def _get_by_id(self, tmdb_id, media_type: str) -> dict:
        try:
            data = self._request(f"/{media_type}/{tmdb_id}", {"language": "zh-CN"})
            return self._compact(data, media_type)
        except Exception:
            return {}

    def _search(self, title, year, media_type: str) -> dict:
        params = {"query": title, "language": "zh-CN", "page": 1}
        if year:
            params["year"] = year
        try:
            data = self._request(f"/search/{media_type}", params)
            results = data.get("results") or []
            if not results:
                return {}
            return self._compact(results[0], media_type)
        except Exception:
            return {}

    def _compact(self, data: dict, media_type: str) -> dict:
        return {
            "media_type": media_type,
            "tmdb_id": data.get("id"),
            "title": data.get("title") or data.get("name"),
            "original_title": data.get("original_title") or data.get("original_name"),
            "year": (data.get("release_date") or data.get("first_air_date") or "")[:4],
            "overview": data.get("overview", ""),
            "poster_path": data.get("poster_path", ""),
            "vote_average": data.get("vote_average"),
        }

    def identify(self, folder_name: str, file_name: str = "") -> dict:
        """识别影视信息。根据文件名/文件夹名判断剧集或电影，返回 TMDB 元数据。"""
        is_tv = False
        for pattern in TV_KEYWORDS["patterns"]:
            if re.search(pattern, file_name):
                is_tv = True
                break
        if not is_tv:
            for keyword in TV_KEYWORDS["folder_keywords"]:
                if re.search(keyword, folder_name, re.IGNORECASE):
                    is_tv = True
                    break
        media_type = "tv" if is_tv else "movie"
        parsed = self.parse_metadata(folder_name)
        if not parsed.get("title") and not parsed.get("tmdb_id"):
            return {"error": "无法从名称中解析出标题", "parsed": parsed}

        if parsed.get("tmdb_id"):
            actual_media_type = "tv" if media_type == "anime" else media_type
            metadata = self._get_by_id(parsed["tmdb_id"], actual_media_type)
            if metadata:
                return metadata
        metadata = self._search(parsed["title"], parsed.get("year"), media_type)
        return metadata
