#!/usr/bin/env python3
"""ランクの境目（THRESHOLDS）を、最終の区分（おとりによる絞り込みを含む）の分布が、目標の割合に近くなるように探す。
目標（科目内）：S30％・A25％・B20％（C＋Dは残り約25％）。2026年11月5日に、S15／A25／B30から変更（運営者の了承あり）。形は、S＞A＞B（Cは、既出か初見かで決まる）。
使い方: python3 tools/fit_thresholds.py         （結果の表を出すだけ）
        python3 tools/fit_thresholds.py write    （compute_freq.py の THRESHOLDS を書き換える）"""
import sys,re,collections,itertools
sys.path.insert(0,'tools')
sys.argv=[sys.argv[0]]+[a for a in sys.argv[1:] if a!='write']
WRITE='write' in open('/proc/self/cmdline','rb').read().decode(errors='ignore')
import compute_freq as CF
TARGET={'S':.30,'A':.25,'B':.20}      # 5ランク（S・A・B・C・D）。CとDは絶対の境目（既出か初見か）なので、目標に含めない
SEL={'yuki','tokka','kinzoku','funjin'}     # 選択科目：Bの下限は3回に固定（C＝通算2回＝過去に1回だけ既出）
feats=CF.collect()
by=collections.defaultdict(list)
for f in feats: by[f['subj']].append(f)
def dist(fs,thr,elim='B'):
    out=CF.decide(fs,{fs[0]['subj']:thr},{fs[0]['subj']:elim}); c=collections.Counter(v['level'] for v in out.values()); n=len(out)
    return {r:c[r]/n for r in 'SABCD'}
def err(d): return sum(abs(d[r]-TARGET[r]) for r in 'SAB')
def ok(d): return 0.60<=d['S']+d['A']+d['B']<=0.80 and d['S']>=d['A']>=d['B']>=0.10   # 選択科目は、Bの下限が3回に固定なので、S≥A≥Bにできない科目は、誤差最小の組を使う
res={}
for subj,fs in by.items():
    cur=CF.THRESHOLDS[subj]; D=fs[0]['fr']['denom']
    top=min(D,max([max(f['fr'].get('pcounts') or [0]) for f in fs if f['fr']['kind']=='choice']+[max(f['pat_count'] for f in fs)]))
    best=None; feas=None
    for elim in ('B','A'):
        for ts in range(4,top+1):
            for ta in range(3,ts):
                tbs=[3] if subj in SEL else range(2,ta)
                for tb in tbs:
                    if tb>=ta: continue
                    d=dist(fs,(ts,ta,tb),elim); e=err(d)
                    if best is None or e<best[0]-1e-9: best=(e,(ts,ta,tb),d,elim)
                    if ok(d) and (feas is None or e<feas[0]-1e-9): feas=(e,(ts,ta,tb),d,elim)
    res[subj]=(cur,dist(fs,cur),feas or best)
NAME={'ippan':'一般','hourei':'関係法令','design':'デザイン','bunseki':'分析','yuki':'有機溶剤','tokka':'特定化学物質','kinzoku':'金属類','funjin':'鉱物性粉じん'}
print('科目 | 現在の境目（S/A/B）→分布（S/A/B/C/D）| 新しい境目 → 分布 | S+A+B')
for s in NAME:
    cur,dc,(e,thr,d,el)=res[s]
    print(f"{NAME[s]} | {cur} → "+'/'.join(f"{dc[r]:.0%}" for r in 'SABCD')+f" | {thr}・おとりの除外は{el}以上 → "+'/'.join(f"{d[r]:.0%}" for r in 'SABCD')+f" | S+A+B {d['S']+d['A']+d['B']:.0%}")
import json; json.dump({s:[list(res[s][2][1]),res[s][2][3]] for s in res},open('/tmp/thr_new.json','w'))

# ---- 第2段階：原理用の境目（論点の境目は、上で決めたものに固定）----
print('\n原理用の境目（論点の境目・おとりの水準は、現在の値で固定）')
for subj in list(CF.PR_THRESHOLDS):
    fs=by[subj]; thr=CF.THRESHOLDS[subj]; el={subj:CF.ELIM_KNOWN.get(subj,'B')}
    base=CF.decide(fs,{subj:thr},el,{}); c=collections.Counter(v['level'] for v in base.values()); n=len(base)
    print(f"{NAME[subj]} 原理なし："+'/'.join(f"{c[r]/n:.0%}" for r in 'SABCD'))
    mx=max(max(f['fr'].get('prcounts') or [0]) for f in fs if f['fr']['kind']=='choice')
    best=None
    for ts in range(5,mx+1):
        for ta in range(4,ts):
            for tb in range(3,ta):
                out=CF.decide(fs,{subj:thr},el,{subj:(ts,ta,tb)}); c=collections.Counter(v['level'] for v in out.values())
                d={r:c[r]/n for r in 'SABCD'}; e=err(d)
                if best is None or e<best[0]-1e-9: best=(e,(ts,ta,tb),d,collections.Counter(v['why'] for v in out.values() if v['why'].startswith('pr_')))
    e,t,d,w=best
    print(f"{NAME[subj]} 原理の境目 {t} → "+'/'.join(f"{d[r]:.0%}" for r in 'SABCD')+f"  原理が決め手の問題 {sum(w.values())}問（{dict(w)}）")
