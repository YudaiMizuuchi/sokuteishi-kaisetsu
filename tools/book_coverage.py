#!/usr/bin/env python3
"""参考書の章と過去問を紐づけ、「その章を習得した読者が、過去問の何％を得点できるか」を出す（サイトの表示にも区分の判定にも使わない）。
使い方:
  python3 tools/book_coverage.py --init     対応表の土台 data/master/book_map.yaml を作る（既にあれば、上書きせず /tmp/book_map_candidates.yaml に候補だけ出す）
  python3 tools/book_coverage.py            カバー率を計算し、/tmp/book_coverage.md に書く
  python3 tools/book_coverage.py --check    検算（全部入りの対応表で、正答が既出の割合と一致すること／空の対応表で0％になること）
  オプション: --r 0.5   テーマ・数値表の章が、初見の事実（論点）を、どれだけ拾えるか（0〜1、既定0。原文で網羅する前提の上限は1）

章の種類（kind）：
  原理   紐づく原理（principles）から導ける論点は、初見でも得点できる（紐づけは、正答を見て決めたものを含むので、やや楽観的）
  テーマ・数値表  章の論点（points／themes）は、過去に出ていれば得点できる。初見の論点は、r の割合で得点できる（原文・表で網羅する前提の、上限の目安）
  論点   章の論点（points）は、過去に出ていれば得点できる
  物質表  章の物質（substances）の表で解ける問題は、得点できる
  解法   章の形式（forms）の問題（計算・穴埋め・組合せ）は、過去に同じ形式が出ていれば得点できる
採点は backtest.py と同じ考え方（その回より前の出題だけで数える）。正答が収録済み→1点、おとりを全部除外できる→1点、2択まで絞れる→0.5点、改変型（正しい記述が収録済み）→0.5点。
"""
import sys,io,re,collections,difflib,yaml,os
sys.path.insert(0,'tools')
_so=sys.stdout; sys.stdout=io.StringIO()
import compute_freq as CF
import substances as SB
sys.stdout=_so
MAP='data/master/book_map.yaml'
ELIM_MIN=3   # おとりとして『知っている』とみなす条件：原理の章に入っているか、その回より前に3回以上出ていること（サイトの判定の「頻出のおとり」に合わせた）
NAME={'ippan':'一般','hourei':'関係法令','design':'デザイン','bunseki':'分析','yuki':'有機溶剤','tokka':'特定化学物質','kinzoku':'金属類','funjin':'鉱物性粉じん'}
FORMS=['計算問題','穴埋め・組合せの問題']
FORMKEY={'calc':'計算問題','combo':'穴埋め・組合せの問題','short':'選択肢が物質名などの問題'}
# 一般の出題枠（docs/analysis/ippan_newtrend_inventory_W.md と同じ）
IPPAN_FRAMES=[
 ('リスクアセスメント指針','危険性又は有害性等の調査等に関する指針|リスクの見積り|リスクアセスメント'),
 ('GHS・絵表示','世界調和システム|GHS|絵表示'),
 ('毒性・健康影響の指標','健康影響及びその管理指標|許容濃度|NOAEL|濃度基準値'),
 ('吸収・代謝・生物学的モニタリング','吸収、代謝|生物学的'),
 ('化学物質の性質・水溶液','性質及び挙動|水溶液|性状及び挙動|物性'),
 ('化学物質による健康障害（物質別）','健康障害'),
 ('粉じん・じん肺','粉じん'),('有機溶剤','有機溶剤'),
 ('温熱（熱中症・WBGT）・寒冷','熱中症|暑熱|WBGT|寒冷|温熱|低体温'),
 ('振動障害','振動'),('騒音','騒音|音及び'),('酸素欠乏・硫化水素','酸素欠乏|硫化水素'),
 ('電磁波','電磁波|紫外線|赤外線|レーザー'),('電離放射線','電離放射線|放射線'),
 ('換気装置（局所排気・プッシュプル）','局所排気|換気装置|プッシュプル'),
 ('保護具','保護具|防じんマスク|防毒マスク|手袋|呼吸用')]
def ippan_frame(stem):
    for n,k in IPPAN_FRAMES:
        if re.search(k,stem): return n
    return 'その他'

def live_points():
    pt=yaml.safe_load(open('data/master/points.yaml',encoding='utf-8'))['points']
    return [p for p in pt if not p.get('merged_into')]

# ---------------------------------------------------------------- 初期版
def init():
    pts=live_points(); ch=[]; n=0
    def add(**k):
        nonlocal n; n+=1; k.setdefault('status','draft'); ch.append(k)
    for p in CF._PRD['principles']:
        if p['points']: add(id=f"bk-{p['id'][3:]}",subject=p['subject'],title=p['name'],kind='原理',principles=[p['id']])
    for th in sorted({p['theme'] for p in pts if p['subject']=='hourei' and p.get('theme')}):
        add(id=f"bk-hourei-th{len([c for c in ch if c['subject']=='hourei' and c['kind']=='数値表'])+1:02d}",subject='hourei',title=th,kind='数値表',themes=[th])
    # 一般：出題の枠ごと（枠の問題に出た全選択肢の論点）
    byframe=collections.defaultdict(set)
    for e,(f,d) in CF.docs['ippan'].items():
        for q in d['questions']:
            if not q.get('choices'): continue
            fr=ippan_frame(str(q['stem']))
            for i in range(1,len(q['choices'])+1):
                pid=CF._K2P.get(('ippan',f"{e}|{q['num']}|{i}"))
                if pid: byframe[fr].add(pid)
    for k,(fr,_) in enumerate(IPPAN_FRAMES+[('その他','')],1):
        if byframe.get(fr): add(id=f'bk-ippan-fr{k:02d}',subject='ippan',title=fr,kind='テーマ',points=sorted(byframe[fr]))
    ver=yaml.safe_load(open('data/master/substances/verified.yaml',encoding='utf-8'))['verified']
    for s in ('tokka','kinzoku'):
        doc=yaml.safe_load(open(f'data/master/substances/{s}.yaml',encoding='utf-8'))
        for sb in doc['substances']:
            if sb['code'] in (ver.get(s) or {}): add(id=f"bk-{s}-sb{sb['code']}",subject=s,title=sb['name'],kind='物質表',substances=[f"sb-{s}-{sb['code']}"])
    for s in NAME: add(id=f'bk-{s}-forms',subject=s,title='計算・穴埋め・組合せ問題の解き方',kind='解法',forms=FORMS)
    return ch

def write_init():
    ch=init()
    if os.path.exists(MAP):
        open('/tmp/book_map_candidates.yaml','w',encoding='utf-8').write(yaml.safe_dump({'chapters':ch},allow_unicode=True,sort_keys=False,width=1000))
        print('既に',MAP,'があるので、上書きしません。候補を /tmp/book_map_candidates.yaml に出しました（',len(ch),'章）'); return
    open(MAP,'w',encoding='utf-8').write('# 参考書の章と、過去問の判定の材料との対応表（tools/book_coverage.py）。サイトの表示・区分の判定には使わない。\n'+yaml.safe_dump({'chapters':ch},allow_unicode=True,sort_keys=False,width=1000))
    c=collections.Counter((x['subject'],x['kind']) for x in ch)
    print(MAP,'を作りました：',len(ch),'章'); 
    for k,v in sorted(c.items()): print(' ',NAME[k[0]],k[1],v)
    # まとめ候補：論点が1つ、または出題が3回以下の小さな原理の章
    cand=[]
    for x in ch:
        if x['kind']!='原理': continue
        p=[q for q in CF._PRD['principles'] if q['id']==x['principles'][0]][0]
        if len(p['points'])<=1 or len(CF.PR_EXAMS[p['id']])<=3: cand.append(dict(id=x['id'],subject=x['subject'],title=x['title'],論点数=len(p['points']),出題回数=len(CF.PR_EXAMS[p['id']])))
    open('/tmp/book_map_merge_candidates.yaml','w',encoding='utf-8').write(yaml.safe_dump({'まとめ候補（小さな原理の章）':cand},allow_unicode=True,sort_keys=False,width=1000))
    print('まとめ候補（小さな原理）',len(cand),'章 → /tmp/book_map_merge_candidates.yaml')

# ---------------------------------------------------------------- 採点の素データ
def form_seen(subj,e,q,k,past):
    key=CF.norm(q['stem'])[:70] if k=='calc' else CF.norm(q['stem'])[:60]
    for e2 in past:
        for q2 in CF.docs[subj][e2][1]['questions']:
            if CF.qkind(q2)!=k or not q2.get('choices'): continue
            key2=CF.norm(q2['stem'])[:70] if k=='calc' else CF.norm(q2['stem'])[:60]
            if difflib.SequenceMatcher(None,key,key2).ratio()>=(CF.THR_CALC if k=='calc' else CF.THR_Q): return True
    return False

def collect_problems():
    P=[]
    for subj,exams in CF.docs.items():
        el=sorted(exams)
        # 近い記述（正誤が逆、類似度0.40以上、ほかの回）の索引
        S=[]
        for e in el:
            for q in exams[e][1]['questions']:
                a=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
                if q.get('status')!='published' or not q.get('choices') or q.get('columns') or not a or not isinstance(a[0],int) or CF.qkind(q)!='stmt': continue
                neg=bool(CF.NEG.search(q['stem']))
                for i,c in enumerate(q['choices'],1): S.append((e,q['num'],i,(i not in a) if neg else (i in a),CF.grams(CF.norm(c))))
        inv=collections.defaultdict(list)
        for k,s in enumerate(S):
            for g in s[4]: inv[g].append(k)
        Sx={(s[0],s[1],s[2]):s for s in S}
        for ni,N in enumerate(el):
            if ni<4: continue
            past=el[:ni]; f,d=exams[N]
            for q in d['questions']:
                if q.get('status')!='published' or not q.get('choices'): continue
                ans=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
                if not ans or ans[0]=='all' or not isinstance(ans[0],int): continue
                k=CF.qkind(q); n=len(q['choices']); a=ans[0]-1
                rec=dict(subj=subj,exam=N,num=q['num'],kind=k,n=n,a=a,idx=ni,past=past)
                txt=str(q['stem'])+' '+str(q['choices'][a])
                tt=SB.table_type(subj,txt) if subj in ('tokka','kinzoku') else None
                rec['sb']=f'sb-{subj}-{tt[0]}' if (tt and tt[1]) else None
                if k=='stmt':
                    rec['pids']=[CF._K2P.get((subj,f"{N}|{q['num']}|{i}")) for i in range(1,n+1)]
                    s0=Sx.get((N,q['num'],a+1)); near=[]
                    if s0:
                        cnt=collections.Counter()
                        for g in s0[4]:
                            for kk in inv[g]: cnt[kk]+=1
                        for kk in cnt:
                            t=S[kk]
                            if t[0]>=N or t[3]==s0[3]: continue
                            if len(s0[4]&t[4])/len(s0[4]|t[4])>=CF.THR_NEAR:
                                pid=CF._K2P.get((subj,f"{t[0]}|{t[1]}|{t[2]}"))
                                if pid: near.append((t[0],pid))
                    rec['near']=near
                else:
                    rec['form']=FORMKEY[k]; rec['seen']=form_seen(subj,N,q,k,past); rec['qp']=CF._K2P.get((subj,f"{N}|{q['num']}|0"))
                P.append(rec)
    return P

# ---------------------------------------------------------------- 対応表の読み込み・採点
QPC_PATH='data/master/qpoint_chapters.yaml'
def load_qpc():
    """tools/assign_qpoints.py の結果：章ID → 足す論点（問題論点を含む）"""
    return (yaml.safe_load(open(QPC_PATH,encoding='utf-8')) or {}) if os.path.exists(QPC_PATH) else {}
def load_map(path=MAP,raw=False):
    ch=yaml.safe_load(open(path,encoding='utf-8'))['chapters'] if os.path.exists(path) else []
    if raw: return ch
    qpc=load_qpc()   # 章の論点（points）に、割り当て表の論点を足す（book_map.yaml 自体は書き換えない）
    for c in ch:
        if c['id'] in qpc: c['points']=sorted(set(c.get('points') or [])|set(qpc[c['id']]))
    return ch

class Scorer:
    def __init__(self,problems,pts):
        self.P=problems; self.theme_pts=collections.defaultdict(set)
        for p in pts:
            if p.get('theme'): self.theme_pts[(p['subject'],p['theme'])].add(p['id'])
        self.prin={p['id']:p for p in CF._PRD['principles']}
    def build(self,chapters,use_qpc=True):
        mode={}; sbs=set(); forms=set()   # mode: (科目,論点id)->'full'|'theme'|'seen'
        rank={'full':3,'theme':2,'seen':1}
        def put(k,m):
            if rank[m]>rank.get(mode.get(k),0): mode[k]=m
        for c in chapters:
            s=c['subject']; kind=c['kind']
            for pr in c.get('principles') or []:
                for x in self.prin[pr]['points']: put((s,x),'full' if kind=='原理' else 'seen')
            for x in c.get('points') or []: put((s,x),'theme' if kind in('テーマ','数値表') else 'seen')
            for th in c.get('themes') or []:
                for x in self.theme_pts.get((s,th),()): put((s,x),'theme')
            for b in c.get('substances') or []: sbs.add(b)
            for f in c.get('forms') or []: forms.add((s,f))
        return mode,sbs,forms
    def score(self,rec,cov,r,elim=True,near=True):
        mode,sbs,forms=cov; s=rec['subj']; N=rec['exam']
        if rec['kind']!='stmt':
            if rec['sb'] and rec['sb'] in sbs: return 1.0,'subst'
            if (s,rec['form']) in forms and rec['seen']: return 1.0,'form'
            qp=rec.get('qp'); m=mode.get((s,qp)) if qp else None   # 問題論点（同じ問題が、章に収録されている）
            if m:
                seen=any(e<N for e in CF._PEX[(s,qp)])
                if m=='full' or seen: return 1.0,'qpoint'
            return 0.0,'none'
        def known(pid):
            if not pid: return False
            m=mode.get((s,pid))
            if m=='full': return True
            if m is None: return False
            return sum(1 for e in CF._PEX[(s,pid)] if e<N)>=ELIM_MIN
        def cv(pid):
            m=mode.get((s,pid)) if pid else None
            if m=='full': return 1.0
            seen=any(e<N for e in CF._PEX[(s,pid)]) if pid else False
            if m=='theme': return 1.0 if seen else r
            if m=='seen': return 1.0 if seen else 0.0
            return 0.0
        if rec['sb'] and rec['sb'] in sbs: return 1.0,'subst'
        pa=rec['pids'][rec['a']]; c=cv(pa)
        if c>=1: return 1.0,'point'
        best=(c,'theme') if c>0 else (0.0,'none')
        if elim:
            k=sum(1 for i,p in enumerate(rec['pids']) if i!=rec['a'] and known(p)); left=rec['n']-k
            if left==1: return 1.0,'elim'
            if left==2 and best[0]<0.5: best=(0.5,'elim2')
        if near and best[0]<0.5 and any(e<N and known(p) for e,p in rec['near']): best=(0.5,'near')
        return best
    def coverage(self,chapters,r,elim=True,near=True,subj=None):
        cov=self.build(chapters); out=collections.defaultdict(list); why=collections.Counter()
        for rec in self.P:
            if subj and rec['subj']!=subj: continue
            sc,w=self.score(rec,cov,r,elim,near); out[rec['subj']].append((rec['exam'],rec['num'],sc)); why[(rec['subj'],w)]+=1
        return out,why

def mean(v): return sum(x[2] for x in v)/len(v) if v else 0.0
def windows(v):
    ex=sorted({x[0] for x in v}); last2=set(ex[-2:])
    return mean(v),mean([x for x in v if x[0]>='2023-08']),mean([x for x in v if x[0] in last2])

# ---------------------------------------------------------------- 検算
def check(P,pts):
    sc=Scorer(P,pts)
    empty=sc.coverage([],0.0,False,False)[0]
    z=max(mean(v) for v in empty.values())
    # 全論点を入れた『論点』章：正答の論点が既出の割合と一致（おとり除外・改変型は無効にして比較）
    allc=[dict(id='all',subject=s,title='all',kind='論点',points=sorted(p['id'] for p in pts if p['subject']==s),status='draft') for s in NAME]
    full=sc.coverage(allc,0.0,False,False)[0]; ok=True
    for s,v in full.items():
        stm=[r for r in P if r['subj']==s and r['kind']=='stmt']
        direct=sum(1 for r in stm if r['pids'][r['a']] and any(e<r['exam'] for e in CF._PEX[(s,r['pids'][r['a']])]))
        got=sum(x[2] for x,r in zip(v,[r for r in P if r['subj']==s]) if r['kind']=='stmt')
        flag='OK' if abs(direct-got)<1e-9 else 'NG'; ok&=flag=='OK'
        print(f'{NAME[s]}: 正答の論点が既出 {direct}問 ／ 全論点を収録した対応表の得点 {got:.1f}問 → {flag}')
    print('空の対応表の最大カバー率（0であること）：',f'{z:.1%}','OK' if z==0 else 'NG')
    return ok and z==0

# ---------------------------------------------------------------- 報告
def report(P,pts,r_main):
    chapters=load_map(); sc=Scorer(P,pts)
    L=['# 参考書のカバー率（対応表 data/master/book_map.yaml）','',f'章の数：{len(chapters)}（{"、".join(f"{NAME[s]}{n}" for s,n in sorted(collections.Counter(c["subject"] for c in chapters).items(),key=lambda x:list(NAME).index(x[0])))}）　テーマ・数値表の章が初見の論点を拾える割合 r＝{r_main}','',
       '採点：正答が収録済み→1点、おとりを全部除外→1点、2択→0.5点、改変型→0.5点。その回より前の出題だけで数える（読者の立場）。原理の章は、正答を見て決めた紐づけを含むので、やや楽観的。','']
    bt={}
    if os.path.exists('/tmp/backtest.md'):
        t=open('/tmp/backtest.md',encoding='utf-8').read()
        if '## 最新2回' in t:
            for l in t[t.index('## 最新2回'):].split('\n'):
                m=re.match(r'\| (\S+) \| \S+ \| \S+ \| (\d+)% \|',l)
                if m: bt[m.group(1)]=int(m.group(2))
    L+=['## 1. 科目別のカバー率','','| 科目 | 章 | 全期間 | 令和5年度以降 | 最新2回 | r=0（過去に出た論点だけ） | r=1（上限） | 全論点を収録（過去に出た論点を全部覚えた場合） | サイトの期待得点率（最新2回） |','|---|---|---|---|---|---|---|---|---|']
    allc=chapters+[dict(id='all-'+x,subject=x,title='all',kind='論点',points=sorted(p['id'] for p in pts if p['subject']==x),status='draft') for x in NAME]
    allv,_=sc.coverage(allc,0.0)
    main,why=sc.coverage(chapters,r_main); lo,_=sc.coverage(chapters,0.0); hi,_=sc.coverage(chapters,1.0)
    for s in NAME:
        if s not in main: continue
        a,b,c=windows(main[s]); l=windows(lo[s])[1]; h=windows(hi[s])[1]
        L.append(f"| {NAME[s]} | {sum(1 for x in chapters if x['subject']==s)} | {a:.0%} | {b:.0%} | {c:.0%} | {l:.0%} | {h:.0%} | {windows(allv[s])[1]:.0%} | {str(bt.get(NAME[s],'－'))+'％' if NAME[s] in bt else '－'} |")
    L+=['','（r=0・r=1の列は、令和5年度以降の値）','']
    # 章別の限界効果
    L+=['## 2. 章別の限界効果（その章だけを外したときの、令和5年度以降のカバー率の落ち幅）','','| 順位 | 科目 | 章 | 種類 | 状態 | 落ち幅（ポイント） | 決め手の問題数（令和5年度以降） |','|---|---|---|---|---|---|---|']
    base={s:windows(main[s])[1] for s in main}; rows=[]
    for c in chapters:
        s=c['subject']; rest=[x for x in chapters if x is not c]
        v,_=sc.coverage(rest,r_main,subj=s); w=windows(v[s])[1]
        dec=sum(1 for (e1,n1,x0),(e2,n2,x1) in zip(sorted(main[s]),sorted(v[s])) if e1>='2023-08' and x0-x1>=0.5)
        rows.append((base[s]-w,s,c['title'],c['kind'],c.get('status','draft'),dec))
    rows.sort(key=lambda x:-x[0])
    for i,(d,s,t,k,st,dec) in enumerate(rows[:25],1): L.append(f'| {i} | {NAME[s]} | {t} | {k} | {st} | {d*100:.1f} | {dec} |')
    L+=['','（落ち幅が0の章は、ほかの章と、正答が重なっている章）','','科目別の上位5章：','']
    for s_ in NAME:
        top=[x for x in rows if x[1]==s_][:5]
        L.append(f"- {NAME[s_]}：" + '、'.join(f'{t}（{d*100:.1f}）' for d,_,t,k,st,dec in top))
    L.append('')
    # 未収録の論点
    covered=set(); mode,_,_=sc.build(chapters); covered={k for k in mode}
    L+=['## 3. どの章にも入っていない論点（出題回数の多い順、科目別の上位15）','']
    for s in NAME:
        un=[p for p in pts if p['subject']==s and (s,p['id']) not in covered]
        un.sort(key=lambda p:-len({k.split('|')[0] for k in p['members']}))
        L+=[f'### {NAME[s]}（未収録 {len(un)}／{sum(1 for p in pts if p["subject"]==s)}論点）','']
        for p in un[:15]: L.append(f"- {p['id'][-9:]}（{len({k.split('|')[0] for k in p['members']})}回）{p['name'][:70]}")
        L.append('')
    # 一般：令和5年度以降のD・C
    L+=['## 4. 一般：令和5年度以降の初見・既出1回の問題（サイトの判定がC・D）を、章で拾えた数','']
    import json
    rows_bt=[]
    if os.path.exists('/tmp/rows_v.json'): rows_bt=[x for x in json.load(open('/tmp/rows_v.json')) if x['subj']=='ippan' and x['exam']>='2023-08' and x['level'] in 'CD']
    if rows_bt:
        key={(x[0],str(x[1])):x[2] for x in main['ippan']}; key1={(x[0],str(x[1])):x[2] for x in hi['ippan']}; key0={(x[0],str(x[1])):x[2] for x in lo['ippan']}
        n=len(rows_bt); g=lambda d,t=1:sum(1 for x in rows_bt if d.get((x['exam'],str(x['num'])),0)>=t)
        L+=[f'対象 {n}問。章で拾えた（0.5点以上）：r=0 → {g(key0,0.5)}問、r={r_main} → {g(key,0.5)}問、r=1（上限） → {g(key1,0.5)}問。1点（確実）：r=0 → {g(key0)}問、r={r_main} → {g(key)}問、r=1 → {g(key1)}問。','']
    else: L+=['（/tmp/rows_v.json が無いので、省略）','']
    if os.path.exists(CHANGES): L+=['']+curve(P,pts,r_main)
    open('/tmp/book_coverage.md','w',encoding='utf-8').write('\n'.join(L))
    print('\n'.join(L[:30]))


# ---------------------------------------------------------------- 検証・読み替え・累積
CHANGES='data/master/book_map_changes.yaml'; ALIASES='data/master/book_id_aliases.yaml'
def build_aliases():
    """統合で消えた章ID → 残った章ID の読み替え表（復習ボタン・目次・旧URLの転送に使う）"""
    chg=yaml.safe_load(open(CHANGES,encoding='utf-8'))
    al={a:m['survivor'] for m in chg['merged_principle_chapters'] for a in m['absorbed_ids']}
    open(ALIASES,'w',encoding='utf-8').write('# 統合で消えた参考書の章ID → 残った章ID（tools/book_coverage.py --aliases）\n'+yaml.safe_dump({'aliases':al},allow_unicode=True,sort_keys=True,width=1000))
    print(ALIASES,'を作りました：',len(al),'件')
def validate():
    ch=load_map(); pts={p['id'] for p in yaml.safe_load(open('data/master/points.yaml',encoding='utf-8'))['points']}
    live={p['id'] for p in live_points()}; prin={p['id'] for p in CF._PRD['principles']}
    parts={p['id'] for p in yaml.safe_load(open('data/master/book.yaml',encoding='utf-8'))['parts']}
    th={p.get('theme') for p in live_points() if p.get('theme')}; err=[]
    ids=[c['id'] for c in ch]
    for k,v in collections.Counter(ids).items():
        if v>1: err.append(f'章IDの重複 {k}')
    for c in ch:
        if c.get('part') not in parts: err.append(f"{c['id']}: part {c.get('part')} が book.yaml の parts に無い")
        for x in c.get('principles') or []:
            if x not in prin: err.append(f"{c['id']}: 原理 {x} が無い")
        for x in c.get('points') or []:
            if x not in live: err.append(f"{c['id']}: 論点 {x} が無い、または統合済み")
        for x in c.get('themes') or []:
            if x not in th: err.append(f"{c['id']}: theme {x} が無い")
        if c['kind'] not in ('原理','テーマ','数値表','論点','物質表','解法'): err.append(f"{c['id']}: kind {c['kind']}")
    if os.path.exists(CHANGES):
        wo=[x['id'] for x in yaml.safe_load(open(CHANGES,encoding='utf-8'))['writing_order']]
        for i in set(ids)-set(wo): err.append(f'執筆順に無い章 {i}')
        for i in set(wo)-set(ids): err.append(f'執筆順にあるが対応表に無い章 {i}')
    if os.path.exists(ALIASES):
        al=yaml.safe_load(open(ALIASES,encoding='utf-8'))['aliases']
        for a,sv in al.items():
            if sv not in ids: err.append(f'読み替え先が無い {a} → {sv}')
            if a in ids: err.append(f'読み替え元が、まだ対応表にある {a}')
    print(f'章 {len(ch)}、エラー {len(err)}'); [print(' ',e) for e in err[:20]]
    return not err
def curve(P,pts,r):
    """執筆順に書いたとき、章がN本そろった時点のカバー率（令和5年度以降）。status に関係なく、順序だけで数える"""
    ch=load_map(); order=[x['id'] for x in yaml.safe_load(open(CHANGES,encoding='utf-8'))['writing_order']]; byid={c['id']:c for c in ch}
    sc=Scorer(P,pts); pts_=[16,30,60,100,150,len(order)]; L=['## 5. 執筆順に書いたときの、累積カバー率（令和5年度以降）','','| 書いた章の数 | '+' | '.join(NAME[s] for s in NAME)+' |','|---|'+'---|'*len(NAME)]
    for n in pts_:
        cov,_=sc.coverage([byid[i] for i in order[:n]],r); L.append(f'| {n} | '+' | '.join(f"{windows(cov[s])[1]:.0%}" if s in cov else '－' for s in NAME)+' |')
    return L

if __name__=='__main__':
    args=sys.argv[1:]
    if '--init' in args: write_init(); sys.exit(0)
    if '--aliases' in args: build_aliases(); sys.exit(0)
    if '--validate' in args: sys.exit(0 if validate() else 1)
    r=float(args[args.index('--r')+1]) if '--r' in args else 0.0
    pts=live_points(); P=collect_problems()
    if '--check' in args: sys.exit(0 if check(P,pts) else 1)
    report(P,pts,r)
