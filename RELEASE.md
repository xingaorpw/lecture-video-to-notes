# v0.2.0

针对真实课堂录播里遇到的“坏音轨/冻结画面/无 PPT”问题，补齐预检、视觉讲义与专用校验。

## 新增

- `probe.py` / `preflight_media`：分别检测视频与音轨时长，识别 1–2 秒坏音轨、无音频流、音轨远短于视频、前段静音。
- `transcribe` 前置预检：音轨不可用时立即失败，不再白跑 ASR；新增 `--no-vad` 排查 VAD 误杀。
- `slides.py`：按间隔抽 PPT/板书帧，输出 `slides/` 与 `slides.json`。
- `validate_notes.py` / `validate-notes`：无音轨/视觉讲义专用校验（章节、字数、题量、来源标注、DOCX）。
- `references/broken-media-and-visual.md`：坏音轨/冻结画面/视觉讲义/外部资料补充的决策树与红线。
- `--no-ppt`：只交付讲义 DOCX，跳过 PPTX 校验。
- 公式 `sanitize_formula`：处理 `\ge/\le/\dfrac/\tfrac/\iint/\infty` 等 mathtext 别名。

## 修复

- `\inf` 前缀替换误伤 `\infty`，公式图显示 `infty`。
- `\ge/\le` 未自动转成 `\geq/\leq`，公式图降级为原文。
- 音轨损坏时 ASR 只报 `No speech segments`，缺少可执行诊断。

## 验收

- `pytest`：17 passed。
- 课堂录播实测：2 小时视频仅 1–2 秒音轨、无音频流、30 分钟后画面冻结等情况，均能在预检阶段识别并按视觉/外部资料模式交付。
- 理论力学 6 讲 + C++ 6 讲讲义 DOCX 全部生成并校验（C++ 为视觉/教材补充模式）。
