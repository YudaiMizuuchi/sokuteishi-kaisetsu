"""罠の型一覧（Excel）から、解説サイト用のマスタと問題データ（YAML）を作る。

使い方:
    python convert_wana.py <罠の型一覧.xlsx があるフォルダ> <出力先フォルダ>

Excelを更新したら、何度でも実行し直せる。ただし data/exams/ の
summary・explanation など手で書いた項目は上書きしないよう、既存ファイルが
あれば chapters・traps・_key_choice だけを更新する。
"""
import sys
import re
from pathlib import Path
import pandas as pd
import yaml

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "data")

SUBJECT_FILES = {
    "design": "デザイン_サンプリング_罠の型一覧.xlsx",
    "bunseki": "分析に関する概論_罠の型一覧.xlsx",
}
TRAP_PREFIX = {"design": "ds", "bunseki": "an"}

# ---------------------------------------------------------------- 科目
SUBJECTS = [
    {"id": "ippan", "name": "労働衛生一般", "kind": "共通"},
    {"id": "hourei", "name": "労働衛生関係法令", "kind": "共通"},
    {"id": "design", "name": "デザイン・サンプリング", "kind": "共通"},
    {"id": "bunseki", "name": "分析に関する概論", "kind": "共通"},
    {"id": "yuki", "name": "有機溶剤", "kind": "選択"},
    {"id": "funjin", "name": "鉱物性粉じん", "kind": "選択"},
    {"id": "tokka", "name": "特定化学物質", "kind": "選択"},
    {"id": "kinzoku", "name": "金属類", "kind": "選択"},
    {"id": "hoshasei", "name": "放射性物質", "kind": "選択"},
]

# ---------------------------------------------------------------- 部
PARTS = [
    {"id": "prep", "num": 0, "name": "ゼロからの準備"},
    {"id": "why", "num": 1, "name": "なぜ測るのか"},
    {"id": "hazards", "num": 2, "name": "有害物質と人体"},
    {"id": "design", "num": 3, "name": "測定を設計する"},
    {"id": "sampling", "num": 4, "name": "試料を採る"},
    {"id": "analysis", "num": 5, "name": "分析する"},
    {"id": "law", "num": 6, "name": "法令で答え合わせ"},
]

# ---------------------------------------------------------------- 章
# num が None の章は「仮の章」（席をそのまま章にしたもの）。章立てが固まったら
# num と name を書き換える。id は変えない。
CHAPTERS = [
    # 第0部（目次案で確定済み）
    ("units", "0-1", "prep", "数と単位"),
    ("mole", "0-2", "prep", "物質量（mol）"),
    ("gas", "0-3", "prep", "気体"),
    ("solution", "0-4", "prep", "溶液の濃度"),
    ("reaction", "0-5", "prep", "反応の量的関係と酸・塩基"),
    ("logarithm", "0-6", "prep", "対数"),
    ("statistics", "0-7", "prep", "平均とばらつき"),
    # 第2部（仮）
    ("states", None, "hazards", "物質の状態と濃度の表し方"),
    ("properties", None, "hazards", "物質の性質"),
    ("organic", None, "hazards", "有機化合物"),
    ("radiation", None, "hazards", "放射性物質と放射能"),
    # 第3部
    ("unit-workplace", None, "design", "単位作業場所"),
    ("a-b-measurement", "3-2", "design", "A測定とB測定"),
    ("personal-sampling", None, "design", "個人サンプリング法"),
    ("evaluation", None, "design", "評価と管理区分"),
    ("noise", None, "design", "騒音"),
    ("other-workplaces", None, "design", "指定作業場以外の測定"),
    # 第4部（仮）
    ("flowmeter", None, "sampling", "流量計"),
    ("sampler-selection", None, "sampling", "捕集方法の選び方"),
    ("solid-sorbent", None, "sampling", "固体捕集法"),
    ("filter", None, "sampling", "ろ過捕集法"),
    ("size-selector", None, "sampling", "分粒装置"),
    ("liquid-direct", None, "sampling", "液体捕集法・直接捕集法"),
    ("relative-meter", None, "sampling", "相対濃度計"),
    ("detector-tube", None, "sampling", "検知管"),
    # 第5部（仮）
    ("equilibrium", None, "analysis", "化学平衡"),
    ("titration", None, "analysis", "容量分析"),
    ("lab-equipment", None, "analysis", "分析の器具"),
    ("standard-gas", None, "analysis", "標準ガス"),
    ("reagents", None, "analysis", "試薬"),
    ("quantification", None, "analysis", "検量線と定量法"),
    ("spectrophotometry", None, "analysis", "吸光光度法"),
    ("aas", None, "analysis", "原子吸光分析法"),
    ("fluorescence", None, "analysis", "蛍光光度法"),
    ("gc", None, "analysis", "ガスクロマトグラフ分析法"),
    ("xrd", None, "analysis", "X線回折分析法"),
]

# 席 → 章（席の既定）
SEAT_CHAPTER = {
    "design": {
        "濃度と物質の状態": "states", "物性": "properties",
        "単位作業場所": "unit-workplace", "A測定・B測定": "a-b-measurement",
        "個人サンプリング法": "personal-sampling", "評価": "evaluation",
        "騒音": "noise", "指定作業場以外": "other-workplaces",
        "統計": "statistics", "測定誤差": "statistics",
        "流量計": "flowmeter", "捕集器具の組合せ": "sampler-selection",
        "固体捕集法": "solid-sorbent", "ろ過捕集法": "filter",
        "分粒装置": "size-selector", "液体捕集・直接捕集": "liquid-direct",
        "相対濃度計": "relative-meter", "検知管": "detector-tube",
        "放射性物質": "radiation",
    },
    "bunseki": {
        "単位と原子": "units", "データの扱い": "statistics",
        "物質量の計算": "mole", "気体": "gas", "有機化合物": "organic",
        "溶液": "solution", "容量分析": "titration", "器具": "lab-equipment",
        "標準ガス": "standard-gas", "試薬": "reagents",
        "検知管・定量法": "quantification", "吸光光度法": "spectrophotometry",
        "原子吸光": "aas", "蛍光光度法": "fluorescence",
        "ガスクロマトグラフ": "gc", "X線回折": "xrd", "放射能": "radiation",
    },
}

# 罠の型ごとの上書き（罠の型の名前 → (主な章, 土台となる第0部の章 or None)）
TRAP_OVERRIDE = {
    "design": {
        "ppm⇔mg/m³の換算（計算）": ("gas", None),
        "体積分率（%）とppmの関係": ("gas", None),
        "騒音測定結果の計算": ("noise", "logarithm"),
        "騒音の評価は算術平均のみ（標準偏差は使わない）": ("noise", "statistics"),
        "濃度がほぼ均一の判断（幾何標準偏差）": ("a-b-measurement", "statistics"),
        "第1評価値は上側5%の推定値（算術平均ではない）": ("evaluation", "statistics"),
        "放射能濃度の計算": ("radiation", "units"),
    },
    "bunseki": {
        "アボガドロ定数（単位はmol⁻¹・定義）": ("mole", None),
        "原子の構造（電子・陽子・質量数・帯電）": ("mole", None),
        "捕集量と通気量からの気中濃度（計算）": ("solution", None),
        "有効数字": ("units", None),
        "燃焼後の密閉容器の圧力（計算）": ("gas", "reaction"),
        "強酸の希釈とpH（計算）": ("logarithm", "solution"),
        "酸・塩の水溶液のpHの大小": ("reaction", None),
        "化学平衡の移動（ルシャトリエの原理）": ("equilibrium", None),
        "平衡定数の計算": ("equilibrium", None),
        "中和反応の量的関係（計算）": ("reaction", None),
        "反応式の量的関係（炭酸カルシウム・燃焼）": ("reaction", None),
        "溶解度積": ("equilibrium", None),
        "気体用流量計（石けん膜・面積式）": ("lab-equipment", None),
        "捕集袋による標準ガス調製（計算）": ("gas", None),
        "検知管の読み取り（吸引終了後すぐ読む）": ("detector-tube", None),
        "シアン化水素検知管の妨害物質": ("detector-tube", None),
        "吸光度・透過率・濃度の計算（ランベルト・ベール）": ("logarithm", "solution"),
        "透過率と光路長の関係": ("spectrophotometry", "logarithm"),
        "半減期の計算": ("logarithm", None),
    },
}

# 章の割り当てで迷ったもの（要確認として出力に残す）
REVIEW_NOTES = [
    "放射性物質と放射能（radiation）を第2部に置いた。科目横断の章として独立させるか要検討。",
    "有機化合物（organic）を第2部に置いた。第0部や第5部に入れる案もある。",
    "ICP発光分析法は検量線と定量法（quantification）のまま。独立の章にするか要検討。",
    "検知管は両科目の罠の型を第4部の detector-tube にまとめた（分析の「検知管・定量法」席のうち読み取りと妨害物質の2型）。",
    "統計・測定誤差（デザイン）とデータの扱い（分析）は、第0部の 0-7 平均とばらつき に直接入れた。",
]

# ---------------------------------------------------------------- 回のキー
def exam_key(label):
    """'2024年度第1回' → '2024-08'、'2024年度第2回' → '2025-02'"""
    m = re.fullmatch(r"(\d{4})年度第([12])回", str(label).strip())
    if not m:
        raise ValueError(f"回の表記が想定外: {label}")
    y, n = int(m.group(1)), int(m.group(2))
    return f"{y}-08" if n == 1 else f"{y + 1}-02"


def rank_of(name, count):
    if "その他" in name:
        return "C"
    return "A" if count >= 3 else "B" if count == 2 else "C"


def clean(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    return None if s in ("", "—") else s


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=1000)


def load(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------- 変換
chapter_ids = {c[0] for c in CHAPTERS}
traps_out, questions_by_file = [], {}

for subj, fname in SUBJECT_FILES.items():
    t = pd.read_excel(SRC / fname, sheet_name="罠の型一覧")
    q = pd.read_excel(SRC / fname, sheet_name="正答肢一覧")
    q["exam"] = q["回"].map(exam_key)

    trap_id = {}
    seq = {}
    for _, r in t.iterrows():
        seat, name = r["席"], r["罠の型"]
        chap, found = TRAP_OVERRIDE[subj].get(name, (SEAT_CHAPTER[subj][seat], None))
        assert chap in chapter_ids and (found is None or found in chapter_ids), name
        seq[chap] = seq.get(chap, 0) + 1
        tid = f"{TRAP_PREFIX[subj]}-{chap}-{seq[chap]:02d}"
        trap_id[(seat, name)] = tid
        hits = q[(q["席"] == seat) & (q["罠の型"] == name)]
        conf = clean(r["確度"])
        trap = {
            "id": tid,
            "subject": subj,
            "chapter": chap,
            "foundation": found,
            "seat": seat,
            "name": name,
            "rank": rank_of(name, len(hits)),
            "count": int(len(hits)),
            "exams": sorted(hits["exam"].unique().tolist()),
            "understanding": clean(r["正しい理解"]),
            "reason": clean(r["なぜそうなるか（理由）"]),
            "confidence": conf,
            "verify": bool(conf and "要確認" in conf),
        }
        if subj == "bunseki":
            trap["calculation"] = clean(r["計算"]) == "○"
        traps_out.append(trap)

    unmatched = set(zip(q["席"], q["罠の型"])) - set(trap_id)
    assert not unmatched, unmatched

    for _, r in q.iterrows():
        tid = trap_id[(r["席"], r["罠の型"])]
        tr = next(x for x in traps_out if x["id"] == tid)
        chapters = [tr["chapter"]] + ([tr["foundation"]] if tr["foundation"] else [])
        key_choice = clean(r.get("正答肢（誤りの記述・正答の選択肢）")) or clean(r.get("正答の選択肢"))
        item = {
            "num": int(r["問"]),
            "status": "draft",
            "chapters": chapters,
            "traps": [tid],
            "rank": None,
            "summary": None,
            "stem": None,
            "choices": [],
            "answer": None,
            "choice_notes": [],
            "explanation": None,
            "figures": [],
            "law_note": None,
            "_key_choice": key_choice,   # 内部用（正答肢の文面）。サイトには出さない
        }
        if subj == "bunseki":
            item["_stem_head"] = clean(r.get("設問（書き出し）"))
        questions_by_file.setdefault((r["exam"], subj), []).append(item)

# ---------------------------------------------------------------- 書き出し
chapters_out = [
    {"id": i, "num": no, "part": p, "name": n, "provisional": no is None, "description": None}
    for i, no, p, n in CHAPTERS
]
dump(OUT / "master" / "subjects.yaml", SUBJECTS)
dump(OUT / "master" / "book.yaml", {
    "parts": PARTS,
    "chapters": chapters_out,
    "traps": traps_out,
    "review_notes": REVIEW_NOTES,
})

AUTO_FIELDS = ("chapters", "traps", "_key_choice", "_stem_head")
for (exam, subj), items in sorted(questions_by_file.items()):
    path = OUT / "exams" / exam / f"{subj}.yaml"
    items = sorted(items, key=lambda x: x["num"])
    if path.exists():  # 手で書いた項目を残し、自動の項目だけ更新する
        old = {x["num"]: x for x in load(path)["questions"]}
        for it in items:
            if it["num"] in old:
                merged = old[it["num"]]
                for k in AUTO_FIELDS:
                    if k in it:
                        merged[k] = it[k]
                it.clear(); it.update(merged)
    dump(path, {"exam": exam, "date": None, "subject": subj, "source_pdf": None, "questions": items})

print(f"罠の型 {len(traps_out)} 件、問題ファイル {len(questions_by_file)} 件を {OUT} に出力しました")
