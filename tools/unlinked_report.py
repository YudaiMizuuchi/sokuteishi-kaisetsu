#!/usr/bin/env python3
"""ランクがD以外（S・A・B・C）で、参考書の章が1つも付かない問題を数える。目標は0。
使い方: python3 tools/unlinked_report.py [--list]"""
import sys,io,glob,yaml,collections,re
sys.path.insert(0,'tools')
_so=sys.stdout; sys.stdout=io.StringIO()
import compute_freq as CF
sys.stdout=_so
qc=yaml.safe_load(open('data/master/question_chapters.yaml',encoding='utf-8'))
NAME={'ippan':'一般','hourei':'関係法令','design':'デザイン','bunseki':'分析','yuki':'有機溶剤','tokka':'特定化学物質','kinzoku':'金属類','funjin':'鉱物性粉じん'}
c=collections.Counter(); tot=collections.Counter(); lst=[]
for s,ex in CF.docs.items():
    for e,(f,d) in ex.items():
        for q in d['questions']:
            fr=q.get('freq') or {}; lv=fr.get('level')
            if not lv or not q.get('choices'): continue
            k=f'{e}|{s}|{q["num"]}'; v=qc.get(k) or {'p':[],'r':[]}
            tot[(s,lv)]+=1
            if lv!='D' and not v['p'] and not v['r']:
                c[(s,lv)]+=1; lst.append((k,lv,CF.qkind(q),re.sub(r'\s+','',str(q['stem']))[:40]))
print('ランクS〜Cで、章が付かない問題：',sum(c.values()),'問')
for s in NAME: print(' ',NAME[s],{lv:c[(s,lv)] for lv in 'SABC' if c[(s,lv)]},'／S〜C全体',sum(tot[(s,lv)] for lv in 'SABC'))
if '--list' in sys.argv:
    for x in sorted(lst): print(*x)
