# converter/texgen.py — 生成 LaTeX 源文件
from .tex2plain import tex2plain

# ---------------- TeX ----------------
def tex_preamble(lang):
    ctex = "\\usepackage{ctex}\n" if lang in ("zh", "bi") else ""
    return f"""% !TeX program = xelatex
\\documentclass[11pt,a4paper]{{article}}
\\usepackage[a4paper,margin=2.2cm]{{geometry}}
\\usepackage{{amsmath,amssymb}}
\\usepackage{{enumitem}}
\\usepackage{{multirow}}
\\usepackage{{xcolor}}
\\usepackage[most]{{tcolorbox}}
\\usepackage{{titlesec}}
\\usepackage{{hyperref}}
\\usepackage{{graphicx}}
\\graphicspath{{{{figures/}}}}
{ctex}
\\definecolor{{chapgray}}{{HTML}}{{4A4A4A}}
\\definecolor{{boxblue}}{{HTML}}{{D9E2EF}}
\\definecolor{{frameblue}}{{HTML}}{{8FA8C8}}

\\titleformat{{\\section}}
  {{\\Large\\bfseries\\color{{chapgray}}}}
  {{\\thesection}}{{0.6em}}{{}}
\\titlespacing{{\\section}}{{0pt}}{{1.2em}}{{0.5em}}

\\newcounter{{kc}}[section]
\\newcommand{{\\kcitem}}[1]{{\\stepcounter{{kc}}\\item[\\textbf{{\\arabic{{kc}}.}}] #1}}
\\newenvironment{{keypoints}}
  {{\\begin{{enumerate}}[leftmargin=2em,itemsep=2pt,topsep=2pt,label={{}}]}}
  {{\\end{{enumerate}}}}
\\newtcolorbox{{keybox}}{{enhanced,breakable,colback=boxblue,colframe=frameblue,
  boxrule=0.8pt,arc=2mm,left=8pt,right=8pt,top=6pt,bottom=6pt}}

\\setlength{{\\parindent}}{{0pt}}
\\newcommand{{\\keyfig}}[2]{{\\par\\medskip\\begin{{center}}\\includegraphics[width=#1\\linewidth]{{#2}}\\end{{center}}\\medskip}}
\\pagestyle{{plain}}
"""


def tex_item(block, lang):
    if lang == "bi":
        # 双语：英文条目在上，中文（灰色小字）紧随其下；子项逐条对照
        en_txt = block.get("en", "")
        zh_txt = block.get("zh", "")
        sub = block.get("sub", {}) or {}
        en_sub = sub.get("en", []) or []
        zh_sub = sub.get("zh", []) or []
        s = f"\\kcitem{{{en_txt}}}"
        if zh_txt:
            s += f"\n  \\par{{\\small\\color{{chapgray}}{zh_txt}}}"
        if en_sub:
            s += "\n  \\begin{itemize}[itemsep=1pt]\n"
            for e, z in zip(en_sub, zh_sub):
                s += f"    \\item {e}"
                if z:
                    s += f"\\par{{\\small\\color{{chapgray}}{z}}}"
                s += "\n"
            s += "  \\end{itemize}"
        return s
    txt = block[lang] if lang == "en" else block["zh"]
    sub = block["sub"][lang] if lang == "en" else block["sub"]["zh"]
    s = f"\\kcitem{{{txt}}}"
    if sub:
        s += "\n  \\begin{itemize}[itemsep=1pt]\n"
        for it in sub:
            s += f"    \\item {it}\n"
        s += "  \\end{itemize}"
    return s


def tex_table(rows):
    out = ["\\begin{center}", "\\renewcommand{\\arraystretch}{1.25}",
           "\\begin{tabular}{|l|c|c|c|}", "\\hline"]
    out.append(" & ".join(rows[0]) + " \\\\ \\hline")
    data = rows[1:]
    k = 0
    while k < len(data):
        r = data[k]
        if k + 1 < len(data) and data[k + 1][0].strip() == "":
            label = r[0]
            out.append(f"\\multirow{{2}}{{*}}{{{label}}} & "
                       + " & ".join(r[1:]) + " \\\\ \\cline{2-4}")
            k += 1
            r2 = data[k]
            out.append(" & " + " & ".join(r2[1:]) + " \\\\ \\hline")
        else:
            out.append(" & ".join(r) + " \\\\ \\hline")
        k += 1
    out.append("\\end{tabular}")
    out.append("\\end{center}")
    return "\n".join(out)


def tex_chapter(ch, lang, prev_part, doc):
    part = ch["part"]
    lines = []
    if part != prev_part and prev_part is not None:
        p = next((x for x in doc.get("parts", []) if x["id"] == part), None)
        if lang == "bi":
            en_label = p["title_en"] if p else part
            zh_label = (p["title_zh"] if p else "")
            lines.append(f"\\newpage\n\\part*{{\\color{{chapgray}}{en_label}}}")
            if zh_label:
                lines.append(f"{{\\Large\\color{{chapgray}}{zh_label}}}\\vspace{{0.3em}}")
            lines.append(f"\\addcontentsline{{toc}}{{section}}{{{en_label}}}\n")
        else:
            label = p[f"title_{lang}"] if p else part
            if lang == "en":
                lines.append(f"\\newpage\n\\part*{{\\color{{chapgray}}{label}}}"
                             f"\n\\addcontentsline{{toc}}{{section}}{{{label}}}\n")
            else:
                lines.append(f"\\newpage\n\\begin{{center}}\n  "
                             "{\\LARGE\\bfseries\\color{chapgray} "
                             f"{label}}}\n\\end{{center}}\n\\vspace{{0.5em}}\n")
    if lang == "bi":
        en_title = ch["title_en"]; zh_title = ch["title_zh"]
    else:
        title = ch["title_en"] if lang == "en" else ch["title_zh"]
    if ch.get("blocks") and ch["blocks"][0].get("t") == "proofs":
        if lang == "bi":
            lines.append(f"\\section*{{{en_title}}}")
            lines.append(f"{{\\large\\color{{chapgray}}{zh_title}}}\\vspace{{0.3em}}")
            lines.append(f"\\addcontentsline{{toc}}{{section}}{{{en_title}}}\n")
            intro_en = ch.get("intro_en", []); intro_zh = ch.get("intro_zh", [])
            if intro_en:
                lines.append(" \\\\ ".join(intro_en) + "\n")
            if intro_zh:
                lines.append("{\\small\\color{chapgray} "
                             + " \\\\ ".join(intro_zh) + "}\n")
            for p in ch["blocks"][0]["proofs"]:
                lines.append("\\begin{keybox}")
                lines.append(f"\\textbf{{{p['name_en']}}} \\hfill {p['formula_en']}\n")
                lines.append("\n".join(p["steps_en"]))
                lines.append("\\par\\vspace{4pt}{\\small\\color{chapgray}")
                lines.append(f"\\textbf{{{p['name_zh']}}} \\hfill {p['formula_zh']}\n")
                lines.append("\n".join(p["steps_zh"]))
                lines.append("}")
                lines.append("\\end{keybox}\n")
        else:
            lines.append(f"\\section*{{{title}}}\n"
                         f"\\addcontentsline{{toc}}{{section}}{{{title}}}\n")
            intro = ch.get(f"intro_{lang}", [])
            if intro:
                lines.append(" \\\\ ".join(intro) + "\n")
            for p in ch["blocks"][0]["proofs"]:
                name = p[f"name_{lang}"]
                formula = p[f"formula_{lang}"]
                steps = p[f"steps_{lang}"]
                lines.append("\\begin{keybox}")
                lines.append(f"\\textbf{{{name}}} \\hfill {formula}\n")
                lines.append("\n".join(steps))
                lines.append("\\end{keybox}\n")
    else:
        if lang == "bi":
            lines.append(f"\\section{{{en_title}}}")
            lines.append(f"{{\\large\\color{{chapgray}}{zh_title}}}\\vspace{{0.3em}}")
        else:
            lines.append(f"\\section{{{title}}}")
        lines.append("\\begin{keybox}\\begin{keypoints}")
        for b in ch["blocks"]:
            if b["t"] == "item":
                lines.append(tex_item(b, lang))
            elif b["t"] == "fig":
                lines.append(f"\\keyfig{{{b['w']}}}{{{b['file']}}}")
            elif b["t"] == "table":
                lines.append(tex_table(b["rows"]))
        lines.append("\\end{keypoints}\\end{keybox}")
    return "\n".join(lines), part


def build_tex(doc, lang):
    preamble = tex_preamble(lang)
    if lang == "bi":
        title = (doc["title_en"].replace("&", "\\&")
                 + "\\\\[0.2em]{\\large\\color{chapgray}"
                 + doc["title_zh"].replace("&", "\\&") + "}")
        subtitle = (doc["subtitle_en"].replace("&", "\\&")
                    + "\\\\ {\\color{chapgray}"
                    + doc["subtitle_zh"].replace("&", "\\&") + "}")
    else:
        # 标题/副标题中的 & 在 LaTeX 里是制表符，需要转义
        title = doc[f"title_{lang}"].replace("&", "\\&")
        subtitle = doc[f"subtitle_{lang}"].replace("&", "\\&")
    body = []
    prev = None
    for ch in doc["chapters"]:
        s, prev = tex_chapter(ch, lang, prev, doc)
        body.append(s)
    body_text = "\n\n".join(body)
    full = (preamble +
            f"\\title{{\\bfseries {title}\\\\ \\large {subtitle}}}\n"
            "\\author{}\\date{}\n\\begin{document}\n\\maketitle\n\\vspace{-3em}\n"
            + body_text + "\n\\end{document}\n")
    return full