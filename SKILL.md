---
name: netdisk
description: 115 网盘集成，合并自 115-netdisk-skill 与 TgtoDrive。支持 115扫码登录/115扫码登陆、二维码图片交互获取 cookies、cookies 保存与验证、目录浏览、文件搜索、分享链接转存、离线下载任务、Telegram 频道监控、目录整理清理、TMDB 影视识别。使用 p115client SDK，基于 cookies 认证。Use when the user asks about 115网盘, 115云盘, 115扫码登录, 115扫码登陆, 115离线下载, 115分享转存, p115client, 115 pan, or 115 netdisk operations.
---

# 115 网盘集成（115-netdisk-skill + TgtoDrive 合并版）

本 skill 合并了两个项目的能力：

- **115-netdisk-skill**：115 App 扫码登录、cookies 保存与验证、目录浏览、文件搜索、离线下载任务
- **TgtoDrive (v6.6.4)**：115 分享链接转存、目录整理与清理、Telegram 频道监控、TMDB 影视识别

## 安装本 Skill

必须安装完整 skill 文件集（`SKILL.md`、`scripts/`、`agents/`、`requirements.txt`），不要只保存 `SKILL.md`。本仓库采用“仓库根目录即 skill 根目录”的结构。

推荐使用安装器（只依赖 Python 标准库，会自动下载 GitHub zip、复制完整 skill 并在 skill 目录内创建 `.venv` 安装依赖；Python 低于 3.12 时会尝试用 `uv` 拉起）：

```bash
curl -fsSL https://raw.githubusercontent.com/<OWNER>/netdisk-skill/master/install.py | python - --repo <OWNER>/netdisk-skill --branch master
```

Windows 如果 `python` 不在 PATH：

```powershell
curl.exe -fsSL https://raw.githubusercontent.com/<OWNER>/netdisk-skill/master/install.py | py - --repo <OWNER>/netdisk-skill --branch master
```

手工安装（Windows PowerShell 7）：

```powershell
git clone https://github.com/<OWNER>/netdisk-skill.git
$targetSkill = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME "skills\netdisk" } else { Join-Path $HOME ".codex\skills\netdisk" }
if (Test-Path -LiteralPath $targetSkill) { Remove-Item -LiteralPath $targetSkill -Recurse -Force }
Copy-Item -LiteralPath ".\netdisk-skill\SKILL.md" -Destination $targetSkill -Force
Copy-Item -LiteralPath ".\netdisk-skill\requirements.txt" -Destination $targetSkill -Force
Copy-Item -LiteralPath ".\netdisk-skill\agents" -Destination $targetSkill -Recurse -Force
Copy-Item -LiteralPath ".\netdisk-skill\scripts" -Destination $targetSkill -Recurse -Force
```

## 运行要求

- 需要 Python 3.12+ 和 `p115client`；扫码登录脚本 `login.py --no-open` 只依赖标准库。
- Windows 备用扫码登录：`scripts/get_cookie.ps1`（PowerShell 7）或 GitHub Releases 中的 `115-cookie-helper-*` 独立二进制。
- 频道监控：需要服务器/本机可访问 Telegram（`t.me/s/` 网页版）。
- TMDB 识别：需要 TMDB API Key（`--api-key`、环境变量 `ENV_TMDB_API_KEY` 或 `~/.tmdb-api-key` 文件）。

## 凭据配置

### 115：扫码登录（推荐）

```bash
python scripts/login.py --no-open
```

脚本会生成二维码 PNG 并输出 `LOGIN_QR_JSON` / `QR_IMAGE_PATH` / `QR_FILE_URI` / `QR_REMOTE_URL` / `QR_MARKDOWN` 标记，等待用户用 115 App 扫码确认，cookies 保存到 `~/.115-cookies`。

agent 看到 `AGENT_ACTION_REQUIRED` 或二维码标记后，必须立即把二维码图片发给用户（Codex 桌面端用绝对路径 Markdown），并继续轮询直到登录成功或失败。

### 115：手动 cookies

```bash
printf '%s' 'UID=xxx; CID=xxx; SEID=xxx; KID=xxx' | python3 scripts/save_cookies.py --stdin
python3 scripts/save_cookies.py --test
```

## 功能与用法

所有命令在安装后的 skill 目录下运行（`cd ~/.codex/skills/netdisk`）。

### 连接与浏览

```bash
python scripts/test_connection.py             # 账户/空间/根目录
python scripts/browse.py                       # 根目录
python scripts/browse.py <目录ID>              # 指定目录
python scripts/browse.py --search 关键词       # 搜索
```

### 离线下载

```bash
python scripts/offline_download.py 'magnet:?xt=urn:btih:xxx'   # 磁力
python scripts/offline_download.py 'ed2k://|file|xxx'          # ed2k
python scripts/offline_download.py 'https://example.com/a.zip' # HTTP
python scripts/offline_download.py --list                      # 任务列表
python scripts/offline_download.py --quota                     # 配额
python scripts/offline_download.py --path                      # 下载目录
```

### 分享链接转存

```bash
python scripts/transfer_share.py 'https://115.com/s/xxx?password=yyy' --target-pid <目录ID>
```

### 目录整理与清理

```bash
python scripts/move_clean.py --source-pid <源目录ID> --target-pid <目标目录ID>  # 递归移动+清空目录
python scripts/move_clean.py --clean-pids <ID1,ID2> [--trash-password 0]         # 清空目录+回收站
```

### TMDB 自动整理

扫描默认的 `云下载` 和 `转存`，先用目录名、失败后再用实际视频文件名调用 TMDB，按 `整理/电影`、`整理/剧集`、`整理/动漫`、`整理/纪录片` 下的 `{tmdb-ID}` 目录匹配。默认只演练，确认结果后加 `--apply` 执行；会把影视目录内的视频、字幕、NFO、图片等内容移动到目标目录，并清理空目录及带“发布页、更多无水印、更多高清、访问 www、网站宣传”等标记的垃圾文件（包括伪装成 `.mkv/.mp4` 的宣传文件）。未识别或未找到对应目录的项目会保留原位。

```bash
python scripts/organize.py
python scripts/organize.py --apply
```

### Telegram 频道监控

```bash
python scripts/monitor.py --channel https://t.me/s/资源频道        # 只扫描列出链接
python scripts/monitor.py --channel https://t.me/s/资源频道 --transfer --target-pid <目录ID>
```

### TMDB 影视识别

```bash
python scripts/identify.py --name "侠医 (2025) {tmdb-298444}" --file "侠医.S01E01.mkv"
python scripts/identify.py --name "The Boys Season 2" --api-key <TMDB_KEY>
```

## Agent 兼容约定

扫码登录脚本兼容 Codex、OpenClaw、Hermes 和普通 CLI agent，同时输出多种标记：

- `LOGIN_QR_JSON`：紧凑 JSON（image_path / image_uri / remote_url / markdown）
- `QR_IMAGE_PATH`：二维码 PNG 本地路径
- `QR_FILE_URI`：`file://` URI
- `QR_REMOTE_URL`：二维码远程图片 URL
- `QR_MARKDOWN`：Markdown 图片语法

Codex 执行 `login.py --no-open` 时属于长轮询任务：用短暂等待启动（如 `yield_time_ms: 1000`）读取首批输出，看到二维码标记后立即在普通聊天消息中发送本地图片 Markdown（绝对路径），例如 `![115 登录二维码](C:\...\115-login-qrcode-xxx.png)`，再继续轮询后台进程直到成功或失败。不要假设 shell 输出中的 Markdown 会自动弹图。

## 常见问题

- **cookies 失效**：重新运行 `scripts/login.py --no-open` 或 `save_cookies.py`。
- **目录整理**：源目录和目标目录不要互相嵌套，避免循环处理。
- **频道扫描无结果**：检查网络能否访问 `t.me`（可能需要代理），频道是否为公开频道。
