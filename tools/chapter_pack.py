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
        if _c[k] and _c[k].get('excluded'): _c[k]=None   # 対象外の回（例：平成26年度第2回〜平成27年度第2回）は、公開していないので、素材に含めない
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
def form(q):
    """設問の形（執筆側が、選択肢の正誤を取り違えないための見出し）"""
    st=clean(q['stem'])
    if q.get('columns'): return '穴埋め・組合せ（表）'
    if re.search(r'組合せ',st): return '組合せを選ぶ'
    if qkind(q)=='calc': return '計算'
    if NEG.search(st): return '誤っているもの（該当しないもの）を選ぶ'
    if re.search(r'規定されていない|義務付けられていない|必要としない|含まれない|ないものはどれか',st): return '該当しないものを選ぶ'
    if re.search(r'正しいもの|適切なもの|適当なもの',st): return '正しいものを選ぶ'
    return '該当するものを選ぶ'
def is_stmt(q):
    """選択肢が、正誤を判定できる文か（語句・式・物質名でないか）"""
    ch=[str(c) for c in (q.get('choices') or [])]
    return (q.get('freq') or {}).get('kind')=='choice' and not q.get('columns') and sum(1 for c in ch if c.rstrip().endswith('。'))>=2
FIGS=[]
def show_q(subj,e,n,mark=None):
    q=question(subj,e,n)
    if not q or not q.get('choices'): return ''
    a=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
    L=[f"**{e}|{subj}|{n}**（{era(e)} {SUBJ[subj]} 問{n}。設問の形：{form(q)}{'' if is_stmt(q) else '。選択肢は語句・式（記述の正誤ではなく、正答かどうかで読む）'}）",'',clean(q['stem']),'']
    if q.get('columns'): L+=['（表の列：'+' ／ '.join(clean(c) for c in q['columns'])+'。各選択肢は、列の順に「／」で区切ってある）','']
    for i,c in enumerate(q['choices'],1): L.append(f"{i}. {clean(c)}"+('　← 正答' if i in a else ''))
    ans=[x for x in a if isinstance(x,int)]
    if ans: L+=['','正答：'+'、'.join(f"{x}（{clean(q['choices'][x-1])[:80]}）" for x in ans)]
    elif a: L+=['','正答：'+str(a)]
    for fg in q.get('figures') or []:
        FIGS.append(fg['file']); L+=['',f"図：figs/{fg['file']}（同梱）。図の内容：{clean(fg.get('alt',''))}"]
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
    _qp=P('qpoint_chapters.yaml')   # 問題論点の割り当て（tools/assign_qpoints.py）
    if os.path.exists(_qp): ids+=(_load(_qp) or {}).get(cid,[])
    for th in ch.get('themes') or []: ids+=[p['id'] for p in pts.values() if p['subject']==subj and p.get('theme')==th and not p.get('merged_into')]
    if ch['kind']=='解法':   # 解法の章：その科目の問題論点（計算・穴埋め・組合せ・物質名を選ぶ問題）を、すべて一覧にする
        ids+=[pid for pid,p in pts.items() if p['subject']==subj and pid.startswith('qp-') and not p.get('merged_into')]
    ids=list(dict.fromkeys(ids))
    def truth(subj_,e,n,i):
        q=question(subj_,e,n)
        if not q: return '?'
        a=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
        if not is_stmt(q): return '正答' if i in a else '正答でない'   # 語句・式の選択肢：記述の正誤ではない
        tr=(q.get('freq') or {}).get('truths')
        if tr and len(tr)>=i: return tr[i-1]
        neg=bool(NEG.search(str(q['stem']))); return '正' if ((i not in a) if neg else (i in a)) else '誤'
    def ctext(subj_,e,n,i):
        q=question(subj_,e,n)
        return clean(q['choices'][i-1]) if q and q.get('choices') and 0<i<=len(q['choices']) else ''
    used=[]
    def _root(i):
        while pts.get(i) and pts[i].get('merged_into'): i=pts[i]['merged_into']
        return i
    _agg={}   # 統合済みの論点の出題も、統合先の論点に数える（compute_freq.py と同じ）
    for _i,_p in pts.items():
        _agg.setdefault(_root(_i),[]).extend(_p['members'])
    def _row(pid):
        p=pts.get(pid)
        if not p or p.get('merged_into'): return None
        p=dict(p); p['members']=sorted(set(_agg.get(pid,p['members'])))
        exs=sorted({k.split('|')[0] for k in p['members']})
        return (-len(exs),pid,p,exs)
    ALLEX=set()
    def _line(r):
        _,pid,p,exs=r
        ap=[]; ALLEX.update(exs); rep={}
        for k in sorted(p['members'],reverse=True):
            e,n,i=k.split('|'); used.append((e,n))
            if i=='0': ap.append(f"{e}|{subj}|{n}（問題）"); continue
            t=truth(subj,e,n,int(i)); ap.append(f"{e}|{subj}|{n}|{i}（{t}）")
            tx=ctext(subj,e,n,int(i))
            if tx: rep.setdefault(t,[]); (tx not in [x[1] for x in rep[t]]) and rep[t].append((f"{e}|{subj}|{n}|{i}",tx))
        out=f"- **{pid}**　{p['name']}　〔{len(exs)}回：{ '、'.join(exs) }〕　{ '、'.join(ap) }"
        LAB={'正':'正しい形','誤':'誤りの形','正答':'正答になった語句','正答でない':'正答でない語句'}
        for t in ('正','誤','正答','正答でない'):
            for ref,tx in (rep.get(t) or [])[:(3 if t=='誤' else 2)]:
                out+=f"\n    - {LAB[t]}（{ref}）：{tx[:300]}"
        return out
    if ids:
        L+=[f"## 論点（{len(ids)}件）",'','出題回数は、その論点が出た回の数（同じ回の重複は1回）。〔n回：…〕は、出た回を全部並べてある（省略なし）。各出題は『回|科目|問|選択肢』と、その記述の正誤（語句・式の選択肢は「正答／正答でない」）。論点の下の行は、代表の選択肢の本文（正しい形は2つまで、誤りの形は3つまで）。','','@@TOTAL@@','']
        prs=list(ch.get('principles') or [])
        if len(prs)>1:   # 原理が複数の章：論点を、原理ごとに分けて並べる（原理に属さない論点は、最後）
            seen=set()
            for pr in prs:
                rows=[]
                for pid in (prin[pr].get('points') or []):
                    if pid in seen: continue
                    r=_row(pid)
                    if r: rows.append(r); seen.add(pid)
                L+=[f"### 原理 {pr}（{prin[pr]['name']}）の論点（{len(rows)}件）",'']
                for r in sorted(rows,key=lambda x:(x[0],x[1])): L.append(_line(r))
                L.append('')
            rows=[]
            for pid in ids:
                if pid in seen: continue
                r=_row(pid)
                if r: rows.append(r)
            if rows:
                L+=[f"### どの原理にも割り当てていない論点（{len(rows)}件）",'']
                for r in sorted(rows,key=lambda x:(x[0],x[1])): L.append(_line(r))
                L.append('')
        else:
            rows=[r for r in (_row(pid) for pid in ids) if r]
            for r in sorted(rows,key=lambda x:(x[0],x[1])): L.append(_line(r))
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
    _lim='40' if ch['kind']=='解法' else '30'
    L+=[f'## この章に関わる過去問（新しい順、最大{_lim}問。この章の論点が3つ以上入っている問と、問題論点の問）'+('。解法の章：計算・穴埋め・組合せ・物質名を選ぶ問題。上の論点の一覧には、この科目の問題論点（qp-）をすべて載せている' if ch['kind']=='解法' else ''),'']
    shown=[];seen=set()
    if ch['kind']=='解法':
        for e in sorted(os.listdir(os.path.join(root,'exams') if os.path.isdir(os.path.join(root,'exams')) else os.path.join(root,'data/exams')),reverse=True):
            d=exam(subj,e)
            if not d: continue
            for q in d['questions']:
                if q.get('choices') and qkind(q)!='stmt' : shown.append((e,q['num']))
    else:
        # その章の論点が3つ以上入っている問（その章の主題の問）と、問題論点の問を、全文で載せる。ほかの問は、論点の下の「代表の選択肢」で読める
        _cnt=collections.Counter(used); _qp=set()
        for pid in ids:
            if pid.startswith('qp-') and pts.get(pid):
                for k in _agg.get(pid,pts[pid]['members']): _qp.add(tuple(k.split('|')[:2]))
        for e,n in sorted(set(used),reverse=True):
            if _cnt[(e,n)]>=3 or (e,n) in _qp or ch.get('substances'): shown.append((e,n))
    LIM=40 if ch['kind']=='解法' else 30
    for e,n in shown[:LIM]:
        t=show_q(subj,e,n)
        if t: L+=[t,'']
    N={'ippan':23,'hourei':23,'design':23,'bunseki':23}.get(subj,12)
    out='\n'.join(L).replace('@@TOTAL@@',f"**章全体（上の論点の和集合）：{len(ALLEX)}回／{N}回**（{'、'.join(sorted(ALLEX))}）" if ids else '')
    if len(shown)>LIM: out+=f"\n\n（全文を載せる対象の過去問は {len(shown)} 問。新しい順に {LIM} 問までを載せた。載っていない問の選択肢は、論点の下の『代表の選択肢』で読める）"
    return out

if __name__=='__main__':
    print(pack(sys.argv[1]))
    if FIGS: sys.stderr.write('FIGS '+' '.join(sorted(set(FIGS)))+'\n')
