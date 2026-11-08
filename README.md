# lecture-video-to-notes

[![CI](https://github.com/xingaorpw/lecture-video-to-notes/actions/workflows/ci.yml/badge.svg)](https://github.com/xingaorpw/lecture-video-to-notes/actions/workflows/ci.yml)
![tests](https://img.shields.io/badge/tests-pytest-brightgreen)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![deps](https://img.shields.io/badge/deps-faster--whisper%20%7C%20pandoc%20%7C%20python--pptx-informational)
![license](https://img.shields.io/badge/license-MIT-green)

把大学课堂录播变成**可核对、可复习、可讲课**的三件套：

- **逐字稿**：`transcript.md` / `.srt` / `.json`，每段带时间戳
- **完整讲义**：`讲义.docx`，含定义、推导、例题、易错点、自测、题库、复习路径
- **授课课件**：`课件.pptx`，含章节页、公式、表格、讲稿备注

不是“几分钟看完”的摘要。每条关键结论都尽量保留 `[HH:MM:SS]`，能跳回原视频核对；每个转写分块都要在讲义里找到归属。

## 真实验收输出

2026-11-02 同济大学《概率论与数理统计》第 9–11 节，2 小时 24 分：

```text
[transcribe] done: 2768 segments, 02:24:32, language=zh (1.0)
[chunk] 5 chunks, 29,243 chars, coverage=1.000, time=1.000
[docx] pandoc: 950 paragraphs, 202 headings, 26 tables
[pptx] 36 slides, 36 with speaker notes
[validate] PASS fails=0 warnings=0
```

| 指标 | 结果 |
| --- | --- |
| 视频 | 531 MB，02:24:32 |
| 转写 | 2768 段，29,243 字，覆盖率 1.0 |
| 讲义 | 7 章，33,469 字，114 个时间戳 |
| 题库 | 35 题，含答案解析 |
| DOCX | 950 段，202 标题，26 表；公式为 Word 原生 OMML |
| PPTX | 36 页，36 页有讲稿备注 |
| 校验 | PASS，0 失败 |

另一讲（2026-10-26）同样 PASS：讲义 38,934 字、37 页 PPT、0 失败。

## 它解决什么问题

普通“视频转文字”只给你一坨逐字稿；普通“AI 总结”会漏掉推导和例题。这个项目把流程拆成可检查的步骤：

```text
视频/音频
  → 提取 16k 单声道音频
  → faster-whisper 逐字稿（带时间戳）
  → 按语义分块 + 覆盖率清单
  → 逐块精读，写分章讲义
  → 组装完整讲义 + 4 个附录
  → Pandoc 生成 DOCX（公式为 OMML）
  → slides.json → 可编辑 PPTX
  → 校验报告（PASS/FAIL）
```

关键质量门：

- `chunks/manifest.json` 的 `coverage.ratio` 必须为 `1.0`
- 每个分块必须能在某一章的覆盖声明里找到
- 关键结论带时间戳，全文时间戳 ≥ 字数 / 500
- 每章七段式：目标、概念、讲解、公式、例题、易错点、小结与自测
- PPT 每页有标题，内容页有讲稿备注，公式页有公式
- 低置信转写标 `[ASR存疑]`，口误标 `[口误修正]`，补充标 `[补充]`

## 安装

### Windows（推荐）

```powershell
git clone git@github.com:xingaorpw/lecture-video-to-notes.git
cd lecture-video-to-notes
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

`setup.ps1` 会建 `.venv`、安装依赖，并优先使用清华 PyPI 镜像。Pandoc 由 `pypandoc-binary` 自带，不需要单独下载。

### 手动安装

```bash
python -m venv .venv
# Windows: .venv\Scripts\python.exe
# macOS/Linux: .venv/bin/python
.venv/bin/pip install -r requirements.txt
```

系统要求：Python 3.10+；ffmpeg 可选（没有时用 PyAV 解码音频）；LibreOffice 可选（用于渲染抽查）。

## 用法

```powershell
$SKILL = "$PWD"
& "$SKILL\scripts\run.cmd" doctor
& "$SKILL\scripts\run.cmd" init `
  --video "D:\录播\第03讲.mp4" `
  --workdir "D:\学习\第03讲" `
  --course "概率论与数理统计" `
  --lecture "第03讲" `
  --glossary "随机变量,分布函数,期望,方差"
& "$SKILL\scripts\run.cmd" transcribe --workdir "D:\学习\第03讲" --language zh --model small
& "$SKILL\scripts\run.cmd" chunk --workdir "D:\学习\第03讲"
# 读 transcript/chunks/*.md，写 notes/chapters/*.md 与 notes/appendices/*.md
& "$SKILL\scripts\run.cmd" assemble --workdir "D:\学习\第03讲"
& "$SKILL\scripts\run.cmd" docx --workdir "D:\学习\第03讲"
# 写 output/slides.json（模板：templates/slides.example.json）
& "$SKILL\scripts\run.cmd" pptx --workdir "D:\学习\第03讲"
& "$SKILL\scripts\run.cmd" validate --workdir "D:\学习\第03讲"
```

macOS/Linux 用 `scripts/run.sh` 或 `.venv/bin/python scripts/lecture.py ...`。

## 坏音轨 / 视觉讲义模式

课堂录播常见“视频完整、音轨只有 1–2 秒”或“完全没音轨”。先预检，别直接跑 ASR：

```powershell
& "$SKILL\scripts\run.cmd" doctor
python scripts\probe.py "D:\录播\第03讲.mp4"
# 输出 FATAL 时：
& "$SKILL\scripts\run.cmd" slides --workdir "D:\学习\第03讲" --interval 60
# 读 slides/ 里的 PPT 帧写讲义，再：
& "$SKILL\scripts\run.cmd" validate-notes --workdir "D:\学习\第03讲" --min-chapters 5
```

规则：

- 课堂 PPT 可读时以 PPT 章节/例题为主；
- 没有 PPT 才用 MOOC/教材补充，且必须标注“不是课堂逐字稿”；
- 不伪造时间戳，不把外部资料说成老师原话；
- 详细流程见 [references/broken-media-and-visual.md](references/broken-media-and-visual.md)。

## 产物

```text
<workdir>/
  transcript/transcript.md / .srt / .json
  transcript/chunks/chunk_*.md + manifest.json
  notes/chapters/ch01.md ...
  notes/appendices/00_知识点总表.md ...
  notes/讲义.md
  output/讲义.docx
  output/slides.json
  output/课件.pptx
  output/校验报告.md
```

## 技术选型

| 环节 | 选择 | 理由 |
| --- | --- | --- |
| 转写 | faster-whisper（CPU int8） | 本地、免费、带时间戳、CPU 可跑 |
| 音频解码 | PyAV（ffmpeg 可选） | 不强制安装 100 MB ffmpeg |
| 分块 | 按停顿/目标字数切 | 长讲座不丢上下文，覆盖率可检查 |
| 讲义 | Markdown → Pandoc → DOCX | 公式转 Word 原生 OMML，排版稳定 |
| 课件 | python-pptx | 可编辑、可逐页控制版式/讲稿 |
| 公式图 | matplotlib（仅 PPT/降级 DOCX） | PPT 公式可视；DOCX 优先 OMML |
| 中文规范化 | zhconv | 繁体转简体，不静默改术语 |

## 已知限制

- **音频缺失无法凭空补**：如果录播音轨静音，讲义只能按画面/教材补录，并会标 `[画面补录]`；不能假装是老师原话。
- **视频完整不等于音轨完整**：真实平台出现过 2 小时视频只有 1–2 秒音频、甚至无音频流；`probe.py` 会先判 FATAL，避免白跑 ASR。
- **PPT 可能不可读**：录播画面可能“无信号”/冻结；视觉模式只能整理可读帧，不能还原老师讲解。
- **ASR 仍会错术语**：`small` 是质量/速度平衡点；术语多的课建议 `medium`，并加 `--glossary`。
- **PDF 导出**：DOCX/PPTX 已可直接用 Word/PowerPoint 打开；项目不内置 LibreOffice，PDF 导出需自行安装。
- **Tongji 平台下载器不在仓库内**：课程平台需要登录态，属于用户环境特定逻辑；仓库只负责“已有视频/音频 → 学习资料”。
- **不默认做 OCR/画面理解**：音频转写是主路径；需要时用 `video-tutorial-summary` 或自行抽帧。
- **CPU 时间**：2.5 小时音频在 Ryzen 7 5800H 上约 40–60 分钟（`small`/`beam=1`）。

## 开发与测试

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
python scripts/lecture.py --help
python scripts/doctor.py --json
```

测试覆盖：时间戳/中文规范化、分块覆盖率、讲义组装、PPTX 生成、媒体预检/短音轨、`--no-ppt`、公式别名、SKILL 契约与模板 JSON。

## 目录

```text
SKILL.md                 # agent 执行手册（DSH skill）
references/              # 调研、讲义规格、PPT 规格、ASR、排错
templates/               # 分章模板、slides 示例、子代理提示词
scripts/                 # CLI 与生成器
tests/                   # pytest
```

## 许可

MIT，见 [LICENSE](LICENSE)。外部工具按其许可证使用：Pandoc GPL、python-docx/python-pptx MIT、faster-whisper MIT。
