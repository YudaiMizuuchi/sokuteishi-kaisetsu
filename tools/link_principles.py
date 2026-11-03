#!/usr/bin/env python3
"""論点と原理の紐づけの候補を出す。候補は、自動では確定しない（人が、紐づけの基準で、採用するものを決める）。
基準：正答の選択肢の正誤が、その原理だけから、直接導けるときだけ紐づける。暗記が要る事実は、紐づけない。
使い方: python3 tools/link_principles.py <科目ID>   → /tmp/principle_links_<科目>.md
採用は、data/master/principle_links.yaml（原理ID: [論点ID...]）に書き、python3 tools/link_principles.py --apply で、principles.yaml の points に反映する。"""
import yaml,re,sys,collections,os
def load_all():
    pr=yaml.safe_load(open('data/master/principles.yaml',encoding='utf-8'))
    m=yaml.safe_load(open('data/master/points.yaml',encoding='utf-8'))
    return pr,m
def candidates(subj):
    pr,m=load_all(); P=[p for p in pr['principles'] if p['subject']==subj]
    # 論点の本文：所属する選択肢の本文を、問題データから引く
    import glob
    txt={}
    for f in glob.glob(f'data/exams/*/{subj}.yaml'):
        d=yaml.safe_load(open(f,encoding='utf-8')); e=f.split('/')[2]
        for q in d['questions']:
            for i,c in enumerate(q.get('choices') or [],1): txt[f"{e}|{q['num']}|{i}"]=re.sub(r'\s+','',str(c))
            a=q['answer'] if isinstance(q.get('answer'),list) else [q.get('answer')]
            if q.get('choices') and a and isinstance(a[0],int) and a[0]<=len(q['choices']):   # 問題論点（キー 回|問|0）の本文＝問題文＋正答
                txt[f"{e}|{q['num']}|0"]=re.sub(r'\s+','',str(q['stem'])+' '+str(q['choices'][a[0]-1]))
    out=[]
    for p in m['points']:
        if p['subject']!=subj or p.get('merged_into'): continue
        body=' '.join(txt.get(k,'') for k in p['members'][:6])
        hits=[]
        for pi,q in enumerate(P):
            if any(re.search(k,body) for k in q['keywords']): hits.append(pi)
        if hits: out.append((p,hits,len({k.split('|')[0] for k in p['members']})))
    return P,out
if __name__=='__main__':
    if sys.argv[1]=='--apply':
        pr,_=load_all(); links=yaml.safe_load(open('data/master/principle_links.yaml',encoding='utf-8')) or {}
        for p in pr['principles']: p['points']=sorted(links.get(p['id'],[]))
        open('data/master/principles.yaml','w',encoding='utf-8').write(yaml.safe_dump(pr,allow_unicode=True,sort_keys=False,width=1000))
        print('反映：',sum(len(p['points']) for p in pr['principles']),'件の紐づけ'); sys.exit(0)
    subj=sys.argv[1]; P,out=candidates(subj)
    lines=[f"{p['id'][-4:]}\t{n}回\t{p['name'][:36]}\t候補:"+','.join(str(h+1) for h in hits[:3]) for p,hits,n in sorted(out,key=lambda x:-x[2])]
    open(f'/tmp/principle_links_{subj}.md','w',encoding='utf-8').write('\n'.join(lines))
    allp=[p for p in yaml.safe_load(open('data/master/points.yaml',encoding='utf-8'))['points'] if p['subject']==subj and not p.get('merged_into')]
    print(subj,'論点',len(allp),'候補のある論点',len(out))
