"""Single operation shared by the simplified GUI and agent-friendly CLI."""
import shutil
import uuid
from pathlib import Path

from .assist import complete_api
from .extract import extract_pdf
from .exporter import build_v2
from .workspace import NeedsModel, fingerprint, key_for, workdir, read_doc, pending, save_doc


def _publish(stage, destination, names):
    """Publish a verified set; restore existing files if publication fails."""
    destination.mkdir(parents=True, exist_ok=True)
    scratch = destination / ('.pdf-convert-' + uuid.uuid4().hex)
    scratch.mkdir()
    prepared, replaced = [], []
    try:
        for name in names:
            target = destination / name
            temporary = scratch / 'new' / name
            temporary.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stage / name, temporary)
            backup = scratch / 'old' / name
            if target.exists():
                if not target.is_file():
                    raise ValueError(f'输出路径不是文件：{target}')
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            prepared.append((target, temporary, backup))
        for target, temporary, backup in prepared:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary.replace(target)
            replaced.append((target, backup))
    except Exception:
        for target, backup in reversed(replaced):
            if backup.exists():
                shutil.copy2(backup, target)
            else:
                target.unlink(missing_ok=True)
        raise
    finally:
        if scratch.resolve().parent == destination.resolve():
            shutil.rmtree(scratch)


def convert_pdf(input_path, output_dir, target='zh', use_llm=False, base_url='', model='', api_key='',
                progress=print, cancelled=lambda: False):
    if target not in ('zh', 'en', 'bi', 'all'):
        raise ValueError('请选择中文、英文、双语或全部。')
    targets = ('zh', 'en', 'bi') if target == 'all' else (target,)
    content_target = 'bi' if target == 'all' else target
    source = Path(input_path).resolve()
    if not source.is_file() or source.suffix.lower() != '.pdf':
        raise ValueError('请选择存在的 PDF 文件。')
    if not str(output_dir).strip():
        raise ValueError('请选择输出目录。')
    destination = Path(output_dir).resolve()
    if destination.exists() and not destination.is_dir():
        raise ValueError('输出目录无效。')
    key = key_for(source)
    digest = fingerprint(source)
    if (workdir(key) / 'content.json').exists():
        cached = read_doc(key)
        if cached.get('source', {}).get('sha256') != digest:
            key += '_' + digest[:8]
    progress('[1/4] 正在读取和解析 PDF。')
    if (workdir(key) / 'content.json').exists():
        doc = read_doc(key)
        if doc.get('analysis_version', 0) < 3:
            previous = doc
            progress('正在更新本地解析检查，已有处理结果会保留。')
            extract_pdf(source, key=key, overwrite=True, progress=progress, cancelled=cancelled)
            doc = read_doc(key)
            for page, old in zip(doc['pages'], previous.get('pages', [])):
                if old.get('resolved'):
                    page['resolved'] = old['resolved']
            save_doc(key, doc)
        progress('已读取本地解析记录，继续检查内容完整性。')
    else:
        extract_pdf(source, key=key, progress=progress, cancelled=cancelled)
        doc = read_doc(key)
    if cancelled():
        raise InterruptedError('处理已停止。')
    progress('[2/4] 正在检查解析完整性和目标语言。')
    rows = pending(doc, content_target)
    used_llm = False
    if rows:
        progress(f'发现 {len(rows)} 页需要补全、翻译或核对。')
        if not use_llm:
            progress('未连接 LLM，已停止；没有生成任何最终文件。')
            raise NeedsModel('本地解析或目标语言不完整。请勾选“连接 LLM”后重新生成，或在支持大模型的 agent 中使用 CLI 继续处理。')
        if not shutil.which('xelatex'):
            raise RuntimeError('未找到 xelatex。请先安装 MiKTeX，再生成全部三种格式。')
        progress('[3/4] 正在连接 LLM，自动补全并翻译所需页面。')
        count = complete_api(key, content_target, base_url, model, api_key, enabled=True,
                             progress=progress, cancelled=cancelled)
        used_llm = count > 0
        doc = read_doc(key)
        remaining = pending(doc, content_target)
        if remaining:
            raise NeedsModel(f'LLM 处理后仍有 {len(remaining)} 页不完整，未生成最终文件。请检查日志或通过 agent CLI 继续处理。')
        progress('LLM 处理完成，内容完整性检查通过。')
    else:
        progress('[3/4] 内容和目标语言已完整，本次不需要连接 LLM。')
    if cancelled():
        raise InterruptedError('处理已停止。')
    progress('[4/4] 正在生成 TeX、PDF 和 PPTX。全部成功后才写入输出目录。')
    stage = workdir(key) / 'builds' / uuid.uuid4().hex
    stage.mkdir(parents=True)
    # Keep build diagnostics under work/ on failure; never publish partial documents.
    def build_log(message):
        if not message.startswith('生成完成：'):
            progress(message)
    for language in targets:
        progress({'zh': '正在生成中文版。', 'en': '正在生成英文版。', 'bi': '正在生成双语版（中文一行，英文一行）。'}[language])
        build_v2(key, language, ('tex', 'pdf', 'pptx'), progress=build_log, cancelled=cancelled, output_dir=stage)
    files = [f'{key}_{language.upper()}.{ext}' for language in targets for ext in ('tex', 'pdf', 'pptx')]
    if any(not (stage / name).is_file() or (stage / name).stat().st_size == 0 for name in files):
        raise RuntimeError('文档生成不完整，没有发布输出文件。')
    if cancelled():
        raise InterruptedError('处理已停止。')
    names = [Path(name) for name in files] + [p.relative_to(stage) for p in (stage / 'figures').rglob('*') if p.is_file()]
    _publish(stage, destination, names)
    shutil.rmtree(stage)
    if target == 'all':
        progress('已完成：中文、英文、双语共 9 个文件全部生成。' + ('本次已使用 LLM。' if used_llm else '本次无需连接 LLM。'))
    else:
        progress('已完成：TeX、PDF、PPTX 全部生成。' + ('本次已使用 LLM。' if used_llm else '本次无需连接 LLM。'))
    progress(f'输出目录：{destination}')
    return {'key': key, 'output_dir': str(destination), 'used_llm': used_llm,
            'files': [str(destination / name) for name in files]}
