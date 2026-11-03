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
                key=CF.norm(q['stem'])[:70] if k=='calc' else CF.norm(q['stem'])[:60]+'|'+atxt
                out.append(dict(subj=subj,e=e,n=q['num'],k=k,key=key,stem=q['stem'],ans=clean(q['choices'][a[0]-1])))
    return out
def groups(items):
    """同じ科目・同じ形式で、判定と同じ類似度のものを、1つにまとめる（連結成分）"""
    par=list(range(len(items)))
    def f(i):
        while par[i]!=i: par[i]=par[par[i]]; i=par[i]
        return i
    by=collections.defaultdict(list)
    for i,it in enumerate(items): by[(it['subj'],it['k'])].append(i)
    for (s,k),ix in by.items():
        thr=CF.THR_CALC if k=='calc' else CF.THR_Q
        for a in range(len(ix)):
            for b in range(a+1,len(ix)):
                i,j=ix[a],ix[b]
                if items[i]['e']==items[j]['e'] or len(items[i]['key'])<8: continue
                if difflib.SequenceMatcher(None,items[i]['key'],items[j]['key']).ratio()>=thr: par[f(i)]=f(j)
    g=collections.defaultdict(list)
    for i in range(len(items)): g[f(i)].append(i)
    return list(g.values())
def name_of(items,idx):
    rep=sorted(idx,key=lambda i:items[i]['e'])[-1]; it=items[rep]
    if it['k']=='short': return f"{short_stem(it['stem'])}→{it['ans'][:24]}"
    return f"{short_stem(it['stem'],30)}（{KIND_LABEL[it['k']]}）"
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
    new=upd=0
    for g in gs:
        s=items[g[0]]['subj']; keys=sorted(f"{items[i]['e']}|{items[i]['n']}|0" for i in g)
        ids={exist[(s,k)] for k in keys if (s,k) in exist}
        if ids:
            pid=sorted(ids)[0]; p=byid[pid]
            if sorted(set(p['members'])|set(keys))!=sorted(p['members']): p['members']=sorted(set(p['members'])|set(keys)); upd+=1
        else:
            nxt[s]+=1; pid=f'qp-{s}-{nxt[s]:04d}'
            p=dict(id=pid,subject=s,name=name_of(items,g),theme='',kind='question',members=keys); m['points'].append(p); byid[pid]=p; new+=1
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
    print('問題論点：新規',new,'更新',upd,'／合計',sum(c.values()),dict(c),'／対象の問題',len(items))
if __name__=='__main__': main()
