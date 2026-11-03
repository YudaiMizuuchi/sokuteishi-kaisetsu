#!/usr/bin/env python3
"""論点マスタ（data/master/points.yaml）の読み書きと、更新。
- 1論点＝1つの事実のまとまり。id は固定（pt-<科目>-<連番>）。回を追加しても、既存の論点の id・名前・所属は変えない。
- 新しい選択肢は、既存の論点の中心（平均ベクトル）との類似度が0.62以上なら、最も近い論点に入れる。どれにも入らなければ、新しい論点にする。
- 同じ事実と判定した論点は、data/master/point_links.yaml の組から、merged_into で統合する（members は残す）。
使い方: python3 tools/build_points.py --update [科目ID ...]"""
import os,re,yaml,math,collections
import build_points as BP
import points as PT
PATH='data/master/points.yaml'; THR=0.62
SUBJECTS=['yuki','tokka','kinzoku','funjin','ippan','hourei','design','bunseki']
def key(it): return f"{it['e']}|{it['n']}|{it['i']}"
def load():
    if not os.path.exists(PATH): return {'meta':{'version':1,'similarity':THR},'points':[]}
    return yaml.safe_load(open(PATH,encoding='utf-8'))
def save(m):
    open(PATH,'w',encoding='utf-8').write(yaml.safe_dump(m,allow_unicode=True,sort_keys=False,width=1000))
def roots(m):
    byid={p['id']:p for p in m['points']}
    def r(i):
        while byid[i].get('merged_into'): i=byid[i]['merged_into']
        return i
    return byid,r
def resolve(m):
    """（科目, 選択肢のキー 回|問|番号）→ 統合後の論点id。キーは、科目が違えば、重なるので、必ず科目と組にする"""
    byid,r=roots(m); out={}
    for p in m['points']:
        for k in p['members']: out[(p['subject'],k)]=r(p['id'])
    return out
def info(m):
    byid,r=roots(m); return {p['id']:(p['name'],p.get('theme','')) for p in m['points'] if not p.get('merged_into')}
def _autoname(items,idx):
    reps=sorted(idx,key=lambda i:(not items[i]['truth'],len(items[i]['text']),items[i]['e'])); rep=items[reps[0]]
    t=re.sub(r'\s+','',rep['text']); t=re.sub(r'^(事業者は、?|なお、?)','',t)
    t=t[:32].rstrip('、，')+('…' if len(t)>32 else '')
    return t+('' if rep['truth'] else '（誤りの記述）')
def _name(rules,items,idx):
    names=collections.Counter(); themes={}
    if rules:
        for i in idx:
            pid,nm,th=PT.assign(rules,items[i]['text'])
            if nm: names[nm]+=1; themes[nm]=th
    if names:
        nm=names.most_common(1)[0][0]; return nm,themes.get(nm,'')
    return _autoname(items,idx),''
def _tfidf(items):
    T=[sorted(BP.terms(it['text'])) for it in items]; N=len(items)
    df=collections.Counter(x for t in T for x in t); V=[]
    for t in T:
        v={x:math.log((N+1)/(df[x]+1))+1 for x in t}; nr=math.sqrt(sum(sorted(a*a for a in v.values()))) or 1
        V.append({k:a/nr for k,a in v.items()})
    return V
def _cos(a,b):
    if len(a)>len(b): a,b=b,a
    return sum(sorted(w*b.get(k,0) for k,w in a.items()))
def update(m,subj):
    items=BP.load(subj); V=_tfidf(items); rules=PT.load_rules(subj)
    kidx={key(it):i for i,it in enumerate(items)}
    mine=[p for p in m['points'] if p['subject']==subj]
    assigned={k for p in mine for k in p['members']}
    new_ids=0
    if not mine:
        groups=BP.group(items,THR)
        for n,g in enumerate(sorted(groups,key=lambda g:(-len({items[i]['e'] for i in g}),-len(g)))):
            nm,th=_name(rules,items,g)
            m['points'].append(dict(id=f'pt-{subj}-{n+1:04d}',subject=subj,name=nm,theme=th,members=sorted(key(items[i]) for i in g)))
        return len(groups)
    # 既存の論点の中心
    cents={}
    for p in mine:
        idx=[kidx[k] for k in p['members'] if k in kidx]
        c=collections.defaultdict(float)
        for i in idx:
            for k,w in V[i].items(): c[k]+=w/max(1,len(idx))
        nr=math.sqrt(sum(a*a for a in c.values())) or 1
        cents[p['id']]={k:a/nr for k,a in c.items()}
    inv=collections.defaultdict(set)
    for pid,c in cents.items():
        for k in c: inv[k].add(pid)
    byid={p['id']:p for p in m['points']}
    nextn=max([int(p['id'].split('-')[-1]) for p in mine])+1
    todo=[i for i,it in enumerate(items) if key(it) not in assigned]
    for i in sorted(todo,key=lambda i:-len(V[i])):
        cand=collections.Counter()
        for k in V[i]:
            for pid in sorted(inv.get(k,())): cand[pid]+=1
        best=None
        for pid in cand:
            if byid[pid].get('merged_into'): continue
            c=_cos(V[i],cents[pid])
            if c>=THR and (best is None or c>best[0]): best=(c,pid)
        if best:
            byid[best[1]]['members'].append(key(items[i])); byid[best[1]]['members'].sort()
        else:
            pid=f'pt-{subj}-{nextn:04d}'; nextn+=1; new_ids+=1
            nm,th=_name(rules,items,[i])
            p=dict(id=pid,subject=subj,name=nm,theme=th,members=[key(items[i])]); m['points'].append(p); byid[pid]=p
            cents[pid]=dict(V[i])
            for k in V[i]: inv[k].add(pid)
    return new_ids
def apply_links(m):
    p='data/master/point_links.yaml'
    if not os.path.exists(p): return 0
    for pt in m['points']: pt.pop('merged_into',None)
    byid,r=roots(m); owner={}
    for pt in m['points']:
        for k in pt['members']: owner[(pt['subject'],k)]=pt['id']
    n=0
    for l in (yaml.safe_load(open(p,encoding='utf-8')) or {}).get('links',[]):
        a,b=owner.get((l['subject'],l['a'])),owner.get((l['subject'],l['b']))
        if not a or not b: continue
        ra,rb=r(a),r(b)
        if ra==rb: continue
        big,small=(ra,rb) if len(byid[ra]['members'])>=len(byid[rb]['members']) else (rb,ra)
        byid[small]['merged_into']=big; n+=1
    return n
def run(subjects=None):
    m=load()
    for s in (subjects or SUBJECTS):
        n=update(m,s)
        print(s,'論点（新規）',n)
    print('統合',apply_links(m),'件')
    m['points'].sort(key=lambda p:(SUBJECTS.index(p['subject']),p['id']))
    save(m); return m
