# 故障排查

## 1. 环境

### `ffmpeg not found`

```powershell
powershell -ExecutionPolicy Bypass -File "$SKILL\scripts\setup.ps1"
```

或手动把 `ffmpeg/bin` 加进 PATH。`doctor` 会按以下顺序找：

1. `PATH`
2. `%LOCALAPPDATA%\lecture-video-to-notes\ffmpeg\**\bin\ffmpeg.exe`
3. `%SKILL_DIR%\tools\ffmpeg\bin\ffmpeg.exe`

### `pandoc not found`

DOCX 仍会生成（python-docx 降级），但公式保真度下降。要完整公式：

```powershell
powershell -ExecutionPolicy Bypass -File "$SKILL\scripts\setup.ps1"
```

### Python 包安装失败（Python 3.13）

`faster-whisper` 依赖 `ctranslate2`、`av`、`onnxruntime`。如果某个包没有 3.13 wheel：

1. 先升级 pip：`& $PY -m pip install -U pip wheel`
2. 重试：`& $PY -m pip install faster-whisper`
3. 仍失败：装 Python 3.12，重建 `.venv`：

```powershell
py -3.12 -m venv "$SKILL\.venv312"
& "$SKILL\.venv312\Scripts\python.exe" -m pip install -r "$SKILL\requirements.txt"
```

然后把 `$PY` 指向 `.venv312`。

### `open() got an unexpected keyword argument 'metadata_errors'`

`faster-whisper 1.2.x` 调用了 `av.open(metadata_errors=...)`，PyAV 19 移除了这个参数。降级 PyAV：

```powershell
& $PY -m pip install "av>=11,<19"
```

`requirements.txt` 已固定该范围；如果手动装过最新版，按上面命令修。

### 中文输出繁体字

默认会用 `zhconv` 转简体；如果不需要，加 `--no-simplify`。没装 `zhconv` 时不会转换，但流程不报错。

### 模型下载慢/超时

```powershell
$env:HF_ENDPOINT = "https://hf-mirror.com"
& $PY "$SKILL\scripts\lecture.py" transcribe ... --model small
```

或先 `--model tiny` 验证流程，再换 `small`。模型缓存在 `%USERPROFILE%\.cache\huggingface\hub`。

## 2. 转写

### 转写结果大段空/重复

- 确认 `--language zh`，不要 `auto`。
- 降低 `--beam-size` 到 1 先看是否改善。
- 检查音频是否只有单声道/极低音量：先跑 `python scripts/probe.py 视频.mp4`。
- 如果 VAD 把语音全过滤，重试 `--no-vad`；仍无结果先看音轨时长。
- 音轨只有 1–2 秒/无音轨 = 录像坏了，不是 ASR 参数问题；转视觉模式，见 `references/broken-media-and-visual.md`。

### 术语全错

- `--glossary` 加术语。
- `--initial-prompt` 写课程背景。
- 换 `medium`；或只重跑问题时间段。

### CPU 太慢

- `--model small --beam-size 1`。
- 关闭其他占 CPU 的程序。
- 有 GPU 时 `--device cuda --compute-type float16`。
- 先跑 `tiny` 出时间轴，再用 `small` 重跑关键章节。

### 视频没有音轨 / 音轨只有 1–2 秒

先跑：

```powershell
python scripts/probe.py "视频.mp4"
```

它会分别输出 `audio_duration` 和 `video_duration`。以下都是致命：

- `has_audio=false`：没有音频流；
- `audio_duration < 10 s`：只录到开头/坏轨；
- `audio_duration < video_duration * 0.5`：音轨明显不完整。

不要反复换模型/VAD：这是素材问题。按 `references/broken-media-and-visual.md` 抽 PPT 帧、用 MOOC/教材补充，或明确告知无法做。

## 3. 分块与讲义

### `coverage.ratio < 1.0`

分块器按时间切，正常应为 1.0。小于 1.0 说明有段落没写进 manifest。重跑 `chunk`；仍失败就把 `manifest.json` 和 `transcript.json` 发给维护者。

### 某章没有覆盖声明

`assemble` 会报错并指出文件名。补一行：

```markdown
> 覆盖：00:00:00–00:18:30（chunk 1–3）
```

### 讲义字数不够

校验按 `时长分钟 × 60` 设最低线。90 分钟课至少 5400 字，但“完整”通常应到 1.2–2 万字。字数不够时不要灌水，回到 chunk 补：

- 定义的条件和反例；
- 推导的每一步；
- 例题的思路和易错点；
- 老师强调的考试点；
- 本章与前后章的联系。

### 时间戳密度不够

每 300–500 字补一个关键时间戳。不要把时间戳堆在段首；放在对应结论/步骤后面。

## 4. DOCX

### 公式变乱码/纯文本

- 确认 Pandoc 可用：`pandoc --version`。
- Markdown 公式用 `$...$` / `$$...$$`，不要用 `\(...\)`。
- Pandoc 命令加 `+tex_math_dollars`。
- 复杂矩阵/分段函数 Pandoc 也可能降级；在讲义里保留 LaTeX 原文，并在交付说明里注明。

### 中文变成方块

- Word/WPS 缺字体：装“微软雅黑”“宋体”。
- 参考模板 `assets/reference.docx` 里已设置 eastAsia 字体；如果仍异常，用 Word 打开后全选 → 字体 → 中文字体设为“宋体”。

### 目录不对

`assemble` 生成的是手动目录；如果标题改动，重跑 `assemble`。Word 里不要手动改目录，改源 Markdown 再重生成。

### 表格太宽

Markdown 表格列数控制在 6 列以内；超宽表格拆成两张，或在 DOCX 里设横向页。

## 5. PPTX

### 文字溢出/遮挡

- 拆页：每页 ≤ 6 条，每条 ≤ 30 字。
- 用 `two_col` 代替长列表。
- 公式页减少 `explain` 到 3–4 条。
- 表格 ≤ 6 列、≤ 8 行。

### 公式是空白

- 检查 `formula` 字段是否以 `$$` 开头结尾。
- matplotlib mathtext 不支持所有 LaTeX；复杂公式会降级为文本。确认 PPT 里至少有可读文本，不能空白。
- 可把公式先渲染成 PNG，再用 `content` 页的图片（后续版本支持 `image` 字段）。

### 中文字体不对

生成器设置 `Microsoft YaHei`。如果机器没有，装字体，或在 `slides.json` 的 `meta.theme` 里换主题（目前只有 `academic-blue`）。

### 讲稿备注看不到

PowerPoint 里“视图 → 备注页”，或演讲者视图。`notes` 字段会写入 `notes_slide`。

## 6. 校验

### `validate` 报 FAIL 但文件明明存在

看报告里的具体项：

- `讲义字数`：按 `时长分钟 × 60` 算，可能视频时长读错；
- `时间戳`：正则只认 `[HH:MM:SS]` 或 `[HH:MM:SS–HH:MM:SS]`；
- `PPT 页数`：按 `round(时长/3)` 算，短视频可能要求 ≥ 15；
- `DOCX 标题数`：Pandoc 生成的 Heading 样式可能不被 python-docx 识别为 `Heading 1`，报告会给出实际值。

### 不想被短视频卡住

短视频（< 20 分钟）用 `--min-slides 8 --min-chars 1500` 覆盖默认阈值。不要为了过校验删内容。

## 7. 路径与编码

- 路径含空格/中文：所有命令用引号；脚本内部用 `pathlib`，不拼字符串。
- Windows 长路径：把工作区放在 `D:\学习\...` 而不是深层 `AppData`。
- 控制台乱码：`chcp 65001`；脚本输出 UTF-8。
- 文件名不要用 `:`、`?`、`*`、`"`、`<`、`>`、`|`。

## 8. 还是不行

按顺序收集：

1. `doctor --json` 输出；
2. 失败命令的完整 stderr；
3. `logs/` 下对应日志；
4. `transcript/transcript.json` 的前 3 段和失败时间段；
5. `output/校验报告.md`。

带着这些信息问，不要只说“跑不了”。
