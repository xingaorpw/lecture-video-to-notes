# 现有工具与技能调研（2026-11-06）

调研目标：课堂录播 → 逐字稿 → 完整讲义 → 授课 PPT。重点看“能不能本地跑、中文课堂是否可用、有没有完整文档/PPT 产出”，而不是只看 star 数。

## 1. 最接近的现成项目

| 项目 | 能力 | 许可 | 为什么没有直接采用 |
| --- | --- | --- | --- |
| [drpwchen/lecture-to-notes](https://github.com/drpwchen/lecture-to-notes) | Claude Code skill + CLI；faster-whisper 转写、幻灯片抽帧/去重/OCR/VLM、时间对齐、结构化笔记、同步 HTML 阅读器 | MIT | 设计非常值得借鉴（尤其是“每个结论可回溯到时间点”），但偏 GPU、英文/繁体中文，流程重（OCR/VLM/HTML），**没有 PPT 产出**；直接引入会带来大量非必要依赖 |
| [lachlanchen/Video2Book](https://github.com/lachlanchen/Video2Book) | 播放列表下载 → 字幕 → TeX 讲义 → 合并 PDF/EPUB；有审校与出处映射 | GPL-3.0 | 输出是 LaTeX/PDF 书，不是 DOCX/PPT；依赖 tmux、TeX、pdfunite 等，Windows 课堂场景偏重；GPL 代码不适合直接复制进本 skill |
| [zhan2333/Recap](https://github.com/zhan2333/Recap) | macOS 原生应用；本地 Whisper；讲义要点 + LaTeX 笔记 PDF | GPL-3.0 | 仅 macOS，输出 PDF，无 PPT；不适合当前 Windows/DSH 环境 |
| [RexTSLO/video-slide-notes](https://github.com/RexTSLO/video-slide-notes) | OpenCV + Whisper 把讲座视频转成结构化 PDF 笔记，面向 NotebookLM/RAG | MIT | 偏 PDF/RAG，无 DOCX/PPT；没有长讲座分块写作规范 |
| [tusharkhatriofficial/StudyLens](https://github.com/tusharkhatriofficial/StudyLens) | 视频/讲座 → transcript、summary、quiz、flashcards；Docker Web 应用 | 仓库未声明明确许可证 | Web 应用，不是 agent skill；输出偏摘要/测验，不是完整讲义和授课课件 |
| [maciekt07/Lecture-Note-Generator-POC](https://github.com/maciekt07/Lecture-Note-Generator-POC) | 本地 LLM 把讲座转成 Markdown 学术笔记 | MIT | POC，偏“笔记”，没有分块覆盖、PPT、DOCX 质量门 |

**结论**：`lecture-to-notes` 的“证据链/时间锚点”思想最适合借鉴；`Video2Book` 的“先逐字稿、再结构化写作”值得保留；但两者都不覆盖“中文课堂 + DOCX 完整讲义 + 可讲课的 PPTX + CPU 可跑”。所以自建一条轻量流水线，而不是 fork 一个重项目。

## 2. 转写引擎选型

| 方案 | 优点 | 代价 | 结论 |
| --- | --- | --- | --- |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT；CTranslate2 推理；CPU int8 可跑；自带 VAD；返回 segment 级时间戳；模型从 tiny 到 large-v3 可选 | 中文术语仍可能错；large 模型 CPU 慢 | **默认引擎**。CPU 用 `small`，验证用 `tiny/base`，术语多再上 `medium` |
| [openai/whisper](https://github.com/openai/whisper) | 官方实现，生态成熟 | PyTorch 依赖重，CPU 更慢 | 不默认；作为对照 |
| [FunASR / SenseVoice](https://github.com/modelscope/FunASR) | 中文识别和标点通常更强；SenseVoice 小模型快 | 依赖 PyTorch/ModelScope，环境更重；时间戳粒度/导出格式需要额外适配 | 作为可选后端，不放进默认安装 |
| [whisper.cpp](https://github.com/ggerganov/whisper.cpp) | C++、CPU 友好、可离线分发 | 需要编译/下载二进制；Python 集成不如 faster-whisper 顺 | 备选；没有 Python 环境时的逃生通道 |

**默认策略**：`faster-whisper` + `language=zh` + `vad_filter=True` + `condition_on_previous_text=False`。后者能减少长音频里的“越写越顺、其实在编”的滚动幻觉。

## 3. 文档与 PPT 生成

| 工具 | 用途 | 许可 | 备注 |
| --- | --- | --- | --- |
| [Pandoc](https://pandoc.org/) | Markdown → DOCX，保留标题/表格/图片/LaTeX 公式（OMML） | GPL-2.0-or-later | 外部可执行文件，不复制源码；`setup.ps1` 下载便携版 |
| [python-docx](https://github.com/python-openxml/python-docx) | DOCX 读取/校验；Pandoc 不可用时的降级生成 | MIT | 作为 fallback，公式保真度低于 Pandoc |
| [python-pptx](https://github.com/scanny/python-pptx) | 生成可编辑 PPTX | MIT | 本 skill 的 PPT 生成器基于它，版式可控 |
| [ppt-master](https://github.com/hugohe3/ppt-master)（本机 DSH skill） | 高级 PPT 美化/模板填充 | MIT | 可选：需要更强设计时，把 `课件.pptx` 交给它二次美化 |
| `office-pptx` / `office-docx`（本机 DSH skill） | Office 文件检查、渲染、转换 | 随宿主 | 可选：用于最终视觉抽查 |

## 4. 本机已有 skill 的边界

| Skill | 能做什么 | 不能做什么 |
| --- | --- | --- |
| `video-tutorial-summary` | 视频字幕/截图 → Obsidian 笔记；有抽帧脚本 | 没有音频提取/ASR 脚本；输出偏 Obsidian；没有 PPT |
| `study-buddy` | 课程资料 → 按知识点排布的讲义、学习计划、考前速通 | 不是“录播视频 → 逐字稿 → DOCX/PPT”的媒体流水线 |
| `ppt-master` | 生成/重建/美化 PPTX | 不负责转写、分章、讲义完整性 |
| `office-pptx` / `office-docx` | 打开、编辑、校验、渲染 Office 文件 | 不负责内容生成 |

**定位**：本 skill 负责“媒体 → 结构化学习资产”的整条链路；`ppt-master`/`office-*` 是下游美化与检查工具，不重复造轮子。

## 5. 设计取舍

采用：

- CPU 优先，`faster-whisper` 默认 `int8`；GPU 只作为加速项。
- 逐字稿不改写，低置信只标记；讲义中的修正必须可追溯。
- 长讲座先分块，再逐块写章节；用 `manifest.json` 做覆盖率硬门。
- 讲义用 Markdown 作为源，Pandoc 转 DOCX；公式走 LaTeX。
- PPT 用结构化 `slides.json`，不直接切讲义；每页有讲稿备注。
- 所有产物落在一个工作区，校验器出 PASS/FAIL 报告。

不采用：

- 不做 Web 应用/数据库；课堂场景不需要。
- 不默认做 OCR/VLM 抽帧；音频转写是主路径，画面作为可选增强。
- 不自动“润色”逐字稿；自动纠错很容易把专有名词改错，且不可追溯。
- 不复制 GPL 项目代码；只借鉴流程思想，脚本为原创。

## 6. 参考链接

- https://github.com/drpwchen/lecture-to-notes
- https://github.com/lachlanchen/Video2Book
- https://github.com/zhan2333/Recap
- https://github.com/RexTSLO/video-slide-notes
- https://github.com/SYSTRAN/faster-whisper
- https://github.com/openai/whisper
- https://github.com/modelscope/FunASR
- https://github.com/ggerganov/whisper.cpp
- https://pandoc.org/
- https://github.com/python-openxml/python-docx
- https://github.com/scanny/python-pptx
