"""Versioned, portable intermediate documents shared by CLI, GUI and Codex."""
import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from paths import INPUT_ROOT, WORK_ROOT


class NeedsModel(RuntimeError):
    pass


def key_for(path):
    return re.sub(r'[^\w.-]+', '_', Path(path).stem).strip('._') or 'document'


def workdir(key):
    if not key or key in ('.', '..') or Path(key).name != key or '/' in key or '\\' in key:
        raise ValueError('key 必须是一个目录名，不能包含路径。')
    return Path(WORK_ROOT) / key


def read_doc(key):
    return json.loads((workdir(key) / 'content.json').read_text(encoding='utf-8'))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def save_doc(key, doc, backup=False):
    path = workdir(key) / 'content.json'
    if backup and path.exists():
        folder = path.parent / 'backups'
        folder.mkdir(exist_ok=True)
        shutil.copy2(path, folder / f'content_{datetime.now():%Y%m%d_%H%M%S_%f}.json')
    write_json(path, doc)
    write_report(key, doc)


def fingerprint(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def source_path(doc):
    # A relative path keeps moved workspaces usable.
    p = Path(doc['source']['path'])
    if not p.is_absolute():
        p = Path(INPUT_ROOT).parent / p
    if not p.is_file():
        raise FileNotFoundError(f'原始文件不存在：{p}')
    if fingerprint(p) != doc['source']['sha256']:
        raise ValueError('原始 PDF 已改变，请重新解析，不能沿用旧坐标。')
    return p


def languages(page):
    blocks = (page.get('resolved') or {}).get('blocks', [])
    if not page.get('resolved') and not page.get('issues'):
        blocks = page.get('native_blocks', [])
    items = [b for b in blocks if b.get('t') == 'item']
    return [lang for lang in ('zh', 'en') if items and all(
        b.get(lang, '').strip() and all(b.get('sub', {}).get(lang, [])) for b in items)]


def pending(doc, target='source'):
    result = []
    for page in doc.get('pages', []):
        reasons = list(page.get('issues', [])) if not page.get('resolved') else []
        if (page.get('resolved') or {}).get('needs_review'):
            reasons.append('模型／人工结果标记为仍需检查')
        required = ('en', 'zh') if target == 'bi' else ((target,) if target in ('en', 'zh') else ())
        available = languages(page)
        for lang in required:
            # Native paragraphs may be used only when extraction passed local checks.
            native_ok = not page.get('issues') and page.get('native_language') == lang and not page.get('resolved')
            if lang not in available and not native_ok:
                reasons.append(f'缺少完整的 {lang} 内容或双语对齐')
        if reasons:
            result.append({'page': page['number'], 'reasons': sorted(set(reasons))})
    return result


def write_report(key, doc):
    if doc.get('schema_version') != 2:
        return
    rows = pending(doc)
    write_json(workdir(key) / 'report.json', {
        'page_count': len(doc['pages']),
        'pages_with_native_text': sum(bool(p['native_text'].strip()) for p in doc['pages']),
        'pending_pages': rows,
        'message': '原貌版可直接生成。可编辑／翻译版本须完成问题页；可启用 API，或导出 Codex 任务。' if rows else '本地检查通过；仍建议核对公式与阅读顺序。',
    })


def figure_path(key, filename):
    root = (workdir(key) / 'figures').resolve()
    path = (root / filename).resolve()
    if root not in path.parents:
        raise ValueError('图片路径必须位于 figures/ 内。')
    return path
