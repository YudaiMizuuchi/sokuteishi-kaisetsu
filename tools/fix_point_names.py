#!/usr/bin/env python3
"""論点名のうち、文の途中で「…」で切れているものを、代表の選択肢の全文から作り直す（名前だけを直す。IDと所属は変えない）。
規則：旧い名前の冒頭と一致する所属選択肢の全文（末尾の「。」を除く）を、名前にする。LIMIT字を超えるものだけ、読点で区切って「…」を付ける。一致する選択肢がなければ、変えない。
「（誤りの記述）」の付記は、残す（その論点の記述が誤りであることを示す）。使い方: python3 tools/fix_point_names.py [--apply]"""
import yaml,re,sys,glob
LIMIT=100
APPLY='--apply' in sys.argv
pts=yaml.safe_load(open('data/master/points.yaml',encoding='utf-8'))
cache={}
def choice(subj,key):
    e,n,i=key.split('|')
    k=(subj,e)
    if k not in cache: cache[k]=yaml.safe_load(open(f'data/exams/{e}/{subj}.yaml',encoding='utf-8'))
    for q in cache[k]['questions']:
        if str(q['num'])==n:
            c=q.get('choices') or []
            if int(i)<=len(c): return re.sub(r'\s+',' ',re.sub(r'\$([^$]*)\$',r'\1',re.sub(r'<[^>]+>','',str(c[int(i)-1])))).strip()
    return ''
def newname(p):
    """旧い名前（先頭が同じ選択肢の冒頭）と一致する所属選択肢の、全文を使う（一致するものがなければ、変えない）。長すぎる文だけ、読点で区切って「…」を付ける"""
    n=p['name']; suffix='（誤りの記述）' if '（誤りの記述）' in n else ''
    stem=re.sub(r'\s','',n.replace('（誤りの記述）','').rstrip('…'))
    for k in sorted(p['members'],reverse=True):
        t=choice(p['subject'],k)
        if t and re.sub(r'\s','',t).startswith(stem):
            t=t.rstrip('。')
            if len(t)>LIMIT:
                cut=t.rfind('、',0,LIMIT-10)
                t=(t[:cut] if cut>=30 else t[:LIMIT-10])+'…'
            return t+suffix
    return None
ch=0;out=[]
for p in pts['points']:
    if p.get('merged_into') or p['id'].startswith('qp-') or '…' not in p['name']: continue
    nn=newname(p)
    if nn and nn!=p['name']:
        ch+=1
        if len(out)<14 and ch%97==1: out.append((p['id'],p['name'],nn))
        if APPLY: p['name']=nn
print('変更',ch)
for o in out: print(o[0][-9:],'\n  旧:',o[1],'\n  新:',o[2])
if APPLY: open('data/master/points.yaml','w',encoding='utf-8').write(yaml.safe_dump(pts,allow_unicode=True,sort_keys=False,width=1000)); print('書き込みました')
