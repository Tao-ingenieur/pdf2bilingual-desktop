"""Exports v2 intermediate data; source facsimiles remain available offline."""
import re
import shutil
from pathlib import Path

from pdf2bilingual.paths import OUTPUT_ROOT
from .workspace import read_doc, workdir, pending, source_path, figure_path, NeedsModel


def tex_escape(text):
    chars = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
             '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(chars.get(c, c) for c in text)


MATH_COMMANDS = set('frac dfrac tfrac sqrt left right big Big bigg Bigg sin cos tan cot sec csc arcsin arccos arctan sinh cosh tanh log ln exp lim sum prod int iint iiint oint infty alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu xi pi varpi rho sigma tau upsilon phi varphi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega cdot times div pm mp le leq ge geq ne neq approx equiv sim simeq propto in notin subset subseteq supset supseteq cup cap emptyset forall exists neg land lor to rightarrow leftarrow Rightarrow Leftarrow Leftrightarrow mapsto vec overrightarrow overline underline hat bar dot ddot tilde widehat widetilde mathrm mathbf mathit mathsf mathbb mathcal boldsymbol text operatorname begin end quad qquad displaystyle textstyle limits nolimits binom dbinom tbinom cfrac cases aligned matrix pmatrix bmatrix vmatrix Vmatrix array color'.split())


def rich_tex(text):
    parts = re.split(r'(\$\$.*?\$\$|\$(?:[^$]|\\\$)*?\$)', text, flags=re.S)
    output = []
    for part in parts:
        if len(part) > 1 and part.startswith('$') and part.endswith('$'):
            commands = re.findall(r'\\([A-Za-z]+)', part)
            if any(cmd not in MATH_COMMANDS for cmd in commands):
                raise ValueError('公式含不支持的 LaTeX 命令，请在 content.json 中检查后重试。')
            environments = re.findall(r'\\(?:begin|end)\s*\{([^}]+)\}', part)
            if any(env not in ('aligned', 'alignedat', 'gathered', 'split', 'cases', 'matrix',
                               'pmatrix', 'bmatrix', 'vmatrix', 'Vmatrix', 'array') for env in environments):
                raise ValueError('公式含不支持的 LaTeX 环境。')
            output.append(part)
        else:
            output.append(tex_escape(part).replace('\n', '\n\n'))
    return ''.join(output)


def _blocks(page):
    if page.get('resolved'):
        return page['resolved']['blocks']
    if page.get('native_blocks'):
        return page['native_blocks']
    lang = page['native_language']
    return [{'t': 'item', 'en': page['native_text'] if lang == 'en' else '',
             'zh': page['native_text'] if lang == 'zh' else '', 'sub': {}}]


def _body_groups(page, lang):
    for block in _blocks(page):
        if block['t'] == 'fig':
            yield ('fig', block['file'])
            continue
        order = ('zh', 'en') if lang == 'bi' else (lang,)
        lines = [block[language] for language in order if block.get(language)]
        if lines:
            yield ('text', lines)
        sub = block.get('sub', {})
        count = max(len(sub.get('en', [])), len(sub.get('zh', [])))
        for idx in range(count):
            lines = []
            for language in order:
                entries = sub.get(language, [])
                if idx < len(entries):
                    lines.append(entries[idx])
            if lines:
                yield ('text', lines)


def _body_lines(page, lang):
    for kind, content in _body_groups(page, lang):
        if kind == 'fig':
            yield kind, content
        else:
            for line in content:
                yield kind, line


def build_v2(key, lang='source', formats=('pdf', 'tex', 'pptx'), progress=print, cancelled=lambda: False, output_dir=None):
    doc = read_doc(key)
    if doc.get('schema_version') != 2:
        from .pipeline import run
        if lang == 'source':
            raise ValueError('旧版 content.json 请指定 zh、en 或 bi。')
        return Path(run(key, (lang,), formats))
    if lang not in ('source', 'en', 'zh', 'bi'):
        raise ValueError('输出语言无效。')
    problems = pending(doc, lang)
    if lang != 'source' and problems:
        nums = ', '.join(str(r['page']) for r in problems)
        raise NeedsModel(f'第 {nums} 页尚需识别／翻译／核对。请启用 LLM，或通过 agent CLI 继续处理；没有生成最终文件。')
    out = Path(output_dir) if output_dir is not None else Path(OUTPUT_ROOT) / key
    out.mkdir(parents=True, exist_ok=True)
    label = lang.upper()
    figure_subdir = f'figures/{key}_{label}'
    figures = out / figure_subdir
    figures.mkdir(parents=True, exist_ok=True)
    required = set(p['preview'] for p in doc['pages']) if lang == 'source' else {
        b['file'] for p in doc['pages'] for b in _blocks(p) if b['t'] == 'fig'}
    for filename in required:
        if cancelled():
            raise InterruptedError('生成已取消。')
        shutil.copy2(figure_path(key, filename), figures / filename)
    if 'pdf' in formats and lang == 'source':
        # Original-page edition: preserve vectors, searchable text and resolution exactly.
        src = source_path(doc)
        shutil.copy2(src, out / f'{key}_{label}.pdf')
        progress(f'PDF 原貌版完成：{len(doc["pages"])} 页，保留原始页面。')
    if 'tex' in formats or ('pdf' in formats and lang != 'source'):
        lines = [r'% !TeX program = xelatex', r'\documentclass[11pt]{article}',
                 r'\usepackage[UTF8]{ctex}' if lang in ('zh', 'bi') else r'\usepackage{fontspec}',
                 r'\usepackage{amsmath,amssymb,graphicx}',
                 r'\usepackage[a4paper,margin=18mm]{geometry}', r'\graphicspath{{' + figure_subdir + '/}}',
                 r'\setlength{\parindent}{0pt}', r'\begin{document}']
        if lang == 'source':
            lines = [r'\documentclass{article}', r'\usepackage{graphicx}',
                     r'\pagestyle{empty}', r'\hoffset=-1in', r'\voffset=-1in', r'\begin{document}']
            for p in doc['pages']:
                # PDF dimensions are bp (1/72 inch), not TeX pt (1/72.27 inch).
                size = f'{p["width"]}bp,{p["height"]}bp'
                lines.append(r'\shipout\vbox{\offinterlineskip\hbox{\special{papersize=' + size + '}'
                             + r'\includegraphics[width=' + f'{p["width"]}bp,height={p["height"]}bp' + ']{' + figure_subdir + '/' + p['preview'] + '}}}')
        else:
            lines.append(r'\section*{' + tex_escape(doc['title']) + '}')
            for p in doc['pages']:
                titles = p.get('resolved') or {}
                if lang == 'bi':
                    title = tex_escape(titles.get('title_zh') or f'第 {p["number"]} 页') + r'\\' + tex_escape(titles.get('title_en') or f'Page {p["number"]}')
                else:
                    title = tex_escape(titles.get(f'title_{lang}') or (f'第 {p["number"]} 页' if lang == 'zh' else f'Page {p["number"]}'))
                lines.append(r'\subsection*{' + title + '}')
                for kind, text in _body_groups(p, lang):
                    if kind == 'fig':
                        lines.append(r'\begin{center}\includegraphics[width=.8\linewidth,height=.55\textheight,keepaspectratio]{' + text + r'}\end{center}')
                    else:
                        for index, line in enumerate(text):
                            lines.append(r'\noindent ' + rich_tex(line) + r'\par')
                            if index + 1 < len(text):
                                lines.append(r'\nopagebreak[4]')
                        lines.append(r'\medskip')
                lines.append(r'\clearpage')
        lines.append(r'\end{document}')
        tex_path = out / f'{key}_{label}.tex'
        tex_path.write_text('\n'.join(lines), encoding='utf-8')
        if 'pdf' in formats and lang != 'source':
            from .pdfgen import compile_pdf
            compile_pdf(key, lang, str(out))
            progress('PDF 编译完成。')
        progress('TeX 排版完成。')
        if 'tex' not in formats:
            tex_path.unlink(missing_ok=True)
    if 'pptx' in formats:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        from PIL import Image
        prs = Presentation()
        prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

        def slide_image(filename):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            slide.background.fill.solid()
            slide.background.fill.fore_color.rgb = RGBColor(242, 244, 248)
            with Image.open(figures / filename) as im:
                ratio = im.width/im.height
            width = min(prs.slide_width, int(prs.slide_height*ratio))
            height = int(width/ratio)
            slide.shapes.add_picture(str(figures / filename), (prs.slide_width-width)//2,
                                     (prs.slide_height-height)//2, width=width, height=height)

        for p in doc['pages']:
            if cancelled():
                raise InterruptedError('生成已取消。')
            if lang == 'source':
                slide_image(p['preview'])
            else:
                # Small text chunks avoid the legacy one-chapter-per-slide overflow.
                from .tex2plain import tex2plain
                chunks = []
                current = ''
                for kind, text in _body_groups(p, lang):
                    if kind == 'fig':
                        if current:
                            chunks.append(('text', current)); current = ''
                        chunks.append(('fig', text))
                        continue
                    text = '\n'.join(tex2plain(line) for line in text)
                    # Keep a Chinese/English pair together when starting a new slide.
                    parts = [text] if lang == 'bi' else [text[start:start+450] for start in range(0, len(text), 450)]
                    for part in parts:
                        if current and len(current)+len(part) > 450:
                            chunks.append(('text', current)); current = ''
                        current += part + '\n\n'
                if current:
                    chunks.append(('text', current))
                for kind, text in chunks:
                    if kind == 'fig':
                        slide_image(text)
                    else:
                        slide = prs.slides.add_slide(prs.slide_layouts[6])
                        title = slide.shapes.add_textbox(Inches(.5), Inches(.3), Inches(12.3), Inches(.6))
                        title.text_frame.text = f'{doc["title"]} · {p["number"]}'
                        title.text_frame.paragraphs[0].font.size = Pt(22)
                        box = slide.shapes.add_textbox(Inches(.6), Inches(1.1), Inches(12.1), Inches(5.9))
                        box.text_frame.word_wrap = True
                        box.text_frame.text = text
                        from pptx.enum.text import MSO_AUTO_SIZE
                        box.text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
                        for paragraph in box.text_frame.paragraphs:
                            paragraph.font.name = 'Microsoft YaHei'
                            paragraph.font.size = Pt(18)
        prs.save(str(out / f'{key}_{label}.pptx'))
        progress(f'PPTX 完成：{len(prs.slides)} 张幻灯片。')
    progress(f'生成完成：{out}')
    return out
