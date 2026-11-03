#!/usr/bin/env python3
"""科目の解説文から、原理の候補（式・法則名・因果の文）を抽出する。
使い方: python3 tools/extract_principles.py <科目ID>   → /tmp/principle_candidates_<科目>.md
原理＝いくつもの論点を生む、もとの理屈。候補は、人（Claude）が、1つの理屈＝1つの原理の形に整えて、data/master/principles.yaml に書く。"""
import yaml,glob,re,sys,collections
subj=sys.argv[1]
sents=[]
for f in sorted(glob.glob(f'data/exams/*/{subj}.yaml')):
    d=yaml.safe_load(open(f,encoding='utf-8')); e=f.split('/')[2]
    for q in d['questions']:
        t=q.get('explanation') or ''
        t=re.sub(r'\*\*|\$[^$]*\$|（参考：[^）]*）','',t)
        for s in re.split(r'(?<=。)|\n+',t):
            s=s.strip()
            if 12<=len(s)<=90: sents.append((e,q['num'],s))
kw=re.compile(r'の法則|の式|の原理|比例|反比例|ほど|ので|ため|＝|∝|なります|生じます|増加|減少|大きく|小さく')
cand=collections.Counter(); ex={}
for e,n,s in sents:
    if not kw.search(s): continue
    key=re.sub(r'\d+(\.\d+)?','#',s); key=re.sub(r'[（(][^）)]*[）)]','',key)
    cand[key[:40]]+=1; ex.setdefault(key[:40],(e,n,s))
rows=cand.most_common(400)
open(f'/tmp/principle_candidates_{subj}.md','w',encoding='utf-8').write('\n'.join(f"{c}\t{ex[k][0]}問{ex[k][1]}\t{ex[k][2]}" for k,c in rows))
print(len(sents),'文 → 候補',len(cand),'（出現の多い上位400を出力）')
