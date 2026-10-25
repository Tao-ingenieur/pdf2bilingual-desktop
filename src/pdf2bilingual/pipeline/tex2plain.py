# converter/tex2plain.py — LaTeX 标记转 Unicode 纯文本（PPT 用）
import re

# ---------- LaTeX → Unicode 纯文本（PPT 渲染用）----------
SUP = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵",
       "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻",
       "=": "⁼", "n": "ⁿ", "i": "ⁱ",
       "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "f": "ᶠ",
       "g": "ᵍ", "h": "ʰ", "j": "ʲ", "k": "ᵏ", "l": "ˡ", "m": "ᵐ",
       "o": "ᵒ", "p": "ᵖ", "r": "ʳ", "s": "ˢ", "t": "ᵗ", "u": "ᵘ",
       "v": "ᵛ", "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ"}
SUB = {"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅",
       "6": "₆", "7": "₇", "8": "₈", "9": "₉", "+": "₊", "-": "₋",
       "a": "ₐ", "e": "ₑ", "x": "ₓ", "o": "ₒ", "h": "ₕ", "k": "ₖ",
       "l": "ₗ", "m": "ₘ", "n": "ₙ", "p": "ₚ", "s": "ₛ", "t": "ₜ",
       "i": "ᵢ", "r": "ᵣ", "u": "ᵤ", "v": "ᵥ"}
SYMBOLS = {"neq": "≠", "geqslant": "≥", "leqslant": "≤", "geq": "≥",
           "leq": "≤", "ge": "≥", "le": "≤", "Rightarrow": "⇒",
           "rightarrow": "→", "to": "→", "cdot": "·", "times": "×", "div": "÷",
           "pm": "±", "mp": "∓", "infty": "∞", "approx": "≈",
           "circ": "°", "theta": "θ", "alpha": "α", "beta": "β",
           "lambda": "λ", "Delta": "Δ",            "in": "∈", "notin": "∉", "int": "∫", "sum": "∑",
           "ldots": "…", "cdots": "⋯", "dots": "…", "vdots": "⋮",
           "propto": "∝", "deg": "°", "pi": "π", "angle": "∠"}
FUNCS = {"sin", "cos", "tan", "log", "ln", "sec", "cosec", "cot",
         "arcsin", "arccos", "arctan", "exp"}
DROPCMDS = {"textbf", "textit", "texttt", "textrm", "mathrm", "mathbf",
            "mathsf", "mathtt", "mathbb", "operatorname", "multirow",
            "hfill", "centering", "noindent", "vspace", "hspace", "text",
            "quad", "qquad", "bigl", "bigr", "Bigl", "Bigr", "big",
            "Big", "bigm", "displaystyle"}
FRACS = {"1/2": "½", "1/3": "⅓", "2/3": "⅔", "1/4": "¼", "3/4": "¾"}


def _balanced(s, i):
    """s[i] 必须是 '{'，返回 (内容, 结束后位置)。"""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
    return s[i + 1:], len(s)


def _replace_cmd(s, cmd, fn=None):
    """把 \\cmd{arg} 替换为 fn(arg)（fn 缺省为恒等）。"""
    out, i = [], 0
    token = "\\" + cmd
    while True:
        j = s.find(token, i)
        if j == -1:
            out.append(s[i:]); break
        k = j + len(token)
        # 防止把 \loga 当作 \log
        if k < len(s) and s[k].isalpha():
            out.append(s[i:k]); i = k; continue
        out.append(s[i:j])
        if k < len(s) and s[k] == "{":
            arg, k2 = _balanced(s, k)
            out.append(fn(arg) if fn else arg)
            i = k2
        else:
            # 无参数的裸命令：保留反斜杠，交给后续符号/丢弃处理
            out.append(token)
            i = k
    return "".join(out)


def _supsub(s):
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in "^_" and i + 1 < n:
            mark = c
            if s[i + 1] == "{":
                arg, j = _balanced(s, i + 1)
                tbl = SUP if mark == "^" else SUB
                conv = "".join(tbl.get(ch, ch) for ch in arg)
                if mark == "_" and any(ch not in tbl for ch in arg):
                    conv = "_(" + arg + ")"
                out.append(conv); i = j
            else:
                ch = s[i + 1]
                tbl = SUP if mark == "^" else SUB
                out.append(tbl.get(ch, ch if ch in "°%" else mark + ch))
                i += 2
        else:
            out.append(c); i += 1
    return "".join(out)


def _frac(s):
    pat = re.compile(r"\\([dt]?)frac")
    out, i = [], 0
    while True:
        m = pat.search(s, i)
        if not m:
            out.append(s[i:]); break
        out.append(s[i:m.start()])
        a, j = _balanced(s, m.end())
        b, k = _balanced(s, j)
        fa, fb = _frac(a).strip(), _frac(b).strip()

        def wrap(t):
            if re.fullmatch(r"[A-Za-z0-9]+", t):
                return t
            if re.fullmatch(r"\([^{}]*\)", t) or re.fullmatch(r"\\sqrt\{[^{}]*\}", t):
                return t          # 已带括号分组，避免双重括号
            return f"({t})"
        out.append(FRACS.get(fa + "/" + fb, wrap(fa) + "/" + wrap(fb)))
        i = k
    return "".join(out)


def _binom(s):
    r"""\binom{n}{r} / \dbinom{n}{r} -> ⁿCᵣ（单字符）或 C(n,r)。"""
    pat = re.compile(r"\\[dt]?binom")
    out, i = [], 0
    while True:
        m = pat.search(s, i)
        if not m:
            out.append(s[i:]); break
        out.append(s[i:m.start()])
        a, j = _balanced(s, m.end())
        b, k = _balanced(s, j)
        a, b = a.strip(), b.strip()
        if len(a) == 1 and len(b) == 1:
            out.append(SUP.get(a, a) + "C" + SUB.get(b, b))
        else:
            out.append(f"C({a}, {b})")
        i = k
    return "".join(out)


def tex2plain(s):
    """把 TeX 数学/文本标记转为可读的 Unicode 纯文本（PPT 用）。"""
    # 显示公式与换行参数：\[ ... \] 与 \\[2pt]
    s = re.sub(r"\\\\\[[^\]]*\]", " ", s)
    s = s.replace("\\[", " ").replace("\\]", " ")
    s = s.replace("\\left", "").replace("\\right", "")
    # \multirow{2}{*}{label} -> label
    s = re.sub(r"\\multirow\{[^{}]*\}\{[^{}]*\}", "", s)
    for cmd in ("mathbb", "textbf", "textit", "texttt", "textrm",
                "mathrm", "mathbf", "mathsf", "mathtt", "operatorname"):
        if cmd == "mathbb":
            s = _replace_cmd(s, cmd, lambda a: {"R": "ℝ", "Z": "ℤ",
                                                "N": "ℕ", "Q": "ℚ"}.get(a.strip(), a))
        else:
            s = _replace_cmd(s, cmd)
    s = _binom(s)
    s = _frac(s)
    s = re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", s)
    s = s.replace("\\sqrt", "√")
    # 符号与函数名（最长前缀匹配，避免 \in\mathrm{R} 拼成 \inR 后无法识别）
    def sym(m):
        name = m.group(1)
        for L in range(len(name), 0, -1):
            head, rest = name[:L], name[L:]
            if head in SYMBOLS:
                return SYMBOLS[head] + rest
            if head in FUNCS:
                return head + (" " if rest else "") + rest
            if head in DROPCMDS:
                return rest
        return name
    s = re.sub(r"\\([a-zA-Z]+)", sym, s)
    s = _supsub(s)
    # 间距与残余符号
    s = s.replace("\\\\", " ")          # 换行符 \\ （先于 \, \; 等间距处理）
    s = s.replace("\\quad", " ").replace("\\qquad", " ")
    s = re.sub(r"\\[,;:! ]", " ", s)
    for esc, ch in (("\\%", "%"), ("\\&", "&"), ("\\{", "{"), ("\\}", "}"),
                    ("\\(", ""), ("\\)", ""), ("$", ""), ("~", " ")):
        s = s.replace(esc, ch)
    s = re.sub(r" {2,}", " ", s)
    s = s.replace("{", "").replace("}", "")
    # 数字/字母与函数名之间补空格（2bc\cos A -> 2bc cos A）
    s = re.sub(r"(\d)(?=(?:sin|cos|tan|log|ln)\b)", r"\1 ", s)
    s = re.sub(r"([a-z])(?=(?:cos|sin|tan)\b)", r"\1 ", s)
    return s.strip()