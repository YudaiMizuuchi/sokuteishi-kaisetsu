#!/usr/bin/env python3
"""ビルド後の公開ページ（_site）の点検。使い方: python3 tools/check_site.py（先に npx @11ty/eleventy）
1. 文字のまま残る Markdown 記号（**、リンク記法 [..](..)、バッククォート、表の区切り、見出し記号）
2. コード書体のまま残る参照（過去問の参照 2026-08|ippan|3、章ID bk-…、論点・原理ID）
3. 内部リンクで、リンク先のページがないもの（404）
4. 個人情報・内部の表現（運営者の氏名など〔語は、リポジトリに書かず、.private_terms に1行1語で置く。ZIPに入れない〕、「本人提供」などの提供者の表現）、内部の資料番号（J-73 など）、書名の表記ゆれ（data/master/references.yaml の variants）
問題が1つでもあれば、終了コード1。"""
import glob,re,os,sys,collections,yaml
ROOT=os.path.join(os.getcwd(),"_site")
if not os.path.isdir(ROOT): sys.exit("_site がない。先に npx @11ty/eleventy を実行する")
files=set()
for f in glob.glob(ROOT+"/**/*",recursive=True):
    if os.path.isfile(f): files.add(f[len(ROOT):])
def exists(path):
    path=path.split("#")[0].split("?")[0]
    if path.startswith("/sokuteishi/"): path=path[len("/sokuteishi"):]
    return any(c in files for c in [path,path.rstrip("/")+"/index.html",path+"index.html"])
MARK={"強調 **":r"\*\*","リンク記法 [..](..)":r"\]\((/|https?:)","バッククォート":r"`","表の区切り |---|":r"\|\s*-{3,}\s*\|","見出し記号 ##":r"(^|\s)#{2,4}\s"}
PRIV={"提供者の表現":r"本人提供|ご提供|提供者|提供元|運営者から提供","内部の資料番号":r"(?<![A-Za-z0-9\-])J-?\d{2,3}(?![0-9])|J11-2021"}
_refs=yaml.safe_load(open("data/master/references.yaml",encoding="utf-8"))["references"]
for _r in _refs:
    for _v in _r.get("variants",[]): PRIV.setdefault("書名のゆれ",""); PRIV["書名のゆれ"]+=("|" if PRIV["書名のゆれ"] else "")+re.escape(_v)
_pt=os.path.join(os.getcwd(),".private_terms")
if os.path.exists(_pt):
    _terms=[l.strip() for l in open(_pt,encoding="utf-8") if l.strip() and not l.startswith("#")]
    if _terms: PRIV["運営者の氏名など（.private_terms）"]="|".join(re.escape(x) for x in _terms)
pcnt=collections.Counter(); pex={}
cnt=collections.Counter(); ex={}; code=collections.Counter(); cex={}; bad=collections.Counter(); bex={}; n=0; pages=0
for f in glob.glob(ROOT+"/**/index.html",recursive=True):
    h=open(f,encoding="utf-8",errors="ignore").read(); pages+=1
    body=re.sub(r"<script.*?</script>|<style.*?</style>","",h,flags=re.S)
    txt=re.sub(r"<[^>]+>","",body); rel=f[len(ROOT)+1:]
    for k,p in MARK.items():
        m=re.search(p,txt,flags=re.M)
        if m: cnt[k]+=1; ex.setdefault(k,(rel,txt[max(0,m.start()-30):m.end()+40].replace("\n"," ")))
    for k,p in PRIV.items():
        if k=="書名のゆれ" and rel=="guide/index.html": continue   # 見方のページの「参考にした図書」は、正式な書名を載せる
        m=re.search(p,txt)
        if m: pcnt[k]+=1; pex.setdefault(k,(rel,txt[max(0,m.start()-25):m.end()+25].replace("\n"," ")))
    for m in re.finditer(r"<code>([^<]{1,80})</code>",body):
        c=m.group(1)
        kind="過去問の参照" if re.fullmatch(r"\d{4}-\d{2}\|\w+\|\d+(\|\d+)?",c) else "章ID" if re.fullmatch(r"bk-[a-z]+-[a-z0-9]+",c) else "論点・原理ID" if re.fullmatch(r"(pt|qp|pr|sb)-[a-z]+-\d+",c) else None
        if kind: code[kind]+=1; cex.setdefault(kind,(rel,c))
    for m in re.finditer(r'href="(/[^"#]*)',body):
        n+=1
        if not exists(m.group(1)): bad[m.group(1)]+=1; bex.setdefault(m.group(1),rel)
print(f"ページ {pages}／内部リンク {n}")
ng=False
for title,c,e in [("文字のまま残る記号",cnt,ex),("コード書体のまま残る参照",code,cex),("リンク先がない内部リンク",bad,bex),("個人情報・内部の表現・書名のゆれ",pcnt,pex)]:
    if c:
        ng=True; print(f"✗ {title}：{sum(c.values())}件（{len(c)}種類）")
        for k in list(c)[:6]: print("   ",k,e.get(k))
    else: print(f"✓ {title}：なし")
sys.exit(1 if ng else 0)
