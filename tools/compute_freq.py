#!/usr/bin/env python3
"""選択肢ごとの出題頻度（その科目の全回のうち、何回、同じ記述が出題されたか）を計算して、問題データの freq に書き込む。
使い方: python3 tools/compute_freq.py        （試算：件数だけ表示）
        python3 tools/compute_freq.py apply  （data/exams/*/*.yaml の各問に freq を書き込む）
新しい回を追加したときは、もう一度 apply を実行する（分母が1つ増える）。
- 統計の単位は「科目」。同じ回で同じ記述が2回出ても、1回と数える。
- 正誤の向きが同じ記述だけを、同じものとみなす（「比例」と「反比例」のように、正誤が逆のものは別）。
- 穴埋め・組合せ・計算問題・物質名を選ぶ問題は、選択肢ではなく、問題として数える。"""
import yaml,glob,re,sys,collections,difflib
APPLY=len(sys.argv)>1 and sys.argv[1]=='apply'
THR_STMT=0.86; THR_SIM=0.70; THR_CALC=0.62; THR_Q=0.90   # THR_SIM：『似た記述』とみなす下限（ガードつき）
NEG=re.compile(r'誤っているもの|不適当|不適切|適切でない|適当でない|正しくないもの|誤っている|あてはまらない|当てはまらない|該当しない')
def norm(s):
    s=re.sub(r'<[^>]+>','',str(s)); s=re.sub(r'\$[^$]*\$','',s)
    return re.sub(r'[\s　、。，．・「」『』（）()\[\]：:,.\-－]','',s)
def grams(t): return {t[i:i+3] for i in range(max(1,len(t)-2))}

def _nums(t): return sorted(re.findall(r'\d+(?:\.\d+)?',t.translate(str.maketrans('０１２３４５６７８９','0123456789'))))
def _cls(t): return sorted(re.findall(r'第[一二三四五六七1-9１-９]+[種類号条]',t))
_FILL=re.compile(r'(通常|一般に|一般的に|原則として|場合は|場合には|ことが多い|である|です|する|いる|ある|の|は|が|を|に|で|と|も|や|、|。|，)')
def similar_guard(a,b):
    """『似た記述』の条件：数字・種類（第○種など）が一致し、差分が、両側とも名詞2文字以上で入れ替わっていない。"""
    if _nums(a)!=_nums(b) or _cls(a)!=_cls(b): return False
    sm=difflib.SequenceMatcher(None,a,b)
    for tag,i1,i2,j1,j2 in sm.get_opcodes():
        if tag!='equal' and len(_FILL.sub('',a[i1:i2]))>=2 and len(_FILL.sub('',b[j1:j2]))>=2: return False
    return True


def rank_of(m,D):
    """出題回数の水準。共通科目（23回）はS≧10・A≧5・B≧3、選択科目（12回）はS≧5・A≧3・B≧2。"""
    t=(10,5,3) if D>=20 else (5,3,2)
    return 'S' if m>=t[0] else 'A' if m>=t[1] else 'B' if m>=t[2] else 'C'
def judge(fr,answers):
    """問題の区分：1＝得点必須、2＝何とか得点したい、3＝失点しても仕方がない。
    選択肢の問題：正答がS・A（同じ記述）→1／正答がB（同じ記述または似た記述）→2／他の選択肢のうち、頻出のおとり（似た記述を含めてB以上）を除いて、残りが1つ（全部除外）または2つ（2択）→2／それ以外→3。
    問題単位の集計：出題回数がS・A→1、B→2、C→3。"""
    D=fr['denom']
    if fr['kind']=='question':
        r=rank_of(fr['count'],D)
        return (1,'q_hi',None) if r in 'SA' else ((2,'q_b',None) if r=='B' else (3,'q_new',None))
    a=answers[0]-1; ms=fr['counts']; sm=fr['similar']; n=len(ms)
    tags=[]
    for i in range(n):
        if i==a:
            r=rank_of(ms[i],D); r2=rank_of(sm[i],D)
            tags.append('ans_hi' if r in 'SA' else 'ans_b' if (r=='B' or r2 in 'SAB') else 'ans_new')
        else:
            tags.append('odo' if rank_of(sm[i],D)!='C' else ('new' if sm[i]<=1 else ''))
    if tags[a]=='ans_hi': return 1,'ans_hi',tags
    if tags[a]=='ans_b': return 2,'ans_b',tags
    k=sum(1 for i in range(n) if i!=a and tags[i]=='odo'); left=n-k
    if left==1: return 2,'elim_all',tags
    if left==2: return 2,'elim_two',tags
    return 3,'none',tags

docs=collections.defaultdict(dict)   # subject -> exam -> (file, data)
for f in sorted(glob.glob('data/exams/*/*.yaml')):
    d=yaml.safe_load(open(f,encoding='utf-8'))
    if d.get('excluded'): continue
    docs[d['subject']][f.split('/')[2]]=(f,d)
def qkind(q):
    ch=q.get('choices') or []
    if q.get('columns'): return 'combo'
    if ch and all(re.search(r'\d',str(c)) and not re.search(r'[ぁ-んァ-ヶ一-龥]{3,}',str(c)) for c in ch): return 'calc'
    if ch and all(len(norm(c))>=12 for c in ch): return 'stmt'
    return 'short'
total=0; stats={}
for subj,exams in docs.items():
    D=len(exams)
    # 記述（選択肢）の集合
    S=[]   # (exam, num, idx, truth, text)
    Qs=[]  # (exam, num, kind, key)
    for e,(f,d) in exams.items():
        for q in d['questions']:
            if q.get('status')!='published' or not q.get('choices'): continue
            ans=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
            if ans and ans[0]=='all': continue
            neg=bool(NEG.search(q['stem'])); k=qkind(q)
            if k=='stmt':
                for i,c in enumerate(q['choices'],1):
                    truth=(i not in ans) if neg else (i in ans)
                    S.append((e,q['num'],i,truth,norm(c)))
            a0=ans[0]; atxt=norm(q['choices'][a0-1]) if isinstance(a0,int) and a0<=len(q['choices']) else ''
            key=norm(q['stem'])[:70] if k=='calc' else norm(q['stem'])[:60]+'|'+atxt
            Qs.append((e,q['num'],k,key))
    # 記述の索引
    G=[grams(s[4]) for s in S]; inv=collections.defaultdict(list)
    for i,g in enumerate(G):
        for x in g: inv[x].append(i)
    match={}; match2={}   # index -> set of exams
    for i,s in enumerate(S):
        cnt=collections.Counter()
        for x in G[i]:
            for j in inv[x]: cnt[j]+=1
        exs={s[0]}; exs2={s[0]}
        for j,c in cnt.items():
            if j==i or S[j][3]!=s[3] or S[j][0]==s[0]: continue
            if c<0.4*min(len(G[i]),len(G[j])): continue
            r=difflib.SequenceMatcher(None,s[4],S[j][4]).ratio()
            if r>=THR_STMT: exs.add(S[j][0]); exs2.add(S[j][0])
            elif r>=THR_SIM and similar_guard(s[4],S[j][4]): exs2.add(S[j][0])
        match[i]=exs; match2[i]=exs2
    idx={(s[0],s[1],s[2]):i for i,s in enumerate(S)}
    # 問題の索引
    qm={}
    for a,(e,n,k,key) in enumerate(Qs):
        exs={e}
        if k!='stmt':
            for (e2,n2,k2,key2) in Qs:
                if e2==e or k2!=k or len(key)<8: continue
                thr=THR_CALC if k=='calc' else THR_Q
                if difflib.SequenceMatcher(None,key,key2).ratio()>=thr: exs.add(e2)
        qm[(e,n)]=(k,len(exs))
    for e,(f,d) in exams.items():
        for q in d['questions']:
            if q.get('status')!='published' or not q.get('choices'): continue
            ans=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
            if ans and ans[0]=='all': continue
            neg=bool(NEG.search(q['stem'])); k=qkind(q)
            if k=='stmt':
                counts=[];counts2=[];truths=''
                for i,c in enumerate(q['choices'],1):
                    counts.append(len(match[idx[(e,q['num'],i)]])); counts2.append(len(match2[idx[(e,q['num'],i)]])); truths+=('正' if ((i not in ans) if neg else (i in ans)) else '誤')
                fr=dict(kind='choice',denom=D,counts=counts,similar=counts2,truths=truths); lv,why,tags=judge(fr,ans); fr.update(level=lv,why=why,tags=tags); stats[(f,q['num'])]=fr
            else:
                kk,m=qm[(e,q['num'])]
                fr=dict(kind='question',denom=D,count=m,form={'calc':'計算問題','combo':'穴埋め・組合せの問題','short':'選択肢が物質名などの問題'}[k]); lv,why,_=judge(fr,ans); fr.update(level=lv,why=why); stats[(f,q['num'])]=fr
    print(subj,'回数',D,'問題',sum(len(x[1]['questions']) for x in exams.values()))
print('統計',len(stats),'問')
if APPLY:
    byfile=collections.defaultdict(dict)
    for (f,n),v in stats.items(): byfile[f][n]=v
    for f,m in byfile.items():
        d=yaml.safe_load(open(f,encoding='utf-8'))
        for q in d['questions']:
            if q['num'] in m: q['freq']=m[q['num']]
        open(f,'w',encoding='utf-8').write(yaml.safe_dump(d,allow_unicode=True,sort_keys=False,width=1000))
    print('書き込みました')
else:
    kc=collections.Counter(v['kind'] for v in stats.values()); print(kc)
    # 選択肢別の頻度の分布
    dist=collections.Counter()
    for v in stats.values():
        if v['kind']=='choice':
            for m in v['counts']: dist[min(m,6)]+=1
    print('記述の出題回数の分布',sorted(dist.items()))
    d2=collections.Counter(); up=0;tot2=0
    for v in stats.values():
        if v['kind']=='choice':
            for a,b in zip(v['counts'],v['similar']):
                tot2+=1; up+=(b>a)
    print('似た記述を含めると回数が増える選択肢',up,'/',tot2)
    lc=collections.Counter(v['level'] for v in stats.values()); print('区分',dict(sorted(lc.items())))
