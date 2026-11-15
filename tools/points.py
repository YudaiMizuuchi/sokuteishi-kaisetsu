#!/usr/bin/env python3
"""論点ルールの読み込みと、選択肢への割り当て。ルールは data/master/points/<科目>.py に書く。
ルール：(論点ID, 頻出テーマ, 論点名, 含む条件, 除く条件[, 'KEY:正規表現'])。上から順に、最初に当てはまったものを採用する。
'KEY:' があると、その正規表現の最初のグループ（物質名など）で、論点を細かく分ける（例：アンモニアの区分）。"""
import os,re
def load_rules(subj):
    p=f'data/master/points/{subj}.py'
    if not os.path.exists(p): return []
    ns={}; exec(open(p,encoding='utf-8').read(),ns); return ns['R']
def _key(k):
    k=k.strip().replace('アルファ','α').replace('ベータ','β').replace('オルト','o').replace('パラ','p').replace('弗化','フッ化')
    return re.sub(r'[\-－\s]','',k)
def assign(rules,text):
    t=re.sub(r'\s+','',str(text))
    for r in rules:
        pid,theme,name,inc,exc=r[:5]; key=r[5] if len(r)>5 else None
        if re.search(inc,t) and not (exc and re.search(exc,t)):
            if key and key.startswith('KEY:'):
                m=re.search(key[4:],t)
                if not m: continue
                k=_key(m.group(1)); return f'{pid}:{k}',f'{k}の区分（第○類物質など）',theme
            return pid,name,theme
    return None,None,None
