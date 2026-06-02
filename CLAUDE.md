# Paper Distill

从学术论文 PDF 批量生成大模型 SFT 微调训练数据。20 个理工科预设 + 自动学科识别 + 数值脱敏，调用 DeepSeek API。

Repository: https://github.com/dmao29800-jpg/paper-distill

## 触发条件

当用户提到以下关键词时调用此 Skill：
- "论文数据清洗" / "生成 SFT 数据" / "论文蒸馏" / "paper distill"
- "从论文提取 QA 对" / "论文知识提取"
- "批量处理论文" + "AI 训练数据" / "微调数据"

---

## 用户教程

### 1. 准备工作

- Python 3.9+：[python.org](https://www.python.org/downloads/)，安装时勾选 "Add Python to PATH"
- DeepSeek API Key：[platform.deepseek.com](https://platform.deepseek.com/api_keys) 注册获取
- 设置环境变量（一劳永逸，重启终端生效）：

```bash
# Windows
setx DEEPSEEK_API_KEY "sk-你的key"

# macOS / Linux
export DEEPSEEK_API_KEY=sk-你的key
```

验证：`echo %DEEPSEEK_API_KEY%` 应显示 `sk-xxx...`

### 2. 安装

```bash
git clone https://github.com/dmao29800-jpg/paper-distill.git
cd paper-distill
pip install -r requirements.txt
```

### 3. 第一次运行

建议先拿 3-5 篇试试水。

**预览分类：**

```bash
python cli.py -i ./papers -o ./output --dry-run --classify
```

输出示例：`论文.pdf → 土木工程(主,34) + 结构工程(10) + 机械工程(7)`

**正式处理：**

```bash
python cli.py -i ./papers -o ./output -c 3
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-i` | PDF 输入文件夹 | 必填 |
| `-o` | 输出文件夹 | 必填 |
| `-c` | 并发数 (1-5) | 1 |
| `-n` | 最多处理几篇 | 全部 |
| `-d` | 指定学科 | auto |
| `--dry-run --classify` | 仅预览分类 | — |
| `--no-clean` | 保留中间文件 | 自动清理 |
| `--list-disciplines` | 列出所有学科 | — |

**输出：** 每个 PDF 生成一个 `.txt` 文件（JSONL），首行 `#` 标注学科，后续每行一个 JSON，字段：`input`、`output`、`doc_id`、`type`。

### 4. 检查质量

**doc_id 是否逐字匹配：**

```bash
python -c "
import json, glob
for f in glob.glob('./output/*.txt'):
    with open(f, encoding='utf-8') as fp:
        fp.readline(); obj = json.loads(fp.readline())
        print(obj['doc_id'])
"
```

**统计类型分布：**

```bash
python -c "
import json, glob
from collections import Counter
types = Counter()
for f in glob.glob('./output/*.txt'):
    with open(f, encoding='utf-8') as fp:
        fp.readline()
        for line in fp: types[json.loads(line)['type']] += 1
for t, c in types.most_common(): print(f'  {t}: {c}')
"
```

理想：解释/分析/因果类 ≥70%，建议/对策类不过半。

### 5. 批量处理

```bash
python cli.py -i ./papers -o ./output -c 3          # 全部，并发3，~25min/100篇，~¥1.5
python cli.py -i ./papers -o ./output -c 5 -n 100   # 前100篇，并发5
```

**中断后恢复：** 重新运行相同命令，自动跳过已完成论文。

**手动指定学科：** `python cli.py -i ./papers -o ./output -d physics`

### 6. 自定义学科

编辑 `configs/disciplines.yaml`：

```yaml
disciplines:
  ocean_engineering:
    domain: "海洋工程"
    keywords:
      high: [海洋平台, 立管, 系泊, 波浪荷载]     # +3 分
      medium: [水深, 浮式, 导管架, 水下, 海流]    # +1 分
    numeric_policy: strict
    forbidden_names: [SACS, OrcaFlex]
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

关键词：`high` = 学科独有术语，`medium` = 常用但可能交叉的术语。

### 7. FAQ

| 问题 | 解决 |
|------|------|
| PDF 提取为空 | 扫描版 PDF 无文本层，需 OCR 预处理 |
| 分类不准 | 手动 `-d physics`，或补充 `disciplines.yaml` 关键词 |
| API 报错 | 降并发 `-c 1`，查余额，`ping api.deepseek.com` |
| 保留日志 | 加 `--no-clean` |
| 多标签太少 | 补充次要学科的 medium 关键词 |
| doc_id 不对 | 确保 PDF 文件名含论文标题（格式：`标题_作者.pdf`）|

---

## 命令速查

```bash
python cli.py -i ./papers -o ./out -c 3                # 自动识别 + 并发3
python cli.py -i ./papers -o ./out -d materials_science  # 指定学科
python cli.py -i ./papers -o ./out --dry-run --classify  # 预览分类
python cli.py -i ./papers -o ./out -c 3 -n 50           # 前50篇
python cli.py --list-disciplines                         # 列出学科
```

---

## 项目结构

```
paper-distill/
├── engine/
│   ├── pdf_extractor.py        # PDF 文本提取
│   ├── api_client.py           # DeepSeek API 封装 + 费用追踪
│   ├── jsonl_parser.py         # JSONL 解析 + 校验
│   ├── prompt_builder.py       # Jinja2 模板 + 学科 Prompt + 脱敏
│   ├── classifier.py           # 关键词分类器 + 多标签
│   ├── checkpoint.py           # 断点续传
│   └── pipeline.py             # 主流水线 + 并发调度
├── configs/
│   └── disciplines.yaml        # 20 学科配置 + 关键词库
├── cli.py                      # 命令行入口
├── README.md                   # 项目介绍
├── CLAUDE.md                   # 本文件
├── requirements.txt
└── .gitignore
```

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

## 依赖

```
pypdf>=3.0.0      # PDF 文本提取
openai>=1.0.0     # DeepSeek API (OpenAI 兼容)
pyyaml>=6.0       # 学科配置解析
jinja2>=3.0       # Prompt 模板渲染
```
