# Content Creator Pipeline — 整合包

通配内容创作者工作流。适用于任何内容形态（观点视频 / 口播 / 长文 / 播客 / 教程等）。

完整闭环：火花 → 深挖写稿 → 盲打分 → 预测 → 拍摄 → 发布 → 复盘 → 校准升级。

---

## 快速开始

### Hermes Agent 环境

```bash
# 把整个包复制到 Hermes skill 目录
cp -r content-creator-pipeline/ ~/.hermes/skills/creative/

# 在 Hermes 对话中
/reload-skills
```

然后说 **"初始化"** 开始。

### 其他 AI CLI（Claude Code / Cline 等）

把整个文件夹复制到你的项目目录，AI 读 `AGENTS.md` + `skill/` 下的子 skill 即可工作。

### 独立桌面程序（不依赖 AI 框架）

见 `references/desktop-workbench.md`（Python + Flask 浏览器 UI）。

---

## 包结构

```
content-creator-pipeline/
├── README.md                    # ← 本文件
├── SKILL.md                     # 主 skill 定义（流程总纲）
├── AGENTS.md                    # AI 操作手册
├── references/
│   ├── dependencies.md          # 依赖来源清单
│   ├── desktop-workbench.md     # 独立桌面程序安装指引
│   └── shared-references/       # 子 skill 共用参考文档
│
├── skill/                       # 所有子 skill 快照（开箱即用）
│   ├── cheat-init/              # 首次初始化
│   │   ├── SKILL.md
│   │   ├── templates/           # 项目脚手架模板
│   │   └── starter-rubrics/     # 冷启动 rubric
│   ├── cheat-seed/              # 选题深挖→写draft
│   ├── cheat-score/             # 盲打分调度
│   ├── cheat-score-blind/       # 盲打分 sub-agent
│   ├── cheat-predict/           # immutable 预测
│   ├── cheat-shoot/             # 拍摄登记
│   ├── cheat-publish/           # 发布登记
│   ├── cheat-retro/             # T+N 复盘
│   ├── cheat-bump/              # rubric 升级
│   ├── cheat-persona/           # 受众画像
│   ├── cheat-recommend/         # 选题推荐
│   ├── cheat-trends/            # 热点抓取
│   ├── cheat-learn-from/        # 对标导入
│   ├── cheat-migrate/           # schema 迁移
│   ├── cheat-status/            # 状态看板
│   ├── humanizer/               # 去 AI 味（外部项目）
│   ├── dbs-hook/                # 开头优化（内置 skill）
│   └── douyin-safe-overlay/     # 金句卡片（内置 skill）
└── PIPELINE_AUDIT.md            # 审查记录
```

---

## 来源说明

本包是**整合包**，所有子 skill 以快照形式打包在 `skill/` 目录下。

| 体系 | 数量 | 说明 |
|------|------|------|
| cheat-on-content | 15 个 | 核心流程（cheat-* 系列） |
| github.com/blader/humanizer | 1 个 | 去 AI 味（MIT 许可） |
| Hermes built-in skills | 2 个 | douyin-safe-overlay + dbs-hook |

详情见 `references/dependencies.md`。

---

## 依赖

| 依赖 | 说明 | 必须？ |
|------|------|--------|
| LLM API Key（OpenAI 兼容） | 所有子 skill 通过 LLM 执行 | ✅ 必须 |
| Hermes Agent | 仅 Hermes 场景需要 | ❌ 可选 |
| 数据抓取 adapter | 自动回收播放/评论数据 | ❌ 可选（不装则手动粘） |

---

## License

本包为 MIT 协议。各子 skill 可能携带不同许可证（humanizer 为 MIT，详见具体文件）。