#!/usr/bin/env python3
"""参考書の章（book/<章ID>.md）の『この章の過去問』に写した、問題文・選択肢が、過去問データと一致するかを照合する。
使い方: python3 tools/check_book_quotes.py [章ID ...]（省略時は、book_map.yaml で written の章すべて）"""
import sys,re,yaml,os,glob
def norm(s): return re.sub(r'[\s　]+','',re.sub(r'\$([^$]*)\$',r'\1',re.sub(r'<[^>]+>','',str(s))))
ids=sys.argv[1:] or [c['id'] for c in yaml.safe_load(open('data/master/book_map.yaml',encoding='utf-8'))['chapters'] if c.get('status')=='written']
tot=0; bad=0
for cid in ids:
    p=f'book/{cid}.md'
    if not os.path.exists(p): continue
    t=open(p,encoding='utf-8').read()
    # **2026-08|design|12**（…） の次の段落＝問題文、続く「1. …」＝選択肢
    blocks=re.split(r'(?=^\*\*\[?[^\n]*?\d{4}-\d\d\|\w+\|\d+)',t,flags=re.M)
    nb=0; nbad=0; msgs=[]
    for b in blocks:
        m=re.match(r'\*\*(\d{4}-\d\d)\|(\w+)\|(\d+)\*\*',b)
        if not m: continue
        e,s,n=m.groups(); f=f'data/exams/{e}/{s}.yaml'
        if not os.path.exists(f): continue
        d=yaml.safe_load(open(f,encoding='utf-8')); q=[x for x in d['questions'] if str(x['num'])==n]
        if not q or not q[0].get('choices'): continue
        q=q[0]; nb+=1
        lines=[l for l in b.split('\n')[1:] if l.strip()]
        stem=norm(q['stem']); ch=[norm(c) for c in q['choices']]
        cl=[l for l in lines if re.match(r'\s*([①-⑩]|\d\.\s)',l)]
        sl=[l for l in lines if l not in cl and not re.match(r'(正答|（|\*\*|-|\|)',l.strip())]
        body=norm(sl[0]) if sl else ''
        txt='　'.join(cl); parts=[p for p in re.split(r'[①-⑩]|(?:^|　)\d\.\s',txt) if p.strip()]
        got=[norm(p) for p in parts]
        probs=[]
        if body!=stem:
            k=next((i for i,(x,y) in enumerate(zip(body,stem)) if x!=y),min(len(body),len(stem)))
            probs.append(f'問題文（{k}字目：章「{body[k:k+8]}」／原本「{stem[k:k+8]}」）')
        if len(got)!=len(ch): probs.append(f'選択肢の数 {len(got)}/{len(ch)}')
        else:
            for i,(g,c) in enumerate(zip(got,ch),1):
                if g!=c:
                    k=next((j for j,(x,y) in enumerate(zip(g,c)) if x!=y),min(len(g),len(c))); probs.append(f'選択肢{i}（章「{g[k:k+8]}」／原本「{c[k:k+8]}」）')
        if probs: nbad+=1; msgs.append(f'  {e}|{s}|{n}：'+'、'.join(probs))
    tot+=nb; bad+=nbad
    print(f'{cid}：照合 {nb}問、食い違い {nbad}問'); [print(x) for x in msgs[:12]]
print('合計 照合',tot,'問／食い違い',bad,'問')
