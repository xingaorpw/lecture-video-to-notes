# Contributing

## 硬约定

1. **不许为过测试改断言**。测试失败先查实现，不能把断言改松、删测试、跳过用例。
2. **不许伪造运行结果**。README/CHANGELOG 里的数字必须来自真实命令输出；没测过就写“没测过”。
3. **不许静默改写转写**。ASR 疑点用 `[ASR存疑]`，口误用 `[口误修正]`，补充用 `[补充]`。
4. **不许把课堂视频/音频提交到仓库**。示例只能用合成音频或公开授权素材。
5. **不新增重量级依赖**，除非能说明它解决了现有依赖解决不了的问题。新增依赖必须同步 `requirements.txt` 和 README。
6. **保持 SKILL.md 可执行**。新增命令要在干净环境跑通；不能只写“建议”。
7. **DOCX 公式优先 OMML**。不要为了图省事把整页公式转成图片；Pandoc 不可用时才降级。
8. **PPT 内容页必须有讲稿备注**。没有备注的页面视为未完成。

## 开发环境

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

Windows：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

## 提交前检查

- [ ] `pytest -q` 全绿
- [ ] `python scripts/lecture.py --help` 正常
- [ ] `python scripts/doctor.py --json` 的必需项为 true
- [ ] 新增/修改的 Markdown 没有 TODO/待补充
- [ ] 没有把 `.venv/`、模型、视频、生成的 DOCX/PPTX 加进提交
- [ ] README 的“真实验收输出”没有被改写成未经验证的数字

## 代码风格

- Python 3.10+，类型标注尽量完整。
- 路径用 `pathlib`，不要手拼字符串。
- 子进程错误要保留 stderr 尾部，方便定位。
- 生成器失败要抛出明确异常，不要静默写空文件。
