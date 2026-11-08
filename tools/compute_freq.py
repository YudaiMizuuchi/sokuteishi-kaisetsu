#!/usr/bin/env python3
"""選択肢ごと・問題ごとの出題頻度と、問題の区分（S・A・B・C）を計算して、問題データの freq に書き込む。
使い方: python3 tools/compute_freq.py        （試算：件数だけ表示）
        python3 tools/compute_freq.py apply  （data/exams/*/*.yaml の各問に freq を書き込む）
新しい回を追加したら、先に python3 tools/build_points.py --update（論点マスタの更新）を実行する。

区分の判定に使う入力は、次の3つだけ。
 1. 論点の出題回数：論点マスタ（data/master/points.yaml）の論点が、その科目で、何回の回に出たか（選択肢のどれかとして）
 2. パターンの紐づけ：その問題に紐づく、ひっかけパターン（共通科目：book.yaml の lw-*・ds-* など）の出題回数
 3. 問題単位の回数：穴埋め・組合せ・計算問題などは、同じ形式の問題が出た回数
「同じ記述の回数」（文字の類似度0.86以上）は、表示用の参考値で、判定には使わない。"""
import yaml,glob,re,sys,collections,difflib
sys.path.insert(0,'tools')
import points_master as PM
import build_points as BP
import substances as SB
APPLY=len(sys.argv)>1 and sys.argv[1]=='apply'
THR_STMT=0.86; THR_CALC=0.62; THR_Q=0.90
# 改変型：正誤が逆で、文字の類似度（3-gramのJaccard）が0.40以上の記述が、ほかの回にある（過去に正しい記述として出た事実の、数値や範囲を変えたもの）。
# 令和5年度以降のDの正答のうち、関係法令では約4分の1（39問中10問）が、これに当たる。一般・デザインでは数問、分析ではほぼ無い。
THR_NEAR=0.40; NEAR_SUBJ={'hourei','ippan','design'}
NEG=re.compile(r'誤っているもの|不適当|不適切|適切でない|適当でない|正しくないもの|誤っている|あてはまらない|当てはまらない|該当しない')
def norm(s):
    s=re.sub(r'<[^>]+>','',str(s)); s=re.sub(r'\$[^$]*\$','',s)
    return re.sub(r'[\s　、。，．・「」『』（）()\[\]：:,.\-－]','',s)
MARKS_Q=re.compile(r'[Ⓐ-Ⓩ㋐-㋾㊀-㊉①-⑩]')
NEGW_Q=re.compile(r'(誤って|間違って)いる|(不適切|不適当|適切でない|適当でない)|正しくない|(適切|適当|正しい)')
TEMPLATE_Q=re.compile(r'組合せ|のうち|次の|として|どれか|ものは|入る|に用い|について|関する|記述')
THR_COMBO=0.60
def qbody(stem):
    """穴埋め・組合せの問題の『中身』：記号（Ⓐ・㋑）、「正しい／誤っている」、「ただし…」、定型の言い回しを除いた問題文"""
    t=re.sub(r'\s+','',str(stem)); t=MARKS_Q.sub('',t); t=re.sub(r'[［\[]\s*[］\]]','',t)
    t=NEGW_Q.sub('〇',t); t=re.sub(r'ただし[^。]*。','',t)
    t=TEMPLATE_Q.sub('',t)
    return norm(t)[:90]
def qkey(q,k,atxt=''):
    """問題単位の問題（計算・穴埋め・組合せ・物質名を選ぶ問題）が、『同じ問題』かどうかを決めるキー。
    計算：問題文の先頭70字（正答は数値が変わるので使わない）、穴埋め・組合せ：問題の中身（正答は使わない＝語句や正誤が変わっても同じテーマ）、物質名を選ぶ：問題文の先頭60字＋正答"""
    if k=='calc': return norm(q['stem'])[:70]
    if k=='combo': return qbody(q['stem'])
    return norm(q['stem'])[:60]+'|'+atxt
def grams(t): return {t[i:i+3] for i in range(max(1,len(t)-2))}

# ランクの境目：科目ごと。頻度（回数）が、S・A・B の各ランクに入る下限（これ未満はC）。
# 目標の割合（科目内）：S約30％・A約25％・B約20％（C＋Dは残り約25％）。2026年11月5日に、S15／A25／B30から変更。tools/fit_thresholds.py で、最終の区分（消去法を含む）の分布が目標に近くなるように決めた（2026年11月3日）。論点マスタが大きく変わったら、もう一度実行する。
THRESHOLDS={
 'ippan':(11,8,6), 'hourei':(17,13,9), 'design':(22,10,8), 'bunseki':(11,10,8),
 'yuki':(6,4,3), 'tokka':(5,4,3), 'kinzoku':(6,4,3), 'funjin':(8,5,3),   # 選択科目のBの下限は3回（C＝通算2回＝過去に1回だけ既出）。2026年11月5日、目標をS30／A25／B20に変更（運営者の了承あり）し、fit_thresholds.py で再探索した。特定化学物質・金属類は、回数が少なく、B下限が3回に固定なので、A＜Bになる
}
# 消去法で「除外できるおとり」とみなす論点の水準（この水準以上）。選択科目は、Cが少なくなりすぎないよう、厳しくできる。
ELIM_KNOWN={'hourei':'A','yuki':'A','kinzoku':'A','funjin':'A'}   # 未指定は 'B'（2026年11月5日の再探索で、一般・デザインを B に、関係法令・有機溶剤・金属類・鉱物性粉じんを A に）
# 直近トレンド：直近K回（共通6回・選択3回）のうち、TREND_MIN回以上に出た論点は、頻度が低くても、少なくともB（押さえるべき事実）にする
TREND_K={'ippan':6,'hourei':6,'design':6,'bunseki':6,'yuki':3,'tokka':3,'kinzoku':3,'funjin':3}
# トレンド（直近に集中）：通算2回以上の論点で、通算回数の半分以上が直近K回にあるとき、水準を1段階上げる（A→S、B→A）。通算1回は対象外
CUR=None   # 計算中の科目
ORDER={'S':0,'A':1,'B':2,'C':3,'D':4}
def rank_of(m,D,subj=None):
    t=THRESHOLDS.get(subj or CUR) or ((10,5,3) if D>=20 else (5,3,2))
    return 'S' if m>=t[0] else 'A' if m>=t[1] else 'B' if m>=t[2] else 'C'
def best(*rs): return min((r for r in rs if r),key=lambda r:ORDER[r],default='C')

def judge(fr,answers,prank=None):
    """問題の区分：S＝得点必須（最優先）、A＝得点必須、B＝何とか得点したい、C＝余裕があれば得点（既出だが1回だけ）、D＝失点しても仕方がない（完全な初見）。
    CとDの境目だけは絶対（既出か初見か）。S・A・Bの境目は科目ごとの相対評価。
    選択肢の問題：正答の頻度＝『正答の選択肢の論点の回数』と『紐づくパターンの水準』の、高いほう。
      S・A：正答の頻度がS・Aの境目以上。B：正答の頻度がB、または、頻出のおとり（論点の回数がB水準以上）を除いて、残りが1つ（全部除外）か2つ（2択）。C：上のどれにも当てはまらない。
    問題単位の集計：問題の出題回数とパターンの水準の、高いほう。"""
    D=fr['denom']
    if fr['kind']=='question':
        rq=rank_of(fr['count'],D); rprin=pr_rank(fr.get('prcount',0),CUR) if fr.get('prid') else 'C'
        r=best(rq,prank,rprin)
        why=('pr_' if (rprin==r and rq!=r and prank!=r) else 'pat_' if (prank==r and rq!=r) else 'q_')   # 原理が決め手／パターンが決め手／問題の出題回数が決め手
        if r in 'SA': return r,(why+r if why!='q_' else 'q_hi'),None
        if r=='B': return 'B',(why+'B' if why!='q_' else 'q_b'),None
        if fr.get('subst_id'): return 'B','subst',None
        seen_min=2 if fr.get('self_counted',True) else 1
        return ('C','q_seen',None) if fr['count']>=seen_min else ('D','q_new',None)
    a=answers[0]-1; n=len(fr['counts'])
    eff=[fr['pcounts'][i] or fr['counts'][i] for i in range(n)]   # 論点の回数（論点がない選択肢は、同じ記述の回数）
    prc=fr.get('prcounts') or [0]*n
    rpoint=rank_of(eff[a],D)
    rprin=pr_rank(prc[a],CUR)
    ra=best(rpoint,prank,rprin)
    tags=[]
    for i in range(n):
        if i==a:
            tags.append('ans_pr' if (ORDER[rprin]<ORDER[rpoint] and ORDER[rprin]<=ORDER.get(prank or 'C')) else 'ans_pat' if (prank and ORDER[prank]<ORDER[rpoint]) else ('ans_hi' if ra in 'SA' else 'ans_b' if ra=='B' else 'ans_new'))
        else:
            kn=ORDER[ELIM_KNOWN.get(CUR,'B')]
            tags.append('odo' if (ORDER[rank_of(eff[i],D)]<=kn or ORDER[pr_rank(prc[i],CUR)]<=kn) else ('new' if eff[i]<=1 else ''))
    def why(base):
        if prank==ra and rpoint!=ra: return 'pat_'+ra
        if rprin==ra and rpoint!=ra: return 'pr_'+ra
        if fr['pcounts'][a]: return 'pt_'+ra
        return base
    tr=fr.get('trend') or [0]*n
    def uplift(r):
        # 直近に集中している論点は、1段階上げる（定番Sはそのまま）
        if eff[a]>=2 and tr[a]*2>=eff[a] and r in 'AB': return {'A':'S','B':'A'}[r],True
        return r,False
    ra,trended=uplift(ra)
    if trended: tags[a]='ans_trend'
    if ra in 'SA': return ra,('trend_'+ra if trended else why('ans_hi')),tags
    if ra=='B': return 'B',why('ans_b'),tags
    k=sum(1 for i in range(n) if i!=a and tags[i]=='odo'); left=n-k
    if left==1: return 'B','elim_all',tags
    if left==2: return 'B','elim_two',tags
    if fr.get('subst_id'): tags[a]='ans_subst'; return 'B','subst',tags   # 物質別の暗記リスト（確認済み）の表で解ける
    seen_min=2 if fr.get('self_counted',True) else 1
    if eff[a]>=seen_min: tags[a]='ans_seen'; return 'C','seen',tags
    if CUR in NEAR_SUBJ and (fr.get('near') or [False]*n)[a]: tags[a]='ans_near'; return 'C','near',tags   # 改変型：過去に正しい記述として出た事実を、変えたもの
    return 'D','none',tags

# ひっかけパターン（data/master/book.yaml）：共通科目のパターンだけを、判定に使う（選択科目の sl-* は、論点に置き換わったので、使わない）
_BOOK=yaml.safe_load(open('data/master/book.yaml',encoding='utf-8'))
TRAPS={t['id']:t for t in _BOOK['traps'] if not t['id'].startswith('sl-')}
def best_pattern(q):
    c=[TRAPS[t] for t in (q.get('traps') or []) if t in TRAPS and 'other' not in t and 'その他' not in TRAPS[t]['name']]
    if not c: return None,None
    t=min(c,key=lambda x:ORDER[x['rank']])
    return rank_of(t['count'],0,t['subject']),t['id']

# 原理マスタ（data/master/principles.yaml）：原理に紐づく論点の、出題回の和集合＝原理の出題回数
import os
_PRD=yaml.safe_load(open('data/master/principles.yaml',encoding='utf-8')) if os.path.exists('data/master/principles.yaml') else {'principles':[]}
# 原理用の境目（科目ごと。原理は論点より広いので、論点とは別に決める）。python3 tools/fit_thresholds.py で決める
# 分析科目：S＝23回中12回以上（半数以上の回で問われた原理）、A＝8回以上、B＝5回以上（2026年11月3日、運営者の判断。Sが多く、Cが少なくなるのは、原理を熟知すべき科目の性格として、許容）
PR_THRESHOLDS={'ippan':(12,8,5),'design':(12,8,5),'bunseki':(12,8,5),'yuki':(10,7,3),'tokka':(8,4,3),'kinzoku':(10,4,3),'funjin':(12,4,3)}   # 一般・デザイン・分析は、23回中12／8／5回（2026年11月3日。2026年11月5日の再探索でも、分布が目標に近いので変えない）。有機溶剤・特定化学物質・金属類は、2026年11月5日に再探索（目標S30／A25／B20）
def pr_rank(m,subj):
    t=PR_THRESHOLDS.get(subj)
    if not t or not m: return 'C'
    return 'S' if m>=t[0] else 'A' if m>=t[1] else 'B' if m>=t[2] else 'C'

# 論点マスタ
_PM=PM.load(); _K2P=PM.resolve(_PM); _PNAME=PM.info(_PM)
_PEX=collections.defaultdict(set)    # (科目, 論点id) -> 回
for (_s,_k),_pid in _K2P.items(): _PEX[(_s,_pid)].add(_k.split('|')[0])
PR_BY_POINT=collections.defaultdict(list); PR_EXAMS={}; PRQ_EXAMS={}; PR_NAME={}
for _pr in _PRD['principles']:
    PR_NAME[_pr['id']]=_pr['name']
    PR_EXAMS[_pr['id']]=set().union(*[_PEX[(_pr['subject'],x)] for x in _pr['points'] if not x.startswith('qp-')]) if [x for x in _pr['points'] if not x.startswith('qp-')] else set()   # 記述の問題（選択肢の論点）：選択肢の論点だけで数える
    PRQ_EXAMS[_pr['id']]=set().union(*[_PEX[(_pr['subject'],x)] for x in _pr['points'] if x.startswith('qp-')]) if [x for x in _pr['points'] if x.startswith('qp-')] else set()   # 問題単位の問題（穴埋め・組合せ・計算・物質名）：問題論点だけで数える
    for x in _pr['points']: PR_BY_POINT[(_pr['subject'],x)].append(_pr['id'])

docs=collections.defaultdict(dict)   # subject -> exam -> (file, data)
for f in sorted(glob.glob('data/exams/*/*.yaml')):
    d=yaml.safe_load(open(f,encoding='utf-8'))
    if d.get('excluded'): continue
    docs[d['subject']][f.split('/')[2]]=(f,d)
FILL=re.compile(r'［\s*㋑|㋑から|㋑及び|㋑[〜～]|入る(語句|数値|式|用語|記号|文字|数)|組合せとして')
MARKS=re.compile(r'^[㋑-㋾\s、，,\-－―–／/]+$')
def qkind(q):
    """問題の形式：combo＝穴埋め・組合せ（見出し列がある、問題文に［㋑］などの穴がある、選択肢が㋑㋺の記号だけ）、calc＝計算問題（選択肢が数値だけ）、stmt＝記述の正誤、short＝物質名などの短い選択肢"""
    ch=q.get('choices') or []
    if q.get('columns'): return 'combo'
    if ch and (FILL.search(str(q['stem'])) or all(MARKS.match(str(c)) for c in ch)): return 'combo'
    if ch and all(re.search(r'\d',str(c)) and not re.search(r'[ぁ-んァ-ヶ一-龥]{3,}',str(c)) for c in ch): return 'calc'
    if ch and all(BP.stmt_like(c) for c in ch): return 'stmt'
    return 'short'

_NEAR_CACHE={}
def compute_near(subj):
    """(回, 問, 選択肢番号) -> 近い記述（正誤が逆）がある回のリスト"""
    if subj in _NEAR_CACHE: return _NEAR_CACHE[subj]
    S=[]
    for e,(f,d) in docs[subj].items():
        for q in d['questions']:
            if q.get('status')!='published' or not q.get('choices') or q.get('columns'): continue
            ans=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
            if not ans or ans[0]=='all' or not isinstance(ans[0],int): continue
            if qkind(q)!='stmt': continue
            neg=bool(NEG.search(q['stem']))
            for i,c in enumerate(q['choices'],1): S.append((e,q['num'],i,(i not in ans) if neg else (i in ans),grams(norm(c))))
    inv=collections.defaultdict(list)
    for i,s_ in enumerate(S):
        for x in s_[4]: inv[x].append(i)
    out={}
    for i,s_ in enumerate(S):
        cnt=collections.Counter()
        for x in s_[4]:
            for j in inv[x]: cnt[j]+=1
        exs=set()
        for j,c in cnt.items():
            t=S[j]
            if t[0]==s_[0] or t[3]==s_[3]: continue
            if len(s_[4]&t[4])/len(s_[4]|t[4])>=THR_NEAR: exs.add(t[0])
        out[(s_[0],s_[1],s_[2])]=sorted(exs)
    _NEAR_CACHE[subj]=out
    return out
def collect():
    """各問の、判定の材料（頻度の素データ）を集める。境目に依存しない。"""
    global CUR
    feats=[]
    for subj,exams in docs.items():
        CUR=subj; D=len(exams)
        S=[]; Qs=[]
        for e,(f,d) in exams.items():
            for q in d['questions']:
                if q.get('status')!='published' or not q.get('choices'): continue
                ans=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
                if ans and ans[0]=='all': continue
                neg=bool(NEG.search(q['stem'])); k=qkind(q)
                if k=='stmt':
                    for i,c in enumerate(q['choices'],1):
                        S.append((e,q['num'],i,(i not in ans) if neg else (i in ans),norm(c)))
                a0=ans[0]; atxt=norm(q['choices'][a0-1]) if isinstance(a0,int) and a0<=len(q['choices']) else ''
                Qs.append((e,q['num'],k,qkey(q,k,atxt)))
        G=[grams(s[4]) for s in S]; inv=collections.defaultdict(list)
        for i,g in enumerate(G):
            for x in g: inv[x].append(i)
        same={}
        for i,s_ in enumerate(S):
            cnt=collections.Counter()
            for x in G[i]:
                for j in inv[x]: cnt[j]+=1
            exs={s_[0]}
            for j,c in cnt.items():
                if j==i or S[j][3]!=s_[3] or S[j][0]==s_[0] or c<0.4*min(len(G[i]),len(G[j])): continue
                if difflib.SequenceMatcher(None,s_[4],S[j][4]).ratio()>=THR_STMT: exs.add(S[j][0])
            same[(s_[0],s_[1],s_[2])]=len(exs)
        exam_list=sorted(exams); recent=set(exam_list[-TREND_K[subj]:])
        pexams=collections.defaultdict(set)
        for s_ in S:
            pid=_K2P.get((subj,f"{s_[0]}|{s_[1]}|{s_[2]}"))
            if pid: pexams[pid].add(s_[0])
        qm={}
        for (e,n,k,key) in Qs:
            exs={e}
            if k!='stmt':
                for (e2,n2,k2,key2) in Qs:
                    if e2==e or k2!=k or len(key)<8: continue
                    if difflib.SequenceMatcher(None,key,key2).ratio()>=(THR_CALC if k=='calc' else THR_Q): exs.add(e2)
            qm[(e,n)]=len(exs)
        for e,(f,d) in exams.items():
            for q in d['questions']:
                if q.get('status')!='published' or not q.get('choices'): continue
                ans=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
                if ans and ans[0]=='all': continue
                neg=bool(NEG.search(q['stem'])); k=qkind(q)
                c=[TRAPS[t] for t in (q.get('traps') or []) if t in TRAPS and 'other' not in t and 'その他' not in TRAPS[t]['name']]
                pt=max(c,key=lambda x:x['count']) if c else None
                if k=='stmt':
                    counts=[];truths='';pcs=[];pids=[];pnames=[];prcs=[];prids=[];prn=[];trend=[]
                    for i,ch in enumerate(q['choices'],1):
                        counts.append(same[(e,q['num'],i)])
                        p=_K2P.get((subj,f"{e}|{q['num']}|{i}")); pids.append(p or ''); pnames.append(_PNAME[p][0] if p else ''); pcs.append(len(pexams[p]) if p else 0)
                        trend.append(len(pexams[p]&recent) if p else 0)
                        truths+=('正' if ((i not in ans) if neg else (i in ans)) else '誤')
                        _cand=PR_BY_POINT.get((subj,p),[]) if p else []
                        _b=max(_cand,key=lambda r:len(PR_EXAMS[r])) if _cand else None
                        prids.append(_b or ''); prn.append(PR_NAME[_b] if _b else ''); prcs.append(len(PR_EXAMS[_b]) if _b else 0)
                    _nm=compute_near(subj); _ne=[_nm.get((e,q['num'],i),[]) for i in range(1,len(q['choices'])+1)]
                    fr=dict(kind='choice',denom=D,counts=counts,truths=truths,pcounts=pcs,points=pids,pnames=pnames,prcounts=prcs,principles=prids,prnames=prn,trend=trend,recent_exams=sorted(recent),near=[bool(x) for x in _ne],near_exams=_ne)
                else:
                    _qp=_K2P.get((subj,f"{e}|{q['num']}|0"))   # 問題論点（tools/build_qpoints.py）。同じ問題の束の、出題回数
                    fr=dict(kind='question',denom=D,count=(len(_PEX[(subj,_qp)]) if _qp else qm[(e,q['num'])]),form={'calc':'計算問題','combo':'穴埋め・組合せの問題','short':'選択肢が物質名などの問題'}[k])
                    _cq=PR_BY_POINT.get((subj,_qp),[]) if _qp else []
                    if _cq:
                        _bq=max(_cq,key=lambda r:len(PRQ_EXAMS[r])); fr.update(prid=_bq,prname=PR_NAME[_bq],prcount=len(PRQ_EXAMS[_bq]))
                _a=ans[0]; _txt=str(q['stem'])+' '+(str(q['choices'][_a-1]) if isinstance(_a,int) and _a<=len(q['choices']) else '')
                _tt=SB.table_type(subj,_txt) if subj in ('tokka','kinzoku') else None
                if _tt and _tt[1]:
                    fr['subst_id']=f'sb-{subj}-{_tt[0]}'; fr['subst_name']=SB.name_of(subj,_tt[0])
                feats.append(dict(file=f,num=q['num'],exam=e,subj=subj,ans=ans,fr=fr,pat_count=pt['count'] if pt else 0,pat_id=pt['id'] if pt else None,pat_subj=pt['subject'] if pt else None))
    return feats
def decide(feats,thresholds=None,elim=None,pr=None):
    """境目を与えて、各問の区分を決める。thresholds が None なら、THRESHOLDS を使う"""
    global CUR,THRESHOLDS,ELIM_KNOWN,PR_THRESHOLDS
    old=THRESHOLDS; olde=ELIM_KNOWN; oldp=PR_THRESHOLDS
    if pr is not None: PR_THRESHOLDS=pr
    if thresholds: THRESHOLDS=thresholds
    if elim is not None: ELIM_KNOWN=elim
    out={}
    try:
        for ft in feats:
            CUR=ft['subj']; fr=dict(ft['fr'])
            pr=rank_of(ft['pat_count'],0,ft['pat_subj']) if ft['pat_id'] else None
            lv,why,tags=judge(fr,ft['ans'],pr); fr.update(level=lv,why=why)
            if tags is not None: fr['tags']=tags
            if why.startswith('pat_') and ft['pat_id']: fr['pat']=ft['pat_id']
            out[(ft['file'],ft['num'])]=fr
    finally: THRESHOLDS=old; ELIM_KNOWN=olde; PR_THRESHOLDS=oldp
    return out
if __name__=='__main__':
    feats=collect(); stats=decide(feats)
    print('統計',len(stats),'問')
    if APPLY:
        _bk=yaml.safe_load(open('data/master/book.yaml',encoding='utf-8')); _ch=0
        for t in _bk['traps']:
            r=rank_of(t['count'],0,t['subject'])
            if r!=t['rank']: t['rank']=r; _ch+=1
        open('data/master/book.yaml','w',encoding='utf-8').write(yaml.safe_dump(_bk,allow_unicode=True,sort_keys=False,width=1000))
        print('パターンのランクを付け直した件数',_ch)
        byfile=collections.defaultdict(dict)
        for (f,n),v in stats.items(): byfile[f][n]=v
        for f,m in byfile.items():
            d=yaml.safe_load(open(f,encoding='utf-8'))
            for q in d['questions']:
                if q['num'] in m: q['freq']=m[q['num']]
            open(f,'w',encoding='utf-8').write(yaml.safe_dump(d,allow_unicode=True,sort_keys=False,width=1000))
        print('書き込みました')
    else:
        print('区分',dict(sorted(collections.Counter(v['level'] for v in stats.values()).items())))
