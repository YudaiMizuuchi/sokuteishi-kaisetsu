"""書き直し用のパックを作る（chapter_pack2.py の出力に、問題論点の全問と、例題の候補を足す）。
使い方（リポジトリのルートで）: python3 -c "import sys;sys.path.insert(0,'tools');import rewrite_pack as r;print(r.mk('rw25','bk-xxx',add=[...],qps=[...],qtitle='…',drop=[...])[0])"
出力は packs/<番号>_<章ID>.md。"""
import sys,re,subprocess; import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from srch import *
from point_inspect import members as _m
def strip(s): return re.sub(r' (pt|qp)-[a-z]+-\d{4}','',s)
def qtext(s,e,n): return f"### `{e}|{s}|{n}`（{era(e)}）\n"+strip(full(s,e,int(n)))+"\n"
def mk(no,ch,add=(),qps=(),qtitle='',drop=()):
    s=ch.split('-')[1]
    cmd=['python3','tools/chapter_pack2.py',ch]+(['--add',','.join(add)] if add else [])+(['--drop',','.join(drop)] if drop else [])
    r=subprocess.run(cmd,capture_output=True,text=True); out=r.stdout; err=r.stderr
    rows=[l.split('\t') for l in err.strip().split('\n')[1:]]
    ids=[x[1] for x in rows if len(x)>1 and x[1].startswith('pt-')]
    if qps:
        ks=sorted({tuple(k.split('|')[:2]) for p in qps for k in _m(p)},reverse=True)
        out+=f"\n\n## 付録　{qtitle}（全問。新しい順）\n\n"+'\n'.join(qtext(s,e,n) for e,n in ks)
    cand=set()
    for p in ids:
        for k in _m(p):
            e,n,i=k.split('|'); x=q(s,e,n)
            if int(i)>0 and x['answer']==int(i) and ((x.get('freq') or {}).get('truths') or '?????')[int(i)-1]=='誤': cand.add((e,n))
    cand=sorted(cand,reverse=True)[:6]
    out+="\n\n## 付録　例題の候補（この章の表の論点の誤りの形が、正答の問。新しい順）\n\n"+'\n'.join(qtext(s,e,n) for e,n in cand)
    open(f'packs/{no}_{ch}.md','w',encoding='utf-8').write(out)
    return err,len(out),cand
