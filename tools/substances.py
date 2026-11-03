#!/usr/bin/env python3
"""物質別の暗記リスト（data/master/substances/*.yaml）と、問題の正答の選択肢を照合する。
『物質の表で解ける』の判定：正答の選択肢が、(1) リストの物質名（別名を含む）を含み、(2) 測定方法の語（捕集・分析法・検出器・脱着など）を含むこと。
verified＝その物質の表を、ガイドブック本文で確認済みか。"""
import os,re,yaml
METHOD=re.compile(r'捕集|検知管|ガスクロマトグラフ|液体クロマトグラフ|吸光光度|蛍光光度|原子吸光|ICP|FID|ECD|FTD|FPD|PID|質量分析|GC|HPLC|脱着|抽出|発色|分析法|測定法|二硫化炭素|活性炭|シリカゲル|ろ紙|ミゼット|インピンジャー|捕集液|標準物質|標準原液|検出器')
_cache={}
def load():
    if _cache: return _cache
    ver=yaml.safe_load(open('data/master/substances/verified.yaml',encoding='utf-8'))['verified'] if os.path.exists('data/master/substances/verified.yaml') else {}
    out={}
    for subj in ('tokka','kinzoku'):
        p=f'data/master/substances/{subj}.yaml'
        if not os.path.exists(p): continue
        doc=yaml.safe_load(open(p,encoding='utf-8')); L=[]
        for sb in doc['substances']:
            pats=[re.compile(r'(?<![ァ-ヶ])'+re.escape(n)+r'(?![ァ-ヶ化])') for n in (sb.get('match') or [sb['name']])]
            L.append((sb['code'],sb['name'],pats,sb['code'] in (ver.get(subj) or {})))
        out[subj]=L
    _cache.update(out); return _cache
def table_type(subject,text):
    """正答の選択肢が『物質の表で解ける』型か。戻り値：(物質コード, 確認済みか) または None"""
    L=load().get(subject)
    if not L or not text or not METHOD.search(text): return None
    for code,name,pats,verified in L:
        if any(p.search(text) for p in pats): return code,verified
    return None

def name_of(subject,code):
    import yaml
    doc=yaml.safe_load(open(f'data/master/substances/{subject}.yaml',encoding='utf-8'))
    for sb in doc['substances']:
        if sb['code']==code: return sb['name']
    return code
