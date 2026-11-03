#!/usr/bin/env python3
"""問題 → 参考書の章（book_map.yaml の章ID）の対応表 data/master/question_chapters.yaml を作る。
使い方: python3 tools/link_book_chapters.py     （章の対応表・論点・原理・物質の表を変えたら、もう一度実行する）
- p（決め手の章）：正答の選択肢の論点が、章の論点（points／principles に紐づく論点／themes）に入っている。物質表の章は、正答が物質の表で解ける問題。解法の章は、計算・穴埋め・組合せの問題。
- r（関連の章）：正答以外の選択肢の論点が入っている章（多い順）。p が空のときだけ、サイトは r の上位2章を使う。
サイトの『参考書で復習する』ボタン・章ページ・絞り込みは、この表を使う。"""
import sys,io,collections,yaml
sys.path.insert(0,'tools')
_so=sys.stdout; sys.stdout=io.StringIO()
import compute_freq as CF, substances as SB, book_coverage as BC
sys.stdout=_so
OUT='data/master/question_chapters.yaml'
KIND_ORDER={'物質表':0,'原理':1,'テーマ':2,'数値表':2,'論点':3,'解法':4}
chs=BC.load_map(); pts=BC.live_points(); sc=BC.Scorer([],pts)
by_pt=collections.defaultdict(list); by_sb=collections.defaultdict(list); by_form=collections.defaultdict(list)
order={c['id']:i for i,c in enumerate(chs)}
for c in chs:
    mode,sbs,forms=sc.build([c])
    for k in mode: by_pt[k].append(c['id'])
    for b in sbs: by_sb[b].append(c['id'])
    for f in forms: by_form[f].append(c['id'])
kind={c['id']:c['kind'] for c in chs}
def srt(ids): return sorted(set(ids),key=lambda i:(KIND_ORDER[kind[i]],order[i]))
out={}; stat=collections.Counter()
for subj,exams in CF.docs.items():
    for e,(f,d) in exams.items():
        for q in d['questions']:
            if q.get('status')!='published' or not q.get('choices'): continue
            a=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
            if not a or a[0]=='all' or not isinstance(a[0],int): continue
            k=CF.qkind(q); n=len(q['choices']); ai=a[0]-1; prim=[]; rel=collections.Counter()
            tt=SB.table_type(subj,str(q['stem'])+' '+str(q['choices'][ai])) if subj in('tokka','kinzoku') else None
            if tt and tt[1]: prim+=by_sb.get(f'sb-{subj}-{tt[0]}',[])
            if k=='stmt':
                for i in range(n):
                    pid=CF._K2P.get((subj,f"{e}|{q['num']}|{i+1}"))
                    if not pid: continue
                    for c in by_pt.get((subj,pid),[]):
                        if i==ai: prim.append(c)
                        else: rel[c]+=1
            else:
                prim+=by_form.get((subj,BC.FORMKEY[k]),[])
            prim=srt(prim); r=[c for c,_ in sorted(rel.items(),key=lambda x:(-x[1],order[x[0]])) if c not in prim][:3]
            out[f'{e}|{subj}|{q["num"]}']={'p':prim,'r':r}
            stat['決め手の章あり' if prim else ('関連の章のみ' if r else '章なし')]+=1
open(OUT,'w',encoding='utf-8').write('# 問題→参考書の章（tools/link_book_chapters.py で作る）。p＝決め手の章、r＝関連の章\n'+yaml.safe_dump(out,allow_unicode=True,sort_keys=True,width=1000,default_flow_style=None))
print(OUT,len(out),'問',dict(stat))
