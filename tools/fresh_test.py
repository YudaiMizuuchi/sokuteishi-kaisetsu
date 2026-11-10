import sys,collections
sys.path.insert(0,'tools')
import compute_freq as CF
H={'ippan':6,'hourei':6,'design':6,'bunseki':6,'yuki':3,'tokka':3,'kinzoku':3,'funjin':3}
NAME={'ippan':'一般','hourei':'関係法令','design':'デザイン','bunseki':'分析','yuki':'有機溶剤','tokka':'特定化学物質','kinzoku':'金属類','funjin':'鉱物性粉じん'}
pt=collections.defaultdict(set)
for (s,k),pid in CF._K2P.items(): pt[(s,pid)].add(k.split('|')[0])
out=[]
for s in NAME:
    exams=sorted(CF.docs[s]); K=H[s]
    # 各問の正答の論点
    Q=[]
    for N in exams:
        f,d=CF.docs[s][N]
        for q in d['questions']:
            if q.get('status')!='published' or not q.get('choices'): continue
            ans=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
            if not ans or ans[0]=='all' or not isinstance(ans[0],int): continue
            pid=CF._K2P.get((s,f"{N}|{q['num']}|{ans[0]}")) if CF.qkind(q)=='stmt' else CF._K2P.get((s,f"{N}|{q['num']}|0"))
            if pid: Q.append((N,pid))
    g=collections.defaultdict(lambda:[0,0])
    for ti in range(K+3,len(exams)-K):          # 基準の回T：前に K+3 回以上、後ろに K 回
        T=exams[ti]; upto=set(exams[:ti+1]); fresh=set(exams[ti+1-K:ti+1]); fut=set(exams[ti+1:ti+1+K])
        for N,pid in Q:
            if N not in upto: continue
            es=pt[(s,pid)]&upto; c=len(es)
            rec=bool(pt[(s,pid)]&fut)
            if c==1: key='初見・直近%d回以内'%K if N in fresh else '初見・それより前'
            elif c==2: key='既出1回（通算2回）'
            else: continue
            g[key][0]+=1; g[key][1]+=rec
    out.append((s,{k:(v[0],v[1]/v[0] if v[0] else 0) for k,v in g.items()}))
print('| 科目 | 初見・直近の回（新しい案では C） | 初見・それより前（D のまま） | 参考：既出1回（今の C） |\n|---|---|---|---|')
for s,g in out:
    f=lambda k: f"{g[k][1]:.0%}（{g[k][0]}件）" if k in g else '－'
    K=H[s]
    print(f"| {NAME[s]} | {f('初見・直近%d回以内'%K)} | {f('初見・それより前')} | {f('既出1回（通算2回）')} |")
