# Paper Distill

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

从学术论文 PDF 批量生成 LoRA/SFT 监督微调训练数据。

**20 个理工科预设 + 自动学科识别** → 论文拖进去，零配置出 JSONL。

## Why Paper Distill?

大模型微调需要高质量领域数据，但从论文提取 QA 对费时费力。Paper Distill 把整篇 PDF 喂给 DeepSeek，自动生成结构化的 `input → output` 训练样本，同时：

- 🔒 **严格脱敏**：去人名、去机构、去软件名、去具体数值
- 🧠 **自动识科**：扫描论文关键词，匹配最合适的 Prompt 模板
- ⚡ **并发处理**：3 并发，100 篇 ≈ 25 分钟
- 💰 **极低成本**：~¥0.015 / 篇论文

## Quick Start

```bash
# 1. Clone
git clone https://github.com/dmao29800-jpg/paper-distill.git
cd paper-distill

# 2. Install
pip install -r requirements.txt

# 3. Set API Key
#    Get one at: https://platform.deepseek.com/api_keys
export DEEPSEEK_API_KEY=sk-xxx

# 4. Run (auto-detect discipline for each paper)
python cli.py -i ./papers -o ./output -c 3

# Preview: see what disciplines will be detected
python cli.py -i ./papers --dry-run --classify -n 20
```

## Usage

```bash
# Auto-detect (default, recommended)
python cli.py -i ./papers -o ./output -c 3

# Fixed discipline
python cli.py -i ./papers -o ./output -d materials_science

# Limit + concurrent
python cli.py -i ./papers -o ./output -c 5 -n 100

# List all 20 disciplines
python cli.py --list-disciplines
```

## Supported Disciplines

| Domain | Key | Numeric Policy |
|--------|-----|----------------|
| 🏗️ 土木工程 | `civil_engineering` | strict |
| 🏛️ 结构工程 | `structural_engineering` | strict |
| 🏢 建筑与城市规划 | `architecture_urban` | contextual |
| ⚙️ 机械工程 | `mechanical_engineering` | contextual |
| ✈️ 航空航天 | `aerospace` | strict |
| 🔬 材料科学与工程 | `materials_science` | contextual |
| ⚗️ 化学工程 | `chemical_engineering` | contextual |
| 🧪 化学 | `chemistry` | contextual |
| ⚡ 电气工程 | `electrical_engineering` | contextual |
| 📟 电子科学与技术 | `electronics` | contextual |
| 💻 计算机科学 | `computer_science` | contextual |
| 🎛️ 控制科学与工程 | `control_automation` | contextual |
| 🔭 物理学 | `physics` | contextual |
| 📐 数学 | `mathematics` | contextual |
| 🌍 环境科学与工程 | `environmental_science` | strict |
| 🔋 能源与动力工程 | `energy_power` | contextual |
| 🚆 交通运输工程 | `transportation` | contextual |
| 🌊 水利工程 | `hydrology_water` | contextual |
| ⛰️ 地质与地球物理 | `geology_geophysics` | contextual |
| 🧬 生物医学 | `biology_medicine` | strict |
| 📦 通用 | `generic` | contextual |

## Output

Each paper → one `.txt` file, JSONL format:

```jsonl
{"input":"为什么在曲线中会出现两个峰值？","output":"首次峰值对应比例极限...","doc_id":"钢纤维混凝土试验及单轴抗拉本构模型研究","type":"因果类"}
```

## Performance

| Metric | Value |
|--------|-------|
| Per paper (single) | 15–30 sec |
| Per paper cost | ~¥0.015 |
| 100 papers (c=3) | ~25 min, ~¥1.5 |
| 100 papers (c=5) | ~15 min, ~¥1.5 |

## Python API

```python
from engine import Pipeline, PromptBuilder, DeepSeekClient, DisciplineClassifier
from pathlib import Path

config = Path("configs/disciplines.yaml")
client = DeepSeekClient(api_key="sk-xxx")
classifier = DisciplineClassifier(config)

pipeline = Pipeline(
    input_dir=Path("./papers"),
    output_dir=Path("./output"),
    api_client=client,
    prompt_builder=PromptBuilder(config),
    discipline="auto",
    classifier=classifier,
    concurrency=3,
)
stats = pipeline.run()
# {'total': 100, 'success': 100, 'failed': 0, 'total_samples': 4001}
```

## Custom Discipline

Edit `configs/disciplines.yaml`:

```yaml
disciplines:
  ocean_engineering:
    domain: "海洋工程"
    keywords:
      high: [海洋平台, 立管, 系泊]
      medium: [水深, 浮式, 波流, 腐蚀]
    numeric_policy: strict
    forbidden_names: [SACS, OrcaFlex]
    ...
```

## Project Structure

```
paper-distill/
├── engine/                     # Core engine (7 modules)
│   ├── pdf_extractor.py        # PDF text extraction
│   ├── api_client.py           # DeepSeek API wrapper
│   ├── jsonl_parser.py         # JSONL parsing & validation
│   ├── prompt_builder.py       # Jinja2 prompt rendering
│   ├── classifier.py           # Keyword-based auto-classifier
│   ├── checkpoint.py           # Resume support
│   └── pipeline.py             # Main orchestration
├── configs/
│   └── disciplines.yaml        # 20 disciplines + keywords
├── cli.py                      # CLI entry point
├── CLAUDE.md                   # Skill documentation
├── requirements.txt
└── .gitignore
```

## Requirements

- Python 3.9+
- [DeepSeek API Key](https://platform.deepseek.com/api_keys)
- pypdf, openai, pyyaml, jinja2

## License

MIT — feel free to use, modify, and distribute.
