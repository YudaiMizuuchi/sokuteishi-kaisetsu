#!/usr/bin/env python3
"""問題論点（id: qp-<科目>-<連番>）を、論点マスタ data/master/points.yaml に追加・更新する。
物質名・用語を選ぶ問題、計算問題、穴埋め・組合せの問題は、選択肢が論点にならないので、『問題そのもの』を1つの論点にする
（同じ問題文で、同じ正答の問題＝1つの論点。計算問題は、問題文が似ていれば同じ）。判定（compute_freq.py の問題単位の回数）と同じ基準。
- members のキーは『回|問|0』（0は、問題全体）。選択肢の論点（pt-…）とは別のIDで、既存の論点の id・名前・所属は変えない。
- 回を追加して実行し直しても、既存の問題論点のIDは変わらない（既存の members と重なる組は、そのIDを引き継ぐ）。
使い方: python3 tools/build_qpoints.py"""
import sys,io,re,yaml,difflib,collections
sys.path.insert(0,'tools')
_so=sys.stdout; sys.stdout=io.StringIO()
import compute_freq as CF
import points as PT
sys.stdout=_so
PATH='data/master/points.yaml'
FACETS=(yaml.safe_load(open('data/master/qp_facets.yaml',encoding='utf-8')) or {}).get('facets',[]) if __import__('os').path.exists('data/master/qp_facets.yaml') else []
KIND_LABEL={'calc':'計算問題','combo':'穴埋め・組合せ','short':'物質名・用語を選ぶ問題'}
def clean(s): return re.sub(r'\s+',' ',re.sub(r'\$([^$]*)\$',r'\1',re.sub(r'<[^>]+>','',str(s)))).strip()
def short_stem(stem,limit=34):
    s=clean(stem)
    s=re.sub(r'^次の[^、。]{1,18}のうち[、，]?','',s)
    s=re.sub(r'^次の[^、。]{1,18}について[、，]?','',s)
    s=re.sub(r'(として|のうち|うち)?[、，]?(最も)?(適切|適当|正しい|誤っている)?(もの|組合せ|ものの組合せ)?は(次の)?(うち)?どれか。?$','',s)
    s=re.sub(r'[はが]どれか。?$','',s); s=s.rstrip('。、， ')
    if len(s)>limit:
        cut=s.rfind('、',0,limit); s=(s[:cut] if cut>=14 else s[:limit-1])+'…'
    return s
def collect():
    out=[]
    for subj,exams in CF.docs.items():
        for e,(f,d) in sorted(exams.items()):
            for q in d['questions']:
                if q.get('status')!='published' or not q.get('choices'): continue
                a=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
                if not a or a[0]=='all' or not isinstance(a[0],int) or a[0]>len(q['choices']): continue
                k=CF.qkind(q)
                if k=='stmt': continue
                atxt=CF.norm(q['choices'][a[0]-1])
                key=CF.qkey(q,k,atxt)
                st=re.sub(r'\s+','',str(q['stem'])); fc=next((f['label'] for f in FACETS if f['subject']==subj and f['kind']==k and re.search(f['pattern'],st)),'')
                out.append(dict(subj=subj,e=e,n=q['num'],k=k,key=key,stem=q['stem'],ans=clean(q['choices'][a[0]-1]),facet=fc))
    return out
def groups(items):
    """同じ科目・同じ形式で、類似度が閾値以上のものを、1つの束にする。穴埋め・組合せは『リーダー方式』（束の最初の問題と比べる。連鎖して別のテーマまで束ねない。同じ回の問題は同じ束に入れない）、計算・物質名を選ぶ問題は連結（判定の従来の数え方に合わせる。計算は数値が変わっていくため）。
    閾値：計算＝CF.THR_CALC、穴埋め・組合せ＝CF.THR_COMBO、物質名を選ぶ問題＝CF.THR_Q（正答の一致も含む）"""
    by=collections.defaultdict(list)
    for i,it in enumerate(items): by[(it['subj'],it['k'],it['facet'])].append(i)
    out=[]
    ONE={(f['subject'],f['kind'],f['label']) for f in FACETS if f.get('one_bundle')}   # 『このパターンの問題は、全部1つのテーマ』と、規則で宣言したもの
    for (s,k,fc),ix in by.items():
        if (s,k,fc) in ONE and fc: out.append(sorted(ix,key=lambda i:(items[i]['e'],items[i]['n']))); continue
        thr={'calc':CF.THR_CALC,'combo':CF.THR_COMBO}.get(k,CF.THR_Q)
        ix=sorted(ix,key=lambda i:(items[i]['e'],items[i]['n']))
        if k=='combo':
            # リーダー方式。同じ回に複数の問題があるときは、類似度の高い組から順に、束へ入れる（出題順ではなく、いちばん似ている束へ）
            leaders=[]; gs=[]
            byexam=collections.defaultdict(list)
            for i in ix: byexam[items[i]['e']].append(i)
            for e in sorted(byexam):
                cands=[]
                for i in byexam[e]:
                    if len(items[i]['key'])<8: continue
                    for bi,l in enumerate(leaders):
                        r=difflib.SequenceMatcher(None,items[l]['key'],items[i]['key']).ratio()
                        if r>=thr: cands.append((-r,i,bi))
                cands.sort(); done=set(); used=set()
                for nr,i,bi in cands:
                    if i in done or bi in used: continue
                    gs[bi].append(i); done.add(i); used.add(bi)
                for i in byexam[e]:
                    if i not in done: leaders.append(i); gs.append([i])
            out+=gs
        else:
            par={i:i for i in ix}
            def f(i):
                while par[i]!=i: par[i]=par[par[i]]; i=par[i]
                return i
            for a in range(len(ix)):
                for b in range(a+1,len(ix)):
                    i,j=ix[a],ix[b]
                    if items[i]['e']==items[j]['e'] or len(items[i]['key'])<8: continue
                    if difflib.SequenceMatcher(None,items[i]['key'],items[j]['key']).ratio()>=thr: par[f(i)]=f(j)
            g=collections.defaultdict(list)
            for i in ix: g[f(i)].append(i)
            out+=list(g.values())
    return out
def name_of(items,idx):
    rep=sorted(idx,key=lambda i:items[i]['e'])[-1]; it=items[rep]
    if it['k']=='short': return f"{short_stem(it['stem'])}→{it['ans'][:24]}"
    return f"{short_stem(it['stem'],30)}（{KIND_LABEL[it['k']]}）"
REF_FILES=['data/master/principle_links.yaml','data/master/qpoint_chapters.yaml','data/master/new_chapter_candidates.yaml','data/master/book_map.yaml']
def remap_refs(mp):
    """吸収された問題論点のIDを、残ったIDに付け替える（原理の紐づけ・章の割り当て・新章の候補・章の対応表の points）"""
    if not mp: return
    import os
    pat=re.compile(r'qp-[a-z]+-\d{4}')
    for f in REF_FILES:
        if not os.path.exists(f): continue
        t=open(f,encoding='utf-8').read(); t2=pat.sub(lambda m:mp.get(m.group(0),m.group(0)),t)
        if t2!=t:
            d=yaml.safe_load(t2)
            def dedupe(x):
                if isinstance(x,list): 
                    out=[];[out.append(v) for v in map(dedupe,x) if v not in out or isinstance(v,(dict,list))]; return out
                if isinstance(x,dict): return {k:dedupe(v) for k,v in x.items()}
                return x
            d=dedupe(d)
            head=''.join(l for l in t2.split('\n',3)[:0])
            comments=[l for l in t.split('\n') if l.startswith('#')]
            open(f,'w',encoding='utf-8').write(('\n'.join(comments)+'\n' if comments else '')+yaml.safe_dump(d,allow_unicode=True,sort_keys=False,width=1000))
def copy_refs(sp):
    """束が分かれたとき、新しい問題論点にも、元の問題論点と同じ参照（原理の紐づけ・章の割り当て・新章の候補・章の対応表の points）を付ける"""
    if not sp: return
    import os
    for f in REF_FILES:
        if not os.path.exists(f): continue
        t=open(f,encoding='utf-8').read(); d=yaml.safe_load(t); ch=[False]
        def walk(x):
            if isinstance(x,list):
                for old,new in sp.items():
                    if old in x and new not in x: x.append(new); ch[0]=True
                for v in x: walk(v)
            elif isinstance(x,dict):
                for v in x.values(): walk(v)
        walk(d)
        if ch[0]:
            comments=[l for l in t.split('\n') if l.startswith('#')]
            open(f,'w',encoding='utf-8').write(('\n'.join(comments)+'\n' if comments else '')+yaml.safe_dump(d,allow_unicode=True,sort_keys=False,width=1000))
def main():
    m=yaml.safe_load(open(PATH,encoding='utf-8')); items=collect()
    exist={}   # 既存の問題論点：メンバー → id
    for p in m['points']:
        if p['id'].startswith('qp-'):
            for k in p['members']: exist[(p['subject'],k)]=p['id']
    byid={p['id']:p for p in m['points']}
    nxt=collections.defaultdict(int)
    for p in m['points']:
        if p['id'].startswith('qp-'): nxt[p['subject']]=max(nxt[p['subject']],int(p['id'].split('-')[-1]))
    gs=groups(items); gs.sort(key=lambda g:(items[g[0]]['subj'],-len({items[i]['e'] for i in g}),-len(g),min(items[i]['e'] for i in g),items[g[0]]['n']))
    new=upd=0; absorbed={}; assigned=set(); splits={}
    gkeys=[sorted(f"{items[i]['e']}|{items[i]['n']}|0" for i in g) for g in gs]
    # IDの引き継ぎ：以前の問題論点と、メンバーがいちばん多く重なる束に、そのIDを渡す（束が分かれても、元のテーマが、元のIDを保つ）
    cand=[]
    for gi,g in enumerate(gs):
        s=items[g[0]]['subj']; cnt=collections.Counter(exist[(s,k)] for k in gkeys[gi] if (s,k) in exist)
        for old,c in cnt.items(): cand.append((c,gi,old))
    cand.sort(key=lambda x:(-x[0],x[2],x[1])); gid={}; used=set()
    for c,gi,old in cand:
        if gi in gid or old in used: continue
        gid[gi]=old; used.add(old)
    for gi,g in enumerate(gs):
        s=items[g[0]]['subj']; keys=gkeys[gi]
        if gi in gid:
            pid=gid[gi]; p=byid[pid]
            if sorted(set(keys))!=sorted(p['members']): p['members']=sorted(set(keys)); upd+=1
        else:
            olds=collections.Counter(exist[(s,k)] for k in keys if (s,k) in exist)   # 以前の束から分かれた場合は、元のIDの参照（原理・章）を引き継ぐ
            nxt[s]+=1; pid=f'qp-{s}-{nxt[s]:04d}'
            if olds: splits[pid]=sorted(olds.items(),key=lambda x:(-x[1],x[0]))[0][0]
            p=dict(id=pid,subject=s,name=name_of(items,g),theme='',kind='question',members=keys); m['points'].append(p); byid[pid]=p; new+=1
        assigned.add(pid)
        gid[gi]=pid
    # どの束にも引き継がれなかった以前のID：メンバーがいちばん多く移った束に、吸収する（参照を付け替える）
    mem2g={}
    for gi,keys in enumerate(gkeys):
        for k in keys: mem2g[(items[gs[gi][0]]['subj'],k)]=gid[gi]
    for p in m['points']:
        if p['id'].startswith('qp-') and p['id'] not in assigned:
            cnt=collections.Counter(mem2g[(p['subject'],k)] for k in p['members'] if (p['subject'],k) in mem2g)
            if cnt: absorbed[p['id']]=sorted(cnt.items(),key=lambda x:(-x[1],x[0]))[0][0]

    # 吸収された論点・どの束にも入らなくなった論点は、消す（吸収されたものは、参照を付け替える）
    gone={p['id'] for p in m['points'] if p['id'].startswith('qp-') and p['id'] not in assigned}
    m['points']=[p for p in m['points'] if p['id'] not in gone]
    # 名前は、束の最新の問題から付け直す（吸収・追加で変わるため）
    for g in gs:
        s=items[g[0]]['subj']; pid=next(p['id'] for p in m['points'] if p['id'].startswith('qp-') and p['subject']==s and f"{items[g[0]]['e']}|{items[g[0]]['n']}|0" in p['members'])
        byid[pid]['name']=name_of(items,g)
    remap_refs(absorbed)
    copy_refs(splits)
    # 頻出テーマ（関係法令）：選択肢の論点と同じ規則（data/master/points/<科目>.py）で、問題文＋正答から付ける
    txt={}
    for it in items: txt[(it['subj'],f"{it['e']}|{it['n']}|0")]=it['stem']+' '+it['ans']
    for p in m['points']:
        if not p['id'].startswith('qp-') or p.get('theme'): continue
        rules=PT.load_rules(p['subject'])
        if not rules: continue
        for k in sorted(p['members'],reverse=True):
            _,_,th=PT.assign(rules,txt.get((p['subject'],k),''))
            if th: p['theme']=th; break
    open(PATH,'w',encoding='utf-8').write(yaml.safe_dump(m,allow_unicode=True,sort_keys=False,width=1000))
    c=collections.Counter(p['subject'] for p in m['points'] if p['id'].startswith('qp-'))
    print('問題論点：新規',new,'更新',upd,'吸収',len(absorbed),'分割',len(splits),'／合計',sum(c.values()),dict(c),'／対象の問題',len(items))
if __name__=='__main__': main()
