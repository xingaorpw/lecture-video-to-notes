# 转写手册：模型、语言、术语与长视频

## 1. 默认配置

```powershell
& $PY "$SKILL\scripts\lecture.py" transcribe `
  --workdir "<工作区>" `
  --language zh `
  --model small `
  --device cpu `
  --compute-type int8 `
  --beam-size 5
```

默认值针对“中文大学课堂、CPU、2–3 小时录播”：

- `language=zh`：不要用 `auto` 赌运气。Whisper 在口音重的课堂上把中文猜成英文、再“翻译”成流利中文，是很常见的失败模式。
- `vad_filter=True`：跳过长时间静音，减少空白段和幻觉。
- `condition_on_previous_text=False`：降低长音频滚动幻觉；代价是上下文连贯性略差，但可核对性更重要。
- `beam_size=5`：质量优先；赶时间用 `1`。

## 2. 模型选择

| 模型 | 相对速度 | 中文课堂建议 | 说明 |
| --- | --- | --- | --- |
| `tiny` | 最快 | 只用于验证流程 | 术语错得多，别用于正式讲义 |
| `base` | 快 | 短课/口音轻 | 比 tiny 稳，仍可能漏术语 |
| `small` | 中等 | **默认** | CPU 可接受，90 分钟课通常能跑完 |
| `medium` | 慢 | 术语多、口音重 | 先用 small 出稿，再局部重跑 |
| `large-v3` | 最慢 | 有 GPU 时 | CPU 不现实；GPU 也要注意显存 |

CPU 时间不是线性的：`small` 在普通轻薄本上可能 0.5–1.5× 音频时长，`medium` 可能 2–4×。先跑 `tiny` 验证链路，再用 `small` 正式跑。

## 3. 术语提示

课堂转写最大的问题不是“听不懂”，是“听成另一个词”。用两个杠杆：

### 3.1 `--glossary`

```powershell
--glossary "矩阵,行列式,秩,特征值,特征向量,线性无关,秩定理"
```

初始化时写入 `course.json`，转写时拼进 `initial_prompt`。只放本课高频术语，不要塞一整本词典。

### 3.2 `--initial-prompt`

```powershell
--initial-prompt "这是一门大学线性代数课堂，中文授课，涉及矩阵、行列式、特征值。"
```

一句话给模型“场景”。不要写“请准确转写”这种无效指令。

## 4. 语言与中英混杂

| 场景 | 参数 | 注意 |
| --- | --- | --- |
| 纯中文 | `--language zh` | 默认 |
| 纯英文 | `--language en` | 英文讲义也用同一套流程 |
| 中英混杂 | `--language auto` | 在 `course.json` 记录实际语言；专有名词用 glossary |
| 方言/口音重 | `--language zh` + `medium` | 先试 5 分钟片段，确认可读再跑全片 |

## 5. 低置信段处理

`transcript.json` 每段带 `avg_logprob` 和 `no_speech_prob`：

- `avg_logprob < -1.0`：标记为低置信。
- `no_speech_prob > 0.6`：可能是静音/噪声误识别。
- 连续 3 段低置信：很可能进了难段（口音、板书、多人讨论）。

处理顺序：

1. 先看 `transcript.md` 对应时间点，判断是“听不清”还是“模型在编”。
2. 听不清：保留原词，标 `[ASR存疑: ...]`；讲义里不要强行解释。
3. 明显口误：标 `[口误修正: 原话 → 正确]`，并在旁边给依据（前后文/公式/教材）。
4. 术语错：用 glossary 重跑该时间段，或手工修正并标注。
5. **不要全局自动替换**。一次“智能纠错”可能把正确的人名、符号、术语改错，而且无法追溯。

## 6. 长视频策略

- 先 `transcribe` 全片，得到完整时间轴；不要按 30 分钟硬切后再转，容易丢上下文。
- 转写后按语义分块（`chunk`），每块 5000–7000 字；块间重叠 1–2 段。
- 写讲义时按块推进，不要一次把 3 小时逐字稿塞进上下文。
- 如果中途失败：`transcript.json` 是增量写的，重跑会跳过已完成音频？当前版本不做断点续传；先看 `logs/`，必要时用 `--start/--end` 只跑片段（后续版本支持）。

## 7. 常见幻觉与识别

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 大段流畅但内容空泛 | 长音频滚动幻觉 | `condition_on_previous_text=False`；检查 `avg_logprob` |
| 同一句重复 | 静音/噪声 | VAD；`no_speech_prob` 过滤 |
| 中文里突然出现英文翻译 | 语言猜错 | 固定 `language=zh` |
| 数字/公式读错 | 口播本身模糊 | 讲义以板书/教材为准，标 `[ASR存疑]` |
| 人名/术语前后不一致 | 模型无领域提示 | glossary + 人工统一，不要自动替换 |

## 8. 输出契约

`transcript.json`：

```json
{
  "source": "D:\\录播\\第03讲.mp4",
  "language": "zh",
  "model": "small",
  "device": "cpu",
  "compute_type": "int8",
  "duration": 5520.4,
  "created": "2026-11-06T20:00:00+08:00",
  "segments": [
    {
      "id": 1,
      "start": 0.0,
      "end": 4.2,
      "text": "好，我们开始上课。",
      "avg_logprob": -0.21,
      "no_speech_prob": 0.01
    }
  ]
}
```

`transcript.md`：每行 `[HH:MM:SS] 文本`，方便人读和 grep。

`transcript.srt`：标准 SRT，方便导入播放器/剪辑软件。

## 9. 隐私

- 默认本地转写，音频不出机器。
- 如果用户改用云端 ASR（Groq/Gemini/OpenAI），必须在交付说明里写明“音频已上传第三方”，并确认用户授权。
- 课堂录播可能包含学生声音/个人信息；不要上传到公共仓库。
