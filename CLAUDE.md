# Paper Distill Skill

从学术论文 PDF 批量生成 LoRA/SFT 监督微调训练数据。
**20 个理工科预设 + 自动学科识别**，调用 DeepSeek API，断点续传，并发处理。

## Repository

https://github.com/dmao29800-jpg/paper-distill

## 触发条件

调用此 Skill 当用户提到：
- "论文数据清洗" / "生成 SFT 数据" / "论文蒸馏" / "paper distill"
- "从论文提取 QA 对" / "论文知识提取"
- "批量处理论文" + "AI 训练数据" / "微调数据"

## 快速开始

### 1. 安装

```bash
git clone https://github.com/dmao29800-jpg/paper-distill.git
cd paper-distill
pip install -r requirements.txt
```

### 2. 设置 API Key

```bash
# Windows
set DEEPSEEK_API_KEY=sk-你的key

# macOS / Linux
export DEEPSEEK_API_KEY=sk-你的key
```

DeepSeek API Key 获取: https://platform.deepseek.com/api_keys

### 3. 运行

```bash
# 零配置：自动检测每篇论文学科（推荐）
python cli.py -i ./papers -o ./output -c 3

# 预览分类结果（不实际处理）
python cli.py -i ./papers --dry-run --classify -n 20

# 手动指定学科
python cli.py -i ./papers -o ./output -d civil_engineering

# 只处理前 100 篇
python cli.py -i ./papers -o ./output -c 5 -n 100

# 查看所有支持的学科
python cli.py --list-disciplines
```

## 核心功能

### 🧠 自动学科识别（默认）

论文拖进去，无需指定学科。引擎扫描论文文本中的关键词，自动匹配最合适的 Prompt 模板。

```
MTT20195602_13.pdf  →  土木工程  (score: 34)  ████████████████████
MTT20215805_22.pdf  →  交通运输  (score: 18)  ██████████████
```

识别逻辑：每个学科有 `high`（权重3分）和 `medium`（权重1分）两组关键词，取最高分且超过阈值（5分）的学科，否则兜底 `generic`。

### 📚 20 个理工科预设

| 大类 | 学科 Key | 禁数策略 |
|------|----------|----------|
| 土木建筑 | `civil_engineering` | strict |
| | `structural_engineering` | strict |
| | `architecture_urban` | contextual |
| 机械制造 | `mechanical_engineering` | contextual |
| | `aerospace` | strict |
| 材料化工 | `materials_science` | contextual |
| | `chemical_engineering` | contextual |
| | `chemistry` | contextual |
| 电气信息 | `electrical_engineering` | contextual |
| | `electronics` | contextual |
| | `computer_science` | contextual |
| | `control_automation` | contextual |
| 理学 | `physics` | contextual |
| | `mathematics` | contextual |
| 环境能源 | `environmental_science` | strict |
| | `energy_power` | contextual |
| 交通水利 | `transportation` | contextual |
| | `hydrology_water` | contextual |
| 地质 | `geology_geophysics` | contextual |
| 生物医学 | `biology_medicine` | strict |
| 兜底 | `generic` | contextual |

### ⚙️ 断点续传

中断后重新运行相同命令，自动跳过已完成论文。进度记录在 `{output_dir}/progress.json`。

### 🔀 并发处理

`-c 3` 表示 3 篇同时处理。建议 3-5，视 API 配额而定。

## 性能参考

| 指标 | 数值 |
|------|------|
| 单篇耗时 | 15-30 秒 |
| 单篇费用 | ¥0.01-0.02 |
| 100 篇总耗时 | ~25 分钟（并发3） |
| 100 篇总费用 | ~¥1.5 |

## 输出格式

每篇论文生成一个 `.txt` 文件，内容为 JSONL：

```jsonl
{"input":"在软土地区进行深基坑开挖时，如何评估其对邻近既有隧道的影响？","output":"可通过数值模拟方法建立三维模型...","doc_id":"软土地区深基坑开挖对邻近既有隧道的影响研究","type":"分析类"}
```

## 自定义学科

编辑 `configs/disciplines.yaml`，添加新条目：

```yaml
disciplines:
  ocean_engineering:
    domain: "海洋工程"
    keywords:
      high: [海洋平台, 立管, 系泊, 波浪荷载]
      medium: [水深, 浮式, 导管架, 水下, 腐蚀, 海流]
    numeric_policy: strict
    forbidden_names: [SACS, OrcaFlex, SESAM]
    type_labels:
      - 解释类/分析类/比较类/评价类
      - 设计类/机理类/因果类/定义类
    target_samples: 40
    min_samples: 25
    type_distribution:
      - "解释/定义/机理 ≥ 40%"
      - "分析/比较/评价 ≥ 30%"
      - "设计/对策/建议 ≤ 30%"
```

关键词选择原则：
- `high`: 该学科独有、不会与其他学科混淆的术语（如"盾构""基坑"对土木工程）
- `medium`: 该学科常用但可能与其他学科有交叉的术语

## Python API

```python
from engine import Pipeline, PromptBuilder, DeepSeekClient, DisciplineClassifier
from pathlib import Path

config = Path("configs/disciplines.yaml")
client = DeepSeekClient(api_key="sk-xxx")
builder = PromptBuilder(config)
classifier = DisciplineClassifier(config)

pipeline = Pipeline(
    input_dir=Path("./papers"),
    output_dir=Path("./output"),
    api_client=client,
    prompt_builder=builder,
    discipline="auto",        # auto-detect per paper
    classifier=classifier,
    concurrency=3,
)
stats = pipeline.run()
print(f"{stats['success']}/{stats['total']} papers, {stats['total_samples']} samples")
```

## 项目结构

```
paper-distill/
├── engine/                     # 核心引擎
│   ├── __init__.py
│   ├── pdf_extractor.py        # PDF 文本提取
│   ├── api_client.py           # DeepSeek API 封装 + 费用追踪
│   ├── jsonl_parser.py         # JSONL 解析 + 字段校验
│   ├── prompt_builder.py       # Jinja2 模板 + 学科渲染
│   ├── classifier.py           # 关键词自动分类器
│   ├── checkpoint.py           # 断点续传
│   └── pipeline.py             # 主流水线 + 并发调度
├── configs/
│   └── disciplines.yaml        # 20 学科配置 + 关键词
├── cli.py                      # 命令行入口
├── CLAUDE.md                   # Skill 说明文档
├── requirements.txt
└── .gitignore
```

## 常见问题

**Q: 论文文本提取为空？**
A: 部分扫描版 PDF 不含文本层，pypdf 无法提取。可尝试用 OCR 工具预处理。

**Q: 自动分类不准？**
A: 手动指定 `-d civil_engineering`。或编辑 `disciplines.yaml` 补充该领域的特征关键词。

**Q: API 频繁报错？**
A: 降低并发数 `-c 1`，或检查 API 账户余额。

**Q: 生成的样本有空字段/格式错误？**
A: 无效行会被自动过滤并统计在日志中，原始响应对应 `_debug_raw.txt` 保存。

## 依赖

```
pypdf>=3.0.0      # PDF 文本提取
openai>=1.0.0     # DeepSeek API (OpenAI 兼容)
pyyaml>=6.0       # 学科配置解析
jinja2>=3.0       # Prompt 模板渲染
```
