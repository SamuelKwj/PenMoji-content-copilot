# Desktop Workbench — 独立桌面程序

> content-creator-pipeline skill 的独立部署变体。
> 不依赖 Hermes Agent，填入 API Key 即可运行。

| 项目 | 路径 |
|------|------|
| 项目根 | `<你的工作台目录>/content-workbench/` |
| main.py | Flask 后端 + 所有 skill 逻辑（内嵌, ~1200 行） |
| static/index.html | 前端界面（暗色主题，左侧栏+对话区） |
| requirements.txt | 只需 flask + requests |
| run.bat | Windows 双击启动 |
| run.sh | Mac/Linux 启动 |

## 内嵌的 Skill

main.py 自带了完整 pipeline 的所有 skill 实现（不依赖外部 skill 文件）：

| Python 函数 | 对应 skill | 触发词 |
|------------|-----------|--------|
| skill_seed() | cheat-seed | "我想做一条关于X" |
| skill_score() + blind_score_script() | cheat-score + cheat-score-blind | "打分这篇 [path]" |
| skill_predict() | cheat-predict | "启动预测 [path]" |
| skill_shoot() | cheat-shoot | "拍了 [path]" |
| skill_publish() | cheat-publish | "已发布 [url]" |
| skill_cards() | douyin-safe-overlay | "做金句卡 [path]" |
| skill_trends() | cheat-trends | "抓热点" |
| skill_status() | cheat-status | "状态" |

## 侧边栏布局（从上到下）

```
状态看板 → 快速操作 → 对话管理(含删除) → API配置(折叠) → 文件路径 → 草稿列表
```

## 对话持久化

每次发消息自动保存到 ~/.content-workbench/conversations/<id>.json，服务重启不丢。侧边栏显示最近 10 条，每条带消息数和 ✕ 删除按钮。

## 创作者信息可配置

不再硬编码。用户自定义：内容形态 / 赛道 / 平台。AI 系统提示词据此自动调整。

## 与 Hermes skill 的关系

pip install -r requirements.txt
python main.py
浏览器打开 http://127.0.0.1:7870

## 与 Hermes skill 的关系

Hermes skill 版: 依赖 Hermes Agent + skill 系统, 15 个独立 SKILL.md 文件, CLI/TUI 对话
桌面工作台版: 依赖 Python 3 + pip, main.py 内嵌全部逻辑, 浏览器图形界面

## 已知问题

- 端口 7860 可能被 Hermes 或其他进程占用 → 改 port=7870
- 对话存 ~/.content-workbench/conversations/（JSON 文件，重启不丢）
- 配置存 ~/.content-workbench/config.json
