"""過去問マスタ（master_C1〜C4_*.json）の問題文・選択肢・正答・図を、data/exams/ の問題に反映する。

使い方:
    python tools/apply_master.py <マスタJSONのフォルダ> --data data [--dry-run] [--figures <図の画像フォルダ>]

- 対象は共通科目（C1 一般・C2 法令・C3 デザイン・C4 分析）。マスタは「正」とし、サイト側の文面がマスタと
  文字レベルで違うときだけ、マスタの文面（サイトの表記に直したもの）で置き換える。
  表記だけの違い（空白、全角半角、単位の書き方、㋑㋺の印、LaTeX の書き方など）は置き換えない。
- マスタの図（figures/<ID>_1.png）は、図の画像フォルダにあれば src/assets/figures にコピーして問題に付ける。
  「【図の内容（文字化）：…】」は、図の代替テキスト（alt）に使う。
- マスタに独自に付けられた注記（※…、紙面の列見出し…、文字化した…）は取り込まない。
"""
import argparse, difflib, glob, json, re, shutil, unicodedata
from pathlib import Path
import yaml

SUB = {1: "ippan", 2: "hourei", 3: "design", 4: "bunseki", 5: "funjin", 6: "tokka", 7: "kinzoku", 8: "yuki"}
MARK = "ⒶⒷⒸⒹⒺ㋑㋺㋩㋥㋭㋬㋣"
FIG_RE = re.compile(r"!\[([^\]]*)\]\(figures/([^)]+)\)")
DESC_RE = re.compile(r"【図の内容（文字化）[：:](.*?)】", re.S)
NOTE_RE = re.compile(r"^(※|（注：文字化|選択肢は表|選択肢の(数値|各行)は|選択肢\d+の.*文字化)")


def exam_key(code):
    m = re.match(r"([HR])(\d+)-(\d)", code)
    era, n, r = m.group(1), int(m.group(2)), int(m.group(3))
    fy = n + 1988 if era == "H" else n + 2018
    return f"{fy}-08" if r == 1 else f"{fy + 1}-02"


# ---------------------------------------------------------------- LaTeX → サイトの表記
GREEK = {"alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "eta": "η", "mu": "μ", "rho": "ρ",
         "sigma": "σ", "Sigma": "Σ", "sum": "Σ", "pi": "π", "theta": "θ", "lambda": "λ", "epsilon": "ε"}
SYM = {"times": "×", "div": "÷", "cdot": "·", "pm": "±", "le": "≦", "leq": "≦", "ge": "≧", "geq": "≧",
       "leftharpoons": "⇄", "rightleftharpoons": "⇄", "leftrightarrows": "⇄", "leftarrows": "⇄", "rightleftarrows": "⇄", "leftrightharpoons": "⇄", "rightarrow": "→", "to": "→", "approx": "≒",
       "ne": "≠", "infty": "∞", "circ": "°", "%": "%", ",": " ", ";": " ", " ": " "}


def _brace(s, i):
    """s[i] が { のとき、対応する } までの内容と次の位置を返す"""
    d = 0
    for j in range(i, len(s)):
        if s[j] == "{": d += 1
        elif s[j] == "}":
            d -= 1
            if d == 0: return s[i + 1:j], j + 1
    return s[i + 1:], len(s)


def tex(s):
    out, i = "", 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            m = re.match(r"\\([A-Za-z]+|.)", s[i:], re.S)
            if not m:
                out += "\\"; i += 1; continue
            name = m.group(1); i += len(m.group(0))
            if name in ("frac", "dfrac"):
                while i < len(s) and s[i] == " ": i += 1
                a, i = _brace(s, i); b, i = _brace(s, i)
                a, b = tex(a), tex(b)
                wrap = lambda x: x if re.fullmatch(r"[\w.α-ωΑ-Ω]+(<su[bp]>[^<]*</su[bp]>)*", x) else f"({x})"
                out += f"{wrap(a)}/{wrap(b)}"
            elif name == "sqrt":
                a, i = _brace(s, i); a = tex(a)
                out += "√" + (a if re.fullmatch(r"[\w.]+", a) else f"({a})")
            elif name in ("bar", "overline"):
                a, i = _brace(s, i); out += tex(a) + "\u0304"
            elif name in ("mathrm", "text", "mathit", "rm", "left", "right", "displaystyle", "boldsymbol"):
                if i < len(s) and s[i] == "{":
                    a, i = _brace(s, i); out += tex(a)
            elif name in ("log", "ln", "exp", "max", "min"): out += name
            elif name in GREEK: out += GREEK[name]
            elif name in SYM: out += SYM[name]
            else: out += "\\" + name   # 未対応は残して、後で検出する
        elif c in "_^" and i + 1 < len(s):
            tag = "sub" if c == "_" else "sup"; i += 1
            if s[i] == "{": a, i = _brace(s, i)
            elif s[i] == "\\":
                m2 = re.match(r"\\([A-Za-z]+)", s[i:])
                if m2 and m2.group(1) in ("mathrm", "text", "mathit", "rm") and s[i + len(m2.group(0)):i + len(m2.group(0)) + 1] == "{":
                    a, i = _brace(s, i + len(m2.group(0)))
                elif m2:
                    a, i = m2.group(0), i + len(m2.group(0))
                else:
                    a, i = s[i], i + 1
            else: a, i = s[i], i + 1
            a = tex(a)
            if tag == "sup" and a in ("2", "3", "-1", "−1", "-2", "−2"):
                out += {"2": "²", "3": "³", "-1": "⁻¹", "−1": "⁻¹", "-2": "⁻²", "−2": "⁻²"}[a]
            else: out += f"<{tag}>{a}</{tag}>"
        elif c == "{" or c == "}": i += 1
        else: out += c; i += 1
    return out


def pretty(s):
    """式だけからなる文字列の = + × のまわりに空白を入れる"""
    if re.fullmatch(r"[A-Za-z0-9=+\-×÷／/()√σΣ\u0304<>\s.|²³⁻¹]+", s) and re.search(r"[=+×]", s):
        s = re.sub(r"\s*([=+×])\s*", lambda m: {"=": " ＝ ", "+": " ＋ ", "×": " × "}[m.group(1)], s)
    return s.strip()


def convert(s):
    """マスタの文字列を、サイトの表記に直す（$…$ の LaTeX を直す。式だけの文字列は空白を整える）"""
    s = str(s or "")
    one = re.fullmatch(r"\s*\$([^$]+)\$\s*", s)
    if one:
        return pretty(tex(one.group(1)))
    return re.sub(r"\$([^$]+)\$", lambda m: tex(m.group(1)), s)


# ---------------------------------------------------------------- 比較用の正規化
def norm(s):
    s = re.sub(r"[Ⓐ-Ⓩ㋑㋺㋩㋥㋭㋬㋣]", "", str(s or ""))
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("剝", "剥").replace("塡", "填").replace("﨑", "崎")
    s = re.sub(r"<[^>]+>", "", s).replace("℃", "°C").replace("·", "")
    s = re.sub(r"\\[A-Za-z]+", "", s)
    return re.sub(r"[\s\u3000、，,。．.「」『』（）()［］\[\]｜|／/・･:：;；\-−―ー–—*`>＝=×÷°\u0304$\\{}_^]", "", s)


def split_choice(c):
    """「Ⓐ…　Ⓑ…」「㋑…　㋺…」の形の組合せを「… ／ …」に直す。(文字列, 見出しの印のリスト or None)"""
    c = c.strip()
    parts = [p for p in re.split(r"[\u3000]+", c) if p]
    if len(parts) < 2: return c, None
    heads, bodies = [], []
    for p in parts:
        m = re.match(f"^([{MARK}])\\s*(.*)$", p)
        if m: heads.append(m.group(1)); bodies.append(m.group(2).strip())
        else: heads.append(None); bodies.append(p.strip())
    if all(heads): return " ／ ".join(bodies), heads
    # 印が ASCII の A, B, C（Ⓐ が通常の A になっているもの）：A, B, C と順に並ぶときだけ印とみなす
    letters = "ABCDE"
    ok, hs, bs = True, [], []
    for n, p in enumerate(parts):
        if n < len(letters) and p.startswith(letters[n]) and len(p) > 1:
            hs.append("ⒶⒷⒸⒹⒺ"[n]); bs.append(p[1:].strip())
        else: ok = False; break
    if ok: return " ／ ".join(bs), hs
    return c, None


def strip_figdesc(t):
    """「（図の3：…（…）…）」を「図の3」にする（括弧が入れ子でも、対応する閉じ括弧まで）"""
    out, i = "", 0
    while i < len(t):
        m = re.match(r"（(図の\d)：", t[i:])
        if m:
            d, j = 0, i
            while j < len(t):
                if t[j] == "（": d += 1
                elif t[j] == "）":
                    d -= 1
                    if d == 0: break
                j += 1
            out += m.group(1); i = j + 1
        else:
            out += t[i]; i += 1
    return out


def clean_text(q):
    """マスタの question + material から、図の記述・注記を除いた本文と、図のファイル名・代替テキストを返す"""
    text = (q["question"] or "")
    mat = q.get("material")
    if mat: text += "\n" + mat
    fig_file = alt = desc = None
    m = FIG_RE.search(text)
    if m: alt, fig_file = m.group(1), m.group(2)
    d = DESC_RE.search(text)
    if d: desc = d.group(1).strip()
    text = FIG_RE.sub("", text); text = DESC_RE.sub("", text)
    blocks, table = [], []
    for ln in text.splitlines():
        t = ln.strip()
        if t.startswith("|"):
            table.append(t); continue
        if table: blocks.append("\n".join(table)); table = []
        if not t or NOTE_RE.match(t): continue
        t = re.sub(r"^[-・]\s+", "", t)
        t = re.sub(r"^（図）\s*", "", t)
        blocks.append(t)
    if table: blocks.append("\n".join(table))
    return convert("\n\n".join(blocks)), fig_file, alt, desc


# マスタ側に独自の注記（列見出し、下線の説明など）が入っていて、サイトの表記のほうが適切なもの
SKIP_STEM = {"H29-1-C2-14", "R7-1-C2-11", "R7-1-C2-14", "R7-2-C2-14", "R8-1-C2-14", "H29-2-C4-04", "H30-1-C4-04"}
SKIP_CHOICES = {"R8-1-C2-14", "H29-2-C4-04"}
DATA_IN_TEXT = {"R5-2-C3-07", "R6-2-C3-06"}
FORCE_STEM = {"R3-1-C6-19"}     # サイト側の本文に読み取りの残骸があるもの
# 選択肢が絵そのもの（文字の選択肢にすると答えの手がかりになる）なので「図の1〜5」のままにする
KEEP_FIGLABEL = {"R8-1-C1-02", "R8-1-C4-07"}
# 分数と根号の入った式は、LaTeX のまま選択肢にする（サイトのビルド時に KaTeX で表示する）
LATEX_CHOICES = {"R2-1-C5-02", "R5-1-C5-02"}
# 原本の印字そのままにしている箇所の注記
TEXT_NOTES = {
    "H28-2-C3-05": "条件文の「個体」は、原本の印字のとおりです（「固体」の誤植とみられますが、原文のまま掲載しています）。",
    "H29-1-C2-11": "選択肢5の「労働者1人にいて」は、原本の印字のとおりです（「について」の「つ」が抜けていますが、原文のまま掲載しています）。",
    "R8-1-C1-06": "選択肢3の「蛋白変成作用」は、一般には「蛋白変性」と表記されますが、原本の印字のとおり掲載しています。",
}
# 図の代替テキストから、答えの手がかりになる語を除く
ALT_STRIP = [(r"（?(メスシリンダー|ビュレット|ホールピペット|メスピペット|メスフラスコ)）?", ""), (r"（健康有害性の絵表示）", "")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("masters")
    ap.add_argument("--data", default="data")
    ap.add_argument("--figures", default=None, help="マスタの図（<ID>_1.png）のあるフォルダ")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", nargs="*", default=None, help="この ID だけ処理する")
    a = ap.parse_args()
    figdir = Path(a.figures) if a.figures else None
    changed, flagged, files = [], [], {}
    for f in sorted(glob.glob(str(Path(a.masters) / "master_C*_*.json"))):
        for q in json.load(open(f, encoding="utf-8"))["questions"]:
            if a.only and q["id"] not in a.only: continue
            key, subj = exam_key(q["exam"]["code"]), SUB[q["subject"]["no"]]
            p = Path(a.data) / "exams" / key / f"{subj}.yaml"
            if not p.exists(): continue
            if p not in files: files[p] = yaml.safe_load(p.read_text(encoding="utf-8"))
            d = files[p]
            if d.get("excluded"): continue
            s = next((x for x in d["questions"] if x["num"] == q["number"]), None)
            if not s or not s.get("stem"): continue
            if q["id"] in TEXT_NOTES: s["text_note"] = TEXT_NOTES[q["id"]]
            # --- 正答
            ans = q["answer"]
            if sorted(ans if isinstance(ans, list) else [ans]) != sorted(s["answer"] if isinstance(s["answer"], list) else [s["answer"]]):
                changed.append((q["id"], "正答（マスタに合わせた）", s["answer"], ans))
                s["answer"] = ans[0] if len(ans) == 1 else ans
            # --- 問題文
            text, fig_file, alt, desc = clean_text(q)
            mt, st = norm(text), norm(s["stem"])
            if q["id"] in SKIP_STEM:
                pass
            elif q["id"] in DATA_IN_TEXT and "【測定結果】" in s["stem"]:
                pass
            elif q["id"] in DATA_IN_TEXT:
                # 図で出していた測定結果を、本文の文字にする
                new_stem = text.replace("\n\n【測定結果】", "\n\n【測定結果】").strip()
                changed.append((q["id"], "問題文（測定結果を文字に）", s["stem"], new_stem)); s["stem"] = new_stem
                for fg in s.get("figures") or []:
                    if not a.dry_run: (Path("src/assets/figures") / fg["file"]).unlink(missing_ok=True)
                s["figures"] = []
            elif mt != st and sorted(mt) != sorted(st):
                sim = difflib.SequenceMatcher(None, mt, st).ratio()
                figs_now = s.get("figures") or []
                drop_fig = bool(figs_now) and not q["figure"]["has_figure"] and "\\" not in text and (
                    all("choices" in x["file"] for x in figs_now) or "|---" in text)
                if drop_fig or q["id"] in FORCE_STEM:
                    changed.append((q["id"], "問題文（図・表を文字に／読み取りの残骸を除く）", s["stem"], text)); s["stem"] = text
                    if "|---" in text:
                        for fg in figs_now:
                            if not a.dry_run: (Path("src/assets/figures") / fg["file"]).unlink(missing_ok=True)
                        s["figures"] = []
                elif mt in st:
                    flagged.append((q["id"], "サイト側の問題文にマスタにない文字がある（置き換えない）", s["stem"][-40:], ""))
                elif sim >= 0.85 and "\\" not in text:
                    changed.append((q["id"], "問題文", s["stem"], text)); s["stem"] = text
                else:
                    flagged.append((q["id"], f"問題文が大きく違う（一致率{sim:.2f}）", s["stem"][:60], text[:60]))
            # --- 選択肢
            new, cols = [], None
            if q["id"] in LATEX_CHOICES:
                new = [c.strip() for c in q["choices"]]
                if len(new) == len(s["choices"]) and any(norm(o) != norm(n) for o, n in zip(s["choices"], new)):
                    changed.append((q["id"], "選択肢（LaTeX）", s["choices"][0], new[0])); s["choices"] = new
            for c in ([] if q["id"] in LATEX_CHOICES else q["choices"]):
                t, h = split_choice(convert(c))
                t = strip_figdesc(t)     # 図の説明文は選択肢に入れない（答えの手がかりになるため）
                new.append(t); cols = cols or h
            if len(new) != len(s["choices"]):
                flagged.append((q["id"], "選択肢の数が違う", len(s["choices"]), len(new)))
            else:
                for i, (o, n) in enumerate(zip(s["choices"], new)):
                    if re.search(r"図の\d$", o.strip()) and "／" in o and q["figure"]["has_figure"]:
                        continue            # 「物質名 ／ 図の3」：Ⓑの列は画像のまま
                    if o.strip().startswith("図の"):
                        # サイトが「図の1」のときは、マスタに文字の選択肢があればそれを使う
                        n = strip_figdesc(n)
                        if q["id"] in KEEP_FIGLABEL or "\\" in n or re.match(r"^図の?\d", n):
                            continue
                        changed.append((q["id"], f"選択肢{i+1}", o, n)); s["choices"][i] = n
                        continue
                    if q["id"] in SKIP_CHOICES:
                        continue
                    if norm(o) != norm(n):
                        if norm(n) in norm(o):
                            continue            # サイト側のほうが文字が多い（置き換えない）
                        if "\\" in n:
                            flagged.append((q["id"], f"選択肢{i+1}に未対応のLaTeX", o[:40], n[:60]))
                        else:
                            changed.append((q["id"], f"選択肢{i+1}", o, n)); s["choices"][i] = n
                if cols and not s.get("columns") and any(h for h in cols) \
                        and all(c.count(" ／ ") == len(cols) - 1 for c in s["choices"]):
                    s["columns"] = cols
            # --- 図
            if q["figure"]["has_figure"] and q["figure"]["files"]:
                src = (figdir / q["figure"]["files"][0]) if figdir else None
                name = f"{key}-{subj}-{q['number']:02d}-fig.png"
                if src and src.exists():
                    already = any(x["file"] == name for x in s.get("figures") or []) and (Path("src/assets/figures") / name).exists()
                    if not a.dry_run and not already:
                        shutil.copy(src, Path("src/assets/figures") / name)
                    old = [x["file"] for x in s.get("figures") or []]
                    text_alt = desc or alt or f"問{q['number']}の図"
                    for pat, rep in ALT_STRIP: text_alt = re.sub(pat, rep, text_alt)
                    s["figures"] = [{"file": name, "alt": text_alt}]
                    for o in old:
                        if o != name and not a.dry_run: (Path("src/assets/figures") / o).unlink(missing_ok=True)
                    changed.append((q["id"], "図", old, name))
                else:
                    flagged.append((q["id"], "マスタの図の画像が見つからない", q["figure"]["files"], ""))
    # 選択肢を文字にできた問題の、選択肢用の旧画像を外す
    for pth, d in files.items():
        for s in d["questions"]:
            figs = s.get("figures") or []
            if figs and all("choices" in x["file"] for x in figs) and not any(c.strip().startswith("図の") for c in s["choices"]):
                if not a.dry_run:
                    for x in figs: (Path("src/assets/figures") / x["file"]).unlink(missing_ok=True)
                s["figures"] = []
    for pth, d in files.items():
        if not a.dry_run:
            pth.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    for c in changed: print("変更", c[0], c[1], "|", str(c[2])[:50].replace("\n", "/"), "→", str(c[3])[:50].replace("\n", "/"))
    for fl in flagged: print("要確認", *fl)
    print(f"変更 {len(changed)} 件、要確認 {len(flagged)} 件" + ("（dry-run）" if a.dry_run else ""))


if __name__ == "__main__":
    main()
