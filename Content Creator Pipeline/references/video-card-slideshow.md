# 金句卡轮播视频生产指南

> 当用户有口播稿 + TTS 配音 + 金句卡片 HTML 时，可合成金句卡轮播视频。
> 适用于知识类、观点类短视频——没人出镜，卡片+配音+字幕。

---

## 工作流

```
口播稿
  ├─→ TTS 配音（text_to_speech 工具）
  ├─→ 金句卡片 HTML（douyin-safe-overlay 或手写）
  │     └─→ Playwright 截图每张卡片为 1080×1920 PNG
  └─→ 字幕（从稿子分段）
       │
       ▼
ffmpeg 合成：
  1. concat demuxer 拼接图片（每张 5-7 秒）
  2. 叠加配音音频
  3. 烧录 SRT 字幕
```

## 步骤

### 1. 准备素材

| 素材 | 来源 | 格式 |
|------|------|------|
| 配音 | `text_to_speech` 工具 | WAV |
| 金句卡 | HTML 设计（9:16，1080×1920） | PNG（单张 1080×1920） |
| 字幕 | 按卡片分段拆稿子 | SRT |

### 2. 截图卡片（Playwright）

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("file:///path/to/cards.html", wait_until="networkidle")

    for i in range(1, 8):
        # 显示单张卡片
        page.evaluate(f"""() => {{
            document.querySelectorAll('.card').forEach(c => c.style.display = 'none');
            const card = document.querySelector('.card-{i}');
            if (card) card.style.display = '';
        }}""")
        page.set_viewport_size({"width": 1080, "height": 1920})
        page.wait_for_timeout(300)
        page.screenshot(path=f"video_out/cards/card_{i}.png")

    browser.close()
```

### 3. 准备字幕

按卡片分段匹配时间戳，每段对应一张卡片的显示时长：

```
1
00:00:00,000 --> 00:00:05,000
第一段金句对应的口播内容
```

**字幕规则：**
- 按卡片分段，不是按句子分段
- 每段时长 = 该卡片显示时长
- 字幕字数控制在 20-30 字/段，太长分行

### 4. ffmpeg 合成

```bash
# Step A：创建图片列表
echo "file 'card_1.png'
duration 5
file 'card_2.png'
duration 5
..." > images.txt
echo "file 'card_7.png'" >> images.txt  # concat demuxer 需要末尾多一行

# Step B：合成为视频
ffmpeg -y -f concat -safe 0 -i images.txt \
  -c:v libx264 -preset medium -crf 20 \
  -pix_fmt yuv420p -r 30 \
  vid_only.mp4

# Step C：叠加音频 + 字幕
ffmpeg -y -i vid_only.mp4 -i voiceover.wav \
  -vf "subtitles=subtitles.srt" \
  -c:v libx264 -preset medium -crf 20 \
  -c:a aac -b:a 192k -pix_fmt yuv420p -shortest \
  final.mp4
```

## 避免的坑

| 坑 | 后果 | 正确做法 |
|----|------|---------|
| `zoompan` 做卡片缩放 | Windows 上极慢（软渲染无硬件加速），7 张卡 5 分钟以上 | 静态图片 + concat，或 `scale` 一次性缩放 |
| `xfade` 做卡片过渡 | 7 个以上 input 的 xfade 链在 Windows 上超时 | concat 直连 |
| 字幕用复杂 ASS 样式 | ffmpeg drawtext 路径解析在 Windows 上容易 bug | 纯 SRT 字幕，不要 ASS |
| 一次性用 `subtitles=` 内联样式 | Windows 路径冒号被 ffmpeg 解析为分隔符 | 分两步：先出视频，再加字幕和音频 |
| f-string 拼接 Windows 路径 | 反斜杠被转义 | 用 `os.path.join` + `.replace('\\\\', '/')` |

## FPS 和时长

```python
FPS = 30
CARD_DUR = 5  # 每张卡秒数
total_frames = NUM_CARDS * CARD_DUR * FPS
```

## 完整生产脚本模板

见同一目录下的 `render_v5.py` 模式：
1. 写 images.txt（concat demuxer 格式）
2. 写 s.srt（按卡片分段）
3. ffmpeg 出裸视频（只图片）
4. ffmpeg 加音频+字幕（-shortest）
