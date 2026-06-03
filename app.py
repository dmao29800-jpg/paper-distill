#!/usr/bin/env python3
"""
Paper Workshop — 论文蒸馏 Web 界面
拖拽 PDF → 自动蒸馏 → 下载 JSONL

Run: python app.py  →  http://127.0.0.1:7860
"""
import os, sys, json, time, tempfile, zipfile, shutil
from pathlib import Path
from datetime import datetime

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

import gradio as gr
import logging
logging.getLogger("paper_distill").setLevel(logging.WARNING)


def process(files, api_key, concurrency, progress=gr.Progress()):
    """Process uploaded PDFs → distill → return ZIP of JSONL."""
    key = (api_key or "").strip() or os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        yield "请先填写 API Key", None
        return
    if not files:
        yield "请先上传 PDF 文件", None
        return

    # Setup workspace
    work = Path(tempfile.mkdtemp(prefix="pw_"))
    pdf_dir = work / "pdfs"
    out_dir = work / "output"
    pdf_dir.mkdir()

    # Save uploaded files
    pdf_count = 0
    for f in files:
        src = Path(f.name)
        dst = pdf_dir / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
            pdf_count += 1

    if pdf_count == 0:
        yield "没有找到 PDF 文件", None
        return

    progress(0.1, desc=f"识别 {pdf_count} 篇论文学科...")

    # Import engine
    from engine.api_client import DeepSeekClient
    from engine.prompt_builder import PromptBuilder
    from engine.classifier import DisciplineClassifier
    from engine.pipeline import Pipeline, AUTO

    config = _SCRIPT_DIR / "configs" / "disciplines.yaml"
    client = DeepSeekClient(key)
    builder = PromptBuilder(config)
    classifier = DisciplineClassifier(config)

    # Classify and show
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    lines = [f"## 论文识别结果\n"]
    lines.append(f"| 论文 | 学科 |")
    lines.append(f"|------|------|")
    for p in pdfs:
        disc_list = classifier.classify_multi_from_pdf(p)
        if len(disc_list) == 1:
            lines.append(f"| {p.name[:50]} | {disc_list[0][1]} ({disc_list[0][2]:.0f}) |")
        else:
            extras = "+".join(n for _, n, _ in disc_list[1:])
            lines.append(f"| {p.name[:50]} | {disc_list[0][1]}(主) + {extras} |")

    progress(0.3, desc="蒸馏中...")

    # Distill
    pipeline = Pipeline(
        input_dir=pdf_dir,
        output_dir=out_dir,
        api_client=client,
        prompt_builder=builder,
        discipline=AUTO,
        concurrency=int(concurrency),
        classifier=classifier,
    )

    stats = pipeline.run()

    # Package
    progress(0.85, desc="打包...")
    zip_path = work / "results.zip"
    txt_files = sorted(out_dir.glob("*.txt"))
    if txt_files:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for txt in txt_files:
                zf.write(txt, txt.name)

    # Summary
    lines.append("")
    lines.append(f"## 蒸馏完成\n")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 论文 | {stats['total']} 篇 |")
    lines.append(f"| 成功 | {stats['success']} 篇 |")
    lines.append(f"| 失败 | {stats['failed']} 篇 |")
    lines.append(f"| 总样本 | {stats['total_samples']} 条 |")
    lines.append(f"| 耗时 | {stats.get('elapsed', 'N/A')} |")
    lines.append(f"| 费用 | ¥{client.total_cost:.4f} |")

    yield "\n".join(lines), str(zip_path) if zip_path.exists() else None

    # Cleanup
    shutil.rmtree(work, ignore_errors=True)


# ── UI ────────────────────────────────────────────────────
with gr.Blocks(title="论文工坊") as app:
    gr.Markdown("# 论文工坊 / Paper Workshop")
    gr.Markdown("上传 PDF 论文 → 自动蒸馏 → 下载 JSONL 训练数据")

    with gr.Row():
        with gr.Column(scale=1):
            upload = gr.File(
                file_count="multiple",
                file_types=[".pdf"],
                label="拖拽 PDF 论文到此处",
                height=200,
            )
            api_key = gr.Textbox(
                label="DeepSeek API Key",
                type="password",
                placeholder="sk-... 或从环境变量读取",
                value=os.environ.get("DEEPSEEK_API_KEY", ""),
            )
            concurrency = gr.Slider(1, 5, value=3, step=1, label="并发数")
            btn = gr.Button("开始蒸馏", variant="primary", size="lg")

        with gr.Column(scale=1):
            summary = gr.Markdown("等待上传...")
            download = gr.File(label="下载 JSONL (ZIP)")

    btn.click(
        fn=process,
        inputs=[upload, api_key, concurrency],
        outputs=[summary, download],
    )

    gr.Markdown("---\n")

    gr.Markdown("""
    ### 使用流程

    1. **获取 PDF**：在你自己的浏览器里，打开知网搜索 → 手动下载论文 PDF → 放到一个文件夹
    2. **拖到这里**：把 PDF 文件拖到上方区域
    3. **点按钮**：填 API Key，点"开始蒸馏"
    4. **下载结果**：ZIP 里是 JSONL 训练数据

    ---
    全部在本地处理，不上传任何数据。
    """)

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print("\n  Paper Workshop / 论文工坊")
    print("  http://127.0.0.1:7860")
    print("  Ctrl+C 停止\n")
    app.launch(server_name="127.0.0.1", server_port=7860,
               share=False, inbrowser=True)
