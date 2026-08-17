# agents/

本目录提供 OpenAI Agent SDK 兼容的 agent 清单（`openai.yaml`）。

`openai.yaml` 声明了 skill 的显示名称、简短描述、默认提示词和隐式调用策略：

- `display_name`: Netdisk (115/123)
- `short_description`: Scan login, browse/transfer/search files, offline downloads on 115 and 123 netdisks
- `default_prompt`: 让 agent 在需要网盘操作时自动使用本 skill
- `allow_implicit_invocation: true`：允许用户未显式点名时按描述触发

Codex 等 agent 会读取 `SKILL.md` 的 frontmatter `description` 作为主要触发条件。
