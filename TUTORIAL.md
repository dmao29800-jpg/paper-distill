# Paper Distill 使用教程

从零开始，把论文 PDF 变成大模型训练数据。

---

## 目录

1. [准备工作](#1-准备工作)
2. [安装](#2-安装)
3. [第一次运行](#3-第一次运行)
4. [检查输出质量](#4-检查输出质量)
5. [批量处理](#5-批量处理)
6. [自定义学科](#6-自定义学科)
7. [常见问题](#7-常见问题)

---

## 1. 准备工作

### 1.1 安装 Python

需要 Python 3.9 或以上。

```powershell
# 检查是否已安装
python --version
```

如果没装：[python.org](https://www.python.org/downloads/) 下载，安装时**勾选 "Add Python to PATH"**。

### 1.2 获取 DeepSeek API Key

1. 打开 [platform.deepseek.com](https://platform.deepseek.com)
2. 注册 / 登录
3. 点击 **API Keys** → **创建 API Key**
4. 复制密钥（格式：`sk-xxxxxxxx`）

> 费用极低：处理 100 篇论文约 ¥1.5

### 1.3 设置环境变量（一次性，永久生效）

```powershell
# Windows PowerShell 管理员模式
setx DEEPSEEK_API_KEY "sk-你的密钥"
```

设置后**重启终端**生效。验证：

```powershell
echo %DEEPSEEK_API_KEY%
# 应该显示 sk-xxx...
```

> 不设置的话，每次运行都要加 `--api-key` 参数，麻烦且不安全。

---

## 2. 安装

### 2.1 下载项目

```powershell
git clone https://github.com/dmao29800-jpg/paper-distill.git
cd paper-distill
```

### 2.2 安装依赖

```powershell
pip install -r requirements.txt
```

安装内容：`pypdf`（PDF 提取）、`openai`（API 调用）、`pyyaml`（配置）、`jinja2`（模板）。

---

## 3. 第一次运行

建议先拿 **3-5 篇** 试试水。

### 3.1 准备论文

找一个文件夹，放入 PDF 论文。例如：

```
C:\papers\
  ├── 深基坑开挖对邻近隧道的影响研究_张三.pdf
  ├── 纤维混凝土力学性能研究_李四.pdf
  └── 钢-混凝土组合梁疲劳性能试验研究_王五.pdf
```

### 3.2 先看看会被识别成什么学科

```powershell
python cli.py -i C:\papers -o C:\papers\output --dry-run --classify
```

输出示例：

```
MTT20195602_19.pdf → 土木工程(主,12) + 结构工程(10) + 机械工程(7)
```

### 3.3 正式运行

```powershell
python cli.py -i C:\papers -o C:\papers\output -c 3
```

参数说明：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-i` | PDF 输入文件夹 | 必填 |
| `-o` | 输出文件夹 | 必填 |
| `-c` | 并发数（1-5） | 1 |
| `-n` | 最多处理几篇 | 全部 |
| `-d` | 指定学科 | auto（自动） |
| `--no-clean` | 保留中间文件 | 不保留 |

### 3.4 查看结果

运行完成后，输出文件夹里只有 `.txt` 文件（JSONL 格式）：

```
C:\papers\output\
  ├── 深基坑开挖对邻近隧道的影响研究_张三.txt
  ├── 纤维混凝土力学性能研究_李四.txt
  └── 钢-混凝土组合梁疲劳性能试验研究_王五.txt
```

每个文件长这样：

```
# 学科归属：土木工程（主）
{"input":"在软土地区进行深基坑开挖时，如何评估其对邻近既有隧道的影响？","output":"可通过数值模拟方法建立三维模型...","doc_id":"深基坑开挖对邻近隧道的影响研究","type":"分析类"}
{"input":"深基坑开挖对邻近隧道的影响主要受哪些因素控制？","output":"主要受基坑与隧道的相对位置、基坑开挖深度...","doc_id":"深基坑开挖对邻近隧道的影响研究","type":"因果类"}
```

第一行 `#` 开头是学科标注。后面每行一个 JSON，四个字段：`input`、`output`、`doc_id`、`type`。

---

## 4. 检查输出质量

### 4.1 看 doc_id 对不对

doc_id 必须**逐字等于论文标题**，不是 PDF 文件名，更不能是 AI 编造的。

```powershell
# 快速抽查：看每篇的第一条 sample 的 doc_id
python -c "
import json, glob
for f in glob.glob('C:/papers/output/*.txt'):
    with open(f, encoding='utf-8') as fp:
        fp.readline()  # skip header
        obj = json.loads(fp.readline())
        print(f'{obj[\"doc_id\"]}')
"
```

### 4.2 看有没有数值泄漏

在输出文件夹中搜索数字：

```powershell
# Windows PowerShell
Get-ChildItem C:\papers\output\*.txt | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    if ($content -match '\d+\.\d+') {
        Write-Host "WARNING: $($_.Name) contains numbers"
    }
}
```

如果 strict 模式下出现 `52.4`、`136.8%` 这类数值，说明脱敏失效。检查 `configs/disciplines.yaml` 中该学科的 `numeric_policy` 是否设为了 `strict`。

### 4.3 看覆盖是否均匀

统计输出样本的类型分布：

```powershell
python -c "
import json, glob
from collections import Counter
types = Counter()
for f in glob.glob('C:/papers/output/*.txt'):
    with open(f, encoding='utf-8') as fp:
        fp.readline()
        for line in fp:
            obj = json.loads(line.strip())
            types[obj['type']] += 1
for t, c in types.most_common():
    print(f'  {t}: {c}')
"
```

理想状态：解释/分析/因果类占比较高（≥70%），建议/对策类不过半。

---

## 5. 批量处理

### 5.1 200 篇一次性跑

```powershell
python cli.py -i C:\papers -o C:\papers\output -c 3
```

预计：
- 并发 3：~25 分钟
- 并发 5：~15 分钟
- 费用：~¥1.5

### 5.2 中断了怎么办

重新运行**完全相同的命令**。已处理成功的论文会自动跳过（通过 `progress.json` 断点续传）。

```powershell
# 中断后重新跑
python cli.py -i C:\papers -o C:\papers\output -c 3
# 自动跳过已完成的，只处理剩下的
```

> `progress.json` 会在全部完成后自动删除。需要保留用 `--no-clean`。

### 5.3 只跑前 100 篇（测试用）

```powershell
python cli.py -i C:\papers -o C:\papers\output -c 3 -n 100
```

---

## 6. 自定义学科

编辑 `configs/disciplines.yaml`。比如添加"海洋工程"：

```yaml
disciplines:
  ocean_engineering:
    domain: "海洋工程"
    keywords:
      high: [海洋平台, 立管, 系泊, 波浪荷载]     # +3 分
      medium: [水深, 浮式, 导管架, 水下, 海流]    # +1 分
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
- **high**：该学科独有，不会跟其他学科混淆
- **medium**：该学科常用，可能与其他学科有交叉

---

## 7. 常见问题

### Q: 论文文本提取为空？

部分扫描版 PDF 不含文本层。用 OCR（如 Tesseract）预处理。

### Q: 自动分类不准？

两种办法：
1. 手动指定：`python cli.py -i ... -o ... -d physics`
2. 补充关键词：编辑 `configs/disciplines.yaml`，给对应学科加 high/medium 关键词

### Q: API 报错？

```
降低并发：-c 1
检查余额：platform.deepseek.com → 用量
检查网络：ping api.deepseek.com
```

### Q: 生成的样本格式不对？

无效行在解析时自动过滤。如果某篇论文全部无效，原始 API 响应会保存为 `*_debug_raw.txt`（仅在 `--no-clean` 模式下保留）。

### Q: 想保留日志排查问题？

```powershell
python cli.py -i ... -o ... --no-clean
```

### Q: 学科只有一个标签，但我觉得应该有多个？

编辑 `configs/disciplines.yaml`，给次要学科加 medium 关键词。多标签规则：分数 ≥ 主学科 50% 且 ≥ 阈值 5 才会被纳入。

---

## 附录：命令速查表

```powershell
# 预览分类
python cli.py -i ./papers -o ./out --dry-run --classify

# 自动检测 + 并发 3
python cli.py -i ./papers -o ./out -c 3

# 手动指定学科
python cli.py -i ./papers -o ./out -d materials_science

# 前 50 篇 + 并发 5
python cli.py -i ./papers -o ./out -c 5 -n 50

# 看所有学科
python cli.py --list-disciplines

# 保留日志
python cli.py -i ./papers -o ./out -c 3 --no-clean
```
