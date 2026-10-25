# converter/pdfgen.py — 用 xelatex 编译 PDF
import os, subprocess, shutil


def compile_pdf(key, lang, work_key):
    if not shutil.which("xelatex"):
        raise RuntimeError('未找到 xelatex。请安装 MiKTeX，或先生成 TeX／PPTX。原貌 PDF 不需要它。')
    tpath = os.path.join(work_key, f"{key}_{lang.upper()}.tex")
    options = ['-disable-installer'] if 'miktex' in shutil.which('xelatex').lower() else []
    for _ in range(2):
        r = subprocess.run(["xelatex", *options, "-no-shell-escape", "-interaction=nonstopmode",
                            "-halt-on-error", os.path.basename(tpath)],
                           cwd=work_key, capture_output=True, text=True, errors='replace', timeout=180,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if r.returncode != 0:
            raise RuntimeError(f"xelatex {lang} 编译失败；日志保留在 {work_key}：\n{r.stdout[-1500:]}")
    else:
        print(f"pdf {lang} built")
