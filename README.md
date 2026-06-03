# Paper Distill / 论文蒸馏

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![GitHub stars](https://img.shields.io/github/stars/dmao29800-jpg/paper-distill?style=social)](https://github.com/dmao29800-jpg/paper-distill)
[![GitHub forks](https://img.shields.io/github/forks/dmao29800-jpg/paper-distill?style=social)](https://github.com/dmao29800-jpg/paper-distill)

---

```
100 篇论文 PDF                         25 分钟
    ↓                                    ↓
  拖进去  ─────────────────────────→  4001 条 SFT 训练样本
                                           ↓
                                    成本约 ¥1.5
```

> 从学术论文 PDF 到高质量 SFT 微调数据，全自动。没有具体数值泄漏，不变成背答案的鹦鹉。
>
> Academic PDFs → SFT training data. Fully automated. No numerical leakage. No parroting.

---

### 🔗 配套工具

> 没有论文 PDF？用 **[CNKI Harvest](https://github.com/dmao29800-jpg/cnki-harvest)** 从知网自动搜索+筛选+下载，输出直接对接 Paper Distill。

---

## 为什么这个工具不一样？

### 市面上大部分 PDF→QA 工具，有一个没人谈的问题

一篇材料论文里写：*"抗压强度 = 52.4 MPa"*

普通工具直接把它变成一个 QA 对：

```jsonl
{"input": "该材料的抗压强度是多少？", "output": "52.4 MPa", "doc_id": "…", "type": "解释类"}
```

微调后，你的模型就成了一个**背诵答案的数据库**——它记住了 52.4，但完全不理解"为什么是 52.4"。

### 我们做的事：事实记忆 → 知识抽象

```
论文原文：抗压强度在掺量0.3%时达到52.4MPa，较对照组提升136.8%

普通工具生成：  "抗压强度是多少？" → "52.4MPa"          ← 背答案

Paper Distill：  "纤维掺量对抗压强度有何影响规律？"         ← 理解规律
                 → "抗压强度随纤维掺量增加呈先升后降趋势，
                    存在最优掺量范围，超过该范围后分散性
                    增大导致强度回落。"
```

**Strict 模式下，prompt 的第一优先级不是"生成更多数据"，而是"严禁任何具体数值"：**

```
【最高优先级约束：严禁具体数值】
output 中严禁出现：
- 具体数字（0.868、9.035%、6.35、1.5）
- 数值范围（1.5~6.35 倍）
- 数学符号与公式（R²、σ、μ）
- 专用模型/方法昵称（CSM 模型、Duncan–Chang、Peck 公式）
- 具体单位组合（0.23D、6.35 倍）

正确做法：全部改写为模糊化通用表述——
  "存在一定倍数关系"
  "超过典型阈值"
  "具有较高相关度"
  "在特定范围内产生影响"
```

> 这背后是一个有研究味道的方向：**如何让 LLM 从论文中学到抽象的领域知识，而不是简单地记住数字？**

---

## 效果一览

| 指标 | 数值 |
|------|------|
| 200 篇实测成功率 | **100%** |
| 200 篇总样本数 | **4001 条** |
| 数值泄漏 | **0 条** |
| 单篇耗时 | 15–30 秒 |
| 单篇成本 | ~¥0.015 |
| 100 篇总耗时 (并发3) | ~25 分钟 |
| 100 篇总成本 | ~¥1.5 |

---

## 功能

| 功能 | 说明 |
|------|------|
| 🧠 **自动学科识别** | 20 个理工科预设，扫描论文关键词自动匹配，逐篇识别 1-3 个学科标签 |
| 🔒 **数值自动脱敏** | strict（严禁数值）/ contextual（允许引用）两种策略，按学科配置 |
| 🏷️ **交叉学科** | 一篇论文可标注多个学科（如"土木工程 + 材料科学"），prompt 会覆盖各学科视角 |
| ⚡ **并发处理** | ThreadPoolExecutor，`-c 3` 即可三篇同时处理 |
| 💾 **断点续传** | 中断后重新运行自动跳过已完成论文 |
| 🧹 **自动清理** | 跑完只保留 JSONL 数据文件，中间产物自动删除 |

---

## 安装

### 🖥️ Web 界面（最简单）

```bash
git clone https://github.com/dmao29800-jpg/paper-distill.git
cd paper-distill
pip install -r requirements.txt gradio
python webui.py
```

浏览器打开 `http://127.0.0.1:7860`，拖拽 PDF → 点按钮 → 下载 JSONL。零命令行。

### Claude Code Skill

```bash
/skill install github.com/dmao29800-jpg/paper-distill
```

安装后对 Claude 说"帮我把这 50 篇论文蒸馏成 SFT 数据"即可。

### 命令行

```bash
git clone https://github.com/dmao29800-jpg/paper-distill.git
cd paper-distill
pip install -r requirements.txt
python cli.py -i ./papers -o ./output -c 3
```

---

## 快速开始

```bash
# 设置 API Key（一次性）
# Windows: setx DEEPSEEK_API_KEY sk-你的key
# macOS/Linux: export DEEPSEEK_API_KEY=sk-你的key

# 自动识别学科，并发 3
python cli.py -i ./papers -o ./output -c 3

# 预览每篇论文的分类结果
python cli.py -i ./papers -o ./output --dry-run --classify -n 20

# 手动指定学科
python cli.py -i ./papers -o ./output -d materials_science

# 查看所有支持的学科
python cli.py --list-disciplines
```

---

## 两种脱敏策略

| 策略 | 适用学科 | 规则 |
|------|---------|------|
| **strict** | 土木、结构、环境、生物医学、航空航天等 | 严禁任何具体数值、公式、模型名、软件名 |
| **contextual** | 材料、化学、物理、计算机等 | 关键数值可引用原文，但需有明确依据，避免罗列 |

strict 学科特征：实验数据密集、规范性强、数值一旦泄漏就会让模型变成"翻书器"。

---

## 支持的学科（20 个）

| | 学科 | Key | 脱敏 |
|---|------|-----|:--:|
| 🏗️ | 土木工程 | `civil_engineering` | strict |
| 🏛️ | 结构工程 | `structural_engineering` | strict |
| 🏢 | 建筑与城市规划 | `architecture_urban` | contextual |
| ⚙️ | 机械工程 | `mechanical_engineering` | contextual |
| ✈️ | 航空航天 | `aerospace` | strict |
| 🔬 | 材料科学与工程 | `materials_science` | contextual |
| ⚗️ | 化学工程 | `chemical_engineering` | contextual |
| 🧪 | 化学 | `chemistry` | contextual |
| ⚡ | 电气工程 | `electrical_engineering` | contextual |
| 📟 | 电子科学与技术 | `electronics` | contextual |
| 💻 | 计算机科学 | `computer_science` | contextual |
| 🎛️ | 控制科学与工程 | `control_automation` | contextual |
| 🔭 | 物理学 | `physics` | contextual |
| 📐 | 数学 | `mathematics` | contextual |
| 🌍 | 环境科学与工程 | `environmental_science` | strict |
| 🔋 | 能源与动力工程 | `energy_power` | contextual |
| 🚆 | 交通运输工程 | `transportation` | contextual |
| 🌊 | 水利工程 | `hydrology_water` | contextual |
| ⛰️ | 地质与地球物理 | `geology_geophysics` | contextual |
| 🧬 | 生物医学 | `biology_medicine` | strict |
| 📦 | 通用（兜底） | `generic` | contextual |

---

## 自动学科识别原理

扫描论文前 30,000 字符，与各学科关键词库匹配。高权重词 +3 分，中权重词 +1 分。取最高分学科（≥ 阈值 5），同时纳入分数 ≥ 主学科 50% 的学科，最多 3 个标签。

```
MTT20195602_19.pdf → 土木工程(主,12) + 结构工程(10) + 机械工程(7)
共价有机框架材料...pdf → 化学(主,22) + 化学工程(21) + 材料科学与工程(13)
```

---

## 输出格式

每篇论文 → 一个 `.txt` 文件，首行为学科标注，后续为 JSONL：

```
# 学科归属：土木工程（主）、材料科学
{"input":"纤维掺量对抗压强度有何影响规律？","output":"抗压强度随纤维掺量增加呈先升后降趋势...","doc_id":"纤维混凝土力学性能研究","type":"因果类"}
```

---

## Python API

```python
from engine import Pipeline, PromptBuilder, DeepSeekClient, DisciplineClassifier
from pathlib import Path
import os

config = Path("configs/disciplines.yaml")
client = DeepSeekClient(api_key=os.environ["DEEPSEEK_API_KEY"])
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

---

## 自定义学科

编辑 `configs/disciplines.yaml`：

```yaml
disciplines:
  ocean_engineering:
    domain: "海洋工程"
    keywords:
      high: [海洋平台, 立管, 系泊, 波浪荷载]        # +3 分
      medium: [水深, 浮式, 导管架, 水下, 腐蚀]       # +1 分
    numeric_policy: strict
    forbidden_names: [SACS, OrcaFlex, SESAM]
    type_labels:
      - 解释类/分析类/比较类/评价类
      - 设计类/机理类/因果类/定义类
    target_samples: 40
    min_samples: 25
```

---

## 项目结构

```
paper-distill/
├── engine/
│   ├── pdf_extractor.py        # PDF 文本提取
│   ├── api_client.py           # DeepSeek API 封装 + 费用追踪
│   ├── jsonl_parser.py         # JSONL 解析 + 校验
│   ├── prompt_builder.py       # Jinja2 模板 + 学科渲染 + 脱敏
│   ├── classifier.py           # 关键词分类器 + 多标签
│   ├── checkpoint.py           # 断点续传
│   └── pipeline.py             # 主流水线 + 并发调度
├── configs/
│   └── disciplines.yaml        # 20 学科配置 + 关键词库
├── cli.py
├── requirements.txt
└── .gitignore
```

---

## FAQ

<details>
<summary><b>Q: 数值脱敏后，模型还能学到有用的知识吗？</b></summary>

能，而且学得更好。脱敏强制模型学习**规律和趋势**（"随掺量增加呈先升后降趋势"），而不是**数值记忆**（"52.4 MPa"）。前者是可迁移的领域知识，后者是背答案。
</details>

<details>
<summary><b>Q: 论文文本提取为空？</b></summary>
部分扫描版 PDF 不含文本层，pypdf 无法提取。可尝试 OCR 预处理。
</details>

<details>
<summary><b>Q: 自动分类不准？</b></summary>
手动指定 <code>-d civil_engineering</code>，或编辑 <code>disciplines.yaml</code> 补充关键词。
</details>

<details>
<summary><b>Q: API 频繁报错？</b></summary>
降低并发 <code>-c 1</code>，检查 API 余额，或确认网络可访问 api.deepseek.com。
</details>

---

## 依赖

```
pypdf>=3.0.0      # PDF 文本提取
openai>=1.0.0     # DeepSeek API (OpenAI 兼容)
pyyaml>=6.0       # 学科配置解析
jinja2>=3.0       # Prompt 模板渲染
```

## License

MIT — 自由使用、修改、分发。
