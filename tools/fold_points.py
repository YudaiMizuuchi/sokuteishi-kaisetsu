"""論点ごとに、選択肢を（正誤・問の出だし・文）でまとめて出す。
使い方: python3 tools/fold_points.py bk-xxx [最小の回数]　／　from fold_points import fold; fold('pt-…')
★は、その選択肢が正答の回。"""
import sys,re,collections; import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from srch import *
from point_inspect import members as _m
def fold(pid,sw=18,cw=64):
    s=pts[pid]['subject']; d=collections.OrderedDict()
    for k in _m(pid):
        e,n,i=k.split('|'); x=q(s,e,n); i=int(i); fr=x.get('freq') or {}
        t=(fr.get('truths') or '?????')[i-1] if i>0 and fr.get('kind')=='choice' else '・'
        st=re.sub(r'\s+','',str(x['stem']))[:sw]
        c=re.sub(r'\s+','',str(x['choices'][i-1]))[:cw] if i>0 else '⇒'+re.sub(r'\s+','',str(x['choices'][x['answer']-1] if isinstance(x['answer'],int) else x['answer']))[:cw]
        ans = (i>0 and x['answer']==i)
        d.setdefault((t,st,c),[]).append(e+('★' if ans else ''))
    o=[f"## {pid} {len(kai(pid))}回 {pts[pid]['name'][:60]}"]
    for (t,st,c),es in d.items(): o.append(f"  {t}×{len(es)} [{st}] {c} {' '.join(x[2:] for x in es) if len(es)<4 else ''}")
    return '\n'.join(o)
if __name__=='__main__':
    ch=sys.argv[1]; mn=int(sys.argv[2]) if len(sys.argv)>2 else 1
    out=[]
    for p in sorted(chids(ch),key=lambda p:-len(kai(p))):
        if len(kai(p))>=mn: out.append(fold(p))
        else: out.append(f"-- {p} {len(kai(p))}回 {pts[p]['name'][:50]}")
    print('\n'.join(out))
