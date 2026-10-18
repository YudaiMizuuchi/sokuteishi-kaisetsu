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
    "ippan": "労働衛生一般_罠の型一覧.xlsx",
    "hourei": "労働衛生関係法令_罠の型一覧.xlsx",
}
TRAP_PREFIX = {"design": "ds", "bunseki": "an", "ippan": "gn", "hourei": "lw"}

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

# ---------------------------------------------------------------- 部（参考書の目次に合わせる）
PARTS = [
    {"id": "prep", "num": 0, "name": "ゼロからの準備"},
    {"id": "why", "num": 1, "name": "なぜ測るのか"},
    {"id": "hazards", "num": 2, "name": "有害要因と人体"},
    {"id": "design", "num": 3, "name": "測定を設計する"},
    {"id": "sampling", "num": 4, "name": "試料を採る"},
    {"id": "analysis", "num": 5, "name": "分析する"},
    {"id": "radiation", "num": 6, "name": "放射線をまとめて"},
    {"id": "law", "num": 7, "name": "法令で答え合わせ"},
]

# ---------------------------------------------------------------- 章（参考書の目次に合わせる）
# id は URL になるので変えない。章番号（num）と名前は目次の改訂に合わせて書き換えてよい。
CHAPTERS = [
    ("units", "0-1", "prep", "数と単位"),
    ("mole", "0-2", "prep", "物質量（mol）"),
    ("gas", "0-3", "prep", "気体"),
    ("solution", "0-4", "prep", "溶液の濃度"),
    ("reaction", "0-5", "prep", "反応の量的関係と酸・塩基"),
    ("logarithm", "0-6", "prep", "対数"),
    ("statistics", "0-7", "prep", "平均とばらつき"),
    ("history", "1-1", "why", "職業病の歴史と作業環境測定の誕生"),
    ("oh-management", "1-2", "why", "三管理と作業環境管理"),
    ("risk-assessment", "1-3", "why", "リスクアセスメントと化学物質の自律的管理"),
    ("exposure-limits", "1-4", "why", "管理濃度・許容濃度・濃度基準値"),
    ("absorption", "2-1", "hazards", "体に入る道・出る道"),
    ("properties", "2-2", "hazards", "ガス・蒸気の性質と空気中でのふるまい"),
    ("organic-solvents", "2-3", "hazards", "有機溶剤"),
    ("toxicity", "2-4", "hazards", "ガス状物質と化学物質の健康障害"),
    ("metals", "2-5", "hazards", "金属"),
    ("dust-disease", "2-6", "hazards", "粒子状物質とじん肺・石綿"),
    ("occupational-cancer", "2-7", "hazards", "職業がん"),
    ("oxygen-deficiency", "2-8", "hazards", "酸素欠乏と硫化水素"),
    ("heat-cold", "2-9", "hazards", "温熱と寒冷"),
    ("noise", "2-10", "hazards", "騒音"),
    ("vibration", "2-11", "hazards", "振動"),
    ("em-waves", "2-12", "hazards", "電磁波"),
    ("ventilation", "2-13", "hazards", "局所排気装置と換気"),
    ("ppe", "2-14", "hazards", "保護具"),
    ("other-environment", "コラム", "hazards", "その他の職場の健康障害"),
    ("unit-workplace", "3-1", "design", "単位作業場所"),
    ("a-b-measurement", "3-2", "design", "A測定とB測定"),
    ("personal-sampling", "3-3", "design", "個人サンプリング法（C測定・D測定）"),
    ("stats-error", "3-4", "design", "統計と測定誤差"),
    ("evaluation", "3-5", "design", "作業環境の評価と管理区分"),
    ("other-workplaces", "3-6", "design", "指定作業場以外の測定"),
    ("sampler-selection", "4-1", "sampling", "捕集方法の全体像"),
    ("filter", "4-2", "sampling", "ろ過捕集と分粒装置"),
    ("solid-sorbent", "4-3", "sampling", "固体捕集"),
    ("liquid-direct", "4-4", "sampling", "液体捕集と直接捕集"),
    ("flowmeter", "4-5", "sampling", "流量計"),
    ("detector-tube", "4-6", "sampling", "検知管"),
    ("relative-meter", "4-7", "sampling", "相対濃度計"),
    ("lab-equipment", "5-1", "analysis", "分析の基本操作"),
    ("quantification", "5-2", "analysis", "データの扱いと定量法"),
    ("organic", "5-3", "analysis", "有機化合物の基礎"),
    ("solution-chem", "5-4", "analysis", "溶液の化学"),
    ("titration", "5-5", "analysis", "容量分析"),
    ("standard-gas", "5-6", "analysis", "標準ガスの調製"),
    ("spectrophotometry", "5-7", "analysis", "吸光光度法"),
    ("aas", "5-8", "analysis", "原子吸光とICP発光"),
    ("fluorescence", "5-9", "analysis", "蛍光光度法"),
    ("gc", "5-10", "analysis", "ガスクロマトグラフ"),
    ("xrd", "5-11", "analysis", "X線回折"),
    ("radiation", "6-1", "radiation", "放射線の正体"),
    ("radiation-effects", "6-2", "radiation", "放射線の人体への影響"),
    ("radiation-sampling", "6-3", "radiation", "放射性物質の捕集と放射能濃度"),
    ("law-radiation", "6-4", "radiation", "電離放射線障害防止規則"),
    ("law-map", "7-1", "law", "法令の地図"),
    ("law-system", "7-2", "law", "衛生管理体制"),
    ("law-health-education", "7-3", "law", "健康診断と安全衛生教育"),
    ("law-chief", "7-4", "law", "作業主任者と規格・型式検定"),
    ("law-measurement-scope", "7-5", "law", "作業環境測定の対象・頻度・記録の保存"),
    ("law-sokuteishi", "7-6", "law", "作業環境測定士と作業環境測定基準"),
    ("law-organic", "7-7", "law", "有機溶剤中毒予防規則"),
    ("law-tokka", "7-8", "law", "特定化学物質障害予防規則"),
    ("law-dust", "7-9", "law", "粉じん則・じん肺法・石綿則"),
    ("law-other", "7-10", "law", "酸欠則・鉛則・事務所則・安衛則の衛生基準"),
]

# 席 → 章（目次の「対応する席」の列のとおり）。席ごとに「土台となる章」も付けられる
SEAT_CHAPTER = {
    "design": {
        "濃度と物質の状態": "dust-disease", "物性": "properties",
        "単位作業場所": "unit-workplace", "A測定・B測定": "a-b-measurement",
        "個人サンプリング法": "personal-sampling", "評価": "evaluation",
        "騒音": "noise", "指定作業場以外": "other-workplaces",
        "統計": "stats-error", "測定誤差": "stats-error",
        "流量計": "flowmeter", "捕集器具の組合せ": "sampler-selection",
        "固体捕集法": "solid-sorbent", "ろ過捕集法": "filter", "分粒装置": "filter",
        "液体捕集・直接捕集": "liquid-direct", "相対濃度計": "relative-meter",
        "検知管": "detector-tube", "放射性物質": "radiation-sampling",
    },
    "bunseki": {
        "単位と原子": "units", "データの扱い": "quantification", "物質量の計算": "mole",
        "気体": "gas", "有機化合物": "organic", "溶液": "solution-chem",
        "容量分析": "titration", "器具": "lab-equipment", "標準ガス": "standard-gas",
        "試薬": "lab-equipment", "検知管・定量法": "quantification",
        "吸光光度法": "spectrophotometry", "原子吸光": "aas", "蛍光光度法": "fluorescence",
        "ガスクロマトグラフ": "gc", "X線回折": "xrd", "放射能": "radiation",
    },
    "ippan": {
        "リスクアセスメント": "risk-assessment", "労働衛生管理": "oh-management", "GHS": "risk-assessment",
        "吸収・代謝": "absorption", "毒性と健康障害": "toxicity", "物質の性状": "properties",
        "職業がん": "occupational-cancer", "粉じん": "dust-disease", "金属": "metals",
        "有機溶剤": "organic-solvents", "温熱・寒冷": "heat-cold", "振動": "vibration",
        "騒音": "noise", "保護具": "ppe", "酸欠・硫化水素": "oxygen-deficiency",
        "電磁波": "em-waves", "電離放射線": "radiation", "局所排気・換気": "ventilation",
        "その他の職場環境": "other-environment", "管理濃度・許容濃度": "exposure-limits",
    },
    "hourei": {
        "衛生管理体制": "law-system", "健康診断": "law-health-education",
        "化学物質管理": "risk-assessment", "安全衛生教育": "law-health-education",
        "作業主任者": "law-chief", "測定の対象と頻度": "law-measurement-scope",
        "規格・型式検定": "law-chief", "特化則": "law-tokka", "作業環境測定士": "law-sokuteishi",
        "作業環境測定基準": "law-sokuteishi", "個人サンプリング法": "personal-sampling",
        "作業環境評価基準": "evaluation", "安衛則の衛生基準": "law-other", "有機則": "law-organic",
        "電離則": "law-radiation", "事務所則": "law-other", "粉じん則・じん肺法": "law-dust",
        "石綿則": "law-dust", "酸欠則": "law-other", "鉛則": "law-other", "関係法令雑問": "law-dust",
    },
}
SEAT_FOUNDATION = {
    "design": {"統計": "statistics", "測定誤差": "statistics"},
    "bunseki": {"データの扱い": "statistics", "溶液": "solution", "容量分析": "reaction"},
    "hourei": {
        "作業環境測定基準": "a-b-measurement", "有機則": "organic-solvents", "鉛則": "metals",
        "粉じん則・じん肺法": "dust-disease", "石綿則": "dust-disease", "酸欠則": "oxygen-deficiency",
        "事務所則": "other-workplaces", "特化則": "toxicity",
    },
}

# 罠の型ごとの上書き（罠の型の名前 → (主な章, 土台となる章 or None)）
TRAP_OVERRIDE = {
    "design": {
        "ppm⇔mg/m³の換算（計算）": ("gas", None),
        "体積分率（%）とppmの関係": ("gas", None),
        "騒音の評価は算術平均のみ（標準偏差は使わない）": ("noise", "statistics"),
        "騒音測定結果の計算": ("noise", "logarithm"),
        "濃度がほぼ均一の判断（幾何標準偏差）": ("a-b-measurement", "statistics"),
        "第1評価値は上側5%の推定値（算術平均ではない）": ("evaluation", "statistics"),
        "放射能濃度の計算": ("radiation-sampling", "units"),
    },
    "bunseki": {
        "アボガドロ定数（単位はmol⁻¹・定義）": ("mole", None),
        "原子の構造（電子・陽子・質量数・帯電）": ("mole", None),
        "捕集量と通気量からの気中濃度（計算）": ("solution", None),
        "有効数字": ("units", None),
        "燃焼後の密閉容器の圧力（計算）": ("gas", "reaction"),
        "強酸の希釈とpH（計算）": ("solution-chem", "logarithm"),
        "酸・塩の水溶液のpHの大小": ("solution-chem", "reaction"),
        "化学平衡の移動（ルシャトリエの原理）": ("solution-chem", None),
        "平衡定数の計算": ("solution-chem", None),
        "溶解度積": ("titration", None),
        "気体用流量計（石けん膜・面積式）": ("flowmeter", None),
        "捕集袋による標準ガス調製（計算）": ("standard-gas", "gas"),
        "検知管の読み取り（吸引終了後すぐ読む）": ("detector-tube", None),
        "シアン化水素検知管の妨害物質": ("detector-tube", None),
        "ICP発光分析法": ("aas", None),
        "吸光度・透過率・濃度の計算（ランベルト・ベール）": ("spectrophotometry", "logarithm"),
        "透過率と光路長の関係": ("spectrophotometry", "logarithm"),
        "半減期の計算": ("radiation", "logarithm"),
    },
    "ippan": {
        "毒性の指標（LD50・NOAEL・量-反応関係）": ("absorption", None),
        "変異原性試験の意味": ("absorption", None),
        "粉じん・ヒュームの発生と粒径": ("dust-disease", None),
        "情報機器作業（VDT）": ("other-environment", None),
        "腰痛予防（腰部保護ベルト）": ("other-environment", None),
        "確定的影響と確率的影響": ("radiation-effects", None),
        "壊変と半減期": ("radiation", "logarithm"),
        "WBGTと基準値": ("heat-cold", None),
    },
    "hourei": {
        "評価値の計算（幾何平均と幾何標準偏差）": ("evaluation", "statistics"),
        "除じん装置の方式（ヒュームはろ過式）": ("law-dust", "ventilation"),
    },
}

# 目次に照らして判断したもの（要確認として出力に残す）
REVIEW_NOTES = [
    "デザインの「濃度と物質の状態」は、「管理濃度の表し方（粉じん・RCF）」の型も含めて目次どおり2-6に置く（確定）。",
    "一般の「労働衛生管理」の席は1-2に置き、そのうち情報機器作業と腰痛予防の型は、目次のコラム（その他の職場の健康障害）に回した。",
    "一般の「毒性と健康障害」のうち、毒性の指標（LD50など）と変異原性試験の型は2-1に、残りは2-4に置いた。",
    "分析の「データの扱い」は5-2を主な章とし、0-7を土台とした。気中濃度の計算は0-4、有効数字は0-1を主な章のままにしている。",
    "分析の「溶液」「容量分析」は5-4・5-5を主な章とし、計算の型は0-4〜0-6を土台として結んだ。",
    "法令の「関係法令雑問」（じん肺健康診断と管理区分）は7-9に置いた。",
    "法令の「化学物質管理」は1-3、「個人サンプリング法」は3-3、「作業環境評価基準」は3-5、「電離則」は6-4に置いた（目次で第7部に章を立てないもの）。",
    "1-1（歴史）と7-1（法令の地図）は読み物の章で、対応する過去問はない。",
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

# 罠の型のIDは URL になるので、前回の book.yaml にある型（科目・席・名前が同じもの）は同じIDを使う
prev_ids, used_ids = {}, set()
if (OUT / "master" / "book.yaml").exists():
    for t in (yaml.safe_load((OUT / "master" / "book.yaml").read_text(encoding="utf-8")) or {}).get("traps", []):
        prev_ids[(t["subject"], t["seat"], t["name"])] = t["id"]
        used_ids.add(t["id"])

for subj, fname in SUBJECT_FILES.items():
    t = pd.read_excel(SRC / fname, sheet_name="罠の型一覧")
    q = pd.read_excel(SRC / fname, sheet_name="正答肢一覧")
    q["exam"] = q["回"].map(exam_key)

    trap_id = {}
    seq = {}
    for _, r in t.iterrows():
        seat, name = r["席"], r["罠の型"]
        chap, found = TRAP_OVERRIDE[subj].get(
            name, (SEAT_CHAPTER[subj][seat], SEAT_FOUNDATION.get(subj, {}).get(seat)))
        assert chap in chapter_ids and (found is None or found in chapter_ids), name
        tid = prev_ids.get((subj, seat, name))
        if not tid:
            while True:
                seq[chap] = seq.get(chap, 0) + 1
                tid = f"{TRAP_PREFIX[subj]}-{chap}-{seq[chap]:02d}"
                if tid not in used_ids:
                    break
            used_ids.add(tid)
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
            "reason": clean(r.get("なぜそうなるか（理由）")),
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
# 問題ファイルで _manual_tags: true にした問題は、章と罠の型をExcelで上書きしない（手で直した分類を守る）
MANUAL_KEEP = ("chapters", "traps")
for (exam, subj), items in sorted(questions_by_file.items()):
    path = OUT / "exams" / exam / f"{subj}.yaml"
    items = sorted(items, key=lambda x: x["num"])
    if path.exists():  # 手で書いた項目を残し、自動の項目だけ更新する
        old = {x["num"]: x for x in load(path)["questions"]}
        for it in items:
            if it["num"] in old:
                merged = old[it["num"]]
                for k in AUTO_FIELDS:
                    if k in it and not (merged.get("_manual_tags") and k in MANUAL_KEEP):
                        merged[k] = it[k]
                it.clear(); it.update(merged)
    head = {"exam": exam, "date": None, "subject": subj, "source_pdf": None}
    if path.exists():  # 実施日と出典URLは手で入れたものを残す
        prev = load(path)
        head["date"], head["source_pdf"] = prev.get("date"), prev.get("source_pdf")
    dump(path, {**head, "questions": items})

print(f"罠の型 {len(traps_out)} 件、問題ファイル {len(questions_by_file)} 件を {OUT} に出力しました")
