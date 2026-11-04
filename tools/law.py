#!/usr/bin/env python3
"""data/law/*.txt（e-Govの法令のRTFをテキストにしたもの）から、条文を引く。
使い方: python3 tools/law.py <法令名の一部> <条>  例: python3 tools/law.py 粉じん 26   python3 tools/law.py 特定化学 36の2
Python から: import law; law.article('粉じん', '26')"""
import re,glob,sys
KAN='〇一二三四五六七八九'
def kan(n):
    n=int(n); s=''
    if n>=100: s+=(KAN[n//100] if n//100>1 else '')+'百'; n%=100
    if n>=10: s+=(KAN[n//10] if n//10>1 else '')+'十'; n%=10
    if n: s+=KAN[n]
    return s or '〇'
def art_label(a):
    parts=str(a).split('の'); return '第'+kan(parts[0])+'条'+''.join('の'+kan(x) for x in parts[1:])
_cache={}
def load(name):
    fs=[f for f in glob.glob('data/law/*.txt') if name in f]
    if not fs: raise SystemExit('見つからない: '+name)
    f=fs[0]
    if f not in _cache: _cache[f]=open(f,encoding='utf-8').read().split('\n')
    return _cache[f]
def article(name,a):
    L=load(name); lab=art_label(a); out=[]; on=False
    for i,l in enumerate(L):
        s=l.strip()
        if re.match(r'^第[〇一二三四五六七八九十百]+条(の[〇一二三四五六七八九十百]+)*[　 ]',s) or re.match(r'^第[〇一二三四五六七八九十百]+条(の[〇一二三四五六七八九十百]+)*$',s):
            head=re.match(r'^(第[〇一二三四五六七八九十百]+条(?:の[〇一二三四五六七八九十百]+)*)',s).group(1)
            if on: break
            if head==lab:
                on=True
                if i>0 and re.match(r'^[（(].*[）)]$',L[i-1].strip()): out.append(L[i-1].strip())
        if on: out.append(s)
    return '\n'.join(x for x in out if x)
if __name__=='__main__':
    print(article(sys.argv[1],sys.argv[2]))
