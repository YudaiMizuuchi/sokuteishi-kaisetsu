import { HtmlBasePlugin } from "@11ty/eleventy";
import site from "./src/_data/site.js";

export default function (eleventyConfig) {
  // "/q/..." のようなルート相対リンクを、自動で "/sokuteishi/q/..." に書き換える
  eleventyConfig.addPlugin(HtmlBasePlugin);
  eleventyConfig.addPassthroughCopy({ "src/assets": "assets" });
  eleventyConfig.addPassthroughCopy({ "src/_redirects": "_redirects" });
  eleventyConfig.addWatchTarget("./data/");
  eleventyConfig.addFilter("json", (v) => JSON.stringify(v).replace(/</g, "\\u003c"));
  eleventyConfig.addFilter("pluck", (arr, key) => arr.map((x) => x[key]));
  // 絶対URL（canonical・サイトマップ・構造化データ用）
  eleventyConfig.addFilter("absUrl", (p) => site.origin + site.pathPrefix.replace(/\/$/, "") + p);
  eleventyConfig.addFilter("plain", (html) => String(html || "").replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim());
  eleventyConfig.addFilter("truncate", (s, n) => (s.length > n ? s.slice(0, n) + "…" : s));

  return {
    pathPrefix: site.pathPrefix,
    dir: { input: "src", output: "_site", includes: "_includes", data: "_data" },
    templateFormats: ["njk"],
    htmlTemplateEngine: "njk",
  };
}
