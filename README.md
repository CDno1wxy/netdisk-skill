# Netdisk Skill（115 网盘自动化）

这是一个面向 Codex、OpenAI Codex CLI 及其他 AI Agent 的 115 网盘自动化 Skill，不是面向普通用户的独立网盘客户端。Agent 可通过本仓库的 `SKILL.md` 和脚本执行登录、离线下载、分享转存、目录整理及 TMDB 媒体识别。

本项目合并自两个项目：

- [chongchong59699/115-netdisk-skill](https://github.com/chongchong59699/115-netdisk-skill)：115 扫码登录、cookies、浏览、搜索、离线下载
- [walkingddd/TgtoDrive](https://github.com/walkingddd/TgtoDrive)（v6.6.4）：115 分享链接转存、目录整理与清理、Telegram 频道监控、TMDB 影视识别

仓库根目录即 skill 根目录。安装时需要复制 `SKILL.md`、`scripts/`、`agents/` 和 `requirements.txt`，不要只保存单个 `SKILL.md`。

## 功能一览

| 模块 | 脚本 | 能力 |
| --- | --- | --- |
| 登录 | `login.py` / `get_cookie.ps1` / `115-cookie-helper` | 扫码登录、cookies 保存与验证 |
| 连接测试 | `test_connection.py` | 账户、空间、根目录 |
| 浏览搜索 | `browse.py` | 目录浏览、文件搜索 |
| 离线下载 | `offline_download.py` | magnet/ed2k/HTTP 任务、列表、配额 |
| 分享转存 | `transfer_share.py` | 115 分享链接转存到指定目录 |
| 目录整理 | `move_clean.py` | 递归移动文件、清理空目录、清空回收站 |
| TMDB 自动整理 | `organize.py` | 按 TMDB 匹配电影 / 剧集目录，整体移动并保留全部文件 |
| 频道监控 | `monitor.py` | 扫描 Telegram 频道中的 115 分享链接 |
| TMDB 识别 | `identify.py` | 电影 / 剧集名称识别（TMDB） |

## 安装

```bash
curl -fsSL https://raw.githubusercontent.com/<OWNER>/netdisk-skill/master/install.py | python - --repo <OWNER>/netdisk-skill --branch master
```

Windows：

```powershell
curl.exe -fsSL https://raw.githubusercontent.com/<OWNER>/netdisk-skill/master/install.py | py - --repo <OWNER>/netdisk-skill --branch master
```

安装器只依赖 Python 标准库，自动复制完整 skill 到 `${CODEX_HOME}/skills/netdisk` 或 `~/.codex/skills/netdisk`，并在 skill 目录内创建 `.venv` 安装依赖（`p115client`、`requests`、`beautifulsoup4`、`guessit`）。

## 快速开始

```bash
cd ~/.codex/skills/netdisk

# 扫码登录（输出二维码，等手机确认）
python scripts/login.py --no-open

# 测试连接 / 浏览 / 搜索
python scripts/test_connection.py
python scripts/browse.py
python scripts/browse.py --search "电影"

# 离线下载
python scripts/offline_download.py "magnet:?xt=urn:btih:xxx"
python scripts/offline_download.py --list

# 分享转存
python scripts/transfer_share.py "https://115.com/s/xxx?password=yyy" --target-pid 123456

# 频道监控
python scripts/monitor.py --channel https://t.me/s/xxx --transfer --target-pid 123456

# TMDB 识别
python scripts/identify.py --name "侠医 (2025) {tmdb-298444}" --file "侠医.S01E01.mkv"

# TMDB 自动整理（默认先演练；确认后加 --apply）
python scripts/organize.py
python scripts/organize.py --apply
```

## 凭据

- 115：`~/.115-cookies`（扫码登录自动写入）
- TMDB：`--api-key`、环境变量 `ENV_TMDB_API_KEY` 或 `~/.tmdb-api-key` 文件
- Tavily（可选）：环境变量 `TAVILY_API_KEY` 或 `~/.tavily-api-key`，用于先检索官方片名候选，再由 TMDB 按标题、年份和类型校验

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
│   ├── browse.py            # 浏览与搜索
│   ├── get_cookie.ps1       # Windows 备用扫码登录
│   ├── identify.py          # TMDB 影视识别
│   ├── lib.py               # 115 公共库（来自 115-netdisk-skill）
│   ├── login.py             # 115 扫码登录
│   ├── monitor.py           # Telegram 频道监控
│   ├── move_clean.py        # 目录整理与清理
│   ├── organize.py          # TMDB 自动整理，整体保留并移动目录内容
│   ├── netdisk.py           # 合并扩展库（转存/监控/TMDB）
│   ├── offline_download.py  # 离线下载
│   ├── save_cookies.py      # cookies 保存与验证
│   ├── test_connection.py   # 连接测试
│   └── transfer_share.py    # 分享转存
├── cmd/115-cookie-helper/   # Go 扫码登录二进制
└── .github/workflows/release.yml
```

## 免责声明

仅用于个人网盘文件管理与媒体库维护。请确保你拥有对应账号、资源和媒体内容的合法使用权，遵守所在地区法律法规与网盘服务条款。
