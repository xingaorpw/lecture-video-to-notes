# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-08

### Added

- 媒体预检 `probe.py` / `preflight_media`：分别检查视频与音轨时长，识别 1–2 秒坏音轨、无音频流、音轨远短于视频、前段静音。
- `transcribe` 前置预检：音轨不可用时立即失败并给出视觉模式提示，不再白跑 ASR；新增 `--no-vad` 排查 VAD 误杀。
- `slides.py`：按时间间隔从录播抽 PPT/板书帧，输出 `slides/` 与 `slides.json`，可选 `--delete-video`。
- `validate_notes.py`：无音轨/视觉讲义专用校验（章节、字数、题量、来源标注、DOCX），不要求逐字稿。
- `references/broken-media-and-visual.md`：坏音轨/冻结画面/视觉讲义/外部资料补充的决策树与红线。
- `--no-ppt`：只交付讲义 DOCX，跳过 PPTX 校验。
- 公式 sanitize 统一为 `sanitize_formula`：处理 `\ge/\le/\dfrac/\tfrac/\iint/\infty` 等 mathtext 别名。

### Fixed

- `\inf` 前缀替换误伤 `\infty`，导致公式图显示 `infty`。
- `\ge/\le` 未自动转成 `\geq/\leq`，公式图降级为原文。
- 课堂录像“视频完整但音轨只有 1–2 秒”时，ASR 只报 `No speech segments`，缺少可执行诊断。

### Changed

- 明确“完整”不等于“必须有逐字稿”：无音轨时优先课堂 PPT，其次 MOOC/教材，必须标注来源，不伪造时间戳/原话。

## [0.1.0] - 2026-11-07

### Added

- 课堂录播/音频 → 逐字稿（JSON / Markdown / SRT），基于 faster-whisper，CPU int8 可跑。
- 按语义分块，生成 `manifest.json` 覆盖率清单，校验每个分块都能归属到章节。
- 分章讲义模板与组装器：课程信息、使用说明、目录、七段式章节、四个附录。
- Pandoc DOCX 生成：封面、页眉页脚、目录、表格样式、Word 原生 OMML 公式。
- PPTX 生成：16:9 学术蓝主题、封面/章节页/内容卡片/公式卡/表格/小结/结束页，逐页讲稿备注。
- 校验器：转写、分块、讲义字数/时间戳、附录/题库、DOCX、PPTX 硬性质量门。
- `doctor` 环境检查、`setup.ps1` 一键安装、`run.cmd` UTF-8 启动器。
- 中文繁体转简体（zhconv），术语提示词，低置信段标记。
- 使用真实 2.5 小时课堂录播完成端到端验收（PASS）。

### Known limitations

- 录播音轨静音段无法还原老师原话，只能按画面/教材补录并标注。
- Tongji 平台下载器依赖登录态，未包含在仓库内。
- PDF 导出依赖外部 LibreOffice。
