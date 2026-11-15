#!/usr/bin/env python3
"""ランクがD以外の問題で、参考書の章が付かないものを、キーワードの規則で、章に割り当てる（結果：data/master/qpoint_chapters.yaml）。
対象：①問題論点（qp-…）：物質名・用語を選ぶ問題、計算・穴埋め・組合せの問題　②正答の論点（pt-…）が、どの章にも入っていない、記述の正誤を選ぶ問題。
book_map.yaml（設計書の章の対応表）は書き換えず、この表で、章の論点（points）に足す。tools/book_coverage.py と tools/link_book_chapters.py が読む。
どの規則にも当たらないものは、/tmp/qpoint_unassigned.md に出す（設計書側で、章を足すか、規則を足す）。
使い方: python3 tools/assign_qpoints.py"""
import sys,io,re,yaml,collections
sys.path.insert(0,'tools')
_so=sys.stdout; sys.stdout=io.StringIO()
import compute_freq as CF, book_coverage as BC
sys.stdout=_so
OUT=BC.QPC_PATH
# 規則：科目ごとに、(正規表現, 章ID)。上から順に、最初に当たったものを採用する。対象の本文＝問題文＋正答（空白なし）
RULES={
 'hourei':[(r'特別有機溶剤','bk-hourei-th13'),(r'第[1１一]種有機溶剤','bk-hourei-th12'),(r'製造に際し.*許可','bk-hourei-th13'),
           (r'特別の教育','bk-hourei-th09'),(r'規格|登録を受けた者|型式検定|防毒マスク|呼吸用保護具','bk-hourei-tp06')],
 'design':[(r'個人サンプリング|C・D測定','bk-design-tp03'),(r'遊離けい酸|粉じん作業','bk-design-tp11'),(r'測定点|単位作業場所','bk-design-tp04'),
           (r'放射性物質の捕集','bk-design-tp10'),(r'蒸気圧|沸点|融点|密度|液体でない','bk-design-tp13')],
 'bunseki':[(r'理論段|ガスクロマトグラ|GC','bk-bunseki-tp05'),(r'ICP|原子吸光|蛍光','bk-bunseki-tp02'),(r'標準偏差|精度|真度','bk-bunseki-tp10'),
            (r'pH|当量点|溶解度積|理想気体|放射能|Bq|単位','bk-bunseki-tp07')],
 'yuki':[(r'テーリング|OV-1|ポリエチレングリコール|PEG|固定相|カラム','bk-yuki-tp01'),(r'蒸気圧|密度|極性|2相|等量の水','bk-yuki-tp03')],
 'tokka':[(r'キャピラリーカラム|標準試料ガス|ガスクロマトグラフ|標準液|標定','bk-tokka-tp03'),(r'沸点|融点','bk-tokka-tp02')],
 'kinzoku':[(r'マンガン化合物|水に溶け','bk-kinzoku-tp07')],
 'funjin':[(r'王水添加りん酸法|りん酸法|遊離けい酸','bk-funjin-tp03')],
 'ippan':[(r'フード|局所排気','bk-ippan-fr15')],
}
def main():
    chs=BC.load_map(raw=True); byid={c['id']:c for c in chs}
    pts=BC.live_points(); sc=BC.Scorer([],pts)
    mode,_,_=sc.build(chs,use_qpc=False)      # 設計書の章だけでの収録
    res=collections.defaultdict(set); un=[]; n=0
    for subj,exams in CF.docs.items():
        for e,(f,d) in exams.items():
            for q in d['questions']:
                fr=q.get('freq') or {}
                if fr.get('level') in (None,'D') or not q.get('choices'): continue
                a=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
                if not a or not isinstance(a[0],int) or a[0]>len(q['choices']): continue
                k=CF.qkind(q)
                pid=CF._K2P.get((subj,f"{e}|{q['num']}|{a[0]}")) if k=='stmt' else CF._K2P.get((subj,f"{e}|{q['num']}|0"))
                if not pid or (subj,pid) in mode: continue
                n+=1; txt=re.sub(r'\s+','',str(q['stem'])+str(q['choices'][a[0]-1]))
                for pat,cid in RULES.get(subj,[]):
                    if re.search(pat,txt): res[cid].add(pid); break
                else: un.append((f'{e}|{subj}|{q["num"]}',fr['level'],k,txt[:50]))
    cur=yaml.safe_load(open(OUT,encoding='utf-8')) if __import__('os').path.exists(OUT) else {}
    out={c:sorted(v) for c,v in sorted(res.items())}
    open(OUT,'w',encoding='utf-8').write('# ランクD以外で、章が付かなかった論点（問題論点 qp-…を含む）の、章への割り当て（tools/assign_qpoints.py）。book_map.yaml の章の points に足して読む\n'+yaml.safe_dump(out,allow_unicode=True,sort_keys=False,width=1000))
    L=['# 規則に当たらず、章が付かない問題（ランクD以外）','']+[f'- {k}｜{lv}｜{kk}｜{t}' for k,lv,kk,t in sorted(set(un))]
    open('/tmp/qpoint_unassigned.md','w',encoding='utf-8').write('\n'.join(L))
    print('対象の問題',n,'／割り当てた論点',sum(len(v) for v in out.values()),'／章',len(out),'／規則に当たらない問題',len(set(un)))
if __name__=='__main__': main()
