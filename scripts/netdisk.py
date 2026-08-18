#!/usr/bin/env python3
"""
netdisk-skill 扩展操作库（115 版）。

合并自:
- 115-netdisk-skill: 115 扫码登录 / cookies / 浏览 / 搜索 / 离线下载
- TgtoDrive (v6.6.4): 115 分享链接转存、目录整理与清理、Telegram 频道监控、TMDB 影视识别

本模块不直接可执行，作为各 CLI 脚本的公共库使用。
"""

import os
import re
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

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

# ============================ 115 分享链接转存（移植自 TgtoDrive） ============================

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


def __check_response(resp):
    """Lazily import p115client's check_response and delegate."""
    from p115client.client import check_response
    return _check_response(resp)


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
                _check_response(resp)
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
                _check_response(resp)
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


def scan_telegram_channel(channel_url: str, limit: int = 20, timeout: int = 15) -> List[dict]:
    """
    单次扫描 Telegram 公开频道（t.me/s/ 网页版），返回最新消息列表。
    每条消息: {id, date, url, text, links: [...]}
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
            "links": extract_115_share_urls(text),
        })
    return messages


# ============================ TMDB 识别（移植自 TgtoDrive share.py） ============================

TV_KEYWORDS = {
    "patterns": [
        r"S\d{1,3}E\d{1,3}",
        r"\bS\d{1,3}\b",
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
            fail("缺少 TMDB API Key，请设置 --api-key、环境变量 ENV_TMDB_API_KEY 或 ~/.tmdb-api-key 文件")
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

        original_name = folder_name
        cleaned = folder_name.replace("（", "(").replace("）", ")")
        cleaned = re.sub(r"^(?:【[^】]*】|\[[^\]]*\])+\s*", "", cleaned)
        title_source = re.split(r"[\[【.]", cleaned, maxsplit=1)[0].strip(" ._-")
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
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", original_name)
        year = year_match.group(1) if year_match else None
        if any("\u4e00" <= char <= "\u9fff" for char in title_source) and len(title_source) >= 2:
            title = title_source
        try:
            import guessit
            guess = guessit.guessit(cleaned)
            title = title or guess.get("title")
            year = year or guess.get("year")
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
        genres = data.get("genres") or []
        genre_ids = data.get("genre_ids") or [item.get("id") for item in genres if isinstance(item, dict)]
        return {
            "media_type": media_type,
            "tmdb_id": data.get("id"),
            "title": data.get("title") or data.get("name"),
            "original_title": data.get("original_title") or data.get("original_name"),
            "year": (data.get("release_date") or data.get("first_air_date") or "")[:4],
            "overview": data.get("overview", ""),
            "poster_path": data.get("poster_path", ""),
            "vote_average": data.get("vote_average"),
            "genre_ids": [int(item) for item in genre_ids if str(item).isdigit()],
        }

    def identify(self, folder_name: str, file_name: str = "") -> dict:
        """识别影视信息。根据文件名/文件夹名判断剧集或电影，返回 TMDB 元数据。"""
        is_tv = False
        for pattern in TV_KEYWORDS["patterns"]:
            if re.search(pattern, file_name) or re.search(pattern, folder_name, re.IGNORECASE):
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
