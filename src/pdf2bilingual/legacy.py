# repo/build.py — 命令行入口
#
# 用法：
#   python build.py <key>                      # 默认 --lang all --format all
#   python build.py --lang zh                  # 仅中文
#   python build.py --lang en --format pdf     # 仅英文 PDF
#   python build.py --lang bi                  # 仅双语
#   python build.py --lang all --format tex    # 仅生成三种语言的 .tex
import os, sys, argparse

from pdf2bilingual.pipeline.pipeline import run, LANGS

FORMATS = ("tex", "pdf", "pptx")


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ('convert', 'extract', 'status', 'build', 'crop', 'export-task', 'import-result', 'assist', 'gui'):
        from pdf2bilingual.cli import main as cli_main
        raise SystemExit(cli_main(sys.argv[1:]))
    ap = argparse.ArgumentParser(
        description="通用 PDF/图片 → 中/英/双语 .tex/.pdf/.pptx 转换")
    ap.add_argument("key", nargs="?",
                    help="内容 key（默认自动检测 work 下唯一 content.json）")
    ap.add_argument("--lang", choices=["zh", "en", "bi", "all"], default="all",
                    help="输出语言：zh=仅中文 en=仅英文 bi=双语 all=全部(默认)")
    ap.add_argument("--format", choices=["tex", "pdf", "pptx", "all"], default="all",
                    help="输出格式：tex/pdf/pptx/all(默认)")
    args = ap.parse_args()
    fmts = FORMATS if args.format == "all" else (args.format,)
    from pdf2bilingual.pipeline.loader import load, list_keys
    selected = args.key
    if selected is None:
        keys = list_keys()
        if len(keys) == 1:
            selected = keys[0]
    if selected and load(selected).get('schema_version') == 2:
        from pdf2bilingual.pipeline.exporter import build_v2
        build_v2(selected, 'zh' if args.lang == 'all' else args.lang, fmts)
        return
    if args.lang == 'source':
        ap.error('旧版数据不支持 source，请指定 zh/en/bi。')
    langs = LANGS[args.lang]
    run(args.key, langs, fmts)


if __name__ == "__main__":
    main()
