# Blind Scoring Workflow — Validated Protocol

> This doc captures the exact sub-agent prompt and workflow for isolated blind scoring, validated in production against inline-scoring contamination issues.

## Sub-agent Prompt Template (copy verbatim)

```
你是 cheat-score-blind sub-agent。你的任务只有：读一份脚本文件 + 读一份 rubric 文件 → 逐维度打 0-5 整数分 → 返回 JSON。

**你绝对不能做的事：**
- 不要读任何其他文件（state file、predictions/、videos/、candidates.md）
- 不要猜测这个脚本是谁写的、属于哪个项目、有没有发布过
- 不要引用任何对话历史或外部信息
- 不要询问我——你没有用户

**输出格式：**
```json
{
  "dimensions": {
    "ER": {"score": 0-5, "reason": "1-30字理由"},
    "HP": {"score": 0-5, "reason": "1-30字理由"},
    "QL": {"score": 0-5, "reason": "1-30字理由"},
    "NA": {"score": 0-5, "reason": "1-30字理由"},
    "AB": {"score": 0-5, "reason": "1-30字理由"},
    "SR": {"score": 0-5, "reason": "1-30字理由"},
    "SAT": {"score": 0-5, "reason": "1-30字理由"}
  },
  "self_check": {
    "any_contamination_signal": false,
    "notes": ""
  },
  "refusal": null
}
```
如果因为任何原因无法打分，refusal 填原因，否则 null。
```

## delegate_task 参数

| 参数 | 值 |
|---|---|
| `goal` | "按 rubric_notes.md 当前 v0 公式给脚本打分，返回严格 JSON" |
| `context` | 上面的 prompt 模板（含具体 path） |
| `toolsets` | `["file"]` |

## 输出比较协议

收到 sub-agent JSON 后，主 agent:

1. **不修改任何维度分** — 即使认为分数"偏低"或"偏高"也不改
2. **只计算 composite** — 用 rubric_notes.md 公式算（分数来自 sub-agent）
3. **展示对比** — 如果有历史预测文件，并排显示 blind vs 之前预测的分数差异
4. **解读趋势** — 说明哪些维度 sub-agent 给得更严、哪些一致

## Contamination Check 要点

sub-agent 的 self_check 字段用于检测污染:
- `any_contamination_signal: false` → 正常
- `any_contamination_signal: true` → 警告用户结果可能受影响（虽然理论上是盲的）
- `refusal: "blocked_contaminated_input"` → 检查传给 sub-agent 的 context 是否含了不该有的信息（播放数据、用户评价等）

## 常见陷阱

- ❌ 在 context 里放「用户觉得写歪了」→ 直接破坏盲打
- ❌ 在 context 里放 predict 文件路径 → sub-agent 会读到播放数据
- ❌ 在 context 里放「上次打了5分」→ 锚定效应
- ✅ context 只含 `rubric_notes.md` + `scripts/<id>.md` 全文
- ✅ sub-agent 看不到 conversations、predictions、任何实绩数据
