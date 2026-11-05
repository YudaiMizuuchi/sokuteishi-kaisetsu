"""参考書の原稿（Claude Docs から Markdown で書き出したもの）を、サイト用の book/<章ID>.md に整える。

使い方:
    python tools/clean_book_md.py <書き出したMarkdown> <章ID>
    例) python tools/clean_book_md.py 3-2.md a-b-measurement

- 先頭のタイトル行と日付の行、章ID・題・部・種類などのメモ欄（``` で囲んだ最初のブロック）を取る
- 「## 6. 動画台本メモ・イラスト指示」「## 7. 執筆メモ」のように、番号つきの制作用の節も取る
- 先頭のタイトル行と日付の行を取る（ページの見出しは book.yaml の章名を使う）
- 動画台本メモ・イラスト／図解の制作方針・生成プロンプト・執筆メモ・要確認事項など、
  制作用の節から後ろを取る
- 本文中のイラスト・図解・器具イラストの指示（**イラストI-01** など）の段落を取る
"""
import re
import sys
from pathlib import Path

STOP = re.compile(r"^##\s+(\d+\.\s*)?(動画台本メモ|イラスト|執筆メモ|要確認事項)")
PLACEHOLDER = re.compile(r"^\*\*(イラスト|図解|器具イラスト)")


def clean(text):
    # 章の先頭にある、章ID・題・部・種類などのメモ欄（``` で囲んだ最初のブロック）を取る
    text = re.sub(r"\A(\s*#[^\n]*\n)?\s*```[^\n]*\n章ID:.*?\n```\n", lambda m: (m.group(1) or ""), text, count=1, flags=re.S)
    lines = text.splitlines()
    out = []
    for i, ln in enumerate(lines):
        if "素材パック" in ln:   # 執筆用の素材の説明（読者には要らない）
            continue
        if i == 0 and ln.startswith("# "):
            continue
        if i <= 3 and re.match(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}", ln):  # 日付・作成者の行
            continue
        if STOP.match(ln):
            break
        if PLACEHOLDER.match(ln):
            continue
        out.append(ln)
    text = "\n".join(out).strip() + "\n"
    return re.sub(r"\n{3,}", "\n\n", text)


def strip_past_questions(t):
    """『この章の過去問』『この章で解けるようになった過去問』の節を、本文から外す（過去問は、過去問解説ページで解く。参考書は、復習の場）。節の末尾は、次の '## ' 見出し、または、ファイルの終わり"""
    return re.sub(r'\n## [^\n]*(この章の過去問|解けるようになった過去問|過去問チェック)[^\n]*\n.*?(?=\n## |\Z)','\n',t,flags=re.S)
def main():
    src, chapter = Path(sys.argv[1]), sys.argv[2]
    dst = Path(__file__).resolve().parent.parent / "book" / f"{chapter}.md"
    dst.write_text(strip_past_questions(clean(src.read_text(encoding="utf-8"))), encoding="utf-8")
    print(f"{src.name} → {dst}")


if __name__ == "__main__":
    main()
