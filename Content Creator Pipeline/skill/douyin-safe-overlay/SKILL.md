---
name: douyin-safe-overlay
description: Use when designing visual explanations, animated diagrams, schematic demos, or Douyin/TikTok-style talking-head layouts where face visibility, captions, safe zones, text overlays, quote cards, full-screen cutaway cards, side cards, or lower-thirds matter. Triggers include 示意图, 图文动效, 演示, 动态说明, 抖音竖屏, 露脸, 口播, 字幕, 金句卡, 卡片遮挡, 安全区, overlay, lower third, talking head, face safe zone, and short-video layout.
---

# Douyin Safe Overlay

Design visual explanations and 9:16 talking-head layouts so the speaker's face stays visible and platform UI does not cover key information.

## Core Rule

When the user asks for a "示意" or wants something easier to understand, prefer a **graphic explanation**:

- use a diagram, animated HTML, or image sequence
- show state changes over time
- label safe / unsafe / attention zones
- show before / during / after

This skill is not only for Douyin layouts. It also covers any situation where a visual, animated, or diagrammatic explanation makes the idea clearer.

There are two different card types:

1. **Full-screen vertical card**
   - Use as a cutaway scene.
   - It replaces the talking head for 2-4 seconds.
   - Good for cover cards, chapter cards, key quotes, recap cards.
   - Do not overlay it on top of the face.

2. **Overlay card**
   - Use while the speaker remains visible.
   - Must be horizontal, lower-third, side-card, or small label.
   - It must avoid eyes, mouth, facial expression, right-side Douyin buttons, and bottom caption/title areas.

If a card is tall/portrait and appears while the speaker is visible, assume it will cover the face unless explicitly positioned as a full-screen cutaway.

## Default 9:16 Zones

Use these as practical design heuristics:

- **Face zone**: upper-left or upper-center, eyes around 30%-35% of frame height.
- **Text-safe zone**: middle/lower-middle, but not too low.
- **Right danger zone**: right 18%-22% of the frame, where likes/comments/share UI appears.
- **Bottom danger zone**: bottom 18%-25%, where handle, caption, music, progress, and platform UI appear.
- **Most reliable overlay**: lower-third horizontal card placed below the face and above the bottom danger zone.

For a 540x960 demo canvas:

- Face-safe example: `left:72px; top:116px; width:270px; height:245px`
- Text-safe example: `left:44px; top:374px; width:356px; height:260px`
- Right danger example: `right:18px; top:96px; width:104px; height:700px`
- Bottom danger example: `left:24px; right:24px; bottom:22px; height:160px`

## Recommended Sequence

For opinion/talking-head Douyin videos:

1. `0-3s`: full face hook, only subtitles or one short phrase.
2. `3-6s`: full-screen quote card cutaway, no face.
3. `6-15s`: talking head with lower-third horizontal card.
4. `15-25s`: talking head with side mini-card if needed.
5. End: full face CTA or full-screen conclusion card, then face CTA.

## Layout Decisions

When asked to make cards for a talking-head video:

- If cards are for **cutaways**, create full-screen 9:16 vertical cards.
- If cards are for **simultaneous talking-head overlay**, create horizontal cards, transparent overlays, lower-thirds, or side labels.
- If the user asks for both, create two asset sets:
  - `cutaway-cards/`: full-screen 9:16.
  - `overlay-cards/`: lower-third / side-card safe overlays.

## Output Requirements

When producing layout mockups or explanatory demos, include:

- A 9:16 HTML demo or image.
- Visible face-safe zone.
- Visible right-side platform UI danger zone.
- Visible bottom UI danger zone.
- At least one correct overlay state and one incorrect face-covering state.
- Clear labels explaining whether each card is for cutaway or overlay use.

## Avoid

- Do not place dense cards over the speaker's eyes, mouth, or upper face.
- Do not put key text in the bottom 18%-25%.
- Do not place important text near the right-side interaction button column.
- Do not treat full-screen portrait cards as overlay elements.
- Do not recommend pure PPT/card-only style unless the user explicitly wants not to appear on camera.

## Preferred Recommendation

For the user's personal-IP opinion content, default to:

**talking head + subtitles + occasional full-screen quote-card cutaways + safe lower-third overlay cards**.

The person carries trust and personality; cards carry structure and memory points.

For other explanatory requests, default to:

**diagram / animated demo + labeled zones + state transitions + short takeaway text**.
