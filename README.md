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
