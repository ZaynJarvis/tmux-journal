# tmux-journal

> 自动捕获 tmux 会话记录，AI 生成结构化工作总结

我的工作和上下文几乎全部发生在 terminal 里。tmux-journal 利用 tmux 的 Enter 键 hook，静默捕获每一条命令和输出，再通过 LLM 将这些交互沉淀成结构化知识——最终可以流入 [OpenViking](https://openviking.com) 这类 context 管理工具中。

零侵入，零手动记录。

## 原理

我的 terminal 工作流全链路：

```
Ghostty（终端）
  └── tmux-start.sh → 每个窗口自动进入 tmux session
        └── 每个 pane ← Enter 键触发 capture.sh
              └── capture.sh → 按 pane 记录命令 + 输出
                    └── summarize.py → AI 结构化总结
                          └── → OpenViking / 其他 context 工具
```

因为所有操作都在 tmux 里，Enter 键 hook 天然覆盖 100% 的 terminal 交互——不需要 shell 插件，不改变任何使用习惯。

详细的本地环境配置（Ghostty / tmux / tmux-start.sh）见 [ENV_CONF.md](./ENV_CONF.md)。

## 核心机制

- 挂载 tmux Enter 键，每次执行命令后捕获当前 pane
- 5 秒防抖 + 内容去重，避免噪音
- 按 pane 存储日志（`pane_%0.log`, `pane_%1.log`, …），自动轮转（5 MB → 1 MB）
- 每 10 次捕获，后台触发一次 LLM 总结 → `summary.log`

## 环境要求

- macOS 或 Linux
- tmux ≥ 2.6
- Python ≥ 3.11
- uv（推荐）或 pip

## 安装

```bash
git clone https://github.com/ZaynJarvis/tmux-journal
cd tmux-journal
uv venv && uv pip install -e .
./install.sh
```

重载 tmux 配置：`tmux source-file ~/.tmux.conf`

本地环境配置参考 [ENV_CONF.md](./ENV_CONF.md)。

## LLM 配置

运行配置向导：
```bash
python summarize.py --setup
```

或直接设置环境变量（自动识别）：
```bash
# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# OpenAI
export OPENAI_API_KEY=sk-...

# 任意 OpenAI 兼容接口
export TERMINAL_LOGGER_API_URL=https://your-endpoint/v1/chat/completions
export TERMINAL_LOGGER_API_KEY=your-key
```

配置文件保存在 `~/.config/terminal-logger/config.json`：

```json
{
  "api_url": "https://api.anthropic.com/v1/messages",
  "api_key_env": "ANTHROPIC_API_KEY",
  "model": "claude-haiku-4-5-20251001",
  "provider": "anthropic"
}
```

## 命令

| 命令 | 说明 |
|------|------|
| `./install.sh` | 安装 tmux hook |
| `./uninstall.sh` | 移除 tmux hook |
| `./watch.sh` | 实时查看日志（分屏） |
| `python summarize.py` | 立即运行总结 |
| `python summarize.py --since 1h` | 总结最近 1 小时 |
| `python summarize.py --setup` | 配置 LLM |

## 日志文件

| 文件 | 内容 |
|------|------|
| `debug.log` | 所有捕获的 pane 快照 |
| `pane_%N.log` | 按 pane 的历史记录 |
| `summary.log` | 最新 AI 总结 |

## 输出格式

LLM 生成三个部分：
- **Key Insights** — 工作模式、习惯、痛点
- **Suggestions** — 具体可执行的改进建议
- **Task / Event Summary** — 按时间或主题归类的活动记录

## 卸载

```bash
./uninstall.sh
rm -rf ~/.config/terminal-logger
```

## 相关文件

- [ENV_CONF.md](./ENV_CONF.md) — 完整本地环境配置（Ghostty / tmux / session picker）
- [README_EN.md](./README_EN.md) — English version

## License

MIT
