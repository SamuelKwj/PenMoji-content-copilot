# Dimension Improvement Guide — Post-Score Rewrite Coaching

> When a cheat-score shows one or more dimensions dragging down composite, and the user asks "怎么改" / "how to improve", use this guide to give per-dimension rewrite suggestions with concrete before/after examples.

## Core Principle

**The user writes the draft themselves** — never rewrite the full script for them. Give targeted, concrete suggestions with example snippets that show the technique. The user integrates what works into their own voice.

Format each suggestion as:

```
**{Dimension} ({score} → target {N}) — {one-line diagnosis}**

改前: [exact quote from their draft showing the problem]
改后: [rewrite showing the technique]
```

## ER — Emotional Resonance (情感共鸣)

**Problem signals:** Draft reads analytical/rational; tells what happened but not how it felt; uses general statements without specific moments.

**Techniques:**
1. **Add a "concrete despair moment"** — one specific timestamp + sensory detail that makes the feeling undeniable
   - 改前: "我们好几天卡在bug上死循环"
   - 改后: "凌晨三点，我盯着终端里第17次同样的报错。GPT3.5给了一段它'觉得'正确的代码。我明知道它可能在瞎编，但我没有能力判断。"

2. **Replace general claims with specific scenes** — swap broad statements for a single memorable image
   - 改前: "AI平权是个伪命题"
   - 改后: "我花了两年和七个废案项目，终于成功证明了一件事——AI确实平权了，它让人人都有机会犯错，而且错得一模一样。"

3. **End with self-reflective gut-punch** — not a lesson, but a realization the reader arrives at with you
   - 改前: "不要被ai平权的虚假希望迷惑"
   - 改后: "现在回头看那几块开发板和无数个通宵，最可惜的不是钱和时间，是悲哀地发现，原来逻辑从未改变过，壁垒从未消除过。"

## HP — Hook Potential (钩子强度)

**Problem signals:** Opening is a general statement ("大家好今天我们来聊聊…"), a question ("你有没有想过…"), or lacks a specific scene.

**Techniques:**
1. **Lead with a concrete before/after contrast** — the hook is the gap between expectation and reality
   - 改前: "AI平权是个伪命题"
   - 改后: "我三个月手搓硬件demo无果，人家一个礼拜产品上线售卖。工具是一样的，差距依旧在人。"

2. **Open with a specific moment, not an abstraction** — "去年冬天我买了块开发板" beats "AI放大能力差距"
3. **One sentence that forces the viewer to pick a side** — the hook should make them think "wait, is that true?"

## QL — Quotable Lines (金句密度)

**Problem signals:** Entire draft is narrative with no standout lines; everything reads at the same intensity level.

**Techniques:**
1. **Find natural argument pivots and sharpen them into standalone sentences** — each major section should have a line that works in isolation
2. **Look for opportunity to coin a paradox or inversion** — "把'我不会做'升级成了'我不会选'" is stronger than any explanation of the same idea
3. **The closing line should be independently sharable** — not a summary, but a mic-drop

## NA — Narrativity (叙事性)

**Problem signals:** List-style structure ("first…second…third…"), essay-like exposition without a story arc, no tension/release.

**Techniques:**
1. **Use the "断言 → 个人故事 → 因果分析 → 社会升级 → 收尾" structure** — the personal story is the narrative engine
2. **Every paragraph should answer "why does this matter NOW"** — not explain, but advance
3. **Find the antagonist** — the thing the draft is arguing against (a belief, a trend, the user's past self)

## AB — Audience Breadth (受众广度)

**Problem signals:** Draft assumes domain knowledge; uses jargon or niche references without translation; only resonates if reader shares one specific experience.

**Techniques:**
1. **Translate niche examples into universal emotions** — "我焊开发板" → "你也被工具坑过" is the bridge
2. **After a technical anecdote, add a universal sentence** that reframes it for everyone
3. **Test: if the reader hasn't used ChatGPT, will they still know who this is for?**

## SR — Social Resonance (社会议题共振)

**Problem signals:** Draft is purely personal/individual; no connection to a structural pattern others can recognize; no "aha that's what I've been feeling" moment.

**Techniques:**
1. **Name the structural pattern explicitly** — "AI的谎言不是它会取代你——是'所有人在它面前都平等了'" names something people feel but can't articulate
2. **Show the systemic layer** — not just "I failed" but "here's the mechanism that makes it inevitable"
3. **End with an implication for everyone, not just the author** — move from personal → universal without leaving the personal behind

## SAT — Satire Depth (讽刺深度)

**Problem signals:** Draft is 100% sincere/earnest; no self-awareness about the irony of the situation; no structural contradiction played for effect.

**Techniques:**
1. **Self-aware framing** — acknowledge the irony of using AI to critique AI:
   - "我花了很多年，得出一个结论——AI没有让我变强。这条视频就是它帮我改的。讽刺吗？是的。但我是认真的。"

2. **Structural irony** — show the contradiction between what the tool promises vs what it delivers:
   - "AI给你一百个方案，你只是从纠结一个变成纠结一百个。这叫什么平权？这叫把'我不会做'升级成了'我不会选'。"

3. **Understated self-deprecation** — let the reader arrive at the irony, don't explain it:
   - "最贵的不是钱和时间，是我花了那么久才承认：AI让我以为我能，但其实我不能。"

4. **Note on user style** — some content forms (sincere/earnest opinion) naturally score low on SAT, and that's OK if the audience connects to authenticity. Only suggest SAT improvements when the draft topic itself has structural irony the user could exploit.

## When to Bypass

- User explicitly says "我就走真诚风" / "I don't do irony" → skip SAT suggestions entirely
- User says "我就按这个发" → stop coaching, move to predict
- The same draft has been through 3+ score-improve cycles → warn "反复改会引入决策疲劳"
