# 作業環境測定士試験 過去問解説サイト

https://aoi-s-office.jp/sokuteishi/ で公開する前提の Eleventy プロジェクト。

## 使い方

    npm install
    npm run dev        # 下書きも表示してローカルで確認（http://localhost:8080/sokuteishi/）
    npm run build      # 本番ビルド（published の問題だけ。_site/ に出力）

## データを入れる流れ

1. 罠の型一覧のExcelから、章・罠の型の割り当てを作る
       python tools/convert_wana.py <Excelのフォルダ> data
2. 公表試験問題のPDFから、問題文・選択肢・正答を取り込む
       pip install pdfplumber pyyaml
       python tools/import_pdf.py <PDFのフォルダ> --data data
   - ファイル名は協会の公表ファイル名のまま（EM20261803.pdf か 20260217-3.pdf の形）
   - 図は src/assets/figures/ に自動で切り出される（図の中の正答の○は白で消す）
   - 数式で文字にできない選択肢は画像になり、選択肢は「図の1」〜「図の5」になる
   - 読み切れなかった問題は import_report.csv に出る。PDFと見比べて YAML を直し、_review と _import_flags を消す
   - 根号（√）や反応の矢印（⇄）など、PDFで図形として描かれている記号は文字として取れないので、手で補う
3. explanation（解説）と、必要なら choice_notes（肢ごとの解説）を書き、status を published にする
4. git push すると Netlify が自動でビルドする

published の問題は、問題文・選択肢・正答・解説がそろっていないとビルドが止まる。
罠の型は、裏取り前（verify: true）でも公開する。誤りに気づいたら、罠の型一覧のExcelで確度に「非公開」と書いて convert_wana.py を実行し直すと、その型はサイトから外れる。問題そのものを外すときは status を draft に戻す。「その他（単発）」の型は表示しない。

## 既存サイト（aoi-s-office.jp）からの配信

このサイトは別のNetlifyサイトとして作り、既存サイトの `_redirects` に次の1行を足して /sokuteishi/ 以下で見せる。

    /sokuteishi/*  https://<このサイトの名前>.netlify.app/sokuteishi/:splat  200

既存サイトの robots.txt に `Sitemap: https://aoi-s-office.jp/sokuteishi/sitemap.xml` を追加し、
Search Console にも同じサイトマップを送信する。

## 設定（src/_data/site.js）

- origin / pathPrefix … 公開先のドメインとフォルダ
- showStem … 問題文・選択肢を表示する（協会の許諾に基づき true）
- sourceName … 出典表示の文言（許諾の条件で指定があれば合わせる）

## 参考書のページ

`book/<章ID>.md` を置くと、`/book/<章ID>/` に参考書の章ページができ、その章に関わる問題の解説欄に
「参考書『〇-〇 …』で復習する」ボタン（新しいタブで開く）が自動で付く。章IDは data/master/book.yaml の chapters の id。

Claude Docs の原稿を Markdown で書き出したら、次で制作用の節（動画台本メモ、イラストの指示や生成プロンプト、
執筆メモ、要確認事項）を取り除いてから置く。

    python tools/clean_book_md.py <書き出したMarkdown> <章ID>

## 確認中の解説

問題データに `review_note: …` を書くと、解説欄に「現在、管理者にて確認中」の枠で表示され、
管理用の一覧ページ `/sokuteishi/review/`（メニュー・サイトマップには載らない、noindex）にまとめて出る。
確認が済んだら、解説を直して `review_note` の行を消す。

## 罠の型一覧を更新したとき

`python tools/convert_wana.py <Excelのフォルダ> data` で変換し直す。罠の型のIDは、名前が同じ型は前回のIDを、
名前を直した型は同じ問題に付いていた旧IDを引き継ぐので、罠の型のページのURLは変わらない。
ランクは Excel の「ランク」列の値をそのまま使う（22回版は A＝22回中5回以上、B＝2〜4回、法令は重み付き回数で判定）。

### 問題集Excelの正答の訂正

`tools/import_book_excel.py` で取り込み直すとき（`--force`）は、次の訂正を `--overrides` で指定する。
2017-02:bunseki:7=3（2018年版の正答）、2018-08:design:1=1、2018-08:bunseki:2=3、2015-02:design:17=4（問題集・試験問題の原本の画像で確認）。
また、2016-08 の一般 問1 は Excel の選択肢の並びが原本と違っていたので、取り込み直した場合は選択肢を「㋑㋩㋥㋺／㋩㋥㋑㋺／㋩㋥㋺㋑／㋥㋩㋑㋺／㋥㋩㋺㋑」、正答を 2 に直す

## 対象の回と公開の方針（2026年10月）

- 対象は平成28年度第1回（2016年8月）〜令和8年度第1回の19回（令和3年度第2回・令和4年度第1回は未収録）。
  平成26年度第2回〜平成27年度第2回の3回はデータを残し、問題ファイルに `excluded` を付けて非公開にしている。
- ひっかけパターン一覧は19回版（`*_ひっかけパターン一覧_19回.xlsx`）。ランクは Excel の数式欄に値が入っていないため、
  convert_wana.py が19回版の基準（A＝4回以上、B＝2〜3回、法令は重み付き回数）で計算する。
- 第2種の共通科目は全問解説付き。第1種の選択科目は、問題と正答だけで公開している（解説は準備中と表示）。

## 過去問マスタ（master_C1〜C4_*.json）の反映

共通科目（一般・法令・デザイン・分析）の問題文・選択肢・正答・図は、マスタ（原本の画像と照合済み）を正とする。

    python tools/apply_master.py <マスタJSONと図の画像があるフォルダ> --data data --figures <同じフォルダ>

- 表記だけの違い（空白、全角半角、LaTeX の書き方、㋑㋺の印など）は置き換えない。文字や内容が違うときだけ、マスタの文面で置き換える。
- マスタの図（`<ID>_1.png`）は `src/assets/figures/<年月>-<科目>-<問>-fig.png` にコピーして問題に付ける。
  「【図の内容（文字化）】」は図の代替テキスト（alt）に使う。選択肢そのものが絵のとき（`KEEP_FIGLABEL`）は、答えの手がかりになるので文字の選択肢にしない。
- マスタに独自に入っている注記（※…、紙面の列見出し…）は取り込まない（`SKIP_STEM` / `SKIP_CHOICES`）。
- 原本の印字（誤植）をそのまま載せている箇所は、問題の `text_note` に書く（「原文について：…」と表示される）。
- 選択科目（C5 鉱物性粉じん・C6 特定化学物質・C7 金属類・C8 有機溶剤）も、同じマスタで突き合わせる。正答が違うときはマスタに合わせる。
  分数と根号の入った式（`KEEP_FIGLABEL` の R2-1-C5-02 など）は画像のまま。表は本文の表にして、元の画像を外す。
- トップページの「このサイトについて」は `src/index.njk`、お問い合わせのURLと未掲載の回は `src/_data/site.js`（`contactUrl`、`missingExams`）。
- 第1種の放射線関係（放射性物質）は対象外。`data/exams/*/hoshasei.yaml` に `excluded` を付け、全問を draft にしている。

## 数式（LaTeX）と図の方針

- 図の画像は、いただいた25枚（絵表示、構造式、グラフ、配置図など、文字や式で表せないもの）だけを使う。それ以外は、本文・表（Markdown の表）・LaTeX で表す。
- 問題文・選択肢・解説の中の `$…$` は、サイトのビルド時に KaTeX で HTML にする（`src/_data/db.js` の `withMath`）。
  `\frac` は読みやすいように `\dfrac` に直して表示する。フォントとCSSは `src/assets/katex/`（woff2のみ）。
- `tools/apply_master.py` は、`LATEX_CHOICES` に入れた問題の選択肢を、マスタの LaTeX のまま入れる。
