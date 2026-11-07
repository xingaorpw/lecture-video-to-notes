---
name: lecture-video-to-notes
description: 大学课堂录播/网课/讲座视频转完整学习资料：提取音频、逐字稿、分章讲义 DOCX、授课 PPTX、复习题与校验报告。用户提供课堂录像、讲座视频、网课回放，或说“转成讲义/做成课件/整理成笔记”时使用。
---

# 课堂录播 → 完整讲义 + 授课 PPT

把一段课堂录播变成三样可独立使用的东西：**可核对的逐字稿**、**可直接打印复习的完整讲义 DOCX**、**可直接上课/汇报的 PPTX**。不是摘要，不是“几分钟看完”，是把老师讲过的东西按知识结构重新组织，并保留回看视频的时间锚点。

## 先定义“完整”

“完整”不是字数多，而是下面四件事同时成立：

1. **覆盖完整**：每个转写分块都能在讲义里找到归属章节，时间轴无断点。
2. **结构完整**：每章都有目标、概念、推导/例题、易错点、小结、自测题；文末有知识点总表、公式/术语速查、题库、复习路径。
3. **证据完整**：关键定义、公式、例题、老师强调的考试点，至少带一个 `[HH:MM:SS]` 时间戳，能回看原视频核对。
4. **交付完整**：讲义 `.md` + `.docx`、课件 `.pptx`、逐字稿 `.json/.md/.srt`、校验报告，全部落在同一个工作区。

缺任何一项，都不算交付完成。

## 路径与解释器

先解析本文件所在目录为 `SKILL_DIR`（不要猜、不要全盘搜索）。Windows 下：

```powershell
$SKILL = "<SKILL_DIR>"
$RUN = "$SKILL\scripts\run.cmd"
```

`run.cmd` 会切 UTF-8、设 `PYTHONIOENCODING`，再调 `.venv` 里的 Python；比直接调 `python` 少一类 Windows 控制台乱码。macOS/Linux 下用 `"$SKILL/scripts/run.sh"`（若存在）或 `"$SKILL/.venv/bin/python" "$SKILL/scripts/lecture.py"`。所有命令都在工作区之外执行，用绝对路径。

## 第 0 步：环境预检

```powershell
& $RUN doctor --json
```

`doctor` 会检查 Python 包、ffmpeg/ffprobe（缺了由 PyAV 兜底）、Pandoc（可选）、磁盘空间、模型缓存。只有 `FAIL` 项必须修；`WARN` 项按需补。

首次使用或换机器：

```powershell
powershell -ExecutionPolicy Bypass -File "$SKILL\scripts\setup.ps1"
# 需要最佳 DOCX 公式保真时：
powershell -ExecutionPolicy Bypass -File "$SKILL\scripts\setup.ps1" -WithPandoc
# 需要 ffmpeg 抽帧/转码时：
powershell -ExecutionPolicy Bypass -File "$SKILL\scripts\setup.ps1" -WithFfmpeg
```

`setup.ps1` 会建 `.venv`、装 Python 依赖（默认走清华 PyPI 镜像，失败自动回退官方源）。ffmpeg/Pandoc 默认不下载：音频解码由 PyAV 兜底，DOCX 由 python-docx 兜底；需要更高公式保真或抽帧时再加 `-WithPandoc` / `-WithFfmpeg`。不需要管理员权限。

## 第 1 步：初始化工作区

```powershell
& $RUN init `
  --video "D:\录播\线性代数第03讲.mp4" `
  --workdir "D:\学习\线性代数\第03讲" `
  --course "线性代数" `
  --lecture "第03讲 矩阵乘法"
```

可选参数：

- `--instructor "张老师"`
- `--language zh`（默认 `zh`；英文课用 `en`；中英混杂用 `auto`，但要在报告里注明）
- `--glossary "矩阵,秩,特征值"`（逗号分隔，转写时作为提示词，显著降低术语错字）

初始化后工作区长这样：

```text
<workdir>/
  course.json
  audio/                 # 16k 单声道 wav
  transcript/            # json / md / srt
  transcript/chunks/     # 逐块精读材料 + manifest.json
  notes/chapters/        # 你写的分章 Markdown
  notes/appendices/      # 知识点总表、公式、题库、复习路径
  notes/assets/          # 讲义图片（可选）
  output/                # docx / pptx / slides.json / 校验报告
  logs/
```

## 第 2 步：提取音频并转写

```powershell
& $RUN transcribe `
  --workdir "D:\学习\线性代数\第03讲" `
  --language zh `
  --model small
```

默认 CPU `int8`，优先保证能跑完：

| 场景 | 建议 |
| --- | --- |
| 先验证流程 | `--model tiny` 或 `--model base` |
| 中文课堂正式交付 | `--model small`（默认）；术语多可换 `medium` |
| 有 NVIDIA GPU | `--device cuda --compute-type float16` |
| 机器慢/视频长 | `--beam-size 1`，先出稿，再用 `medium` 只重跑低置信段落 |
| 中英混杂 | `--language auto`，并在 `course.json` 里记录实际语言 |
| 中文输出繁体 | 默认用 `zhconv` 转简体；要保留原样加 `--no-simplify` |

产物：

- `audio/lecture.wav`
- `transcript/transcript.json`（带 `start/end/text/avg_logprob/no_speech_prob`）
- `transcript/transcript.md`（人读版，`[HH:MM:SS]` 开头）
- `transcript/transcript.srt`

**不要自动改写逐字稿。** 低置信段落只做标记；讲义里如果修正，写成 `[ASR存疑: 原词 → 应为]`，让读者能判断。

## 第 3 步：按语义分块

```powershell
& $RUN chunk `
  --workdir "D:\学习\线性代数\第03讲" `
  --target-chars 6000 `
  --overlap 2
```

分块器优先在停顿处切，目标每块 5000–7000 中文字符，相邻块重叠 1–2 段，保证跨块的推导不被切断。产物：

- `transcript/chunks/chunk_001.md` …
- `transcript/chunks/manifest.json`（总段数、总字符、每块时间范围、覆盖率）

分块后先读 `manifest.json`，确认 `coverage.ratio` 为 `1.0`，再开始写讲义。

## 第 4 步：逐块精读，写分章讲义

这是本 skill 的核心，不要跳过，也不要只读前几块。

1. 按顺序读 **每一个** `chunk_*.md`。长讲座可以每读完一块，先在 `notes/chapters/` 写这一块对应的章节草稿；不要等全部读完再凭记忆写。
2. 按知识结构合并相邻块，形成 3–8 章。每章一个文件：`notes/chapters/ch01.md`、`ch02.md`……
3. 每章开头必须有一行覆盖声明：

```markdown
> 覆盖：00:00:00–00:18:30（chunk 1–3）｜对应小节：矩阵乘法的定义、行列视角
```

4. 每章按 `templates/note-template.md` 的七段式写：本章目标 / 核心概念 / 详细讲解 / 公式与推导 / 例题与证明 / 易错点与考试提示 / 小结与自测。
5. 关键句带时间戳，例如 `矩阵乘法要求左矩阵的列数等于右矩阵的行数 [00:12:40]。` 每 300–500 字至少一个时间戳；整章没有时间戳视为不合格。
6. 老师口头强调的“这个必考”“这里容易错”“再讲一遍”，单独放进“考试提示”或“易错点”，并带时间戳。
7. 听不清、前后矛盾、明显口误：写 `[ASR存疑: ...]` 或 `[口误修正: ...]`，不要假装没听见，也不要编一个更顺的版本。
8. 视频里没有、你补的背景知识：用 `[补充]` 开头，并说明“讲义补充，非课堂原文”。补充只用于打通前置知识，不能替代课堂内容。

写完后检查：**每一块都能在某一章的覆盖声明里找到。** 找不到就是漏讲，回去补。

### 分章写作的颗粒度

- 定义：给出来源、符号、适用条件、反例。
- 定理：条件 → 结论 → 证明思路 → 一个具体例子 → 常见误用。
- 例题：题目 → 思路 → 步骤 → 答案 → 易错点；老师跳步的地方要补全，并标 `[补充]`。
- 证明：每一步“为什么可以这样”要写出来，不能只抄结论。
- 计算：关键中间结果要保留，方便读者对照。

## 第 5 步：组装完整讲义

```powershell
& $RUN assemble --workdir "D:\学习\线性代数\第03讲"
```

组装器会：

- 按 `ch01.md`、`ch02.md`… 的顺序合并；
- 生成课程信息、使用说明、目录；
- 追加 `notes/appendices/` 下的知识点总表、公式/术语速查、题库、复习路径；
- 检查章节覆盖声明是否连续，输出 `notes/讲义.md`。

`notes/appendices/` 至少要有：

| 文件 | 内容 |
| --- | --- |
| `00_知识点总表.md` | 一张表：知识点 / 所在章节 / 一句话解释 / 时间戳 |
| `01_公式与术语.md` | 公式、符号、适用条件；中英术语对照 |
| `02_题库.md` | 20–40 题：选择/填空/计算/证明/简答，附答案与解析 |
| `03_复习路径.md` | 30 分钟速通 / 90 分钟系统复习 / 考前查漏三条路径 |

这些不是装饰。没有它们，讲义只能“读”，不能“练”和“查”。

## 第 6 步：生成 DOCX

```powershell
& $RUN docx --workdir "D:\学习\线性代数\第03讲"
```

优先用 Pandoc + `assets/reference.docx` 模板，保留标题层级、表格、图片、LaTeX 公式（转 OMML）。Pandoc 不可用时自动降级到 python-docx，公式以文本/图片呈现。产物：`output/讲义.docx`。

生成后至少检查：

- 用 Word/WPS 打开不报错；
- 目录、标题层级、表格边框正常；
- 公式没有变成乱码；
- 中文字体不是宋体缺字方块。

## 第 7 步：写 `slides.json`

不要直接把讲义粘成 PPT。先设计授课节奏，再写结构化输入。模板见 `templates/slides.example.json`，完整字段见 `references/ppt-spec.md`。

最低要求：

- 90 分钟课：**25–40 页**；按 `max(15, min(45, round(时长分钟 / 4)))` 估算，校验下限按同一公式，创作目标仍按上表。
- 结构：封面 → 本讲路线 → 3–6 个章节（每章有章节页）→ 每章 2–4 页内容 + 1 个例题/证明 → 总结 → 课后任务/结束页。
- 每页标题是**结论句**，不是“概念一”“第一部分”。
- 每页正文 ≤ 6 条，每条 ≤ 30 个中文字符；超了拆页，不要缩字号硬塞。
- 每个内容页写 `notes`（讲稿）80–200 字，说明“这一页怎么讲、哪里停、问什么问题”。
- 公式放 `formula` 字段，用 LaTeX：`$$\det(AB)=\det(A)\det(B)$$`；推导步骤放 `explain`。
- 对比用 `two_col`，数据用 `table`，不要用大段文字。

保存到 `output/slides.json`。

## 第 8 步：生成 PPTX

```powershell
& $RUN pptx --workdir "D:\学习\线性代数\第03讲"
```

生成器会做：中文字体、统一配色、标题/正文层级、表格样式、公式渲染、页码、页脚、讲稿备注、超长内容自动拆页。产物：`output/课件.pptx`。

生成后必须逐页翻一遍（或让 `office-render`/LibreOffice 渲染成图片抽查）：

- 没有文字溢出、遮挡、跑到画布外；
- 公式清晰，不是空白；
- 表格没有挤成一团；
- 每页讲稿备注存在；
- 章节页和内容页节奏合理。

## 第 9 步：校验与交付

```powershell
& $RUN validate --workdir "D:\学习\线性代数\第03讲"
```

校验器输出 `output/校验报告.md`，并给出 PASS/FAIL。硬性门：

| 门 | 通过条件 |
| --- | --- |
| 转写 | `segments > 0`，时长与视频误差 < 5%，空段占比 < 20% |
| 分块 | `coverage.ratio == 1.0`，无时间断点 |
| 讲义 | 每章有覆盖声明；字数 ≥ `时长分钟 × 60`；时间戳 ≥ `字数 / 500`；无 TODO/待补充/此处省略 |
| 附录 | 四个附录文件齐全，题库 ≥ 20 题 |
| DOCX | 可被 python-docx 打开；标题数 ≥ 章节数；段落 ≥ 50；表格 ≥ 2 |
| PPTX | 页数达标；每页有标题；内容页有讲稿；无空页；公式页有公式 |
| 诚实性 | 无未标注的编造内容；补充内容带 `[补充]`；ASR 疑点带 `[ASR存疑]` |

任何 FAIL 都要修到 PASS，或者在交付说明里明确写“未通过项 + 原因 + 影响”。不要用“差不多”糊过去。

最终交付时给用户一张清单：

```text
逐字稿：transcript/transcript.md / .srt / .json
完整讲义：output/讲义.docx（源文件 notes/讲义.md）
授课课件：output/课件.pptx（源文件 output/slides.json）
校验报告：output/校验报告.md
```

同时报告：视频时长、转写模型、分块数、章节数、讲义字数、PPT 页数、已知问题（ASR 存疑/公式降级/未截取画面）。

## 失败处理速查

| 现象 | 处理 |
| --- | --- |
| `ffmpeg not found` | 跑 `setup.ps1`；或把 ffmpeg/bin 加到 PATH |
| 模型下载慢/失败 | 先 `--model tiny` 验证流程；设置 `HF_ENDPOINT=https://hf-mirror.com` 后重试 |
| CPU 转写太慢 | `--beam-size 1`；先 `small` 出稿，再只重跑低置信时间段 |
| 中文术语错得多 | `--glossary` 加术语；`--initial-prompt` 写一句课程背景；换 `medium` |
| 讲义越写越像摘要 | 回到 chunk，按“定义→条件→推导→例子→易错点”逐段补，不许用“总之”跳过 |
| PPT 文字溢出 | 拆页；每页 ≤ 6 条；把长句改成“结论 + 3 个支撑点” |
| 公式变乱码 | 确认 Pandoc 可用；PPT 公式用 `formula` 字段；降级时保留 LaTeX 原文 |
| 校验 FAIL | 先看报告里的 `FAIL` 行，按“覆盖→内容→引用→格式”的顺序修 |

## 参考

- `references/research.md`：现有开源工具/技能调研、选型理由、许可证。
- `references/note-spec.md`：讲义结构、写作颗粒度、覆盖与引用规则。
- `references/ppt-spec.md`：`slides.json` 完整字段、版式、设计系统。
- `references/asr-playbook.md`：模型选择、术语提示、低置信处理、长视频策略。
- `references/troubleshooting.md`：常见错误与修复。
- `templates/note-template.md`：分章模板。
- `templates/slides.example.json`：可直接改的课件输入示例。
