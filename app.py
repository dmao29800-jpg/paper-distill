#!/usr/bin/env python3
"""
论文工坊 / Paper Workshop — 知网采集 + 论文蒸馏 一站式 Web 界面
Run: python app.py   →  open http://127.0.0.1:7860
"""
import os, sys, json, time, shutil, tempfile, zipfile, logging, re, threading
from pathlib import Path
from datetime import datetime

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

# ── Try importing cnki-harvest (optional) ──────────────────
_CNKI_DIR = _SCRIPT_DIR.parent / "cnki-harvest"
_CNKI_AVAILABLE = _CNKI_DIR.exists()
if _CNKI_AVAILABLE:
    sys.path.insert(0, str(_CNKI_DIR))

import gradio as gr
import yaml

# ── Config loading ─────────────────────────────────────────
def _load_disciplines():
    """Load 3-layer discipline config from cnki-harvest or fallback."""
    paths = [
        _CNKI_DIR / "configs" / "disciplines.yaml" if _CNKI_AVAILABLE else None,
        _SCRIPT_DIR / "configs" / "disciplines.yaml",
    ]
    for p in paths:
        if p and p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
    return {"disciplines": {}}


_DISC_CONFIG = _load_disciplines()


def get_categories():
    return list(_DISC_CONFIG.get("disciplines", {}).keys())


def get_disciplines(category: str):
    return list(_DISC_CONFIG.get("disciplines", {}).get(category, {}).keys())


def get_sub_disciplines(category: str, discipline: str):
    disc = _DISC_CONFIG.get("disciplines", {}).get(category, {}).get(discipline, {})
    subs = disc.get("sub_disciplines", {})
    return list(subs.keys())


def get_keywords_for_sub(category: str, discipline: str, sub: str):
    disc = _DISC_CONFIG.get("disciplines", {}).get(category, {}).get(discipline, {})
    sub_cfg = disc.get("sub_disciplines", {}).get(sub, {})
    return ", ".join(sub_cfg.get("keywords", []))


def get_all_keywords(category: str, discipline: str):
    disc = _DISC_CONFIG.get("disciplines", {}).get(category, {}).get(discipline, {})
    kw = []
    for sub_cfg in disc.get("sub_disciplines", {}).values():
        kw.extend(sub_cfg.get("keywords", []))
    return list(set(kw))


# ── CNKI Search Engine ────────────────────────────────────
def search_cnki(discipline: str, from_year: int, to_year: int,
                core_only: bool, max_results: int, log_fn) -> list[dict]:
    """Search CNKI. Returns list of paper metadata dicts."""
    if not _CNKI_AVAILABLE:
        return _mock_search(discipline, max_results)

    log_fn("正在连接知网...")
    from engine.searcher import search as cnki_search
    keywords = get_all_keywords(
        _current_category or "工学",
        discipline
    )
    core_journals = None
    if core_only:
        disc = _DISC_CONFIG.get("disciplines", {}).get(
            _current_category or "工学", {}
        ).get(discipline, {})
        core_journals = disc.get("core_journals", []) or \
            _DISC_CONFIG.get("core_journal_list", [])

    log_fn(f"搜索关键词: {len(keywords)} 个, 核心期刊: {core_only}")
    papers = cnki_search(
        keywords=keywords,
        from_year=from_year,
        to_year=to_year,
        core_only=core_only,
        core_journals=core_journals,
        max_results=max_results,
    )
    return papers


_current_category = None


def _mock_search(discipline, count):
    return [{
        "title": f"[模拟] {discipline}领域论文-{i}",
        "authors": "测试作者",
        "journal": "测试期刊",
        "year": "2024",
        "detail_url": "",
        "is_core": True,
    } for i in range(min(count, 5))]


# ── CNKI PDF Download ─────────────────────────────────────
def download_papers(papers: list[dict], output_dir: Path,
                    log_fn, progress_fn) -> tuple[int, int]:
    """Download papers with rate limiting. Returns (success, failed)."""
    if not _CNKI_AVAILABLE:
        log_fn("[模拟模式] cnki-harvest 未安装，跳过真实下载")
        for i, p in enumerate(papers):
            (output_dir / f"mock_{i}.txt").write_text(f"mock paper: {p['title']}")
        return len(papers), 0

    from engine.downloader import DownloadController
    from engine.checkpoint import Checkpoint

    checkpoint = Checkpoint(output_dir / ".harvest_progress.json")
    controller = DownloadController(output_dir, checkpoint)

    success = 0
    failed = 0
    total = len(papers)

    for i, paper in enumerate(papers):
        title = paper.get("title", f"paper-{i}")[:60]
        progress_fn((i + 1) / total, f"下载中 ({i+1}/{total}): {title}")

        if checkpoint.is_done(title):
            success += 1
            continue

        try:
            result = controller.download(paper)
            if result:
                checkpoint.mark_done(title, "downloaded")
                success += 1
                log_fn(f"  ✓ {title}")
            else:
                checkpoint.mark_done(title, "failed")
                failed += 1
                log_fn(f"  ✗ {title}")
        except Exception as e:
            checkpoint.mark_done(title, "failed")
            failed += 1
            log_fn(f"  ✗ {title} — {e}")

        checkpoint.save()
        time.sleep(1.5)

    return success, failed


# ── Paper Distill Pipeline ─────────────────────────────────
def run_distill(input_dir: Path, output_dir: Path, api_key: str,
                concurrency: int, log_fn, progress_fn):
    """Run paper-distill pipeline with progress."""
    from engine.api_client import DeepSeekClient
    from engine.prompt_builder import PromptBuilder
    from engine.classifier import DisciplineClassifier
    from engine.pipeline import Pipeline, AUTO

    config = _SCRIPT_DIR / "configs" / "disciplines.yaml"
    client = DeepSeekClient(api_key)
    builder = PromptBuilder(config)
    classifier = DisciplineClassifier(config)

    pdfs = sorted(f for f in input_dir.glob("*.pdf")
                  if not f.name.startswith("~"))

    if not pdfs:
        log_fn("没有找到 PDF 文件")
        return None

    log_fn(f"找到 {len(pdfs)} 篇论文，开始蒸馏...")

    # Classify first
    log_fn("正在识别学科...")
    classify_map = {}
    for i, p in enumerate(pdfs):
        disc_list = classifier.classify_multi_from_pdf(p)
        classify_map[p.name] = disc_list
        if len(disc_list) == 1:
            log_fn(f"  {p.name[:40]} → {disc_list[0][1]} ({disc_list[0][2]:.0f})")
        else:
            extras = "+".join(n for _, n, _ in disc_list[1:])
            log_fn(f"  {p.name[:40]} → {disc_list[0][1]}(主) + {extras}")

    # Run pipeline
    pipeline = Pipeline(
        input_dir=input_dir,
        output_dir=output_dir,
        api_client=client,
        prompt_builder=builder,
        discipline=AUTO,
        concurrency=concurrency,
        classifier=classifier,
    )

    stats = pipeline.run()
    return stats


# ── Main UI Handler (Generator for streaming) ──────────────
def run_pipeline(
    category, discipline, sub_discipline, custom_keywords,
    from_year, to_year, max_papers, core_only,
    api_key, concurrency,
    progress=gr.Progress(),
):
    """Unified pipeline: CNKI search → download → distill."""
    global _current_category
    _current_category = category

    log_lines = []
    def log(msg):
        log_lines.append(f"[{datetime.now():%H:%M:%S}] {msg}")

    if not discipline:
        yield "请选择学科", None, "\n".join(log_lines)
        return

    # Validate API key for distill step
    key = (api_key or "").strip() or os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        yield "请输入 DeepSeek API Key", None, "\n".join(log_lines)
        return

    # Setup workspace
    work_dir = Path(tempfile.mkdtemp(prefix="paper_workshop_"))
    pdf_dir = work_dir / "pdfs"
    distill_out = work_dir / "distilled"
    pdf_dir.mkdir()
    distill_out.mkdir()

    # ── Phase 1: CNKI Search ──
    progress(0.05, desc="Phase 1/3: 搜索知网...")
    log("=" * 40)
    log(f"学科: {category} → {discipline} → {sub_discipline or '全部'}")
    log(f"年份: {from_year}-{to_year}, 核心: {core_only}, 最多: {max_papers}")
    yield None, None, "\n".join(log_lines)

    # Build keywords
    if custom_keywords and custom_keywords.strip():
        keywords = [k.strip() for k in custom_keywords.replace("，", ",").split(",") if k.strip()]
        log(f"自定义关键词: {keywords}")
        papers = _search_with_keywords(
            category, discipline, keywords, from_year, to_year,
            core_only, max_papers, log
        )
    else:
        papers = search_cnki(discipline, from_year, to_year,
                             core_only, max_papers, log)

    if not papers:
        log("未找到匹配论文")
        yield "未找到论文，请调整筛选条件", None, "\n".join(log_lines)
        return

    log(f"找到 {len(papers)} 篇论文")
    yield None, None, "\n".join(log_lines)

    # ── Phase 2: Download PDFs ──
    progress(0.15, desc="Phase 2/3: 下载 PDF...")
    log("正在下载 PDF...")
    yield None, None, "\n".join(log_lines)

    def progress_fn(val, msg):
        progress(0.15 + val * 0.35, desc=msg)

    ok, bad = download_papers(papers, pdf_dir, log, progress_fn)
    log(f"下载完成: {ok} 成功, {bad} 失败")

    pdf_count = len(list(pdf_dir.glob("*.pdf")))
    if pdf_count == 0:
        log("没有成功下载任何 PDF")
        yield "下载失败", None, "\n".join(log_lines)
        return

    yield None, None, "\n".join(log_lines)

    # ── Phase 3: Distill ──
    progress(0.55, desc="Phase 3/3: 蒸馏论文...")
    log(f"开始蒸馏 {pdf_count} 篇论文 (并发={concurrency})...")
    yield None, None, "\n".join(log_lines)

    def distill_progress(val, msg):
        progress(0.55 + val * 0.35, desc=msg)

    # Override pipeline logging to capture progress
    stats = run_distill(pdf_dir, distill_out, key,
                        int(concurrency), log, distill_progress)

    if not stats:
        log("蒸馏失败")
        yield "蒸馏过程出错", None, "\n".join(log_lines)
        return

    # ── Package results ──
    progress(0.92, desc="打包结果...")
    zip_path = work_dir / "paper_workshop_results.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for txt in sorted(distill_out.glob("*.txt")):
            zf.write(txt, txt.name)
        # Also include raw PDFs
        for pdf in sorted(pdf_dir.glob("*.pdf")):
            zf.write(pdf, f"raw_pdfs/{pdf.name}")

    log("=" * 40)
    log(f"全部完成!")
    log(f"  论文: {stats['total']} | 成功: {stats['success']}")
    log(f"  总样本: {stats['total_samples']}")
    log(f"  耗时: {stats.get('elapsed', 'N/A')}")

    # Build summary
    summary = f"""## 处理完成

| 指标 | 数值 |
|------|------|
| 搜索论文 | {len(papers)} 篇 |
| 下载成功 | {ok} 篇 |
| 蒸馏成功 | {stats['success']}/{stats['total']} |
| 总样本数 | {stats['total_samples']} |
| 耗时 | {stats.get('elapsed', 'N/A')} |
"""

    yield summary, str(zip_path), "\n".join(log_lines)

    # Cleanup
    threading.Thread(target=lambda: shutil.rmtree(work_dir, ignore_errors=True)).start()


def _search_with_keywords(category, discipline, custom_kw, fy, ty,
                          core, max_r, log_fn):
    """Search CNKI with custom keywords instead of preset ones."""
    if not _CNKI_AVAILABLE:
        return _mock_search(discipline, max_r)
    from engine.searcher import search as cnki_search
    core_journals = None
    if core:
        disc = _DISC_CONFIG.get("disciplines", {}).get(
            category, {}).get(discipline, {})
        core_journals = disc.get("core_journals", []) or \
            _DISC_CONFIG.get("core_journal_list", [])
    return cnki_search(
        keywords=custom_kw,
        from_year=fy, to_year=ty,
        core_only=core, core_journals=core_journals,
        max_results=max_r,
    )


# ── Gradio UI ──────────────────────────────────────────────
def update_disciplines(category):
    return gr.update(choices=get_disciplines(category), value=None)


def update_subs(category, discipline):
    subs = get_sub_disciplines(category, discipline)
    return gr.update(choices=["全部"] + subs, value="全部")


def update_keywords(category, discipline, sub):
    if sub and sub != "全部":
        return get_keywords_for_sub(category, discipline, sub)
    keywords = get_all_keywords(category, discipline)
    return ", ".join(keywords)


with gr.Blocks(title="论文工坊 / Paper Workshop") as app:
    gr.Markdown("""
    # 📚 论文工坊 / Paper Workshop

    知网采集 → 自动下载 → 知识蒸馏 → SFT 训练数据。一站式完成。
    """)

    with gr.Row():
        # ── Left Panel: Config ──
        with gr.Column(scale=1):
            gr.Markdown("### 📥 搜索配置")

            cat = gr.Dropdown(
                choices=get_categories(), label="1. 学科门类",
                value="工学" if "工学" in get_categories() else None,
                interactive=True,
            )
            disc = gr.Dropdown(
                label="2. 一级学科", interactive=True,
            )
            sub = gr.Dropdown(
                label="3. 二级学科", interactive=True,
            )
            keywords_box = gr.Textbox(
                label="关键词（可编辑）", lines=3,
                placeholder="自动填充，可手动修改...",
            )

            gr.Markdown("### ⚙️ 采集参数")
            with gr.Row():
                from_year = gr.Number(label="起始年", value=2020, precision=0)
                to_year = gr.Number(label="截止年", value=2026, precision=0)
            with gr.Row():
                max_papers = gr.Slider(10, 300, value=50, step=10,
                                       label="最多下载篇数")
                core_only = gr.Checkbox(label="仅核心期刊", value=True)

            gr.Markdown("### 🧪 蒸馏参数")
            api_key = gr.Textbox(
                label="DeepSeek API Key", type="password",
                placeholder="sk-...",
                value=os.environ.get("DEEPSEEK_API_KEY", ""),
            )
            concurrency = gr.Slider(1, 5, value=2, step=1, label="并发数")

            run_btn = gr.Button("▶ 开始全流程", variant="primary", size="lg")

        # ── Right Panel: Progress + Results ──
        with gr.Column(scale=2):
            gr.Markdown("### 📊 实时进度")
            log_output = gr.Textbox(
                label="处理日志", lines=18, max_lines=30,
                autoscroll=True, interactive=False,
            )

            summary_output = gr.Markdown("等待开始...")
            download_output = gr.File(label="下载结果 (ZIP)", visible=True)

    # ── Cascading discipline logic ──
    cat.change(fn=update_disciplines, inputs=cat, outputs=disc)
    disc.change(fn=update_subs, inputs=[cat, disc], outputs=sub)
    disc.change(
        fn=lambda c, d, s: update_keywords(c, d, s),
        inputs=[cat, disc, sub], outputs=keywords_box,
    )
    sub.change(
        fn=lambda c, d, s: update_keywords(c, d, s),
        inputs=[cat, disc, sub], outputs=keywords_box,
    )

    # ── Run button ──
    run_btn.click(
        fn=run_pipeline,
        inputs=[cat, disc, sub, keywords_box,
                from_year, to_year, max_papers, core_only,
                api_key, concurrency],
        outputs=[summary_output, download_output, log_output],
    )

    gr.Markdown("---\n**隐私说明**：全部在本地运行，不上传任何数据到外部服务器。")


if __name__ == "__main__":
    print(f"\n  📚 论文工坊 / Paper Workshop")
    print(f"  {'─' * 40}")
    print(f"  打开浏览器: http://127.0.0.1:7860")
    print(f"  按 Ctrl+C 停止\n")
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=True,
    )
