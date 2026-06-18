# Hermes 环境执行指南

cheat-trends 在 Hermes Agent 中运行时，部分 adapter 的默认 fetch 机制（WebFetch）不可用。
本文档记录替代执行路径。

## 优先级原则

manual-paste 永远是第一路径——用户手动粘贴热点效率最高、最准。
外部 API 抓取仅在 manual-paste 不足时作为补充。

## 各 adapter 的执行方式

### manual-paste（兜底）

1. 用户粘贴标题/URL列表（每行一条）
2. 对每条，如果带URL → 用 terminal(browser_navigate 或 curl) 获取 snippet
3. 解析到 candidate-schema 格式
4. 不依赖任何工具，永远可用

### hackernews（公开 API，无需 key）

用 terminal(cmd) → curl 调 Algolia API：

```bash
curl -s --max-time 15 "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=15" -o /tmp/hn_trends.json
```

然后在 execute_code 或 Python 中解析 JSON：
```python
from hermes_tools import terminal
raw = terminal("cat /tmp/hn_trends.json")
import json
data = json.loads(raw['output'])
for hit in data['hits']:
    title = hit['title']
    points = hit['points']
    comments = hit['num_comments']
    url = hit.get('url', f"https://news.ycombinator.com/item?id={hit['objectID']}")
```

**注意**：pipe 到 python3 可能 exit code 49（Windows MSYS 的 curl→Python pipe 问题）。
**解决方法**：先 curl 写到文件，再用 execute_code 或分开的 terminal 调用读文件解析。

### 其他 adapter（reddit, bilibili 等）

尝试用 browser_navigate 访问公开端点，或 terminal(cmd) → curl。
如果被反爬拦截（如微博、知乎、tophub），降级到 manual-paste 让用户提供。
**不反复重试**——反爬问题用户自己决策。

## 去重检查

读 candidates.md + predictions/ 目录查重：
```python
from hermes_tools import terminal, read_file
# 或用 execute_code 里的 terminal() + search_files()
```

## 粗打分

在 execute_code 中用 inline 的 rubric 逻辑打分（7维 0-5整数，v0等权）：
composite = (ER+HP+QL+NA+AB+SR+SAT) / 7 × 2.0

不调 delegate_task（粗打分不需要 blind 隔离——只是筛选，不是正式预测）。

## 写入 candidates.md

按 cheat-recommend 兼容的格式写入（H3 `### [tier] 标题` + id + composite + 概念）。
