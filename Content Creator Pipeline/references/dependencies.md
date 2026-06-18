# Content Creator Pipeline — 子 Skill 依赖清单

> 本包是**整合包**，所有子 skill 以快照形式打包在 `skill/` 目录下。
> 以下清单供追踪上游来源用。新用户直接复制 `skill/` 即可，无需逐个安装。

---

## 📦 核心依赖（必须安装）

以下 8 个 skill 构成 pipeline 的最小闭环。缺失任何一个，流程无法完整执行。

### 1. cheat-seed — 选题深挖→写 draft

| 项目 | 值 |
|------|-----|
| 作用 | 跟创作者对话深挖一个具体经历/角度 → 收敛到选题 → 写 draft |
| 上游来源 | cheat-on-content 体系（Hermes skills: creative/cheat-on-content） |
| 本包路径 | `skill/cheat-seed/SKILL.md` |
| 触发词 | "我想做一条关于X的" / "seed" / "找选题" |

### 2. cheat-score — 单稿盲打分

| 项目 | 值 |
|------|-----|
| 作用 | 读稿子 + rubric → delegate 到 cheat-score-blind sub-agent → 展示 7 维分 |
| 上游来源 | cheat-on-content 体系 |
| 本包路径 | `skill/cheat-score/SKILL.md` |
| 触发词 | "打分这篇 [path]" |

### 3. cheat-score-blind — 盲打分 sub-agent

| 项目 | 值 |
|------|-----|
| 作用 | **不直接触发**。由 cheat-score/cheat-predict 通过 delegate_task 调用 |
| 上游来源 | cheat-on-content 体系 |
| 本包路径 | `skill/cheat-score-blind/SKILL.md` |
| 隔离规则 | 只读 script + rubric_notes.md，不读 predictions/ / state / 对话历史 |
| ⚠️ | 这是 channel B（隔离打分通道），不是用户 skill |

### 4. cheat-predict — 写 immutable 预测日志

| 项目 | 值 |
|------|-----|
| 作用 | blind check → 盲打分 → 锚点对比 → bucket → 反事实 → 用户 review → immutable 落盘 |
| 上游来源 | cheat-on-content 体系 |
| 本包路径 | `skill/cheat-predict/SKILL.md` |
| 触发词 | "启动预测 [path]" |
| ⚠️ | 预测段落盘后不可修改 |

### 5. cheat-shoot — 拍摄登记

| 项目 | 值 |
|------|-----|
| 作用 | 建 video folder + 确认拍摄稿一致性 + buffer +1 |
| 上游来源 | cheat-on-content 体系 |
| 本包路径 | `skill/cheat-shoot/SKILL.md` |
| 触发词 | "拍了 [path]" |

### 6. cheat-publish — 发布登记

| 项目 | 值 |
|------|-----|
| 作用 | 在 predictions/ header 加 URL + 更新时间 → 更新 state |
| 上游来源 | cheat-on-content 体系 |
| 本包路径 | `skill/cheat-publish/SKILL.md` |
| 触发词 | "已发布 [url]" |

### 7. cheat-retro — T+N 复盘

| 项目 | 值 |
|------|-----|
| 作用 | 回收播放/评论数据 → 写复盘段 → 预测 vs 实绩 → 观察 |
| 上游来源 | cheat-on-content 体系 |
| 本包路径 | `skill/cheat-retro/SKILL.md` |
| 触发词 | "复盘 [path]" |

### 8. cheat-status — 状态看板

| 项目 | 值 |
|------|-----|
| 作用 | 显示校准进度 / 待复盘 / buffer / rubric 版本 |
| 上游来源 | cheat-on-content 体系 |
| 本包路径 | `skill/cheat-status/SKILL.md` |
| 触发词 | "状态" / "看板" / "进度" |

---

## 🧩 扩展依赖（可选安装）

以下 skill 按需安装。不装不影响核心闭环，但部分功能不可用。

### 9. cheat-bump — rubric 升级

| 项目 | 值 |
|------|-----|
| 作用 | 校准池重打分 → 调权重 → 跨模型审核 → 升级 rubric |
| 安装时机 | 累积 ≥5 篇复盘的创作者 |
| 上游来源 | cheat-on-content 体系 |
| 本包路径 | `skill/cheat-bump/SKILL.md` |
| 触发词 | "升级 rubric" / "bump" |
| ⚠️ | 跨模型审核依赖 MCP llm-chat 工具 |

### 10. cheat-persona — 受众画像

| 项目 | 值 |
|------|-----|
| 作用 | 从复盘评论数据聚类 → 写入 audience.md |
| 安装时机 | 有几篇复盘数据后 |
| 上游来源 | cheat-on-content 体系 |
| 本包路径 | `skill/cheat-persona/SKILL.md` |
| 触发词 | "更新受众画像" / "我的观众是谁" |
| ⚠️ | audience.md 含实绩信号，blind sub-agent 禁读 |

### 11. cheat-recommend — 推荐选题

| 项目 | 值 |
|------|-----|
| 作用 | 从 candidates.md 按 rubric 排序推荐 top N |
| 上游来源 | cheat-on-content 体系 |
| 本包路径 | `skill/cheat-recommend/SKILL.md` |
| 触发词 | "推荐选题" |

### 12. cheat-trends — 抓热点

| 项目 | 值 |
|------|-----|
| 作用 | 抓今日热点 → 粗打分 → 写入 candidates.md |
| 上游来源 | cheat-on-content 体系 |
| 本包路径 | `skill/cheat-trends/SKILL.md` |
| 触发词 | "抓热点" / "今天有什么可做的" |
| 前置 | trend-sources adapter 配置（需手动装） |

### 13. cheat-learn-from — 对标导入

| 项目 | 值 |
|------|-----|
| 作用 | 导入 5-10 条对标账号视频 → 拆 pattern → 写 benchmark.md |
| 上游来源 | cheat-on-content 体系 |
| 本包路径 | `skill/cheat-learn-from/SKILL.md` |
| 触发词 | "学这个账号" / "导入对标" |
| 推荐 | 冷启动用户强烈建议装 |

### 14. cheat-init — 初始化脚手架

| 项目 | 值 |
|------|-----|
| 作用 | 首次搭建项目目录、state file、rubric、hooks |
| 上游来源 | cheat-on-content 体系 |
| 本包路径 | `skill/cheat-init/SKILL.md` |
| 触发词 | "初始化" / "init" |
| ⚠️ | 已有项目不要重新 init |

### 15. cheat-migrate — 升级 schema

| 项目 | 值 |
|------|-----|
| 作用 | 升级 .cheat-state.json 到当前 schema_version |
| 上游来源 | cheat-on-content 体系 |
| 本包路径 | `skill/cheat-migrate/SKILL.md` |
| 触发词 | "迁移" / "migrate" |

---

## 🛠 辅助 skill（来自其他包）

以下 skill 非 cheat-on-content 体系，来自独立项目。

### 16. humanizer — 去 AI 味

| 项目 | 值 |
|------|-----|
| 作用 | 去掉 AI 写作 tells（em-dash 滥用 / rule of three / 空泛归因） |
| 上游来源 | 外部项目 [github.com/blader/humanizer](https://github.com/blader/humanizer) |
| 许可证 | MIT |
| 本包路径 | `skill/humanizer/SKILL.md` |
| ⚠️ | MIT 协议，不打包进 cheat-on-content |

### 17. douyin-safe-overlay — 金句卡片 / 抖音安全布局

| 项目 | 值 |
|------|-----|
| 作用 | 设计 9:16 竖屏 overlay 卡片、全屏切卡、安全区布局 |
| 上游来源 | Hermes built-in: creative/douyin-safe-overlay |
| 本包路径 | `skill/douyin-safe-overlay/SKILL.md` |
| 触发词 | "做金句卡" / "做卡片" |

### 18. dbs-hook — 短视频开头优化

| 项目 | 值 |
|------|-----|
| 作用 | 诊断前 3 秒钩子问题 + 生成优化方案 |
| 上游来源 | Hermes built-in: creative/dbs-hook |
| 本包路径 | `skill/dbs-hook/SKILL.md` |
| 触发词 | "优化开头" / "帮我改开头" |

### 19. hermes-agent-skill-authoring — 编写/修改 skill

| 项目 | 值 |
|------|-----|
| 作用 | 创建/编辑/验证 SKILL.md |
| 上游来源 | Hermes built-in: software-development/hermes-agent-skill-authoring |
| 本包路径 | ❌ 不在本包内（Hermes 系统内置 skill，不打包） |
| 何时用 | 装新 skill 或修改已有 skill 时 |

---

## ⚙️ 安装指引（给新 AI / 新用户）

### 方式 A：复制整个 pipeline 包（推荐）

1. 确保 Hermes Agent 已安装或 AI CLI 可用
2. 把 `content-creator-pipeline/` 整个文件夹复制到 `~/.hermes/skills/creative/`（Hermes）或项目目录（其他 AI）
3. 子 skill 全部在 `skill/` 目录下，开箱即用

### 方式 B：逐个安装（仅装需要的）

参考上面的每个子 skill 表格，用 AI 框架对应的方法逐个创建。

---

## 🔍 验证安装

安装完成后，运行以下检查：

```bash
# 检查核心子 skill 是否可加载
skill_view(name='cheat-score')
skill_view(name='cheat-predict')
skill_view(name='cheat-seed')

# 检查 blind sub-agent
skill_view(name='cheat-score-blind')

# 检查本 pipeline
skill_view(name='content-creator-pipeline')
```

如果都能加载成功，说明依赖完整，可以开始创作流程。
