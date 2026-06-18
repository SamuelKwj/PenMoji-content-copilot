# 工作流可视化（Workflow Visualization）

> 大王要求把 cheat-content 工作流做成思维导图/流程图时的标准做法。
> 触发词：「做成思维导图」/「画个流程图」/「可视化工作流」/「画一下流程」。

---

## 双轨产出策略（默认）

大王的偏好是**同时产出两份**，一份编辑用、一份成品用：

| 轨道 | Skill | 输出 | 用途 |
|------|-------|------|------|
| 编辑底稿 | `excalidraw` | `.excalidraw` JSON | 拖到 excalidraw.com，大王自己改 |
| 成品图 | `baoyu-infographic` | PNG | 截图发圈/做封面/手机看 |

也可以单选——大王明确说"只做 X"时按要求来。

**额外 fallback**：如果只要一份纯文字的（`md` 思维导图），用 `write_file` 直接落 markdown 树状大纲到桌面，不调 skill。大王要 md 型就给纯 md，不要顺手做图。

---

## Excalidraw 思维导图布局模板

cheat-content 八阶段流程图的可复用布局：

### 画布尺寸
- 画布 ~1500×900px，节点 260×140px，间距 80px

### 节点位置（中心放射 + 横排）
```
            [s1]   [s2]   [s3]   [s4]    ← 上排：① 收录 ② 写稿 ③ 打分 ④ 预测
                                  ↓
[law]  [aux]  [core(灵感)]      [s4.5]  ← 中排：铁律 / 辅助 / 中心 / 预测后流水线
                                  ↓
            [s8]   [s7]   [s6]   [s5]    ← 下排：⑧ 校准 ⑦ 复盘 ⑥ 发布 ⑤ 拍摄
```

### 颜色编码（与铁律一致的语义）
| 阶段 | Hex | 含义 |
|------|-----|------|
| 中心节点（灵感/火花） | `#fff3bf` 黄 | 起点 |
| ①② 输入端（收录/写稿） | `#a5d8ff` 蓝 | 输入流 |
| ③④ 评估（打分/预测） | `#d0bfff` 紫 | 评估流 |
| ④.5 预测后流水线 | `#c3fae8` 青 | 辅助产出 |
| ⑤ 拍摄 | `#ffd8a8` 橙 | 中间态 |
| ⑥⑦ 发布/复盘 | `#b2f2bb` 绿 | 输出流 |
| 铁律/⑧校准 | `#ffc9c9` 红 | 警示/反馈 |

### 箭头规则
- 实线箭头：主流程（中心→①→②→③→④→④.5→⑤→⑥→⑦）
- 虚线箭头：反馈环（⑦→⑧、⑧→中心）
- 箭头都用 `startBinding` + `endBinding` 绑死到 shape，不要手算坐标

### 必坑提醒
- 文字必走 container binding（`boundElements` + `containerId`），不要用 `label` 字段——会被静默忽略
- 标准信封必须有 `type/version/source/elements/appState` 五字段
- 字体 fontSize ≥ 16，标题 ≥ 20
- 文字内不要 emoji（excalidraw 字体不渲染）；用 `🔒` 这种放在 label 里要谨慎

---

## baoyu-infographic 思维导图配方

### 默认组合（大王首选）

| 维度 | 选 | 理由 |
|------|-----|------|
| Layout | `tree-branching` | 中心放射，思维导图原型 |
| Style | `morandi-journal` | 暖色手绘+笔记本质感，符合"汉语美感+人味" |
| Aspect | `portrait` | 长图利于手机看 |

### 备选组合

| 用途 | Layout + Style |
|------|---------------|
| 高密度全流程总览 | `dense-modules` + `morandi-journal` |
| 教学讲解 | `hub-spoke` + `hand-drawn-edu` |
| 强结构对比 | `bento-grid` + `craft-handmade`（默认） |
| 暗色科技感（不推荐给大王） | `tree-branching` + `cyberpunk-neon` |

### Prompt 关键词（思维导图特化）

写 image_generate prompt 时，必含以下要素：

1. 明确 layout：`tree-branching layout` / `hub-spoke radial`
2. 明确风格：`morandi-journal style` + `warm Morandi tones (sage green, dusty pink, muted ochre)`
3. 中心节点：`CENTER ROOT NODE` 单独描述
4. 分支节点：每个分支单列一行，含 emoji 序号 + 标题 + 1-2 句子说明
5. 旁注：`small Chinese handwritten notes` 增加人味
6. 视觉细节：`washi tape decorations`、`subtle paper texture`、`Chinese handwritten font feel`
7. 收尾铁律：`high information density, all text crisp and legible`

---

## 文件落盘规则

| 类型 | 路径 |
|------|------|
| md 大纲 | `桌面/<主题>工作流思维导图.md` |
| Excalidraw | `桌面/<主题>工作流.excalidraw` |
| 成品 PNG | image_generate 默认缓存路径，向大王报路径 |

**注意**：大王在 CLI 看回复，不要用 MEDIA: 标签（CLI 不识别），直接打印绝对路径即可。

---

## 检查清单（落盘前）

- [ ] 内容来自 AGENTS.md / 实际目录，不是凭记忆编
- [ ] 每个阶段含：触发词、流程、输出文件、铁律（如适用）
- [ ] 八阶段闭环箭头正确（包括反馈环 ⑦→⑧→中心）
- [ ] 四大铁律单独成块
- [ ] 当前状态/已发布作品有真实数据填充
- [ ] 内容三部曲（能力错觉→知识平权幻觉→AI 时代什么最值钱）作为彩蛋单列
