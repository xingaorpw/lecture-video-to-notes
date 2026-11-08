# 坏音轨、冻结画面与视觉讲义

这份文档记录真实课堂录播里遇到过的坑，以及“没有可用音轨时如何不造假地交付”。

## 1. 先做媒体预检，不要直接跑 ASR

```python
from common import preflight_media
check = preflight_media(video_path)
```

`preflight_media` 会返回：

- `has_audio`：是否存在音频流；
- `audio_duration`：音频流真实时长（不是视频时长）；
- `video_duration`：视频流时长；
- `rms_db`：前 30 秒音频响度（dBFS）；
- `fatal`：无音轨、音轨只有 1–2 秒、音轨远短于视频；
- `warnings`：静音等非致命警告。

真实案例：

| 现象 | 结果 |
| --- | --- |
| 2h 视频，音频流 1.3 s | ASR 报 `No speech segments` |
| 2h 视频，完全没有音频流 | 无法转写 |
| 音频前 30 s 约 -58 dBFS | 可能麦克风未开/静音 |
| 画面 30 min 后“无信号”并冻结 | 视觉讲义也没有足够素材 |

**原则**：`fatal` 非空时不要花几十分钟转写；先停下来判断素材是否可用。

## 2. 决策树

```text
媒体预检
├── 有可用音轨 → transcribe → chunk → 正常讲义
└── 无可用音轨
    ├── 抽帧后 PPT/板书可读 → 视觉讲义（课堂 PPT 为主）
    └── PPT 不可读/画面冻结
        ├── 有 MOOC/教材/课件 → 外部资料补充讲义（必须标注）
        └── 都没有 → 明确告知不可做，不伪造
```

## 3. 抽帧

```bash
python scripts/slides.py --workdir "<workdir>" --interval 60
python scripts/slides.py --workdir "<workdir>" --interval 30 --start 0 --end 1800
```

产物：`slides/t00000.jpg ...`、`slides/slides.json`。

建议：

- 先用 60–300 s 间隔粗看，找到 PPT 出现的时间段；
- 再对有效段用 15–30 s 间隔细抽；
- 画面冻结/无信号时，抽帧没有意义，直接走外部资料；
- 默认保留视频；确认不需要后加 `--delete-video`。

## 4. 视觉讲义写法

- **主结构**以课堂 PPT 的章节/例题为准；
- PPT 缺失的部分，用 MOOC/教材补充，但必须写清“补充”；
- `04_课堂信息.md` 必须包含来源与限制，例如：
  - “课堂录像音轨仅 1.3 s，画面 30 min 后冻结；本章按课堂 PPT 第 3 讲 + MOOC 补充，不是逐字稿。”
- 不使用假时间戳；视觉讲义可以不写 `[HH:MM:SS]`；
- 不把外部资料说成“老师原话”；
- 每个例题给：题目、思路、代码、运行结果、易错点；
- 目标：5–6 章，≥8,000 字，≥20 题（推荐 30 题）。

## 5. 校验

```bash
python scripts/validate_notes.py --workdir "<workdir>" --min-chapters 5
```

它会检查：

- `notes/讲义.md` 存在；
- 章节数、附录数；
- 字数、题库题量；
- 无 TODO/待补充；
- `04_课堂信息.md` 有来源/限制说明；
- DOCX 可打开、段落数。

> 这个模式不校验逐字稿/分块，因为源视频没有可用音轨；它是“视觉/教材补充”专用门，不是正常模式的替代。

## 6. 删除媒体的安全规则

- 只有 `transcript.json` / `chunks/manifest.json` 成功生成后才删视频/音频；
- ASR 失败时保留 `source.mp4`，方便换模型/换 VAD 重试；
- 视觉模式确认 `slides/` 已抽完后再删；
- 删除前打印绝对路径，避免误删。

## 7. 平台/工具坑

- `playurl` 的多个 key 可能指向同一个 MP4，换清晰度不等于换音轨；
- `av` 19 与 faster-whisper 不兼容，requirements 固定 `av>=11,<19`；
- `pypandoc_binary` 的 `get_pandoc_path()` 可能不带 `.exe`，要检查 `.with_suffix(".exe")`；
- matplotlib mathtext 不认 `\ge/\le/\dfrac/\text` 等别名，公式图前要 sanitize；
- `\inf` 前缀替换不能误伤 `\infty`；
- 视频流完整不代表音轨完整，必须分别看 `audio_duration` 和 `video_duration`。
