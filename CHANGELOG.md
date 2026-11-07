# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
