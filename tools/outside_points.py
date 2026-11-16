"""章の論点が2つ以上入る問（選択肢単位）で、正答の選択肢が、章の外の論点になっているものを並べる。
使い方（リポジトリのルートで）： python3 tools/outside_points.py bk-xxx-0001 [bk-…]
同じ事実の誤りの形が、別の章・章なしに落ちていないかを、パックの前に見る。
"""
import sys,re,collections; sys.path.insert(0,'tools')
from srch import *
from point_inspect import members
def outside(ch):
    s=ch.split('-')[1]; ids=set(chids(ch)); qs=collections.Counter()
    for p in ids:
        for k in members(p):
            e,n,i=k.split('|'); qs[(e,n)]+=1
    out=[]
    for (e,n),c in sorted(qs.items()):
        if c<2: continue
        x=q(s,e,n); fr=x.get('freq') or {}
        if fr.get('kind')!='choice' or not isinstance(x['answer'],int): continue
        p=root(fr['points'][x['answer']-1])
        if p not in ids:
            out.append(f"{e}|{n} 正答{x['answer']} {p} {len(kai(p))}回 {where(p)} :: {re.sub(chr(10),'',str(x['choices'][x['answer']-1]))[:90]}")
    return out
if __name__=='__main__':
    for ch in sys.argv[1:]:
        print('==',ch); print('\n'.join(outside(ch)))
