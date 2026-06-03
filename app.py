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
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Global ── */
.gradio-container {
    max-width: 1400px !important;
    margin: 0 auto !important;
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
}
body, .gradio-container {
    background: linear-gradient(160deg, #060b14 0%, #0a1322 30%, #0e1a2e 60%, #0b1628 100%) !important;
    color: #c8d6e5 !important;
}

/* ── Header ── */
.app-header {
    text-align: center;
    padding: 32px 0 8px 0;
    position: relative;
}
.app-header h1 {
    font-size: 2.4em;
    font-weight: 700;
    letter-spacing: 3px;
    background: linear-gradient(135deg, #00e5ff 0%, #00b0ff 40%, #7c4dff 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
    text-shadow: none;
}
.app-header .subtitle {
    color: #546e7a;
    font-size: 0.95em;
    letter-spacing: 2px;
    margin-top: 4px;
    text-transform: uppercase;
}

/* ── Glow line ── */
.glow-divider {
    width: 60%;
    height: 2px;
    margin: 16px auto 24px auto;
    background: linear-gradient(90deg, transparent, #00e5ff55, #7c4dff55, transparent);
    border-radius: 2px;
}

/* ── Cards ── */
.card-panel {
    background: linear-gradient(145deg, #0d1525cc, #101a2ecc);
    border: 1px solid #1e2d4a;
    border-radius: 14px;
    padding: 24px;
    margin-bottom: 16px;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255,255,255,0.03);
    transition: border-color 0.3s ease;
}
.card-panel:hover {
    border-color: #00e5ff33;
}
.card-label {
    font-size: 0.8em;
    color: #78909c;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid #1a2940;
}

/* ── File upload area ── */
.upload-zone {
    border: 2px dashed #1e3a5f !important;
    border-radius: 14px !important;
    background: linear-gradient(145deg, #0a1220dd, #0e182add) !important;
    transition: all 0.3s ease !important;
    min-height: 180px !important;
}
.upload-zone:hover, .upload-zone:focus-within {
    border-color: #00e5ff88 !important;
    box-shadow: 0 0 32px rgba(0, 229, 255, 0.08) !important;
}
.upload-zone label, .upload-zone .or, .upload-zone .icon {
    color: #607d8b !important;
}

/* ── Inputs ── */
input, textarea, select, .svelte-1f3546o {
    background: #0d1525 !important;
    border: 1px solid #1e3050 !important;
    border-radius: 8px !important;
    color: #c8d6e5 !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
input:focus, textarea:focus, select:focus {
    border-color: #00e5ff66 !important;
    box-shadow: 0 0 12px rgba(0, 229, 255, 0.06) !important;
    outline: none !important;
}

/* ── Slider ── */
.slider-track, input[type="range"] {
    accent-color: #00bcd4;
}
.slider input[type="range"]::-webkit-slider-thumb {
    background: #00e5ff;
    box-shadow: 0 0 10px rgba(0, 229, 255, 0.4);
}

/* ── Button ── */
button.primary, .lg.primary {
    width: 100% !important;
    padding: 22px 0 !important;
    font-size: 1.25em !important;
    font-weight: 700 !important;
    letter-spacing: 6px !important;
    border: none !important;
    border-radius: 12px !important;
    background: linear-gradient(135deg, #00e5ff 0%, #00bcd4 40%, #0091ea 100%) !important;
    color: #fff !important;
    cursor: pointer !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 28px rgba(0, 229, 255, 0.25), 0 0 60px rgba(0, 229, 255, 0.06) !important;
    position: relative !important;
    overflow: hidden !important;
}
button.primary:hover, .lg.primary:hover {
    background: linear-gradient(135deg, #00f0ff 0%, #00e5ff 40%, #00b0ff 100%) !important;
    box-shadow: 0 8px 40px rgba(0, 229, 255, 0.45), 0 0 80px rgba(0, 229, 255, 0.12) !important;
    transform: translateY(-2px) !important;
}
button.primary:active {
    transform: translateY(0) !important;
    box-shadow: 0 2px 16px rgba(0, 188, 212, 0.25) !important;
}
/* Scan line effect on button */
button.primary::after {
    content: '';
    position: absolute;
    top: 0; left: -100%;
    width: 200%; height: 100%;
    background: linear-gradient(90deg, transparent 40%, rgba(255,255,255,0.08) 50%, transparent 60%);
    animation: btn-scan 3s infinite;
}
@keyframes btn-scan {
    0% { left: -100%; }
    100% { left: 100%; }
}

/* ── Download box ── */
.download-box {
    border: 1px solid #1e3a20 !important;
    border-radius: 12px !important;
    background: #0a150dcc !important;
}

/* ── Labels ── */
label, .label-text, span.svelte-1gfkn6j {
    color: #78909c !important;
    font-weight: 500 !important;
    font-size: 0.88em !important;
    letter-spacing: 0.5px !important;
    text-transform: uppercase !important;
}

/* ── Markdown content ── */
.prose, .md, .markdown {
    color: #b0bec5 !important;
}
.prose h2, .md h2 {
    color: #00e5ff !important;
    font-weight: 600 !important;
}
.prose table, .md table {
    border-collapse: collapse !important;
    width: 100% !important;
}
.prose th, .md th {
    background: #0d1525 !important;
    color: #00bcd4 !important;
    border-bottom: 1px solid #1e3050 !important;
    padding: 8px 12px !important;
}
.prose td, .md td {
    border-bottom: 1px solid #0d1a2e !important;
    padding: 6px 12px !important;
}

/* ── Footer ── */
.app-footer {
    text-align: center;
    color: #37474f;
    font-size: 0.78em;
    letter-spacing: 1px;
    padding: 24px 0 8px 0;
    border-top: 1px solid #0d1a2e;
    margin-top: 24px;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0a1220; }
::-webkit-scrollbar-thumb { background: #1e3050; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #00e5ff44; }

/* ── Animation keyframes ── */
@keyframes pulse-glow {
    0%, 100% { box-shadow: 0 0 5px rgba(0,229,255,0.1); }
    50% { box-shadow: 0 0 20px rgba(0,229,255,0.2); }
}
"""

with gr.Blocks(title="Paper Workshop", css=CSS, theme=gr.themes.Base()) as app:

    # ── Header ──
    gr.HTML("""
    <div class="app-header">
        <h1>论文工坊</h1>
        <div class="subtitle">学术知识蒸馏引擎  ·  PDF  →  SFT 训练数据</div>
    </div>
    <div class="glow-divider"></div>
    """)

    with gr.Row():
        with gr.Column(scale=4):
            # Upload card
            gr.HTML('<div class="card-panel"><div class="card-label">  上传论文 PDF</div>')
            upload = gr.File(
                file_count="multiple",
                file_types=[".pdf"],
                label="拖拽文件到此处或点击上传",
                elem_classes=["upload-zone"],
                height=220,
            )
            gr.HTML('</div>')

            # Config card
            gr.HTML('<div class="card-panel"><div class="card-label">  蒸馏配置</div>')
            with gr.Row():
                with gr.Column(scale=3):
                    api_key = gr.Textbox(
                        label="DeepSeek API Key",
                        type="password",
                        placeholder="sk-... 或从环境变量 DEEPSEEK_API_KEY 读取",
                        value=os.environ.get("DEEPSEEK_API_KEY", ""),
                    )
                with gr.Column(scale=1):
                    concurrency = gr.Slider(
                        1, 5, value=3, step=1,
                        label="并发线程数",
                    )
            gr.HTML('</div>')

            # Button
            btn = gr.Button("开  始  蒸  馏", variant="primary", size="lg")

        with gr.Column(scale=3):
            # Results card
            gr.HTML('<div class="card-panel"><div class="card-label">  处理结果</div>')
            summary = gr.Markdown(
                "###  待命中\n\n"
                "上传论文 PDF 后点击「开始蒸馏」\n\n"
                "> 系统就绪，等待知识提取任务。"
            )
            gr.HTML('</div>')

            # Download card
            gr.HTML('<div class="card-panel"><div class="card-label">  结果下载</div>')
            download = gr.File(
                label="蒸馏完成后在此处下载 ZIP",
                elem_classes=["download-box"],
            )
            gr.HTML('</div>')

    btn.click(
        fn=process,
        inputs=[upload, api_key, concurrency],
        outputs=[summary, download],
    )

    # Footer
    gr.HTML("""
    <div class="app-footer">
        <div style="display: flex; justify-content: center; gap: 32px; flex-wrap: wrap;">
            <span>  PDF 提取</span>
            <span style="color: #1e3050;">|</span>
            <span>  学科识别</span>
            <span style="color: #1e3050;">|</span>
            <span>  知识蒸馏</span>
            <span style="color: #1e3050;">|</span>
            <span>  数值脱敏</span>
        </div>
        <div style="margin-top: 12px; color: #263238;">
            全部本地处理  |  不上传数据  |  MIT 开源
        </div>
    </div>
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
