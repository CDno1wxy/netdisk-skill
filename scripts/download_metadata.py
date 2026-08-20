import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


def metadata_path():
    return Path.home() / ".codex" / "netdisk-download-metadata.json"


def magnet_name(url):
    query = parse_qs(urlparse(url).query)
    return unquote((query.get("dn") or [""])[0]).strip()


def fallback_metadata(url):
    raw_name = magnet_name(url)
    title = raw_name
    title = re.split(r"\[|\b(19\d{2}|20\d{2})\b|\.(?=[A-Za-z])", title, maxsplit=1)[0]
    title = re.sub(r"^\[[^]]+\]\s*", "", title).strip(" .-")
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", raw_name)
    info_hash = (parse_qs(urlparse(url).query).get("xt") or [""])[0].split(":")[-1].lower()
    return {
        "info_hash": info_hash,
        "url": url,
        "raw_name": raw_name,
        "title": title or raw_name,
        "year": years[0] if years else "",
        "updated_at": int(time.time()),
    }


def load_metadata():
    path = metadata_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_metadata(entry):
    info_hash = entry.get("info_hash")
    if not info_hash:
        return
    path = metadata_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_metadata()
    data[info_hash] = entry
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def metadata_matches_name(entry, name):
    name_key = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", name.lower())
    keys = [entry.get("raw_name", ""), entry.get("title", ""), entry.get("original_title", "")]
    for value in keys:
        value_key = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.lower())
        if value_key and (value_key in name_key or name_key in value_key):
            return True
    return False
