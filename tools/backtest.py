#!/usr/bin/env python3
"""区分のバックテスト（判定の回数は、その回より前の回だけで数える。受験者の立場）：受験者の立場（その回までの出題だけ）で区分を判定し、あとの回の出題と照らして、当たりを測る。
使い方: python3 tools/backtest.py     → /tmp/backtest.md に表を書く（サイトには載せない）
判定：各回Nについて、N以前の回だけで、論点の回数・パターンの回数・問題単位の回数を数え、境目は、現在の境目を、回数（N以前の回数／全回数）に比例して縮める。
測るもの：
 ・再出題率：その区分の問題の、正答の論点（パターン・問題形式）が、あとの H 回（3年分＝共通6回・選択3回）に、もう一度、出たか
 ・過去の既出率：正答の論点が、Nより前の回に出ていたか
 ・期待得点率：S〜Cを全部学習した場合の、Nの得点の目安（正答の論点が既出なら1点。消去法は、全部除外なら1点、2択なら0.5点。Cは0点）"""
import sys,collections,difflib,re,yaml
sys.path.insert(0,'tools')
import compute_freq as CF
subj_exams={s:sorted(e) for s,e in CF.docs.items()}
H={'ippan':6,'hourei':6,'design':6,'bunseki':6,'yuki':3,'tokka':3,'kinzoku':3,'funjin':3}
pt_exams=collections.defaultdict(set)    # (科目, 論点id) -> 回
for (subj,k),pid in CF._K2P.items(): pt_exams[(subj,pid)].add(k.split('|')[0])
TR=CF.TRAPS
def run(pr_on=True,trend_on=True,latest=False,subst_on=False,near_on=True):
    rows=[]   # 各問の結果
    for subj,exams in subj_exams.items():
        D=len(CF.docs[subj]); fulltd=CF.THRESHOLDS[subj]
        for ni,N in enumerate(exams):
            past=exams[:ni]; upto=exams[:ni+1]; fut=exams[ni+1:ni+1+H[subj]]
            if len(past)<4: continue
            if len(fut)<H[subj] and not latest: continue
            if latest and ni<len(exams)-2: continue
            scale=len(past)/D
            thr=tuple(max(2,round(t*scale)) for t in fulltd); thr=(max(thr[0],thr[1]+1,3),max(thr[1],thr[2]+1,3),max(thr[2],2))
            f,d=CF.docs[subj][N]
            for q in d['questions']:
                if q.get('status')!='published' or not q.get('choices'): continue
                ans=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
                if ans and ans[0]=='all': continue
                k=CF.qkind(q); n=len(q['choices'])
                _a0=ans[0]; _txt=str(q['stem'])+' '+(str(q['choices'][_a0-1]) if isinstance(_a0,int) and _a0<=len(q['choices']) else '')
                _tt=CF.SB.table_type(subj,_txt) if (subj in ('tokka','kinzoku') and subst_on) else None
                _sid=f'sb-{subj}-{_tt[0]}' if (_tt and _tt[1]) else None
                pats=[TR[t] for t in (q.get('traps') or []) if t in TR and 'other' not in t and 'その他' not in TR[t]['name']]
                pt=max(pats,key=lambda x:len([e for e in x.get('exams',[]) if e<=N])) if pats else None
                pc_upto=len([e for e in pt['exams'] if e<N]) if pt else 0
                CF.CUR=subj; old=CF.THRESHOLDS; CF.THRESHOLDS={**old,subj:thr}
                try:
                    prank=CF.rank_of(pc_upto,0,subj) if pt else None
                    if k=='stmt':
                        pcs=[];pids=[]
                        for i in range(1,n+1):
                            pid=CF._K2P.get((subj,f"{N}|{q['num']}|{i}")); pids.append(pid)
                            pcs.append(len([e for e in pt_exams[(subj,pid)] if e<N]) if pid else 0)
                        prcs=[]; prb=[]
                        for pid in pids:
                            cand=CF.PR_BY_POINT.get((subj,pid),[]) if pid else []
                            bb=max(cand,key=lambda r:len([e for e in CF.PR_EXAMS[r] if e<N])) if cand else None
                            prb.append(bb); prcs.append(len([e for e in CF.PR_EXAMS[bb] if e<N]) if bb else 0)
                        recent=set(past[-CF.TREND_K[subj]:])   # その回より前の直近K回
                        trend=[len([e for e in pt_exams[(subj,pid)] if e in recent]) if pid else 0 for pid in pids]
                        _nm=CF.compute_near(subj); _nr=[any(e2<N for e2 in _nm.get((N,q['num'],i),[])) for i in range(1,n+1)] if near_on else [False]*n
                        fr=dict(kind='choice',denom=len(past),counts=[0]*n,truths='',pcounts=pcs,prcounts=prcs,trend=trend if trend_on else [0]*n,self_counted=False,subst_id=_sid,near=_nr)
                        _oldpr=CF.PR_THRESHOLDS
                        CF.PR_THRESHOLDS={sj:tuple(max(2,round(x*scale)) for x in v) for sj,v in _oldpr.items()} if pr_on else {}
                        try: lv,why,tags=CF.judge(fr,ans,prank)
                        finally: CF.PR_THRESHOLDS=_oldpr
                        a=ans[0]-1; apid=pids[a]
                        if why.startswith('pr_') and prb[a]:
                            seen_before=len([e for e in CF.PR_EXAMS[prb[a]] if e<N])>=1
                            recur=len([e for e in CF.PR_EXAMS[prb[a]] if e in fut])>=1
                        else:
                            seen_before=(len([e for e in pt_exams[(subj,apid)] if e<N])>=1) if apid else False
                            recur=(len([e for e in pt_exams[(subj,apid)] if e in fut])>=1) if apid else False
                        dist_seen=[(len([e for e in pt_exams[(subj,p)] if e<N])>=1) if p else False for i,p in enumerate(pids) if i!=a]
                    else:
                        key=CF.norm(q['stem'])[:70] if k=='calc' else CF.norm(q['stem'])[:60]
                        def sim(e2):
                            dd=CF.docs[subj][e2][1]
                            for q2 in dd['questions']:
                                if CF.qkind(q2)!=k or not q2.get('choices'): continue
                                key2=CF.norm(q2['stem'])[:70] if k=='calc' else CF.norm(q2['stem'])[:60]
                                if difflib.SequenceMatcher(None,key,key2).ratio()>=(CF.THR_CALC if k=='calc' else CF.THR_Q): return True
                            return False
                        cnt=sum(1 for e2 in past if sim(e2))
                        fr=dict(kind='question',denom=len(past),count=cnt,form='',self_counted=False,subst_id=_sid)
                        lv,why,tags=CF.judge(fr,ans,prank)
                        seen_before=cnt>=1; recur=any(sim(e2) for e2 in fut); dist_seen=[]
                finally: CF.THRESHOLDS=old
                if lv in 'SABC':
                    if why=='elim_all': score=1.0
                    elif why=='elim_two': score=0.5
                    elif why=='subst': score=1.0
                    elif why=='near': score=0.5   # 改変型：過去の正しい記述を覚えていれば、おとりと見分けられる（半分の得点）
                    else: score=1.0 if seen_before else 0.0
                else: score=0.0
                rows.append(dict(subj=subj,exam=N,num=q['num'],level=lv,why=why,seen=seen_before,recur=recur,score=score))
    return rows
rows=run(pr_on=False,trend_on=False)
rows_pr=run(pr_on=True,trend_on=False)
rows_tr=run(pr_on=True,trend_on=True)
NAME={'ippan':'一般','hourei':'関係法令','design':'デザイン','bunseki':'分析','yuki':'有機溶剤','tokka':'特定化学物質','kinzoku':'金属類','funjin':'鉱物性粉じん'}
out=['# 区分のバックテスト（受験者の立場：その回までの出題だけで判定）','',f'評価した問題数：{len(rows)}','']
out+=['## 区分ごとの、再出題率（あとの3年分に、正答の論点が、もう一度出たか）と、過去の既出率','','| 科目 | 区分 | 問題数 | 割合 | 過去に既出 | あとの3年に再出題 |','|---|---|---|---|---|---|']
for s in NAME:
    rs=[r for r in rows if r['subj']==s]; n=len(rs)
    for lv in 'SABCD':
        x=[r for r in rs if r['level']==lv]
        if x: out.append(f"| {NAME[s]} | {lv} | {len(x)} | {len(x)/n:.0%} | {sum(r['seen'] for r in x)/len(x):.0%} | {sum(r['recur'] for r in x)/len(x):.0%} |")
out+=['','## 期待得点率（S〜Cを全部学習した場合の目安。回別・科目別）','','| 科目 | 評価した回 | 期待得点率の平均 | 最小 | 最大 |','|---|---|---|---|---|']
for s in NAME:
    byexam=collections.defaultdict(list)
    for r in rows:
        if r['subj']==s: byexam[r['exam']].append(r['score'])
    v=[sum(x)/len(x) for x in byexam.values()]
    if v: out.append(f"| {NAME[s]} | {len(v)} | {sum(v)/len(v):.0%} | {min(v):.0%} | {max(v):.0%} |")
# ---- 原理の効果（原理を入れる前と後）----
def agg(rs):
    n=len(rs); c=collections.Counter(r['level'] for r in rs)
    by=collections.defaultdict(list)
    for r in rs: by[r['exam']].append(r['score'])
    exp=sum(sum(v)/len(v) for v in by.values())/len(by)
    return n,c,exp
for subj in CF.PR_THRESHOLDS:
    b0=[r for r in rows if r['subj']==subj]; b1=[r for r in rows_pr if r['subj']==subj]
    if not b0: continue
    out+=['',f'## 原理を入れた効果：{NAME[subj]}','','| 項目 | 原理なし | 原理あり |','|---|---|---|']
    n0,c0,e0=agg(b0); n1,c1,e1=agg(b1)
    out.append(f"| 区分の割合（S／A／B／C／D） | {'／'.join(f'{c0[k]/n0:.0%}' for k in 'SABC')} | {'／'.join(f'{c1[k]/n1:.0%}' for k in 'SABC')} |")
    out.append(f"| 期待得点率（S〜C学習時）の平均 | {e0:.0%} | {e1:.0%} |")
    prq=[r for r in b1 if r['why'].startswith('pr_')]
    bykey={(r['exam'],r['num']):r for r in b0}
    moved=[r for r in prq if bykey[(r['exam'],r['num'])]['level']=='C']
    c_before=[r for r in b0 if r['level']=='C']
    out.append(f"| 原理が決め手になった問題 | 0問 | {len(prq)}問 |")
    out.append(f"| 原理なしでCだった問題のうち、原理で解けると判定された割合 | － | {len(moved)}／{len(c_before)}＝{len(moved)/max(1,len(c_before)):.0%} |")
    if prq: out.append(f"| 原理が決め手の問題の、過去の既出率／あとの3年の再出題率 | － | {sum(r['seen'] for r in prq)/len(prq):.0%}／{sum(r['recur'] for r in prq)/len(prq):.0%} |")
rows_latest=run(pr_on=True,trend_on=True,latest=True,subst_on=True)
rows_latest0=run(pr_on=True,trend_on=True,latest=True,subst_on=False)
out+=['','## 最新2回を、それ以前の全回で判定した場合（実際の受験者に近い条件）','','| 科目 | 評価した回 | 区分の割合（S／A／B／C／D） | 期待得点率 |','|---|---|---|---|']
for subj in NAME:
    rs=[r for r in rows_latest if r['subj']==subj]
    if not rs: continue
    n,c,e=agg(rs); ex=sorted({r['exam'] for r in rs})
    out.append(f"| {NAME[subj]} | {'・'.join(ex)} | {'／'.join(f'{c[k]/n:.0%}' for k in 'SABCD')} | {e:.0%} |")
out+=['','## 物質の表（確認済みの物質）を入れた効果：最新2回（特定化学物質・金属類）','','| 科目 | 期待得点率（表なし） | 期待得点率（表あり） | 表が決め手の問題 |','|---|---|---|---|']
for subj in ('tokka','kinzoku'):
    r0=[r for r in rows_latest0 if r['subj']==subj]; r1=[r for r in rows_latest if r['subj']==subj]
    if r0: out.append(f"| {NAME[subj]} | {agg(r0)[2]:.0%} | {agg(r1)[2]:.0%} | {sum(1 for r in r1 if r['why']=='subst')}問 |")
out+=['','## 直近トレンドを入れた効果（原理あり → 原理＋トレンド）','','| 科目 | 期待得点率（原理あり） | 期待得点率（原理＋トレンド） | トレンドが決め手の問題 | その再出題率 |','|---|---|---|---|---|']
for subj in NAME:
    b1=[r for r in rows_pr if r['subj']==subj]; b2=[r for r in rows_tr if r['subj']==subj]
    if not b1: continue
    _,_,e1=agg(b1); _,_,e2=agg(b2); tq=[r for r in b2 if r['why'].startswith('trend')]
    out.append(f"| {NAME[subj]} | {e1:.0%} | {e2:.0%} | {len(tq)}問 | {sum(r['recur'] for r in tq)/len(tq):.0%} |" if tq else f"| {NAME[subj]} | {e1:.0%} | {e2:.0%} | 0問 | － |")
open('/tmp/backtest.md','w',encoding='utf-8').write('\n'.join(out))
print('\n'.join(out))
