"""Offline-first command line frontend. Use --help for commands."""
import argparse
import json
import os
import sys
from pathlib import Path

from pdf2bilingual.pipeline.workspace import NeedsModel, read_doc, pending, workdir


def parser():
    p = argparse.ArgumentParser(description='PDF 本地解析、裁图、Codex/API 补全与文档生成')
    commands = p.add_subparsers(dest='command', required=True)
    convert = commands.add_parser('convert', help='自动解析、按需连接 LLM，并生成 TeX/PDF/PPTX')
    convert.add_argument('input', type=Path)
    convert.add_argument('--output', type=Path, required=True)
    convert.add_argument('--lang', choices=['zh', 'en', 'bi', 'all'], default='zh')
    convert.add_argument('--enable-model', action='store_true')
    convert.add_argument('--base-url', default=os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1'))
    convert.add_argument('--model', default=os.environ.get('OPENAI_MODEL', ''))
    extract = commands.add_parser('extract', help='离线解析 PDF；不调用模型')
    extract.add_argument('input', type=Path)
    extract.add_argument('--key')
    extract.add_argument('--dpi', type=int, default=144)
    extract.add_argument('--overwrite', action='store_true')
    status = commands.add_parser('status', help='显示问题页及缺少的语言')
    status.add_argument('key')
    status.add_argument('--lang', choices=['zh', 'en', 'bi'], default='zh')
    build = commands.add_parser('build', help='根据完整内容生成目标语言文档')
    build.add_argument('key')
    build.add_argument('--lang', choices=['zh', 'en', 'bi'], default='zh')
    build.add_argument('--format', choices=['all', 'pdf', 'tex', 'pptx'], default='all')
    task = commands.add_parser('export-task', help='导出 Codex 任务，无需 API Key')
    task.add_argument('key')
    task.add_argument('--lang', choices=['zh', 'en', 'bi'], default='zh')
    imp = commands.add_parser('import-result', help='校验并导入 Codex／人工处理结果')
    imp.add_argument('key')
    imp.add_argument('result', type=Path)
    crop = commands.add_parser('crop', help='按 PDF 点坐标裁图，原点左上')
    crop.add_argument('key')
    crop.add_argument('--page', type=int, required=True)
    crop.add_argument('--bbox', nargs=4, type=float, required=True)
    crop.add_argument('--name')
    model = commands.add_parser('assist', help='显式启用 API 后补全／翻译待办页')
    model.add_argument('key')
    model.add_argument('--lang', choices=['zh', 'en', 'bi'], default='zh')
    model.add_argument('--enable-model', action='store_true', help='允许向指定 API 发送待办页截图和文字')
    model.add_argument('--base-url', default=os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1'))
    model.add_argument('--model', default=os.environ.get('OPENAI_MODEL', ''))
    commands.add_parser('gui', help='启动 Windows 界面')
    return p


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    args = parser().parse_args(argv)
    try:
        if args.command == 'convert':
            from pdf2bilingual.pipeline.convert import convert_pdf
            convert_pdf(args.input, args.output, args.lang, args.enable_model, args.base_url, args.model)
        elif args.command == 'extract':
            from pdf2bilingual.pipeline.extract import extract_pdf
            key = extract_pdf(args.input, args.key, args.dpi, args.overwrite)
            print(f'已保存：{workdir(key)}')
            print('status 查看待办；缺少内容时可使用 LLM 或 agent CLI 继续处理。')
        elif args.command == 'status':
            doc = read_doc(args.key)
            rows = pending(doc, args.lang)
            print(json.dumps({'key': args.key, 'target': args.lang, 'pages': len(doc.get('pages', [])), 'pending': rows}, ensure_ascii=False, indent=2))
            return 2 if rows else 0
        elif args.command == 'build':
            from pdf2bilingual.pipeline.exporter import build_v2
            build_v2(args.key, args.lang, ('pdf', 'tex', 'pptx') if args.format == 'all' else (args.format,))
        elif args.command == 'export-task':
            from pdf2bilingual.pipeline.assist import export_handoff
            print(export_handoff(args.key, args.lang))
        elif args.command == 'import-result':
            from pdf2bilingual.pipeline.assist import import_result
            print(f'已导入 {import_result(args.key, args.result)} 页；原内容已备份。')
        elif args.command == 'crop':
            from pdf2bilingual.pipeline.extract import crop_figure
            from pdf2bilingual.pipeline.workspace import save_doc
            doc = read_doc(args.key)
            if not 1 <= args.page <= len(doc['pages']):
                raise ValueError('页码超出范围。')
            fig = crop_figure(args.key, args.page, args.bbox, args.name, doc)
            doc['pages'][args.page-1]['figures'].append(fig)
            save_doc(args.key, doc, backup=True)
            print(json.dumps(fig, ensure_ascii=False))
        elif args.command == 'assist':
            from pdf2bilingual.pipeline.assist import complete_api
            print(f'完成 {complete_api(args.key, args.lang, args.base_url, args.model, enabled=args.enable_model)} 页。')
        elif args.command == 'gui':
            from pdf2bilingual.gui.app import main as gui_main
            gui_main([])
        return 0
    except NeedsModel as exc:
        print(f'需要继续处理：{exc}', file=sys.stderr)
        return 2
    except Exception as exc:
        print(f'失败：{exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
