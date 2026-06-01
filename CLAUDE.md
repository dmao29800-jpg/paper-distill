# Paper Distill Skill

从学术论文 PDF 批量生成 LoRA/SFT 监督微调训练数据。支持多学科 Prompt 模板，调用 DeepSeek API，断点续传，并发处理。

## 触发条件

调用此 Skill 当用户提到：
- "论文数据清洗" / "生成 SFT 数据" / "论文蒸馏" / "paper distill"
- "从论文提取 QA 对" / "论文知识提取"
- "批量处理论文" + AI 训练数据

## 依赖

- Python 3.9+
- 安装: `pip install -r requirements.txt`
- 环境变量: `DEEPSEEK_API_KEY=sk-xxx`

## 使用方法

### CLI

```bash
# 列出所有学科
python cli.py --list-disciplines

# 处理论文 (土木工程)
python cli.py -i ./papers -o ./output -d civil_engineering -c 3

# 处理论文 (材料科学)
python cli.py -i ./papers -o ./output -d materials_science -c 5

# 限制数量 + dry-run 预览
python cli.py -i ./papers -o ./output -d generic -n 10 --dry-run
```

### Python API

```python
from engine import Pipeline, PromptBuilder, DeepSeekClient
from pathlib import Path

client = DeepSeekClient(api_key="sk-xxx")
builder = PromptBuilder(Path("configs/disciplines.yaml"))
pipeline = Pipeline(
    input_dir=Path("./papers"),
    output_dir=Path("./output"),
    api_client=client,
    prompt_builder=builder,
    discipline="civil_engineering",
    concurrency=3,
)
stats = pipeline.run()
print(stats)
```

## 学科预设

| 预设 | 领域 | 禁数策略 |
|------|------|----------|
| `civil_engineering` | 土木工程 | strict（严禁数值） |
| `materials_science` | 材料科学 | contextual（允许引用关键数值） |
| `computer_science` | 计算机科学 | contextual |
| `biology_medicine` | 生物医学 | strict |
| `generic` | 通用 | contextual |

## 自定义学科

编辑 `configs/disciplines.yaml`，添加新的 discipline 配置即可。

## 输出格式

每篇论文生成一个 `.txt` 文件，内容为 JSONL：
```jsonl
{"input":"...","output":"...","doc_id":"论文中文标题","type":"解释类"}
```

## 项目结构

```
paper-distill/
├── engine/              核心引擎
│   ├── pdf_extractor.py
│   ├── api_client.py
│   ├── jsonl_parser.py
│   ├── prompt_builder.py
│   ├── checkpoint.py
│   └── pipeline.py
├── configs/
│   └── disciplines.yaml 学科配置
├── cli.py               CLI 入口
└── requirements.txt
```
