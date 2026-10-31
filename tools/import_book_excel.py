"""問題集を整理したExcel（「〇〇年作業環境測定士試験_問題のみ_照合修正版.xlsx」）から、
問題文・選択肢・正答を data/exams/<実施年月>/<科目>.yaml に取り込む。

使い方:
    python tools/import_book_excel.py <Excel> [<Excel> ...] --data data [--overrides 回:科目:問=正答 ...]

- 既に問題文が入っている問題は上書きしない（--force で上書き）
- 章・罠の型（convert_wana.py が入れたもの）はそのまま残す
- 組合せの選択肢（「Ⓐ…　Ⓑ…」「㋑…　㋺…」「A…　B…」）は「… ／ …」の形に直し、列の見出しを付ける
"""
import argparse, re, unicodedata
from pathlib import Path
import pandas as pd
import yaml

SUBJ = {"労働衛生一般": "ippan", "労働衛生関係法令": "hourei", "デザイン・サンプリング": "design",
        "分析に関する概論": "bunseki", "有機溶剤": "yuki", "鉱物性粉じん": "funjin",
        "特定化学物質": "tokka", "金属類": "kinzoku", "放射性物質": "hoshasei"}
MARK = "ⒶⒷⒸⒹⒺ㋑㋺㋩㋥㋭"


def clean(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = str(s).replace("\\n", "\n").strip()
    s = s.replace("，", "、").replace("．", "。")
    s = re.sub(r"[ 　]*、[ 　]*", "、", s)
    return s


def detail(s):
    s = clean(s)
    if not s:
        return ""
    # 振り仮名などの取り込みの残り（短く、記号も式も含まないもの）は捨てる
    if len(s) < 10 and not re.search(f"[{MARK}＝=\\[]", s):
        return ""
    return s.replace("\n", "\n\n")


def split_choice(c):
    parts = [p for p in re.split(r"\u3000+", c) if p]
    if len(parts) < 2:
        return c, None
    heads, bodies = [], []
    for p in parts:
        m = re.match(f"^([{MARK}]|[A-E](?=[^A-Za-z0-9]))\\s*(.*)$", p)
        if m:
            heads.append(m.group(1)); bodies.append(m.group(2).strip())
        else:
            heads.append(None); bodies.append(p.strip())
    if all(h for h in heads) and not any(bodies):     # ㋑　㋺ のような組合せの選び方
        return " ".join(heads), None
    if all(h for h in heads):
        return " ／ ".join(bodies), heads
    return " ／ ".join(bodies), None


def load(p):
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("excel", nargs="+")
    ap.add_argument("--data", default="data")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--overrides", nargs="*", default=[])
    a = ap.parse_args()
    ov = {}
    for o in a.overrides:
        k, v = o.split("=")
        e, s, n = k.split(":")
        ov[(e, s, int(n))] = int(v)
    rows = {}
    for x in a.excel:                      # 後に指定したExcelを優先
        df = pd.read_excel(x, sheet_name="問題")
        for _, r in df.iterrows():
            s = SUBJ.get(r["科目（章）"])
            if not s:
                continue
            rows[(f"{int(r['西暦'])}-{int(r['月']):02d}", s, int(r["問番号"]))] = r
    files = {}
    for (exam, subj, num), r in sorted(rows.items()):
        p = Path(a.data) / "exams" / exam / f"{subj}.yaml"
        if p not in files:
            d = load(p) or {"exam": exam, "date": None, "subject": subj, "source_pdf": None, "questions": []}
            files[p] = d
        d = files[p]
        qs = {q["num"]: q for q in d["questions"]}
        q = qs.get(num)
        if not q:
            q = {"num": num, "status": "draft", "chapters": [], "traps": [], "rank": None}
            d["questions"].append(q)
        if q.get("stem") and not a.force:
            continue
        choices, cols = [], None
        for i in range(1, 6):
            t, h = split_choice(clean(r[f"選択肢{i}"]))
            choices.append(t)
            cols = cols or h
        stem = clean(r["問題文"])
        det = detail(r["記述・条件（㋑～㋥・表・データ等）"])
        if det:
            stem += "\n\n" + det
        q.update({"stem": stem, "choices": choices, "columns": cols,
                  "answer": ov.get((exam, subj, num), int(r["正答"])),
                  "choice_notes": q.get("choice_notes") or [], "explanation": q.get("explanation"),
                  "figures": q.get("figures") or [], "law_note": q.get("law_note")})
        q.setdefault("status", "draft")
        fig = str(r.get("図の有無") or "")
        if fig.startswith("図あり"):
            q["_review"] = f"原本に図あり（{fig}）。文章で表記している。"
        d["questions"].sort(key=lambda x: x["num"])
    for p, d in files.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    print(f"{len(rows)} 問を {len(files)} ファイルに取り込みました")


if __name__ == "__main__":
    main()
