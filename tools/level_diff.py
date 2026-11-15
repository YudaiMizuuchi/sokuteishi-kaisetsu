#!/usr/bin/env python3
"""区分の変化を、前回の保存（/tmp/levels_before.json）と比べて一覧にする。使い方: python3 tools/level_diff.py [--list]"""
import glob,yaml,json,collections,sys
b=json.load(open('/tmp/levels_before.json'))
ORD={'S':0,'A':1,'B':2,'C':3,'D':4}
NAME={'ippan':'一般','hourei':'関係法令','design':'デザイン','bunseki':'分析','yuki':'有機溶剤','tokka':'特定化学物質','kinzoku':'金属類','funjin':'鉱物性粉じん'}
rows=[]; ch=collections.Counter(); tot=0
for f in glob.glob('data/exams/*/*.yaml'):
    d=yaml.safe_load(open(f,encoding='utf8')); e=f.split('/')[-2]
    for q in d['questions']:
        fr=q.get('freq') or {}
        if not fr: continue
        k=f"{e}|{d['subject']}|{q['num']}"; old=b.get(k)
        if not old: continue
        tot+=1
        if old[0]!=fr.get('level') or old[1]!=fr.get('why'):
            rows.append((d['subject'],k,fr.get('kind'),old[0],fr.get('level'),old[1],fr.get('why')))
            if old[0]!=fr.get('level'): ch[(d['subject'],fr.get('kind'),'上がる' if ORD[fr['level']]<ORD[old[0]] else '下がる')]+=1
print('区分が変わった問題',sum(ch.values()),'／理由だけ変わった',len(rows)-sum(ch.values()),'／全',tot)
for s in NAME:
    u=sum(v for (a,k,dr),v in ch.items() if a==s and dr=='上がる'); dn=sum(v for (a,k,dr),v in ch.items() if a==s and dr=='下がる')
    if u or dn: print(' ',NAME[s],'上がる',u,'下がる',dn,{k:v for (a,k,dr),v in ch.items() if a==s})
if '--list' in sys.argv:
    for r in sorted(rows): print(*r)
