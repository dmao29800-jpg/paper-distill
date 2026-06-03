#!/usr/bin/env python3
"""
Paper Workshop — 知网关键词搜索 + 下载 + 蒸馏 一站式
Run: python app.py  →  http://127.0.0.1:7860
"""
import os, sys, json, time, shutil, tempfile, zipfile, logging, threading
from pathlib import Path
from datetime import datetime

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

# ── cnki-harvest path ──────────────────────────────────────
_CNKI_DIR = _SCRIPT_DIR.parent / "cnki-harvest"
_HAS_CNKI = _CNKI_DIR.exists()
if _HAS_CNKI:
    sys.path.insert(0, str(_CNKI_DIR))

import gradio as gr
import yaml

# ── Helpers ────────────────────────────────────────────────
def _load_journals():
    """Load core journal list for --core filtering."""
    p = _CNKI_DIR / "configs" / "disciplines.yaml"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("core_journal_list", [])

_CORE_JOURNALS = _load_journals()


# ── Phase 1: Search CNKI ──────────────────────────────────
def phase_search(keywords: str, from_year: int, to_year: int,
                 core_only: bool, max_results: int) -> tuple:
    """Search CNKI. Returns (papers: list[dict] | None, error: str)."""
    kw = [k.strip() for k in keywords.replace("，", ",").split(",") if k.strip()]
    if not kw:
        return None, "请输入至少一个关键词"

    if not _HAS_CNKI:
        return None, "cnki-harvest 未安装（需要放在 paper-distill 同级目录）"

    try:
        from engine.searcher import search as cnki_search
    except ImportError as e:
        return None, f"加载 cnki-harvest 失败: {e}"

    journals = _CORE_JOURNALS if core_only else None
    try:
        papers = cnki_search(
            keywords=kw,
            from_year=from_year, to_year=to_year,
            core_only=core_only,
            core_journals=journals,
            max_results=max_results,
        )
    except Exception as e:
        return None, f"知网搜索失败: {e}"

    if not papers:
        return [], "未找到匹配论文，尝试换关键词或放宽年份"

    return papers, None


# ── Phase 2: Download PDFs ────────────────────────────────
def phase_download(papers: list[dict], output_dir: Path) -> tuple:
    """Download paper PDFs. Returns (ok: int, fail: int, log: list[str])."""
    log = []
    output_dir.mkdir(parents=True, exist_ok=True)

    if not _HAS_CNKI:
        log.append("[模拟] 未检测到 cnki-harvest，跳过下载")
        return 0, 0, log

    from engine.downloader import DownloadController
    from engine.checkpoint import Checkpoint

    ckpt = Checkpoint(output_dir / ".harvest_progress.json")
    ctrl = DownloadController(output_dir, ckpt)

    ok, fail = 0, 0
    total = len(papers)

    for i, p in enumerate(papers):
        title = p.get("title", f"paper-{i}")[:60]
        if ckpt.is_done(title):
            ok += 1
            continue

        try:
            result = ctrl.download(p)
            if result:
                ckpt.mark_done(title, "downloaded")
                ok += 1
                log.append(f"  [{i+1}/{total}] OK  {title}")
            else:
                ckpt.mark_done(title, "failed")
                fail += 1
                log.append(f"  [{i+1}/{total}] FAIL  {title}")
        except Exception as e:
            ckpt.mark_done(title, "failed")
            fail += 1
            log.append(f"  [{i+1}/{total}] ERR  {title}: {e}")

        ckpt.save()
        time.sleep(1.5)

    return ok, fail, log


# ── Phase 3: Distill ──────────────────────────────────────
def phase_distill(input_dir: Path, output_dir: Path,
                  api_key: str, concurrency: int) -> dict:
    """Run paper-distill pipeline."""
    from engine.api_client import DeepSeekClient
    from engine.prompt_builder import PromptBuilder
    from engine.classifier import DisciplineClassifier
    from engine.pipeline import Pipeline, AUTO

    config = _SCRIPT_DIR / "configs" / "disciplines.yaml"
    client = DeepSeekClient(api_key)
    builder = PromptBuilder(config)
    classifier = DisciplineClassifier(config) if config.exists() else None

    pipeline = Pipeline(
        input_dir=input_dir,
        output_dir=output_dir,
        api_client=client,
        prompt_builder=builder,
        discipline=AUTO,
        concurrency=concurrency,
        classifier=classifier,
    )
    return pipeline.run()


# ── Main Handler ──────────────────────────────────────────
def run(keywords, from_year, to_year, max_papers, core_only,
        api_key, concurrency, progress=gr.Progress()):
    """Generator: yield (status_msg, zip_path, log_text)."""

    # Validate
    key = (api_key or "").strip() or os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        yield "❌ 请输入 DeepSeek API Key", None, "[!] 缺少 API Key"
        return

    # Setup workspace
    work = Path(tempfile.mkdtemp(prefix="pw_"))
    pdf_dir = work / "pdfs"
    out_dir = work / "output"
    pdf_dir.mkdir()

    T = lambda: datetime.now().strftime("%H:%M:%S")
    log = []

    def add(msg):
        log.append(f"[{T()}] {msg}")

    add(f"关键词: {keywords}")
    add(f"年份: {from_year}-{to_year} | 核心: {core_only} | 最多: {max_papers}")
    yield None, None, "\n".join(log)

    # ── Phase 1: Search ──
    progress(0.05, desc="搜索知网...")
    add("正在搜索知网...")
    yield None, None, "\n".join(log)

    papers, err = phase_search(
        keywords, int(from_year), int(to_year),
        core_only, int(max_papers),
    )

    if err:
        add(f"[!] {err}")
        yield f"❌ {err}", None, "\n".join(log)
        return
    if not papers:
        add("[!] 未找到任何论文")
        yield "❌ 未找到论文", None, "\n".join(log)
        return

    add(f"找到 {len(papers)} 篇论文")
    yield None, None, "\n".join(log)

    # ── Phase 2: Download ──
    progress(0.2, desc="下载 PDF...")
    add(f"开始下载 ({len(papers)} 篇)...")
    yield None, None, "\n".join(log)

    ok, fail, dlog = phase_download(papers, pdf_dir)
    for line in dlog:
        add(line)
    add(f"下载: {ok} 成功, {fail} 失败")

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        add("[!] 所有 PDF 下载失败")
        yield "❌ 下载失败", None, "\n".join(log)
        return

    yield None, None, "\n".join(log)

    # ── Phase 3: Distill ──
    progress(0.5, desc="蒸馏论文...")
    add(f"开始蒸馏 {len(pdfs)} 篇 (并发 {concurrency})...")
    yield None, None, "\n".join(log)

    try:
        stats = phase_distill(pdf_dir, out_dir, key, int(concurrency))
    except Exception as e:
        add(f"[!] 蒸馏异常: {e}")
        yield "❌ 蒸馏失败", None, "\n".join(log)
        return

    ok_d = stats.get("success", 0)
    fail_d = stats.get("failed", 0)
    samples = stats.get("total_samples", 0)
    elapsed = stats.get("elapsed", "N/A")
    add(f"蒸馏: {ok_d} 成功, {fail_d} 失败 | {samples} 样本 | {elapsed}")

    # ── Package ──
    progress(0.9, desc="打包...")
    zip_path = work / "results.zip"
    txt_files = sorted(out_dir.glob("*.txt"))
    if not txt_files:
        add("[!] 蒸馏未产出文件")
        yield "❌ 无输出文件", None, "\n".join(log)
        return

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for txt in txt_files:
            zf.write(txt, txt.name)

    add("=" * 40)
    add(f"DONE | 论文: {len(pdfs)} | 蒸馏: {ok_d}/{ok_d+fail_d} | 样本: {samples}")
    yield None, None, "\n".join(log)

    summary = (
        f"## 完成\n\n"
        f"| | |\n|-|-|\n"
        f"| 搜索 | {len(papers)} 篇 |\n"
        f"| 下载 | {ok} 成功, {fail} 失败 |\n"
        f"| 蒸馏 | {ok_d} 成功, {fail_d} 失败 |\n"
        f"| 样本 | {samples} 条 |\n"
        f"| 耗时 | {elapsed} |\n"
    )
    yield summary, str(zip_path), "\n".join(log)


# ── UI ────────────────────────────────────────────────────
with gr.Blocks(title="论文工坊") as app:
    gr.Markdown("# 论文工坊 / Paper Workshop")
    gr.Markdown("关键词搜知网 → 自动下载 PDF → 蒸馏为 SFT 训练数据")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 搜索参数")
            keywords = gr.Textbox(
                label="关键词（逗号分隔）",
                placeholder="例如: 深基坑, 盾构隧道, 软土, 沉降",
                lines=3,
            )
            with gr.Row():
                from_year = gr.Number(label="起始年", value=2020, precision=0)
                to_year = gr.Number(label="截止年", value=2026, precision=0)
            max_papers = gr.Slider(5, 100, value=20, step=5, label="最多下载篇数")
            core_only = gr.Checkbox(label="仅核心期刊 (北大+CSCD)", value=False)

            gr.Markdown("### 蒸馏参数")
            api_key = gr.Textbox(
                label="DeepSeek API Key", type="password",
                placeholder="sk-...",
                value=os.environ.get("DEEPSEEK_API_KEY", ""),
            )
            concurrency = gr.Slider(1, 5, value=2, step=1, label="并发数")

            btn = gr.Button("开始全流程", variant="primary", size="lg")

        with gr.Column(scale=2):
            gr.Markdown("### 实时日志")
            log_box = gr.Textbox(
                label="", lines=20, max_lines=40,
                autoscroll=True, interactive=False,
            )
            summary = gr.Markdown("等待开始...")
            download = gr.File(label="下载结果 (ZIP)")

    btn.click(
        fn=run,
        inputs=[keywords, from_year, to_year, max_papers, core_only,
                api_key, concurrency],
        outputs=[summary, download, log_box],
    )

    gr.Markdown("---\n全部在本地运行，不上传数据。")

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print("\n  Paper Workshop / 论文工坊")
    print("  " + "-" * 40)
    print("  http://127.0.0.1:7860")
    print("  Ctrl+C 停止\n")
    app.launch(server_name="127.0.0.1", server_port=7860,
               share=False, inbrowser=True)
