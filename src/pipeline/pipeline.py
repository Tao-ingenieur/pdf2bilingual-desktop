# converter/pipeline.py — 编排：读取 → 生成 → 复制 → 清理
import os, shutil
from paths import WORK_ROOT, OUTPUT_ROOT
from .loader import load, list_keys
from .texgen import build_tex
from .pptxgen import build_ppt
from .pdfgen import compile_pdf

LANGS = {"zh": ["zh"], "en": ["en"], "bi": ["bi"], "all": ["zh", "en", "bi"]}


def run(key=None, langs=("zh", "en", "bi"), formats=("tex", "pdf", "pptx")):
    if key is None:
        ks = list_keys()
        if len(ks) != 1:
            raise SystemExit("无法确定 key，请指定：python build.py <key>")
        key = ks[0]
    doc = load(key)
    work_key = os.path.join(WORK_ROOT, key)
    os.makedirs(work_key, exist_ok=True)

    # 1) 生成 tex（tex 或 pdf 需要）
    if "tex" in formats or "pdf" in formats:
        for lang in langs:
            tex = build_tex(doc, lang)
            with open(os.path.join(work_key, f"{key}_{lang.upper()}.tex"), "w", encoding="utf-8") as f:
                f.write(tex)
    # 2) 编译 pdf
    if "pdf" in formats:
        for lang in langs:
            compile_pdf(key, lang, work_key)
    # 3) 生成 pptx
    if "pptx" in formats:
        for lang in langs:
            prs = build_ppt(doc, lang, key)
            prs.save(os.path.join(work_key, f"{key}_{lang.upper()}.pptx"))
            print(f"pptx {lang} built")

    # 4) 复制到 OUTPUT_ROOT/<key>/
    out_dir = os.path.join(OUTPUT_ROOT, key)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "figures"), exist_ok=True)
    for lang in langs:
        for ext in ("tex", "pdf", "pptx"):
            if ext not in formats:
                continue
            src = os.path.join(work_key, f"{key}_{lang.upper()}.{ext}")
            if os.path.exists(src):
                shutil.copyfile(src, os.path.join(out_dir, f"{key}_{lang.upper()}.{ext}"))
    figsrc = os.path.join(work_key, "figures")
    if os.path.isdir(figsrc):
        for f in os.listdir(figsrc):
            shutil.copyfile(os.path.join(figsrc, f), os.path.join(out_dir, "figures", f))

    # 5) 清理 work 中间件（保留 content.json + figures）
    removed = 0
    for f in os.listdir(work_key):
        if f.startswith(key + "_") and f.rsplit(".", 1)[-1].lower() in ("tex", "pdf", "pptx", "aux", "log", "out"):
            try:
                os.remove(os.path.join(work_key, f))
                removed += 1
            except OSError as e:
                print(f"cleanup skip {f}: {e}")
    if removed:
        print(f"cleaned {removed} intermediate file(s) in dist/work/{key}")
    print("done ->", out_dir)
    return out_dir
