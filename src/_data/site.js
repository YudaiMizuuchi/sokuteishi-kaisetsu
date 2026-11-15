// サイト全体の設定。
export default {
  title: "作業環境測定士試験 過去問解説",
  description: "作業環境測定士試験の過去問を、年度・科目・参考書の章・ひっかけパターンで絞り込んで学べる解説サイト。",
  // 公開するドメインと、その下のフォルダ（既存のツール群と同じドメインに置く）
  origin: "https://aoi-s-office.jp",
  pathPrefix: "/sokuteishi/",
  author: "あおい技術サービス事務所",
  // 安全衛生技術試験協会から転載の許諾を得ているので、問題文・選択肢・正答を表示する
  showStem: true,
  sourceName: "公益財団法人 安全衛生技術試験協会 公表試験問題",
  officialIndex: "https://www.exam.or.jp/emkohyo/",
  // npm run dev / preview のときだけ draft の問題も表示する（その場合は noindex）
  showDrafts: process.env.SHOW_DRAFTS === "1",
  pageSize: 20,
  // 「管理人を応援する」のリンク先（Amazon 欲しいものリスト）
  supportUrl: "https://www.amazon.co.jp/hz/wishlist/ls/SPA8YXBIA6NM?ref_=wl_share",
  // お問い合わせフォームのURL（Googleフォーム）
  contactUrl: "https://forms.gle/KxzPPomLpmS2L1L76",
  // まだ掲載できていない回があるときは、ここに書く（トップページの案内に出る）
  missingExams: [],
};
