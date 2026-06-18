# Content Creator Pipeline — 独立包审查报告

## 一、硬伤（开箱即用会出错）

### 1. templates/ 和 starter-rubrics/ 缺失
cheat-init 大量引用：
```
cheat-on-content/starter-rubrics/<form>-zero.md   ← 不存在
cheat-on-content/templates/rubric-memo.template.md ← 不存在
cheat-on-content/templates/script_patterns.template.md  ← 不存在
cheat-on-content/templates/benchmark.template.md   ← 不存在
cheat-on-content/templates/audience.template.md    ← 不存在
```
这些模板在 `cheat-on-content/` 下有，但在 pipeline 包里不存在。
**接收方只有 pipeline 包的话，cheat-init 执行到复制步骤时会失败。**

**修复：** 把 cheat-on-content 的 templates/ + starter-rubrics/ 复制到 pipeline/skill/ 里，或者整合到 pipeline/skill/cheat-init/ 下。

### 2. adapters/perf-data/ 缺失
cheat-retro、cheat-init 引用 `cheat-on-content/adapters/perf-data/`（数据抓取 adapter）。
pipeline 包里不存在任何 adapter。

**修复：** 要么打包 adapter 子集，要么在 SKILL.md 里明确声明 adapter 是单独安装的外部依赖。

---

## 二、KK 专属痕迹（泛化后可删）

### 3. cheat-score SKILL.md 第 14-26 行
```
规则来源: 用户（奉孝大人/KK）在一次 inline 评分后质询"客观吗"...
```
这个设计决策的故事很有教育意义，但人名不应出现在通用包里。

**建议：** 改为通用表述，比如 "校准实验中发现主 agent inline 评分因上下文污染不客观，由此产生硬性规则"。

### 4. cheat-score/references/blind-scoring-workflow.md 第 3 行
```
This doc captures the exact sub-agent prompt and workflow validated in production with user 奉孝大人 (KK).
```
同理，泛化描述。

### 5. references/agents-md-summary.md 整份文件
全篇是 KK（奉孝大人）的专属 AGENTS.md 摘要——`~/cheat-content/` 路径、当前状态、已发布视频信息。

**建议：** 从 pipeline 包中删除，或替换为一个空白模板。

---

## 三、路径引用问题（依赖包路径 vs pipeline 路径）

### 6. 所有子 skill description 字段
15 个 cheat-* skill 的描述都写 "cheat-on-content 的 XXX"。在 pipeline 独立包语境下应该泛化。

### 7. cheat-init step 3 中 hack 路径
引用 `.claude/settings.json`、`.cheat-hooks/` 等 Claude Code 路径。
Hermes 环境下这些路径不适用。

建议写：通用钩子安装指导（不同 AI 框架的实现不同，让使用者在各自配置中实现）。

### 8. cheat-retro 第 101 行
`<adapters-dir>` 指向 `cheat-on-content/adapters/perf-data/`。独立包里没有。

---

## 四、SKILL.md（主文件）需要调整

### 9. 第 306-314 行 — 便携桌面包引用
```
~/Desktop/content-creator-pipeline/（21 个文件...）
~/Desktop/content-workbench/（6 个文件...）
```
这两个是 KK 桌面上的本地路径。通用包里应删掉或改为抽象说明。

### 10. 第 382-391 行 — Pitfall 4 "skill/ 目录的副本是死内容"
这个 pitfall 描述的是 cheat-on-content 和 pipeline 同时存在时的双副本冲突。
但对面只装 pipeline 包时，pipeline/skill/ 里的副本就是唯一来源，不是死内容。

**建议：** 重写为 "双环境说明"——单装 pipeline 时正常使用，若同时有 cheat-on-content 则后者优先。

---

## 五、参考文件的问题

### 11. references/dependencies.md
每个子 skill 表格中的"路径"和"来源"列引用 `creative/cheat-on-content/skills/`。
应该在表里加备注：独立安装时路径为 `creative/content-creator-pipeline/skill/<name>/`。

### 12. references/desktop-workbench.md
有用，但指向 KK 本地桌面路径。应改为通用安装指引。

---

## 六、结构缺失

### 13. 没有 install.sh
SKILL.md 第 312 行提到 `bash install.sh`，但 pipelines/skill/ 下没有。

### 14. 缺少 README.md
独立包最好有最外层的 README 说明安装方法。
