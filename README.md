# Netdisk Skill（115 / 123 网盘自动化）

给 Codex / AI agent 使用的网盘自动化 skill，合并自两个项目：

- [chongchong59699/115-netdisk-skill](https://github.com/chongchong59699/115-netdisk-skill)：115 扫码登录、cookies、浏览、搜索、离线下载
- [walkingddd/TgtoDrive](https://github.com/walkingddd/TgtoDrive)（v6.6.4）：115 / 123 分享链接转存、123 直链与分享创建、123 磁力离线、115 目录整理与清理、Telegram 频道监控、TMDB 影视识别

仓库根目录即 skill 根目录。安装时需要复制 `SKILL.md`、`scripts/`、`agents/` 和 `requirements.txt`，不要只保存单个 `SKILL.md`。

## 功能一览

| 模块 | 脚本 | 能力 |
| --- | --- | --- |
| 115 登录 | `login.py` / `get_cookie.ps1` / `115-cookie-helper` | 扫码登录、cookies 保存与验证 |
| 连接测试 | `test_connection.py` | 115 / 123 账户、空间、根目录 |
| 浏览搜索 | `browse.py` | 115 / 123 目录浏览、文件搜索 |
| 离线下载 | `offline_download.py` | 115 magnet/ed2k/HTTP，123 磁力离线 |
| 分享转存 | `transfer_share.py` | 115 / 123 分享链接转存到指定目录 |
| 123 直链 | `direct_url.py` | 123 下载直链（按 file-id 或路径） |
| 123 分享 | `share_link.py` | 创建 123 分享链接 |
| 115 整理 | `move_clean.py` | 递归移动文件、清理空目录、清空回收站 |
| 频道监控 | `monitor.py` | 扫描 Telegram 频道中的 115 / 123 分享链接 |
| TMDB 识别 | `identify.py` | 电影 / 剧集名称识别（TMDB） |

> 说明：TgtoDrive 8.x 新版的 STRM 生成、Emby 302 反代、光鸭/天翼接入只存在于 Docker 镜像中，公开仓库的 v6.6.4 快照没有这些代码，本 skill v1 未收录。

## 安装

```bash
curl -fsSL https://raw.githubusercontent.com/<OWNER>/netdisk-skill/master/install.py | python - --repo <OWNER>/netdisk-skill --branch master
```

Windows：

```powershell
curl.exe -fsSL https://raw.githubusercontent.com/<OWNER>/netdisk-skill/master/install.py | py - --repo <OWNER>/netdisk-skill --branch master
```

安装器只依赖 Python 标准库，自动复制完整 skill 到 `${CODEX_HOME}/skills/netdisk` 或 `~/.codex/skills/netdisk`，并在 skill 目录内创建 `.venv` 安装依赖（`p115client`、`p123client`、`requests`、`beautifulsoup4`、`python-dotenv`、`guessit`）。

## 快速开始

```bash
cd ~/.codex/skills/netdisk

# 115 扫码登录（输出二维码，等手机确认）
python scripts/login.py --no-open

# 123 token
python scripts/save_cookies.py --disk 123 --token <token>

# 测试连接
python scripts/test_connection.py
python scripts/test_connection.py --disk 123

# 浏览 / 搜索
python scripts/browse.py
python scripts/browse.py --search "电影"
python scripts/browse.py --disk 123

# 分享转存
python scripts/transfer_share.py "https://115.com/s/xxx?password=yyy" --target-pid 123456

# 123 直链
python scripts/direct_url.py --path "/影视/侠医/Season 1/侠医.S01E01.mkv"

# 频道监控
python scripts/monitor.py --channel https://t.me/s/xxx --transfer --target-pid 123456

# TMDB 识别
python scripts/identify.py --name "侠医 (2025) {tmdb-298444}" --file "侠医.S01E01.mkv"
```

## 凭据

- 115：`~/.115-cookies`（扫码登录自动写入）
- 123：`~/.123-token`（`save_cookies.py --disk 123` 写入，或配置 `ENV_123_CLIENT_ID` / `ENV_123_CLIENT_SECRET` 自动换取）
- TMDB：环境变量 `ENV_TMDB_API_KEY`、`--api-key` 或 `~/.tmdb-api-key` 文件（按优先级读取）

## 目录结构

```text
.
├── SKILL.md
├── install.py
├── requirements.txt
├── agents/
│   ├── README.md
│   └── openai.yaml
├── scripts/
│   ├── browse.py        # 115 / 123 浏览与搜索
│   ├── direct_url.py    # 123 下载直链
│   ├── get_cookie.ps1   # Windows 备用扫码登录
│   ├── identify.py      # TMDB 影视识别
│   ├── lib.py           # 115 公共库（来自 115-netdisk-skill）
│   ├── login.py         # 115 扫码登录
│   ├── monitor.py       # Telegram 频道监控
│   ├── move_clean.py    # 115 目录整理与清理
│   ├── netdisk.py       # 合并扩展库（123 + 115 转存/监控/TMDB）
│   ├── offline_download.py  # 115 / 123 离线下载
│   ├── save_cookies.py  # 115 cookies / 123 token
│   ├── share_link.py    # 123 分享创建
│   ├── test_connection.py
│   └── transfer_share.py    # 115 / 123 分享转存
├── cmd/115-cookie-helper/   # Go 扫码登录二进制
└── .github/workflows/release.yml
```

## 免责声明

仅用于个人网盘文件管理与媒体库维护。请确保你拥有对应账号、资源和媒体内容的合法使用权，遵守所在地区法律法规与网盘服务条款。
