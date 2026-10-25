"""Offline PDF text/position extraction, rendering, and deterministic cropping."""
import re
import shutil
import logging
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image

from paths import INPUT_ROOT
from .workspace import fingerprint, key_for, workdir, save_doc, figure_path


def bilingual_blocks(lines):
    """Accept only clear alternating English/Chinese lines, without guessing pairs."""
    if not lines or len(lines) % 2:
        return []
    blocks = []
    for a, b in zip(lines[::2], lines[1::2]):
        def language(text):
            cn = bool(re.search(r'[\u4e00-\u9fff]', text))
            en = bool(re.search(r'[A-Za-z]', text))
            return 'zh' if cn and not en else ('en' if en and not cn else None)
        la, lb = language(a), language(b)
        if {la, lb} != {'zh', 'en'}:
            return []
        blocks.append({'t': 'item', la: a, lb: b, 'sub': {'en': [], 'zh': []}})
    return blocks


def crop_figure(key, page_number, bbox, name=None, doc=None):
    from .workspace import read_doc
    doc = doc or read_doc(key)
    page = doc['pages'][page_number - 1]
    if len(bbox) != 4 or not all(isinstance(x, (int, float)) for x in bbox):
        raise ValueError('bbox 需要四个数字，单位是 PDF 点。')
    x0, y0, x1, y1 = bbox
    if not (0 <= x0 < x1 <= page['width'] and 0 <= y0 < y1 <= page['height']):
        raise ValueError('裁图坐标超出页面。')
    name = name or f'p{page_number:03d}_crop_{len(page["figures"]) + 1:03d}.png'
    path = figure_path(key, name)
    with Image.open(figure_path(key, page['preview'])) as image:
        sx, sy = image.width / page['width'], image.height / page['height']
        image.crop((round(x0*sx), round(y0*sy), round(x1*sx), round(y1*sy))).save(path)
    return {'file': name, 'bbox': list(bbox), 'source_page': page_number, 'kind': 'crop'}


def extract_pdf(path, key=None, dpi=144, overwrite=False, progress=print, cancelled=lambda: False):
    path = Path(path).resolve()
    logging.getLogger('pdfminer.pdffont').setLevel(logging.ERROR)
    if not path.is_file() or path.suffix.lower() != '.pdf':
        raise ValueError('请选择存在的 PDF 文件。')
    if not 72 <= dpi <= 300:
        raise ValueError('DPI 范围为 72–300。')
    key = key or key_for(path)
    folder = workdir(key)
    if (folder / 'content.json').exists() and not overwrite:
        raise FileExistsError(f'{key} 已有解析结果。请打开已有项目，或指定新 key／使用 --overwrite。')
    folder.mkdir(parents=True, exist_ok=True)
    # Keep a local copy, including PDFs selected outside dist/input.
    inputs = Path(INPUT_ROOT)
    inputs.mkdir(parents=True, exist_ok=True)
    local = inputs / path.name
    if path != local.resolve():
        if local.exists() and fingerprint(local) != fingerprint(path):
            local = inputs / f'{path.stem}_{fingerprint(path)[:8]}.pdf'
        if not local.exists():
            shutil.copy2(path, local)
    digest = fingerprint(local)
    generation = folder / 'figures'
    generation.mkdir(exist_ok=True)
    # Stage metadata: an interrupted rerun never replaces content.json.
    pages = []
    render = pdfium.PdfDocument(str(local))
    try:
        with pdfplumber.open(local) as pdf:
            for idx, page in enumerate(pdf.pages):
                if cancelled():
                    raise InterruptedError('解析已取消；已有 content.json 未改变。')
                text = page.extract_text(x_tolerance=2, y_tolerance=3) or ''
                number = idx + 1
                # Content-addressed names preserve previous figures on overwrite.
                preview = f'{digest[:10]}_p{number:03d}_{dpi}dpi.png'
                rendered = render[idx]
                bitmap = rendered.render(scale=dpi/72)
                try:
                    bitmap.to_pil().convert('RGB').save(generation / preview)
                finally:
                    bitmap.close()
                    rendered.close()
                lines = [s.strip() for s in text.splitlines() if s.strip()]
                issues = []
                if len(re.sub(r'\s', '', text)) < 30:
                    issues.append('无有效文字层，需要 OCR／视觉识别')
                elif lines and sum(len(s) <= 2 for s in lines) / len(lines) > .35:
                    issues.append('文字碎片较多，阅读顺序或公式需要检查')
                image_area = sum(max(0, im['x1']-im['x0'])*max(0, im['bottom']-im['top']) for im in page.images)
                if image_area > page.width*page.height*.45 and len(text) < 400 and not issues:
                    issues.append('大幅图片可能包含未提取的正文或公式')
                if re.search(r'[∫∑√∂∏∞≠≤≥\u0370-\u03ff]|\b(?:sin|cos|tan|lim)\b', text):
                    issues.append('检测到数学公式，需要核对结构与符号')
                if image_area > page.width*page.height*.015:
                    issues.append('页面含图片，需确认图中内容和正文关联')
                if len(page.lines) + len(page.rects) + len(page.curves) > 10:
                    issues.append('页面含表格或矢量图形，需要核对内容结构')
                cn = len(re.findall(r'[\u4e00-\u9fff]', text))
                latin = len(re.findall('[A-Za-z]', text))
                language = 'zh' if cn > 10 and cn > latin*.15 else 'en'
                words = page.extract_words(x_tolerance=2, y_tolerance=3)
                info = {
                    'number': number, 'width': float(page.width), 'height': float(page.height),
                    'preview': preview, 'native_text': text, 'native_language': language,
                    'native_blocks': bilingual_blocks(lines),
                    'words': [{'text': w['text'], 'bbox': [w['x0'], w['top'], w['x1'], w['bottom']]} for w in words],
                    'issues': issues, 'figures': [], 'resolved': None,
                }
                pages.append(info)
                for n, im in enumerate(page.images):
                    bbox = [max(0, im['x0']), max(0, im['top']), min(page.width, im['x1']), min(page.height, im['bottom'])]
                    if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                        continue
                    # Full-page images are preserved as previews, not mislabeled as individual diagrams.
                    if (bbox[2]-bbox[0])*(bbox[3]-bbox[1]) > page.width*page.height*.8:
                        continue
                    fig = crop_figure(key, number, bbox, f'{digest[:10]}_p{number:03d}_image{n+1:03d}.png', {'pages': pages})
                    fig['kind'] = 'embedded_image_candidate'
                    info['figures'].append(fig)
                progress(f'解析 {number}/{len(pdf.pages)} 页：{len(text)} 字符，{len(issues)} 项待检查')
                page.close()
    finally:
        render.close()
    doc = {
        'schema_version': 2, 'analysis_version': 3, 'key': key, 'title': path.stem,
        'source': {'path': 'input/' + local.name, 'sha256': digest, 'dpi': dpi},
        'coordinate_system': 'PDF points; origin top-left; page numbers start at 1',
        'pages': pages,
    }
    save_doc(key, doc, backup=overwrite)
    return key
