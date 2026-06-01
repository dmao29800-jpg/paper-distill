# Paper Distill / 论文蒸馏

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![GitHub stars](https://img.shields.io/github/stars/dmao29800-jpg/paper-distill?style=social)](https://github.com/dmao29800-jpg/paper-distill)
[![GitHub forks](https://img.shields.io/github/forks/dmao29800-jpg/paper-distill?style=social)](https://github.com/dmao29800-jpg/paper-distill)

> 🚀 从学术论文 PDF 批量生成大模型 SFT 微调训练数据
>
> 🚀 Batch generation of LLM SFT fine-tuning data from academic paper PDFs

**20 个理工科预设 + 自动学科识别** → 论文拖进去，零配置出 JSONL。
**20 STEM discipline presets + auto-detection** → drop papers in, get JSONL out.

---

## Why? / 为什么需要？

大模型微调需要高质量领域数据，但从论文手动提取 QA 对费时费力。Paper Distill 把整篇 PDF 喂给 DeepSeek，自动生成结构化的训练样本，同时自动脱敏、自动识科。

Fine-tuning LLMs requires high-quality domain data, but manually extracting QA pairs from papers is painstaking. Paper Distill feeds full PDFs to DeepSeek API, auto-generates structured training samples with built-in anonymization and discipline detection.

| 痛点 / Pain Point | 解决方案 / Solution |
|---|---|
| 🔓 手动提取费时 / Manual extraction is slow | ⚡ 15-30 秒/篇，支持并发 |
| 🏷️ 不知道用什么 Prompt / Don't know which prompt to use | 🧠 自动识别 20 个理工学科 |
| 🔢 训练数据泄漏具体数值 / Numerical leakage in training data | 🔒 两种脱敏策略 (strict / contextual) |
| 💸 标注成本高 / High annotation cost | 💰 ~¥0.015 / 篇 |

---

## Installation / 安装方式

> **无需独立网站，GitHub 本身就是你的产品主页。** No website needed — GitHub is your product homepage.

两种方式任选 / Choose one:

### 方式一：Claude Code Skill（推荐 ★）

适用于 [Claude Code](https://claude.ai/code) 用户。一行命令安装，之后对 Claude 说 "帮我把这 50 篇论文蒸馏成 SFT 数据" 即可自动运行。

For [Claude Code](https://claude.ai/code) users. One-command install, then just tell Claude what to do.

```bash
/skill install github.com/dmao29800-jpg/paper-distill
```

安装后 Claude 会自动读取项目的 CLAUDE.md，按指引调用引擎。无需手动记参数。

After installing, Claude reads CLAUDE.md and runs the pipeline automatically. No need to remember CLI flags.

### 方式二：直接使用 / Direct Use

没有 Claude Code？直接克隆仓库。No Claude Code? Just clone the repo.

```bash
# 1. Clone / 克隆
git clone https://github.com/dmao29800-jpg/paper-distill.git
cd paper-distill

# 2. Install / 安装
pip install -r requirements.txt

# 3. Set API Key / 设置密钥
#    Get one at / 获取地址: https://platform.deepseek.com/api_keys
#    ⚠️ 切勿将真实 key 提交到 git！/ Never commit your real key!
export DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx

# 4. Run / 运行 (auto-detect discipline per paper)
python cli.py -i ./papers -o ./output -c 3
```

> 💡 也可以在 GitHub 仓库页面点击绿色的 **"Code"** 按钮 → **"Download ZIP"**，解压后直接使用，连 git 都不需要。
>
> 💡 Or click the green **"Code"** button → **"Download ZIP"** on the GitHub page — no git required.

### 分发模型 / Distribution Model

```
用户 → GitHub 仓库首页 → 看 README 了解功能（中英双语）
                       → 点 Code → Download ZIP（零门槛）
                       → 或复制 /skill install 命令（Claude Code 用户）
                       → 或 git clone（开发者）
```

---

## Quick Start / 快速开始

> 以下命令假定你已经完成安装。If you completed installation above, skip to here.

```bash
# 🔍 自动检测学科（默认，推荐）/ Auto-detect (default, recommended)
python cli.py -i ./papers -o ./output -c 3

# 📋 预览每篇论文会被识别为什么学科 / Preview classification
python cli.py -i ./papers --dry-run --classify -n 20

# 🎯 手动指定学科 / Fixed discipline
python cli.py -i ./papers -o ./output -d materials_science

# ⚡ 高并发 + 限制数量 / High concurrency + limit
python cli.py -i ./papers -o ./output -c 5 -n 100

# 📚 查看全部 20 个学科预设 / List all disciplines
python cli.py --list-disciplines
```

> ⚠️ **Security / 安全提醒**：API Key 应通过环境变量传入，不要硬编码在代码或配置文件中，更不要提交到 Git。建议将 `export DEEPSEEK_API_KEY=...` 写入 `~/.bashrc` 或使用 `.env` 文件（已在 `.gitignore` 中排除）。
>
> ⚠️ **Security**: Always use the `DEEPSEEK_API_KEY` env var — never hardcode keys. The `.env` file is already in `.gitignore`.

---

## Usage / 使用方式

```bash
# 🔍 自动检测学科（默认，推荐）/ Auto-detect (default, recommended)
python cli.py -i ./papers -o ./output -c 3

# 📋 预览每篇论文会被识别为什么学科 / Preview classification
python cli.py -i ./papers --dry-run --classify -n 20

# 🎯 手动指定学科 / Fixed discipline
python cli.py -i ./papers -o ./output -d materials_science

# ⚡ 高并发 + 限制数量 / High concurrency + limit
python cli.py -i ./papers -o ./output -c 5 -n 100

# 📚 查看全部 20 个学科预设 / List all disciplines
python cli.py --list-disciplines
```

---

## Supported Disciplines / 支持的学科

| Emoji | 学科 / Discipline | Key / 标识符 | 禁数策略 / Numeric Policy |
|-------|---|---|:---:|
| 🏗️ | 土木工程 / Civil Engineering | `civil_engineering` | strict |
| 🏛️ | 结构工程 / Structural Engineering | `structural_engineering` | strict |
| 🏢 | 建筑与城市规划 / Architecture & Urban Planning | `architecture_urban` | contextual |
| ⚙️ | 机械工程 / Mechanical Engineering | `mechanical_engineering` | contextual |
| ✈️ | 航空航天 / Aerospace Engineering | `aerospace` | strict |
| 🔬 | 材料科学与工程 / Materials Science | `materials_science` | contextual |
| ⚗️ | 化学工程 / Chemical Engineering | `chemical_engineering` | contextual |
| 🧪 | 化学 / Chemistry | `chemistry` | contextual |
| ⚡ | 电气工程 / Electrical Engineering | `electrical_engineering` | contextual |
| 📟 | 电子科学与技术 / Electronic Engineering | `electronics` | contextual |
| 💻 | 计算机科学 / Computer Science | `computer_science` | contextual |
| 🎛️ | 控制科学与工程 / Control & Automation | `control_automation` | contextual |
| 🔭 | 物理学 / Physics | `physics` | contextual |
| 📐 | 数学 / Mathematics | `mathematics` | contextual |
| 🌍 | 环境科学与工程 / Environmental Science | `environmental_science` | strict |
| 🔋 | 能源与动力工程 / Energy & Power | `energy_power` | contextual |
| 🚆 | 交通运输工程 / Transportation | `transportation` | contextual |
| 🌊 | 水利工程 / Hydrology & Water Resources | `hydrology_water` | contextual |
| ⛰️ | 地质与地球物理 / Geology & Geophysics | `geology_geophysics` | contextual |
| 🧬 | 生物医学 / Biology & Medicine | `biology_medicine` | strict |
| 📦 | 通用 / Generic (兜底 fallback) | `generic` | contextual |

> **Strict** = 严禁任何具体数值 / No numbers allowed
> **Contextual** = 可引用原文关键数值 / Key numbers allowed with citation

---

## How Auto-Detection Works / 自动识别原理

每篇论文扫描前 30,000 字符，与各学科的关键词库匹配。高权重词命中 +3 分，中权重词 +1 分，取最高分且超过阈值（5分）的学科。

Scans first 30K chars of each paper against discipline keyword libraries. High-weight keywords = +3 pts, medium = +1 pt. Picks the highest-scoring discipline above confidence threshold (5 pts).

```
MTT20195602_13.pdf  →  土木工程 / Civil Engineering  (score: 34)  ████████████████████
MTT20215805_22.pdf  →  交通运输 / Transportation      (score: 18)  ██████████████
MTT20225901_02.pdf  →  材料科学 / Materials Science   (score: 15)  ████████████
```

---

## Output / 输出格式

每篇论文 → 一个 `.txt` 文件，JSONL 格式。
Each paper → one `.txt` file in JSONL format.

```jsonl
{"input":"在软土地区进行深基坑开挖时，如何评估其对邻近既有隧道的影响？","output":"可通过数值模拟方法建立三维模型...","doc_id":"软土地区深基坑开挖对邻近既有隧道的影响研究","type":"分析类"}
{"input":"What is the mechanism of grain refinement by rare earth elements?","output":"Rare earth elements segregate at the solidification front...","doc_id":"Effect of Rare Earth Microalloying on Cast Aluminum Alloys","type":"机理类/Mechanism"}
```

Fields / 字段：`input` (问题/question), `output` (回答/answer), `doc_id` (论文中文标题/paper title), `type` (类别/category)

---

## Performance / 性能

| Metric / 指标 | Value / 数值 |
|---------------|-------------|
| 单篇耗时 / Per paper (single) | 15–30 sec |
| 单篇费用 / Per paper cost | ~¥0.015 |
| 100 篇 (c=3) / 100 papers (c=3) | ~25 min, ~¥1.5 |
| 100 篇 (c=5) / 100 papers (c=5) | ~15 min, ~¥1.5 |
| 200 篇实测 / 200 papers tested | 100% 成功率 / success rate, 4001 样本 / samples |

---

## Python API

```python
from pathlib import Path
from engine import Pipeline, PromptBuilder, DeepSeekClient, DisciplineClassifier

# ⚠️ 密钥通过环境变量传入，不要硬编码 / Use env vars, never hardcode keys
import os
api_key = os.environ["DEEPSEEK_API_KEY"]

config = Path("configs/disciplines.yaml")
client = DeepSeekClient(api_key=api_key)
classifier = DisciplineClassifier(config)

pipeline = Pipeline(
    input_dir=Path("./papers"),
    output_dir=Path("./output"),
    api_client=client,
    prompt_builder=PromptBuilder(config),
    discipline="auto",               # auto-detect per paper / 逐篇自动识别
    classifier=classifier,
    concurrency=3,
)
stats = pipeline.run()
print(stats)
# {'total': 100, 'success': 100, 'failed': 0, 'total_samples': 4001}
```

---

## Custom Discipline / 自定义学科

编辑 `configs/disciplines.yaml`，添加新条目。Edit `configs/disciplines.yaml`:

```yaml
disciplines:
  # 示例：海洋工程 / Example: Ocean Engineering
  ocean_engineering:
    domain: "海洋工程"
    keywords:
      high: [海洋平台, 立管, 系泊, 波浪荷载]           # 高权重 / high weight (+3)
      medium: [水深, 浮式, 导管架, 水下, 腐蚀, 海流]    # 中权重 / medium weight (+1)
    numeric_policy: strict               # strict = 严禁数值 / contextual = 允许引用
    forbidden_names: [SACS, OrcaFlex]    # 禁用的软件/方法名
    type_labels:
      - 解释类/分析类/比较类/评价类
      - 设计类/机理类/因果类/定义类
    target_samples: 40                   # 目标样本数
    min_samples: 25                      # 最少样本数
    type_distribution:
      - "解释/定义/机理 ≥ 40%"
      - "分析/比较/评价 ≥ 30%"
      - "设计/对策/建议 ≤ 30%"
```

关键词选择原则 / Keyword selection guide:
- `high`：学科独有、不会混淆的术语 / Unique, non-overlapping terms
- `medium`：学科常用、可能交叉的术语 / Common, potentially overlapping terms

---

## Project Structure / 项目结构

```
paper-distill/
├── engine/                     # 核心引擎 / Core engine (7 modules)
│   ├── __init__.py
│   ├── pdf_extractor.py        # PDF 文本提取 / PDF text extraction
│   ├── api_client.py           # DeepSeek API 封装 / API wrapper + cost tracking
│   ├── jsonl_parser.py         # JSONL 解析校验 / Parse & validate
│   ├── prompt_builder.py       # Jinja2 模板渲染 / Prompt rendering
│   ├── classifier.py           # 关键词自动分类器 / Keyword auto-classifier
│   ├── checkpoint.py           # 断点续传 / Resume support
│   └── pipeline.py             # 主流水线 + 并发 / Main pipeline + concurrency
├── configs/
│   └── disciplines.yaml        # 20 学科配置 + 关键词库
├── cli.py                      # 命令行入口 / CLI entry point
├── CLAUDE.md                   # Skill 文档 / Skill documentation
├── README.md                   # 项目说明 / Project overview
├── requirements.txt            # 依赖 / Dependencies
└── .gitignore                  # Git 忽略规则
```

---

## FAQ / 常见问题

<details>
<summary><b>Q: 论文文本提取为空？PDF text extraction empty?</b></summary>
部分扫描版 PDF 不含文本层，pypdf 无法提取。可尝试用 OCR 工具（如 Tesseract）预处理。Some scanned PDFs lack a text layer. Try OCR preprocessing.
</details>

<details>
<summary><b>Q: 自动分类不准？Auto-classification wrong?</b></summary>
手动指定 <code>-d civil_engineering</code>，或编辑 <code>disciplines.yaml</code> 补充该领域的特征关键词。Manually specify the discipline, or add more keywords to the config.
</details>

<details>
<summary><b>Q: API 频繁报错？Frequent API errors?</b></summary>
降低并发 <code>-c 1</code>，检查 API 余额，或确认网络可访问 api.deepseek.com。Lower concurrency, check balance, or verify network access.
</details>

<details>
<summary><b>Q: 生成的样本有格式错误？Malformed samples?</b></summary>
无效行在解析时自动过滤，原始响应对应 <code>_debug_raw.txt</code> 保存供排查。Invalid lines are auto-filtered; raw responses saved as <code>*_debug_raw.txt</code>.
</details>

<details>
<summary><b>Q: 如何保护 API Key 不泄露？How to keep API key secure?</b></summary>
务必使用环境变量 <code>DEEPSEEK_API_KEY</code>，不要硬编码在代码中。<code>.env</code> 文件已在 <code>.gitignore</code> 中排除。Always use the env var, never hardcode. <code>.env</code> is gitignored.
</details>

---

## Requirements / 依赖

```
pypdf>=3.0.0      # PDF 文本提取
openai>=1.0.0     # DeepSeek API (OpenAI 兼容)
pyyaml>=6.0       # 学科配置解析 / YAML config
jinja2>=3.0       # Prompt 模板渲染
```

---

## License / 许可

MIT — 自由使用、修改、分发。Feel free to use, modify, and distribute.
