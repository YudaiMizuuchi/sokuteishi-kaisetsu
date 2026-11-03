#!/usr/bin/env python3
"""参考書の1章ぶんの素材（原理の説明・論点・過去問の問題文と正答）を、Markdownで出す。
使い方: python3 chapter_pack.py <章ID> [--root .]      例: python3 chapter_pack.py bk-bunseki-forms
  必要なファイル: book_map.yaml / principles.yaml / points.yaml / substances_verified.yaml / book_id_aliases.yaml（任意）と、exams/<年月>/<科目>.yaml
  過去問の指し方：『2026-08|design|12』＝令和8年度第1回・デザイン・問12。選択肢は『2026-08|design|12|3』のように、番号を足す。"""
import sys,re,yaml,os,collections
try: _L=yaml.CSafeLoader
except Exception: _L=yaml.SafeLoader
def _load(p): return yaml.load(open(p,encoding='utf-8'),Loader=_L)
root='.'
if '--root' in sys.argv: root=sys.argv[sys.argv.index('--root')+1]
def P(*a):
    for base in (root,os.path.join(root,'data/master'),os.path.join(root,'data/master/substances')):
        p=os.path.join(base,*a)
        if os.path.exists(p): return p
    return os.path.join(root,*a)
NEG=re.compile(r'誤っているもの|不適当|不適切|適切でない|適当でない|正しくないもの|誤っている|あてはまらない|当てはまらない|該当しない')
SUBJ={'ippan':'労働衛生一般','hourei':'労働衛生関係法令','design':'デザイン・サンプリング','bunseki':'分析に関する概論','yuki':'有機溶剤','tokka':'特定化学物質','kinzoku':'金属類','funjin':'鉱物性粉じん'}
def era(e):
    y,m=map(int,e.split('-')); fy=y-1 if m<=3 else y; r=2 if m<=3 else 1
    n=fy-2018 if fy>=2019 else fy-1988
    return f"{'令和' if fy>=2019 else '平成'}{'元' if n==1 and fy>=2019 else n}年度第{r}回"
_c={}
def exam(subj,e):
    k=(subj,e)
    if k not in _c:
        p=os.path.join(root,'exams',e,subj+'.yaml'); p=p if os.path.exists(p) else os.path.join(root,'data/exams',e,subj+'.yaml')
        _c[k]=_load(p) if os.path.exists(p) else None
    return _c[k]
def clean(s): return re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',str(s))).strip()
def qkind(q):
    ch=q.get('choices') or []
    if q.get('columns'): return 'combo'
    if ch and all(re.search(r'\d',str(c)) and not re.search(r'[ぁ-んァ-ヶ一-龥]{3,}',str(c)) for c in ch): return 'calc'
    return 'stmt'
def question(subj,e,n):
    d=exam(subj,e)
    if not d: return None
    for q in d['questions']:
        if str(q['num'])==str(n): return q
def show_q(subj,e,n,mark=None):
    q=question(subj,e,n)
    if not q or not q.get('choices'): return ''
    a=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
    L=[f"**{e}|{subj}|{n}**（{era(e)} {SUBJ[subj]} 問{n}）",'',clean(q['stem']),'']
    for i,c in enumerate(q['choices'],1): L.append(f"{i}. {clean(c)}"+('　← 正答' if i in a else ''))
    if q.get('columns'): L.append('（穴埋めの表あり：'+clean(q['columns'])[:200]+'）')
    return '\n'.join(L)
_G={}
def _g():
    if _G: return _G
    al=_load(P('book_id_aliases.yaml'))['aliases'] if os.path.exists(P('book_id_aliases.yaml')) else {}
    _G['al']=al
    _G['ch']={c['id']:c for c in _load(P('book_map.yaml'))['chapters']}
    _G['prin']={p['id']:p for p in _load(P('principles.yaml'))['principles']}
    _G['pts']={p['id']:p for p in _load(P('points.yaml'))['points']}
    vp=P('substances_verified.yaml') if os.path.exists(P('substances_verified.yaml')) else P('verified.yaml')
    _G['ver']=_load(vp)['verified']
    return _G
def pack(cid):
    G=_g(); cid=G['al'].get(cid,cid); ch=G['ch'][cid]; prin=G['prin']; pts=G['pts']
    subj=ch['subject']
    L=[f"# 素材：{cid} {ch['title']}",'',f"- 科目：{SUBJ[subj]}　種類：{ch['kind']}　部：{ch.get('part','')}　状態：{ch.get('status','')}",'']
    ids=[]
    for pr in ch.get('principles') or []:
        p=prin[pr]; L+=[f"## 原理 {pr}：{p['name']}",'',p['statement'],'']+([f"公式：{p['formula']}",''] if p.get('formula') else [])
        ids+=p.get('points') or []
    ids+=ch.get('points') or []
    for th in ch.get('themes') or []: ids+=[p['id'] for p in pts.values() if p['subject']==subj and p.get('theme')==th and not p.get('merged_into')]
    ids=list(dict.fromkeys(ids))
    def truth(subj_,e,n,i):
        q=question(subj_,e,n)
        if not q: return '?'
        a=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
        neg=bool(NEG.search(str(q['stem']))); return '正' if ((i not in a) if neg else (i in a)) else '誤'
    used=[]
    if ids:
        L+=[f"## 論点（{len(ids)}件）",'','出題回数は、その論点が出た回の数（同じ回の重複は1回）。各出題は『回|科目|問|選択肢』と、その記述の正誤。','']
        rows=[]
        for pid in ids:
            p=pts.get(pid)
            if not p or p.get('merged_into'): continue
            exs=sorted({k.split('|')[0] for k in p['members']})
            rows.append((-len(exs),pid,p,exs))
        for _,pid,p,exs in sorted(rows,key=lambda x:(x[0],x[1])):
            ap=[]
            for k in sorted(p['members'],reverse=True)[:6]:
                e,n,i=k.split('|'); ap.append(f"{e}|{subj}|{n}|{i}（{truth(subj,e,n,int(i))}）"); used.append((e,n))
            L.append(f"- **{pid}**　{p['name']}　〔{len(exs)}回：{ '、'.join(exs[-4:]) }〕　{ '、'.join(ap) }")
        L.append('')
    # 物質表
    for sb in ch.get('substances') or []:
        _,s,code=sb.split('-'); v=G['ver']
        L+=[f"## 物質の表 {sb}（確認済み）",'']
        for no,x in (v.get(s,{}).get(code) or {}).items(): L.append(f"- {no}｜捕集：{x['捕集']}｜処理：{x['処理']}｜分析：{x['分析']}")
        L.append('')
    # 物質表の章：その物質名と測定方法の語を含む正答の問題
    METHOD=re.compile(r'捕集|検知管|ガスクロマトグラフ|液体クロマトグラフ|吸光光度|蛍光光度|原子吸光|ICP|FID|ECD|FTD|FPD|PID|質量分析|GC|HPLC|脱着|抽出|発色|分析法|測定法|二硫化炭素|活性炭|シリカゲル|ろ紙|ミゼット|インピンジャー|捕集液|標準物質|標準原液|検出器')
    if ch.get('substances'):
        _,s_,code=ch['substances'][0].split('-')
        sd=_load(P(s_+'.yaml'))
        sb=[x for x in sd['substances'] if x['code']==code][0]
        pats=[re.compile(r'(?<![ァ-ヶ])'+re.escape(n)+r'(?![ァ-ヶ化])') for n in (sb.get('match') or [sb['name']])]
        exs=sorted(os.listdir(os.path.join(root,'exams') if os.path.isdir(os.path.join(root,'exams')) else os.path.join(root,'data/exams')),reverse=True)
        for e in exs:
            d=exam(s_,e)
            if not d: continue
            for q in d['questions']:
                a=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
                if not q.get('choices') or not a or not isinstance(a[0],int): continue
                t=str(q['stem'])+' '+str(q['choices'][a[0]-1])
                if METHOD.search(t) and any(p.search(t) for p in pats): used.append((e,q['num']))
    # 過去問（決め手になる問題）
    L+=['## この章に関わる過去問（新しい順、最大25問）','']
    shown=[];seen=set()
    if ch['kind']=='解法':
        for e in sorted(os.listdir(os.path.join(root,'exams') if os.path.isdir(os.path.join(root,'exams')) else os.path.join(root,'data/exams')),reverse=True):
            d=exam(subj,e)
            if not d: continue
            for q in d['questions']:
                if q.get('choices') and qkind(q) in('calc','combo') : shown.append((e,q['num']))
    else:
        for e,n in sorted(set(used),reverse=True): shown.append((e,n))
    for e,n in shown[:25]:
        t=show_q(subj,e,n)
        if t: L+=[t,'']
    return '\n'.join(L)

if __name__=='__main__':
    print(pack(sys.argv[1]))
