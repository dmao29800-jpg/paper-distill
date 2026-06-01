"""Prompt builder with Jinja2 templates and YAML discipline configs."""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# -- Default template (bundled, no Jinja2 dependency needed for basic use) --
DEFAULT_TEMPLATE = """你是一名"{{ domain }}"领域的数据工程师。基于我提供的论文文本（仅含摘要与正文），请生成用于 LoRA/SFT 的监督样本，输出为 JSONL，每行一个 JSON 对象，字段仅包括：

{% if cross_disciplinary_note %}
【交叉学科提示】{{ cross_disciplinary_note }}
{% endif %}

input：问题或指令（中文）

output：回答（中文；必须可由所给摘要/正文概括推得，不得杜撰）

doc_id：论文名字

type：从下列集合中选择或细化（中文标签即可）：
{{ type_labels | join('/') }}

{% if numeric_policy == "strict" %}
【最高优先级约束：严禁具体数值——每条输出前必须逐条自检】
output 中严禁出现以下任何内容：
- 具体数字（如 0.868、9.035%、6.35、1.5、0.23D、50%）
- 数值范围（如 1.5~6.35 倍）
- 数学符号与公式（如 R²、σ、μ）
- 专用模型/方法昵称（如 CSM 模型、Duncan–Chang、Peck 公式{% if forbidden_names %}{% for n in forbidden_names %}、{{ n }}{% endfor %}{% endif %}）
- 具体单位组合（如 0.23D、6.35 倍、9.9103%）
正确做法：全部改写为模糊化通用表述，例如"存在一定倍数关系""超过典型阈值""具有较高相关度""在特定范围内产生影响""某经验公式""数值模拟软件""非线性本构模型"。
{% elif numeric_policy == "contextual" %}
数值处理原则：原文中有明确依据时可引用关键数值，但避免罗列大量数据；没有依据时概括为"一定范围内""超过典型阈值"等通用表述。
{% endif %}

强约束（务必全部满足）

只用摘要与正文内容；不得引入外部知识、参考文献、公式编号、图表编号、URL/DOI、年份等。

禁止出现任何人名/机构名/项目名/品牌与商标/具体软件名/化学商品名。
{% if forbidden_names %}
特别注意禁止以下专用名称：{% for n in forbidden_names %}{{ n }}{% if not loop.last %}、{% endif %}{% endfor %}。一律改为"某研究""数值模拟软件""经验公式"等通用表述。
{% endif %}

doc_id必须是论文的中文名称而不是编号的pdf文件名

一律改写为通用表述：例如
{% if generic_examples %}
{% for ex in generic_examples %}
"{{ ex }}"等。
{% endfor %}
{% else %}
"某研究/既有研究/相关研究表明/数值模拟软件/非线性本构模型"等。
{% endif %}

禁止"X等""Author et al."等具体名称。

去重与多样性：output 之间不得高度相似；input 的提问风格多样（工程口语/学术/场景化/步骤化）。

仅输出 JSONL，UTF-8，不要任何解释、前后缀或代码框。

【绝对约束：数量目标】务必首先尝试生成 {{ target_samples }} 条监督样本。只有在论文内容极度不足时，才可以低于 {{ min_samples }} 条。请勿在内容充足时保守输出。
若文本信息不足以生成 {{ target_samples }} 条，宁少勿编，只输出可保证依据的条数。同时请使用纯文本进行对话。

类型覆盖建议（可按文本实际灵活分配）
{% for rule in type_distribution %}
{{ rule }}
{% endfor %}

合规自检（逐条检查，不合规则重写）

是否出现任何中文/英文人名？（如"贺××/Wang/Smith"等）→ 重写为"某研究"。

是否出现任何品牌/软件/化学商品名？→ 改为通用类别名。
{% if forbidden_names %}
是否出现 {{ ', '.join(forbidden_names) }} 等专用名称？→ 改为通用描述。
{% endif %}

是否出现外链/DOI/年份/图表编号？→ 删除或概括。

{% if numeric_policy == "strict" %}
是否出现任何具体数字、百分比、小数、范围值？→ 改写为"一定范围内""显著影响""超过阈值"等模糊表述。

是否出现任何专用模型/方法昵称？→ 改为通用描述（"经验公式""本构模型""数值模拟方法"）。
{% endif %}

output 是否能在摘要/正文中找到依据或原理？若否→重写或删除。

与已有样本是否高度重复？若是→重述或更换角度。

输出格式（示例，仅示范结构，实际不要输出本行）
{{ output_example }}

论文文件名：{paper_filename}

论文内容如下：
{paper_text}"""


class PromptBuilder:
    """Build discipline-specific prompts from YAML config + Jinja2 template."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Args:
            config_path: Path to disciplines.yaml. If None, uses bundled default.
        """
        self._config = {}
        self._template_str = DEFAULT_TEMPLATE
        self._jinja2_available = False

        # Try loading Jinja2 for advanced template features
        try:
            from jinja2 import Template
            self._Template = Template
            self._jinja2_available = True
        except ImportError:
            logger.debug("Jinja2 not installed, using str.replace() fallback")
            self._Template = None

        # Load config
        if config_path and config_path.exists():
            self._load_config(config_path)

    def _load_config(self, config_path: Path):
        """Load discipline configs from YAML file."""
        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML not installed — install it for YAML support")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._config = data.get("disciplines", {})
        logger.info(f"Loaded {len(self._config)} disciplines from {config_path}")

    @property
    def disciplines(self) -> list[str]:
        """List available discipline names."""
        return list(self._config.keys())

    def build(self, discipline = "generic",
              paper_filename: str = "{paper_filename}",
              paper_text: str = "{paper_text}") -> str:
        """
        Build a complete prompt for the given discipline(s).

        Args:
            discipline: Single discipline key (str) or list of keys for
                        cross-disciplinary papers.
            paper_filename: PDF filename for identification.
            paper_text: Extracted paper full text.

        Returns:
            The complete prompt string with all placeholders resolved.
        """
        if isinstance(discipline, list) and len(discipline) > 1:
            # Multi-discipline: merge configs and build cross-disciplinary note
            merged_cfg = self._merge_configs(discipline)
            params = dict(self._default_params(discipline[0]))
            params.update(merged_cfg)
            params["cross_disciplinary_note"] = self._build_cross_disciplinary_note(discipline)
        else:
            # Single discipline (str or single-element list)
            key = discipline[0] if isinstance(discipline, list) else discipline
            cfg = self._config.get(key, {})
            params = dict(self._default_params(key))
            params.update(cfg)
            params["cross_disciplinary_note"] = ""

        if self._jinja2_available:
            template = self._Template(self._template_str)
            prompt = template.render(**params)
        else:
            prompt = self._template_str
            # Simple variable substitution
            for key, value in params.items():
                if isinstance(value, list):
                    value = "\n".join(str(v) for v in value)
                prompt = prompt.replace(f"{{{{{{ key }}}}}}", str(value))

        # Handle conditional blocks in non-Jinja2 mode
        prompt = self._strip_jinja_blocks(prompt, params)

        return prompt

    def _merge_configs(self, discipline_keys: list[str]) -> dict:
        """
        Merge config entries for multiple disciplines into a single prompt context.

        Merge rules:
          - domain: join via "与" (2) or "、"+"与" (3+)
          - numeric_policy: "strict" if ANY discipline is strict
          - forbidden_names: sorted union (deduplicated)
          - type_labels: union preserving first-seen order
          - generic_examples: union preserving first-seen order
          - target_samples / min_samples: maximum across all
          - type_distribution: concatenated

        Returns a dict with the same shape as a single YAML discipline entry.
        """
        merged: dict = {
            "domain": "",
            "numeric_policy": "contextual",
            "forbidden_names": [],
            "generic_examples": [],
            "type_labels": [],
            "target_samples": 0,
            "min_samples": 0,
            "type_distribution": [],
        }

        domains = []
        seen_names: set = set()
        seen_labels: set = set()
        seen_examples: set = set()

        for key in discipline_keys:
            cfg = self._config.get(key, {})
            if not cfg:
                continue

            # Domain
            dom = cfg.get("domain", key.replace("_", " ").title())
            domains.append(dom)

            # Numeric policy: any strict → strict
            if cfg.get("numeric_policy") == "strict":
                merged["numeric_policy"] = "strict"

            # Forbidden names: union with dedup
            for n in cfg.get("forbidden_names", []):
                if n not in seen_names:
                    seen_names.add(n)
                    merged["forbidden_names"].append(n)

            # Type labels: union preserving order
            for lb in cfg.get("type_labels", []):
                if lb not in seen_labels:
                    seen_labels.add(lb)
                    merged["type_labels"].append(lb)

            # Generic examples: union preserving order
            for ex in cfg.get("generic_examples", []):
                if ex not in seen_examples:
                    seen_examples.add(ex)
                    merged["generic_examples"].append(ex)

            # Target / min samples: take max
            merged["target_samples"] = max(
                merged["target_samples"], cfg.get("target_samples", 0)
            )
            merged["min_samples"] = max(
                merged["min_samples"], cfg.get("min_samples", 0)
            )

            # Type distribution: concatenate
            for rule in cfg.get("type_distribution", []):
                merged["type_distribution"].append(rule)

        # Build domain string
        if len(domains) == 1:
            merged["domain"] = domains[0]
        elif len(domains) == 2:
            merged["domain"] = f"{domains[0]}与{domains[1]}"
        else:
            merged["domain"] = "、".join(domains[:-1]) + f"与{domains[-1]}"

        # Sort forbidden_names for consistency
        merged["forbidden_names"].sort()

        # Provide defaults if nothing was found
        if not merged["type_labels"]:
            merged["type_labels"] = [
                "解释类", "分析类", "比较类", "评价类", "建议类",
                "流程类", "因果类", "定义类", "对策类", "分类类",
                "决策类", "纠错类", "多证据分析类", "风险类",
            ]
        if merged["target_samples"] == 0:
            merged["target_samples"] = 40
        if merged["min_samples"] == 0:
            merged["min_samples"] = 30

        return merged

    def _build_cross_disciplinary_note(self, discipline_keys: list[str]) -> str:
        """
        Build a note instructing the model to cover multiple disciplines.

        Example:
          本文涉及多个学科领域：土木工程（主）、材料科学。
          请在生成样本时覆盖各学科的视角，合理分配不同学科类型的问题，
          确保每个学科领域均有对应的监督样本产出。
        """
        domains = []
        for i, key in enumerate(discipline_keys):
            cfg = self._config.get(key, {})
            dom = cfg.get("domain", key.replace("_", " ").title())
            if i == 0:
                domains.append(f"{dom}（主）")
            else:
                domains.append(dom)

        fields_str = "、".join(domains)
        return (
            f"本文涉及多个学科领域：{fields_str}。"
            f"请在生成样本时覆盖各学科的视角，合理分配不同学科类型的问题，"
            f"确保每个学科领域均有对应的监督样本产出。"
        )

    def _strip_jinja_blocks(self, text: str, params: dict) -> str:
        """Remove Jinja2 control blocks when running without Jinja2.
        Simple approach: keep if/endif content when condition is truthy, strip otherwise."""
        import re

        # Handle {% if %}...{% endif %} blocks (simple cases)
        def replacer(match):
            condition = match.group(1).strip()
            content = match.group(2)
            should_keep = False

            if "cross_disciplinary_note" in condition:
                should_keep = bool(params.get("cross_disciplinary_note"))
            elif "numeric_policy == \"strict\"" in condition:
                should_keep = params.get("numeric_policy") == "strict"
            elif "numeric_policy == \"contextual\"" in condition:
                should_keep = params.get("numeric_policy") == "contextual"
            elif "forbidden_names" in condition:
                names = params.get("forbidden_names", [])
                should_keep = bool(names)
            else:
                should_keep = True  # default: keep

            return content if should_keep else ""

        text = re.sub(
            r'\{%\s*if\s+(.*?)\s*%\}(.*?)\{%\s*endif\s*%\}',
            replacer, text, flags=re.DOTALL
        )

        # Remove remaining {% %} and {{ }} tags (simple approach)
        text = re.sub(r'\{%\s*for\s+.*?\s*%\}', '', text)
        text = re.sub(r'\{%\s*endfor\s*%\}', '', text)
        text = re.sub(r'\{\{\s*\w+\.\w+\(.*?\)\s*\}\}', '', text)
        text = re.sub(r'\{\{\s*\w+\(.*?\)\s*\}\}', '', text)

        return text

    @staticmethod
    def _default_params(discipline: str) -> dict:
        """Default parameters for a generic discipline."""
        return {
            "domain": discipline.replace("_", " ").title(),
            "cross_disciplinary_note": "",
            "type_labels": [
                "解释类", "分析类", "比较类", "评价类", "建议类",
                "流程类", "因果类", "定义类", "对策类", "分类类",
                "决策类", "纠错类", "多证据分析类", "风险类",
            ],
            "numeric_policy": "strict",
            "forbidden_names": [],
            "generic_examples": [],
            "target_samples": 40,
            "min_samples": 30,
            "type_distribution": [
                "解释/定义/因果 ≥ 40%",
                "分析/比较/评价 ≥ 30%",
                "建议/对策/流程/决策/风险 ≤ 30%",
            ],
            "output_example": (
                '{"input":"为什么在曲线中会出现两个峰值？",'
                '"output":"首次峰值对应比例极限，来源于基体与纤维的弹性粘结；'
                '二次峰值出现在一定裂口宽度处，源于弯钩锚固充分发挥所致的再承载能力提升。",'
                '"doc_id":"钢纤维混凝土试验及单轴抗拉本构模型研究","type":"因果类"}'
            ),
        }
