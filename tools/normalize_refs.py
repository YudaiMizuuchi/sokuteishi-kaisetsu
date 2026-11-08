#!/usr/bin/env python3
"""参考図書の書名を、data/master/references.yaml の canonical に統一する。
使い方: python3 tools/normalize_refs.py          （点検だけ。置き換えが要る箇所を数える）
        python3 tools/normalize_refs.py --apply  （置き換える）
対象（サイトに出るもの）: book/*.md、data/exams/*/*.yaml、data/master/*.yaml（references.yaml を除く）、data/master/substances/*.yaml、src/*.njk、src/_includes/*
内部の資料番号（J-73 など）は、canonical の書名（『…』）に置き換える。"""
import glob,re,sys,yaml
R=yaml.safe_load(open("data/master/references.yaml",encoding="utf-8"))["references"]
rules=[]
for r in R:
    c=r["canonical"]
    for v in sorted(r.get("variants",[]),key=len,reverse=True):
        rules.append((re.compile(r"『"+re.escape(v)+r"』"),f"『{c}』"))
        rules.append((re.compile(r"(?<!『)"+re.escape(v)+r"(?!』)"),f"『{c}』"))  # 『』なしで書いてあるもの
    for code in sorted(r.get("codes",[]),key=len,reverse=True):
        rules.append((re.compile(r"(?<![A-Za-z0-9\-])"+re.escape(code)+r"(?![0-9])"),f"『{c}』"))
files=[f for g in ("book/*.md","data/exams/*/*.yaml","data/master/*.yaml","data/master/substances/*.yaml","src/*.njk","src/_includes/*") for f in glob.glob(g) if not f.endswith("references.yaml")]
apply="--apply" in sys.argv; total=0; changed=[]
for f in files:
    try: t=open(f,encoding="utf-8").read()
    except: continue
    o=t
    for rx,rep in rules: t=rx.sub(rep,t)
    t=t.replace("『『","『").replace("』』","』")
    if t!=o:
        n=sum(len(rx.findall(o)) for rx,_ in rules); total+=n; changed.append((f,n))
        if apply: open(f,"w",encoding="utf-8").write(t)
print(("置き換えた" if apply else "置き換えが要る")+f"：{total}か所／{len(changed)}ファイル")
for f,n in sorted(changed,key=lambda x:-x[1])[:12]: print("  ",n,f)
