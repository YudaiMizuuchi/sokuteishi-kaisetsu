"""安全衛生技術試験協会の公表試験問題PDFから、問題文・選択肢・正答・図を data/exams/ に取り込む。

使い方:
    pip install pdfplumber pyyaml
    python tools/import_pdf.py <PDFのフォルダ> [--data data] [--figures src/assets/figures] [--force]

ファイル名から回と科目を判定する。
    EM20261803.pdf … EM + 年度 + 回(1/2) + 8 + 科目番号(01〜09)
    20260217-3.pdf … 実施日 + "-" + 科目番号(1〜9)

公表PDFの作り（一太郎で作成）に合わせた読み取り:
- 正答の「○」は文字ではなく細かい図形の集まりで描かれているので、図形のかたまりから見つける
- 上付き・下付きの文字（m⁻¹、H₂ など）は文字の大きさと位置から判定する
- ふりがなは捨てる
- 図（画像・図形）は問題ごとに切り出して PNG にする。図の中の○印は白で消す
- 数式などで選択肢を文字にできない問題は、選択肢の部分を画像にする

既存の問題ファイルがあれば、stem・choices・answer・figures が空の問題だけを埋める（--force で上書き）。
罠の型一覧から作った正答肢（_key_choice）と照合し、要確認の問題を import_report.csv に書き出す。
"""
import argparse
import csv
import difflib
import re
import unicodedata
from pathlib import Path

import yaml

SUBJECT_CODES = {
    "1": "ippan", "2": "hourei", "3": "design", "4": "bunseki",
    "5": "yuki", "6": "funjin", "7": "tokka", "8": "kinzoku", "9": "hoshasei",
}
SUP = str.maketrans("0123456789-+−()nx", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺⁻⁽⁾ⁿˣ")
SUB = str.maketrans("0123456789-+()", "₀₁₂₃₄₅₆₇₈₉₋₊₍₎")
CHOICE_DIGITS = "１２３４５"


# ---------------------------------------------------------------- 回と科目
def exam_from_filename(name):
    m = re.search(r"EM(\d{4})([12])8(\d{2})", name)
    if m:
        fy, rnd, code = int(m.group(1)), m.group(2), m.group(3)
        exam = f"{fy}-08" if rnd == "1" else f"{fy + 1}-02"
        return exam, SUBJECT_CODES.get(str(int(code))), None
    m = re.search(r"(\d{4})(\d{2})(\d{2})-(\d)", name)
    if m:
        y, mo, d, code = m.groups()
        return f"{y}-{mo}", SUBJECT_CODES.get(code), f"{y}-{mo}-{d}"
    return None, None, None


# ---------------------------------------------------------------- 文字の整形
def to_half(s):
    """全角の英数字だけを半角にする（和文の記号や括弧はそのまま）。"""
    out = []
    for ch in s:
        o = ord(ch)
        if 0xFF10 <= o <= 0xFF19 or 0xFF21 <= o <= 0xFF3A or 0xFF41 <= o <= 0xFF5A:
            out.append(chr(o - 0xFEE0))
        elif ch == "－":
            out.append("-")
        elif ch == "Ⅾ":  # ローマ数字の D（C・Ⅾ測定）を通常の D に
            out.append("D")
        else:
            out.append(ch)
    return "".join(out)


def is_kana(ch):
    return "\u3040" <= ch <= "\u30ff"


def tidy(s):
    """PDF由来の余分な空白を詰め、穴埋めの記号を［㋑］の形にする。"""
    s = re.sub(r"(?<=[0-9A-Za-z,]) (?=-)", "", s)          # 1,2 -ジクロロ → 1,2-ジクロロ
    s = re.sub(r"(?<=-) (?=[（(0-9])", "", s)
    s = re.sub(r"（\s+", "（", s)
    s = re.sub(r"\s+）", "）", s)
    if "に入る" in s and "「" in s:
        head, body = s.split("「", 1)
        body = re.sub(r"\s*([㋑㋺㋩㋥])\s*", r"［\1］", body)
        s = head + "「" + body
    return s


def md_escape(s):
    return re.sub(r"([*_`\[\]\\])", r"\\\1", s)


# ---------------------------------------------------------------- 行の組み立て
class Line:
    def __init__(self, page, chars):
        self.page = page
        self.main = list(chars)
        self.small = []
        self.top = min(c["top"] for c in chars)
        self.bottom = max(c["bottom"] for c in chars)

    @property
    def x0(self):
        return min(c["x0"] for c in self.main)

    def text(self, exclude=None, col_gap=None):
        """col_gap を指定すると、それより広い間隔を表の列の区切り（ ／ ）とみなす。"""
        cs = sorted(self.main + self.small, key=lambda c: c["x0"])
        if exclude:
            cs = [c for c in cs if not inside(c, exclude)]
        out, prev = "", None
        for c in cs:
            t = c["text"]
            if c.get("kind") == "sup":
                t = to_half(t).translate(SUP)
            elif c.get("kind") == "sub":
                t = to_half(t).translate(SUB)
            if prev is not None:
                gap = c["x0"] - prev["x1"]
                ascii_pair = (prev["text"].isascii() and c["text"].isascii()) or c.get("kind") or prev.get("kind")
                if col_gap and gap > col_gap:
                    out = out.rstrip() + " ／ "
                elif not out.endswith(" ") and gap > (1.5 if ascii_pair else 2.5):
                    out += " "
            out += t
            prev = c
        return out.strip()


def inside(c, boxes):
    cx, cy = (c["x0"] + c["x1"]) / 2, (c["top"] + c["bottom"]) / 2
    return any(b[0] <= cx <= b[2] and b[1] <= cy <= b[3] for b in boxes)


def build_lines(page, pno):
    chars = [c for c in page.chars if c["text"].strip()]
    body = sorted((c for c in chars if c["size"] >= 9), key=lambda c: (c["top"], c["x0"]))
    small = [c for c in chars if c["size"] < 9]
    lines = []
    for c in body:
        for ln in lines:
            if abs(ln.top - c["top"]) < 3:
                ln.main.append(c)
                ln.bottom = max(ln.bottom, c["bottom"])
                break
        else:
            lines.append(Line(pno, [c]))
    for c in small:
        if is_kana(c["text"]):
            continue  # ふりがな
        cy = (c["top"] + c["bottom"]) / 2
        best = min(lines, key=lambda ln: abs((ln.top + ln.bottom) / 2 - cy), default=None)
        if not best or abs((best.top + best.bottom) / 2 - cy) > 10:
            continue
        mid = (best.top + best.bottom) / 2
        best.small.append(dict(c, kind="sup" if cy < mid else "sub"))
    for ln in lines:
        ln.main.sort(key=lambda c: c["x0"])
    return sorted(lines, key=lambda ln: ln.top)


NOISE = [
    re.compile(r"^[0-9０-９\s]{6,}$"),  # 右上の試験コード
    re.compile(r"^(分析|ﾃﾞｻﾞｲﾝ|デザイン|一般|法令|有機|粉じん|特化|金属|放射).{0,6}\d+\s*/\s*\d+$"),
    re.compile(r"^（\s*終\s*り\s*）$"),
]


# ---------------------------------------------------------------- 図形のかたまり
def graphic_boxes(page):
    boxes = []
    for k in ("rects", "curves", "lines"):
        for o in getattr(page, k):
            boxes.append((o["x0"], o["top"], o["x1"], o["bottom"]))
    return boxes


def clusters(boxes, gap=4):
    parent = list(range(len(boxes)))

    def f(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    cell = {}
    for i, (x0, t, x1, b) in enumerate(boxes):
        for gx in range(int(x0 // gap) - 1, int(x1 // gap) + 2):
            for gy in range(int(t // gap) - 1, int(b // gap) + 2):
                cell.setdefault((gx, gy), []).append(i)
    for v in cell.values():
        for j in v[1:]:
            a, b = f(v[0]), f(j)
            if a != b:
                parent[a] = b
    groups = {}
    for i, bx in enumerate(boxes):
        groups.setdefault(f(i), []).append(bx)
    return [(min(b[0] for b in g), min(b[1] for b in g), max(b[2] for b in g), max(b[3] for b in g))
            for g in groups.values()]


def is_mark(b):
    w, h = b[2] - b[0], b[3] - b[1]
    return 8 <= w <= 14 and 8 <= h <= 14 and abs(w - h) < 3


def merge_boxes(boxes, pad=6):
    boxes = [list(b) for b in boxes]
    changed = True
    while changed:
        changed = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if a[0] - pad <= b[2] and b[0] - pad <= a[2] and a[1] - pad <= b[3] and b[1] - pad <= a[3]:
                    boxes[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                    boxes.pop(j)
                    changed = True
                    break
            if changed:
                break
    return [tuple(b) for b in boxes]


# ---------------------------------------------------------------- 1冊分の読み取り
def read_pdf(path):
    import pdfplumber
    pdf = pdfplumber.open(path)
    pages = []
    for pno, page in enumerate(pdf.pages):
        lines = [ln for ln in build_lines(page, pno) if not any(p.match(ln.text()) for p in NOISE)]
        groups = clusters(graphic_boxes(page))
        marks = [b for b in groups if is_mark(b)]
        figs = [b for b in groups if not is_mark(b) and b[2] - b[0] > 30 and b[3] - b[1] > 30
                and b[2] - b[0] < page.width * 0.85]
        figs += [(im["x0"], im["top"], im["x1"], im["bottom"]) for im in page.images]
        pages.append({"no": pno, "page": page, "lines": lines, "marks": marks, "figs": merge_boxes(figs)})

    # 問の開始行を、問1から順番どおりに探す（本文中の「問3」などは拾わない）
    starts, expected = [], 1
    for p in pages:
        for ln in p["lines"]:
            m = re.match(r"^問\s*([0-9０-９]{1,2})(?![0-9０-９])", ln.text())
            if m and int(to_half(m.group(1))) == expected:
                starts.append(ln)
                expected += 1

    flat = [(p, ln) for p in pages for ln in p["lines"]]
    pos = {id(ln): k for k, (p, ln) in enumerate(flat)}
    questions = []
    for i, sln in enumerate(starts):
        a = pos[id(sln)]
        b = pos[id(starts[i + 1])] if i + 1 < len(starts) else len(flat)
        questions.append(parse_question(i + 1, flat[a:b]))
    return pdf, questions


def parse_question(num, qlines):
    flags = []
    pgs = {}
    for p, ln in qlines:
        pgs.setdefault(p["no"], p)
    top_of = {n: min(ln.top for p, ln in qlines if p["no"] == n) for n in pgs}
    bot_of = {n: max(ln.bottom for p, ln in qlines if p["no"] == n) for n in pgs}

    # 図の判定の前に、図を考えずに選択肢を探しておく（5つそろえば、その行は図に含めない）
    pre = find_choices(qlines, {n: [] for n in pgs})
    protected = {id(qlines[k][1]) for k in pre} if len(pre) == 5 else set()

    # この問の範囲にある図
    figs = []
    for n, pg in pgs.items():
        lo = top_of[n] - 5
        nxt = [ln.top for ln in pg["lines"] if ln.top > bot_of[n] + 1]
        hi = min(nxt) - 2 if nxt else pg["page"].height - 40
        for b in pg["figs"]:
            if b[1] >= lo and b[1] < hi:
                figs.append((pg, b))
    first_ln = qlines[0][1]
    by_page = {}
    for pg, b in figs:
        by_page.setdefault(pg["no"], [pg, None])
        cur = by_page[pg["no"]][1]
        by_page[pg["no"]][1] = b if cur is None else (min(cur[0], b[0]), min(cur[1], b[1]), max(cur[2], b[2]), max(cur[3], b[3]))
    figs = []
    for n, (pg, b) in by_page.items():
        for _ in range(5):  # 図のまわりの短い行（ラベル）を図に含める
            grown = b
            for p, ln in qlines:
                if p["no"] != n or ln is first_ln:
                    continue
                t = ln.text()
                if len(t) <= 14 and ln.bottom > b[1] - 30 and ln.top < b[3] + 30 and id(ln) not in protected \
                        and not re.search(r"[。、]$", t) and not re.fullmatch(r"[ⒶⒷⒸⒹ㋑㋺㋩㋥\s]+", t):
                    xs = [c["x0"] for c in ln.main + ln.small] + [c["x1"] for c in ln.main + ln.small]
                    grown = (min(grown[0], min(xs)), min(grown[1], ln.top), max(grown[2], max(xs)), max(grown[3], ln.bottom))
            if grown == b:
                break
            b = grown
        figs.append((pg, b))
    fig_boxes = {n: [b for p, b in figs if p["no"] == n] for n in pgs}

    choice_idx = find_choices(qlines, fig_boxes)
    stem_end0 = choice_idx[0] if choice_idx else len(qlines)
    header = [ln for p, ln in qlines[:stem_end0] if re.fullmatch(r"[ⒶⒷⒸⒹ㋑㋺㋩㋥\s]+", ln.text())]
    col_gap = 8 if header else None

    def ltext(p, ln, cols=False):
        return to_half(ln.text(fig_boxes[p["no"]], col_gap if cols else None))

    # 正答（○印）：印の右隣にある 1〜5 の数字
    answer = set()
    for n, pg in pgs.items():
        for m in pg["marks"]:
            if not (top_of[n] - 5 <= m[1] <= bot_of[n] + 5):
                continue
            my = (m[1] + m[3]) / 2
            for c in pg["page"].chars:
                if c["text"] in CHOICE_DIGITS and 0 < c["x0"] - m[2] < 20 and abs((c["top"] + c["bottom"]) / 2 - my) < 5:
                    answer.add(CHOICE_DIGITS.index(c["text"]) + 1)
    answer = sorted(answer)

    stem_end = choice_idx[0] if choice_idx else len(qlines)
    stem_lines = [ltext(p, ln) for p, ln in qlines[:stem_end] if ln not in header]
    stem_lines[0] = re.sub(r"^問\s*[0-9]{1,2}\s*", "", stem_lines[0])
    choices = []
    for j, k in enumerate(choice_idx):
        nk = choice_idx[j + 1] if j + 1 < len(choice_idx) else len(qlines)
        parts = [ltext(p, ln, cols=True) for p, ln in qlines[k:nk]]
        parts[0] = re.sub(r"^[1-5]\s*(／\s*)?", "", parts[0])
        choices.append(tidy(join(parts)))

    stem = tidy(re.sub(r"の\s+に入る", "の［　］に入る", join(stem_lines)))

    choice_image = len(choices) != 5 or any(not c for c in choices) or any(re.search(r"[Σ∑]", c) for c in choices)
    if choice_image:
        flags.append("選択肢を画像にした（文字で入れられるなら手で直す）")
    if len(answer) != 1:
        flags.append(f"○が{len(answer)}個")
    if header and any("／" not in c for c in choices):
        flags.append("組合せの列を分けられない選択肢がある")

    return {
        "num": num, "stem": stem, "choices": choices,
        "answer": answer[0] if len(answer) == 1 else (answer or None),
        "flags": flags, "figs": figs, "choice_image": choice_image, "qlines": qlines,
        "choice_start": choice_idx[0] if choice_idx else None,
        "columns": header[0].text().split() if header else None,
        "header_index": next((k for k, (p, ln) in enumerate(qlines) if header and ln is header[0]), None),
    }


def find_choices(qlines, fig_boxes):
    """行頭の 1〜5 を、同じ字下げ位置で順番どおりに探す。"""
    idx, label_x, expected = [], None, 1
    for k, (p, ln) in enumerate(qlines):
        if k == 0 or expected > 5:
            continue
        cs = [c for c in ln.main if not inside(c, fig_boxes[p["no"]])]
        if not cs or cs[0]["text"] != CHOICE_DIGITS[expected - 1]:
            continue
        gap_ok = len(cs) == 1 or cs[1]["x0"] - cs[0]["x1"] > 3
        if gap_ok and (label_x is None or abs(cs[0]["x0"] - label_x) < 4):
            label_x = cs[0]["x0"]
            idx.append(k)
            expected += 1
    return idx


def join(parts):
    out = ""
    for p in [p.strip() for p in parts if p.strip()]:
        if out and re.search(r"[A-Za-z0-9.,)]$", out) and re.match(r"[A-Za-z0-9(]", p):
            out += " " + p
        else:
            out += p
    return out


# ---------------------------------------------------------------- 図の書き出し
def save_crop(pg, box, path, pad=6):
    page = pg["page"]
    bbox = (max(0, box[0] - pad), max(0, box[1] - pad), min(page.width, box[2] + pad), min(page.height, box[3] + pad))
    im = page.crop(bbox).to_image(resolution=200)
    for m in pg["marks"]:  # ○印（正答）を白で消す
        if m[0] >= bbox[0] - 2 and m[2] <= bbox[2] + 2 and m[1] >= bbox[1] - 2 and m[3] <= bbox[3] + 2:
            im.draw_rect((m[0] - 1, m[1] - 1, m[2] + 1, m[3] + 1), fill=(255, 255, 255), stroke=(255, 255, 255), stroke_width=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, format="PNG")


def export_figures(q, base, fig_dir):
    out = []
    for n, (pg, b) in enumerate(q["figs"], 1):
        name = f"{base}-{n}.png"
        save_crop(pg, b, fig_dir / name)
        out.append({"file": name, "alt": f"問{q['num']}の図"})
    if q["choice_image"] and q["figs"] and len([c for c in q["choices"] if c]) == 0:
        q["choices"] = [f"図の{n}" for n in range(1, 6)]
    elif q["choice_image"]:
        start = q["choice_start"] if q["choice_start"] is not None else 1
        if q.get("header_index") is not None:
            start = min(start, q["header_index"])
        p0 = q["qlines"][start][0]
        lines = [ln for pp, ln in q["qlines"][start:] if pp is p0]
        if lines:
            box = (min(ln.x0 for ln in lines) - 20, min(ln.top for ln in lines) - 4,
                   p0["page"].width - 50, max(ln.bottom for ln in lines) + 4)
            name = f"{base}-choices.png"
            save_crop(p0, box, fig_dir / name)
            out.append({"file": name, "alt": f"問{q['num']}の選択肢"})
        q["choices"] = [f"図の{n}" for n in range(1, 6)]
    return out


# ---------------------------------------------------------------- 正答肢との照合
def squash(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    return re.sub(r"[\s、。,.・･()（）「」⁻⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉\-]", "", s)


def check_key(q, key_choice):
    if not key_choice or not isinstance(q["answer"], int) or q["answer"] > len(q["choices"]):
        return None
    a, k = squash(q["choices"][q["answer"] - 1]), squash(key_choice)
    if not a or not k or k in a or a in k:
        return None
    ratio = difflib.SequenceMatcher(None, a, k).ratio()
    return None if ratio >= 0.6 else f"正答肢と一致しない（類似度{ratio:.2f}）"


# ---------------------------------------------------------------- 書き込み
def empty_question(num):
    return {"num": num, "status": "draft", "chapters": [], "traps": [], "rank": None, "summary": None,
            "stem": None, "columns": None, "choices": [], "answer": None, "choice_notes": [], "explanation": None,
            "figures": [], "law_note": None}


def merge(path, exam, subject, date, parsed, fig_dir, force):
    if path.exists():
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        doc = {"exam": exam, "date": None, "subject": subject, "source_pdf": None, "questions": []}
    if date and not doc.get("date"):
        doc["date"] = date
    by_num = {q["num"]: q for q in doc["questions"]}
    report = []
    for p in parsed:
        q = by_num.get(p["num"]) or by_num.setdefault(p["num"], empty_question(p["num"]))
        base = f"{exam}-{subject}-{p['num']:02d}"
        flags = list(p["flags"])
        mismatch = check_key(p, q.get("_key_choice"))  # 選択肢を画像にする前に照合する
        if mismatch:
            flags.append(mismatch)
        filled = False
        if force or not q.get("figures"):
            figs = export_figures(p, base, fig_dir)
            if figs:
                q["figures"], filled = figs, True
        elif p["choice_image"]:
            p["choices"] = [f"図の{n}" for n in range(1, 6)]
        if force or not q.get("stem"):
            q["stem"], filled = md_escape(p["stem"]), True
        if force or not q.get("choices"):
            q["choices"], filled = [md_escape(c) for c in p["choices"]], True
        if force or q.get("answer") is None:
            q["answer"], filled = p["answer"], True
        if p.get("columns") and not p["choice_image"] and (force or not q.get("columns")):
            q["columns"] = p["columns"]  # 組合せ問題の列の見出し（Ⓐ Ⓑ など）
        if filled:
            q["_review"] = True
        if flags:
            q["_import_flags"] = flags
        else:
            q.pop("_import_flags", None)
        report.append((path.as_posix(), p["num"], " / ".join(flags)))
    for n in sorted(set(range(1, 21)) - {p["num"] for p in parsed}):
        report.append((path.as_posix(), n, "PDFから見つけられない"))
    doc["questions"] = [by_num[k] for k in sorted(by_num)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_dir")
    ap.add_argument("--data", default="data")
    ap.add_argument("--figures", default="src/assets/figures")
    ap.add_argument("--force", action="store_true", help="入力済みの問題文・選択肢・正答・図も上書きする")
    args = ap.parse_args()

    rows = []
    for pdf_path in sorted(Path(args.pdf_dir).glob("*.pdf")):
        exam, subject, date = exam_from_filename(pdf_path.name)
        if not exam or not subject:
            print(f"スキップ（ファイル名から回・科目を判定できない）: {pdf_path.name}")
            continue
        pdf, parsed = read_pdf(pdf_path)
        out = Path(args.data) / "exams" / exam / f"{subject}.yaml"
        rep = merge(out, exam, subject, date, parsed, Path(args.figures), args.force)
        pdf.close()
        bad = sum(1 for r in rep if r[2])
        print(f"{pdf_path.name} → {out}：{len(parsed)}問を読み取り、要確認 {bad}問")
        rows += rep

    with open("import_report.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["ファイル", "問", "要確認の内容"])
        w.writerows(r for r in rows if r[2])
    print("要確認の一覧: import_report.csv")


if __name__ == "__main__":
    main()
