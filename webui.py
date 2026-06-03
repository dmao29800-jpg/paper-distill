#!/usr/bin/env python3
"""
Paper Distill Web UI — 浏览器上传论文，一键蒸馏。
Powered by Gradio.  Run: python webui.py
"""
import os
import sys
import json
import tempfile
import zipfile
import logging
import shutil
from pathlib import Path
from datetime import datetime

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

import gradio as gr

from engine.api_client import DeepSeekClient
from engine.prompt_builder import PromptBuilder
from engine.classifier import DisciplineClassifier
from engine.pipeline import Pipeline, AUTO

# ── Config ──────────────────────────────────────────────────
CONFIG_PATH = _SCRIPT_DIR / "configs" / "disciplines.yaml"
builder = PromptBuilder(CONFIG_PATH)
classifier = DisciplineClassifier(CONFIG_PATH)


# ── Core logic ──────────────────────────────────────────────
def process_papers(
    pdf_files,
    discipline_choice,
    concurrency,
    api_key,
    progress=gr.Progress(),
):
    """Main processing function called by Gradio."""
    if not pdf_files:
        return "请先上传 PDF 文件", None

    if not api_key or not api_key.strip():
        return "请输入 DeepSeek API Key", None

    api_key = api_key.strip()

    # Setup temp dirs
    work_dir = Path(tempfile.mkdtemp(prefix="paper_distill_"))
    input_dir = work_dir / "papers"
    output_dir = work_dir / "output"
    input_dir.mkdir()

    # Save uploaded files
    saved = []
    for f in progress.tqdm(pdf_files, desc="保存上传文件"):
        src = Path(f.name)
        dst = input_dir / src.name
        shutil.copy2(src, dst)
        saved.append(dst)

    # Classify first
    progress(0, desc="正在识别学科...")
    classify_lines = []
    for i, p in enumerate(saved):
        disc_list = classifier.classify_multi_from_pdf(p)
        if len(disc_list) == 1:
            classify_lines.append(f"{p.name} → {disc_list[0][1]} (score: {disc_list[0][2]:.0f})")
        else:
            primary = disc_list[0]
            extras = " + ".join(f"{n}({s:.0f})" for _, n, s in disc_list[1:])
            classify_lines.append(f"{p.name} → {primary[1]}(主,{primary[2]:.0f}) + {extras}")

    # Run pipeline
    api_client = DeepSeekClient(api_key)
    disc = discipline_choice if discipline_choice != "auto" else AUTO

    pipeline = Pipeline(
        input_dir=input_dir,
        output_dir=output_dir,
        api_client=api_client,
        prompt_builder=builder,
        discipline=disc,
        concurrency=int(concurrency),
        classifier=classifier if disc == AUTO else None,
    )

    progress(0.5, desc="正在蒸馏论文...")
    stats = pipeline.run()

    # Collect results
    progress(0.9, desc="打包结果...")
    zip_path = work_dir / "paper_distill_results.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for txt in sorted(output_dir.glob("*.txt")):
            zf.write(txt, txt.name)

    # Build report
    report = []
    report.append(f"## 处理完成")
    report.append(f"")
    report.append(f"| 指标 | 数值 |")
    report.append(f"|------|------|")
    report.append(f"| 论文数 | {stats['total']} |")
    report.append(f"| 成功 | {stats['success']} |")
    report.append(f"| 失败 | {stats['failed']} |")
    report.append(f"| 总样本 | {stats['total_samples']} |")
    report.append(f"| 耗时 | {stats.get('elapsed', 'N/A')} |")
    report.append(f"| API 费用 | ¥{api_client.total_cost:.4f} |")
    report.append(f"")
    report.append(f"### 学科识别结果")
    for line in classify_lines:
        report.append(f"- {line}")

    # Cleanup work dir
    shutil.rmtree(work_dir, ignore_errors=True)

    return "\n".join(report), str(zip_path) if zip_path.exists() else None


# ── UI ──────────────────────────────────────────────────────
with gr.Blocks(title="Paper Distill") as demo:
    gr.Markdown("""
    # 📚 Paper Distill / 论文蒸馏

    上传 PDF 论文 → 自动识别学科 → AI 生成 SFT 训练数据 → 下载 JSONL
    """)

    with gr.Row():
        with gr.Column(scale=2):
            files = gr.File(
                file_count="multiple",
                file_types=[".pdf"],
                label="拖拽 PDF 论文到此处",
                height=160,
            )

            with gr.Row():
                discipline = gr.Dropdown(
                    choices=["auto"] + sorted(classifier.names),
                    value="auto",
                    label="学科（auto=自动识别）",
                    scale=2,
                )
                concurrency = gr.Slider(
                    1, 5, value=3, step=1,
                    label="并发数",
                    scale=1,
                )

            api_key = gr.Textbox(
                label="DeepSeek API Key",
                type="password",
                placeholder="sk-... 或留空从环境变量 DEEPSEEK_API_KEY 读取",
                value=os.environ.get("DEEPSEEK_API_KEY", ""),
            )

            btn = gr.Button("开始蒸馏", variant="primary", size="lg")

        with gr.Column(scale=1):
            report = gr.Markdown("等待上传...")
            download = gr.File(label="下载结果 (ZIP)")

    btn.click(
        fn=process_papers,
        inputs=[files, discipline, concurrency, api_key],
        outputs=[report, download],
    )

    gr.Markdown("""
    ---
    **隐私说明**：所有文件在本地处理后自动删除，不上传任何服务器。
    """)


if __name__ == "__main__":
    print(f"\n  Paper Distill Web UI")
    print(f"  {'─' * 40}")
    print(f"  打开浏览器访问: http://127.0.0.1:7860")
    print(f"  按 Ctrl+C 停止\n")
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=True,
    )
