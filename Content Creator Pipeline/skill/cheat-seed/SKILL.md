---
name: cheat-seed
description: 跟用户对话讨论选题——**默认一次一个**，用户主动给主题或经历，AI 围绕用户的输入深挖、提炼角度、写一份 draft（或只出大纲+评分骨架，适用于自己写稿的用户）。不是 AI 拿三个开放问题追用户，也不是一次给 5 个候选。触发词：\"帮我挖一下\"/\"找选题\"/\"我想做一条 X\"/\"最近有个想法\"/\"seed\"。
argument-hint: '--batch N or --outline or topic'
allowed-tools: Bash(*), Read, Write, Edit, Glob, WebFetch, Skill
---

# /cheat-seed — 选题对话

## 用户触发词（用户不需要记skill名）

用户说的自然语言会自动路由到这里：

| 用户说... | 对应模式 | AI怎么做 |
|-----------|:--------:|----------|
| "帮我挖一下 [主题]" | Mode A | 深挖角度 → 出大纲+评分骨架 |
| "我想做一条关于 X 的" | Mode A | 同上 |
| "我最近 [经历]" | Mode A | 同上 |
| "最近想做点 [方向] 的" | Mode B | 单问"为什么"→ 逼出真动机 |
| "不知道做什么" | Mode C | 拉热点 + 用户挑 |
| "帮我想个题" | Mode C | 同上 |

**输出文件位置：**
- 大纲版：`scripts/<日期>_<id>_<短标题>_大纲.md`
- 完整draft版：`scripts/<日期>_<id>_<短标题>.md`

**每个输出结尾必带"下一步说什么"引导** —— 用户不需要知道下一个skill名。

cheat-seed 的核心是**跟用户讨论选题**，不是机械地 brainstorm。好内容来自用户的真实经历 + 观察 + 情绪——这些是 AI 不可能凭空 brainstorm 出来的。AI 的角色是**听用户讲 → 帮提炼角度 → 写一份 deliverable**（可能是大纲或draft），不是 dump 15 候选让用户挑。

**默认模式**：对话式一次一个。用户主动给主题则深挖 → 出大纲（不写完整稿——除非用户要求）。
**Batch 模式**（`--batch N`）：旧的 brainstorm N 候选 + 写 N 份 draft 流程。

## 三种 Mode（自动识别）

```
Mode A — 用户主动给主题（最常见）：
  用户说"帮我挖一下 X" 或 "我想做一条关于 X 的"
  ↓
  AI 围绕 X 深挖——什么瞬间触发？最让你在意的点是？
  ↓
  收敛到一个具体角度 → 提议 → 用户认可 → 输出大纲 → 完成
  ↓
  问"下一篇？" 或用户说"今天就这样"

Mode B — 用户给方向但不具体：
  用户："最近想做点关于 [职场 / 婚恋 / AI / ...] 的"
  ↓
  AI：只问一次"为什么想做这个方向？"
  ↓
  有具体经历 → 转 Mode A；没有 → 转 Mode C

Mode C — 用户完全没想法：
  用户："不知道做什么"
  ↓
  AI：拉热点 + 用户挑 → 回到内省 → 转 Mode A

Batch Mode — 用户显式要批量（--batch N）：
  3 问题 → 15 候选 → 用户挑 N → 写 N 份 draft
```

**关键纠正**：AI 不主动开放问——等用户给输入再深挖。一次一个选题，不是 5 个。

## 输出模式（核心新增）

本 skill 支持两种输出模式，自动识别用户偏好：

| 输出模式 | 产出 | 适合 |
|:--------:|:----|:----|
| **大纲版**（默认） | outline + 评分骨架 + 录制提示 | 自己写稿的创作者——只给脚手架 |
| **draft版** | 完整散文稿 | 希望AI写完整稿的用户 |

**识别规则：**
- 用户说"我自己写" / 拒绝AI写的稿 / 明确说你写的稿不行 → **立刻切换到大纲版**
- 用户说"帮我写出来" / "写一份完整稿" → draft版
- 未明确 → 先问"要大纲+评分骨架还是完整稿？"
- 有历史记录的（用户profile或memory标了"自己写稿"）→ 默认大纲版，不问

**大纲版输出格式：**

```markdown
# [标题] — 大纲 + 评分骨架

**钩子（前5秒）：** [一句反常识断言]

**第一段：现象** [一句话]
**第二段：反转（核心）** [一句话] → 个人经历锚点提示
**第三段：升级** [一句话]
**收尾：** [MVP句方向]

## 评分骨架

| 维度 | 当前 | 可冲到 | 怎么冲 |
|:----|:---:|:-----:|:--------|
| ER共鸣 | N | N+1 | [具体建议] |
| HP钩子 | N | N+1 | [具体建议] |
| ... | ... | ... | ... |

**composite预估：** (ER+HP+...)/7×2 = X.X

## 录制提示
- 2-3条关于节奏、语气、表达的提示
```

**draft版输出格式：** 沿用原有的段落版 draft 格式（含"必须改写"警告）。

## Constants

- **DEFAULT_TREND_SOURCES = ["manual-paste"]**
- **MODE_B_MAX_REPROBE_TURNS = 2**
- **MAX_DEEP_DIVE_TURNS = 4**
- **OUTPUT_MODE = auto** — auto（根据用户自动选）/ outline / draft
- **DRAFT_LENGTH** — 派生自 typical_duration_seconds

## Inputs

| 必填 | 来源 |
|---|---|
| `.cheat-state.json` | 读 calibration_samples / typical_duration / cadence |
| `rubric_notes.md` | 读当前 rubric |
| `script_patterns.md` | 写 draft 时按 cheat sheet 选结构 |
| `predictions/*.md`（如有） | 历史 context |
| `audience.md`（如有） | 受众画像 |

## Workflow

### Phase 0: 前置检查 + 加载 context

1. 读 `.cheat-state.json` → 不存在则提示先跑 `/cheat-init`
2. 读 `rubric_notes.md` + `script_patterns.md`
3. 读已有 prediction 文件和 benchmark.md（如存在）
4. 读 `audience.md`（如存在）作为受众镜子
5. 检查用户的入参，决定 Mode

### Phase 1: Mode 分流

**含具体名词 + 情绪/经历词** → **Mode A**
**含方向词但无具体内容** → **Mode B**
**"不知道做什么"** → **Mode C**
**显式 `--batch N`** → **Batch Mode**

### Phase 2A: Mode A 深挖

围绕用户给的内容深挖，不要切到别的。

**反问类型（一次只问 1 个，最多 4 轮）：**
- 触发瞬间："最初是哪个具体瞬间触发你想做的？"
- 情绪锚点："这里面最让你觉得有意思的是哪个细节？"
- 角度选择："你想说的是现象批判、自我反思、还是泛化到普遍？"
- 受众想象："你说给哪种人听？"
- 反对意见探测："如果有人反驳，你怎么回？"

**收敛输出：**

```
我感觉这个角度能做：

[一句话立意]

走法：
- 钩子：[具体场景]
- 主体：[3个观察]
- 收尾：[MVP句]

粗打分：ER=X HP=X ... → composite≈X.X

要出大纲还是写完整稿？
```

### Phase 2B: Mode B — 单问"为什么"

只问一个问题："为什么想做这个主题？"

| 用户答 | 分流 |
|---|---|
| 含具体经历 | 转 Mode A |
| 抽象热度归因 | 反问"你自己最有感觉的角度是啥？" → 继续空则转 Mode C |
| "不知道" | 转 Mode C |

### Phase 2C: Mode C — 外部素材

拉外部素材 + 用户挑 + 回到内省。

### Phase 2D: Batch Mode

旧的批量 brainstorm 流程。

### Phase 3: 落候选池

写入 candidates.md，标 tier1 + deep_read。

### Phase 4: 输出 deliverable

**OUTPUT_MODE=outline** 时：
- 写 `scripts/<日期>_<id>_<短标题>_大纲.md`
- 格式：大纲 + 评分骨架 + 录制提示
- 不写完整散文稿

**OUTPUT_MODE=draft** 时：
- 写 `scripts/<日期>_<id>_<短标题>.md`
- 走原有的段落版格式 + humanizer

### Phase 5: 输出"下一步"引导

**大纲版输出后：**

```
✅ 大纲已写到：scripts/<...>_大纲.md

接下来你可以：
1. 在这个文件里直接改写填充 → 写成完整稿
2. 写完后跟我说"打分这篇 scripts/<...>.md" → 我调cheat-score盲打分
3. 决定要发了 → "启动预测 scripts/<...>.md"

上一篇你想做什么？
```

**draft版输出后：**

```
✅ Draft已写到：scripts/<...>.md

接下来你可以：
1. 改写这份draft——加你的语气、经历、真实金句
2. 改完跑"打分这篇 scripts/<...>.md"
3. 决定要发 → "启动预测 scripts/<...>.md"
```

## Key Rules

1. **AI 不主动开放问**——等用户给输入再深挖
2. **一次一个选题**
3. **反问纪律**：一次问 1 个，最多 4 轮
4. **深挖围绕用户给的话题**，不要切到别的
5. **每个输出必带"下一步说什么"引导**
6. **大纲版不下水写稿**——给出结构+骨架即可，肉让用户自己填
7. **draft 正文是段落版不是字幕格式**
8. **humanizer 只去 AI 味，不替用户改写**

## Refusals

- 「跳过深挖，直接写」 → 询问"给我一句话立意我就写"
- 「AI 替我决定 topic」 → 拒绝。AI 只呈现素材 + 问角度
- 「一次写 5 个 draft」 → 必须显式 --batch 5
- 「我懒得改写直接拍 AI draft」 → 允许但标 unmodified_ai_draft: true

## Integration

- 上游：`/cheat-init` / `/cheat-recommend` / `/cheat-status`
- 下游：`scripts/<...>.md` → 用户改写 → `/cheat-predict`
- 与 `/cheat-trends` 区别：seed 是讨论+产出大纲/draft；trends 是抓+打分
