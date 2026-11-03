#!/usr/bin/env python3
"""ガイドブックの目次（物質別各論）から、物質×測定方法の一覧を作り、本文から、捕集材・流量・波長・検出器などを、拾う。
使い方: python3 tools/build_substances.py   → data/master/substances/<tokka|kinzoku>.yaml
入力: /tmp/GB3.txt, /tmp/GB4.txt（OCRのXMLをページごとのテキストにしたもの。<<pN>> の区切り）
注意：OCRの誤りがあるので、抽出した値は「要確認」。ページ番号をたどって、ガイドブックで確認すること。"""
import re,yaml,collections,sys
SRC={'tokka':('/tmp/GB3.txt','ガイドブック3 特定化学物質関係（金属類を除く）'),'kinzoku':('/tmp/GB4.txt','ガイドブック4 金属類')}
def pages(path):
    t=open(path,encoding='utf-8').read(); parts=re.split(r'<<p(\d+)>>\n',t)
    return {int(parts[i]):parts[i+1] for i in range(1,len(parts),2)}
def clean(s): return re.sub(r'[‥…\.・\s]+$','',re.sub(r'[‥…]{2,}.*$','',s)).strip()
def toc(pg,start_marker='物質別各論'):
    # 目次：「物質別各論」から、本文の最初まで
    start=min(p for p,t in pg.items() if start_marker in t and p<30)
    subs=[]; cur=None
    for p in range(start,start+8):
        for line in pg[p].split('\n'):
            line=line.strip()
            m=re.match(r'^(\d{4})\s*([^\d…‥\.]+?)\s*[…‥\.]{0,}\s*\d*$',line)
            m2=re.match(r'^(\d{4})\s*(.+?)[…‥]{2,}',line)
            if (m2 or m) and not re.match(r'^\d{4}\s*年',line):
                mm=m2 or m
                cur=dict(code=mm.group(1),name=clean(mm.group(2)),methods=[]); subs.append(cur); continue
            m=re.match(r'^(\d{1,3})\.(\d{1,2})\s*([^\d…‥]+?)\s*[…‥]*\s*(\d{0,3})$',line)
            if m and cur is not None and m.group(3).strip():
                cur['methods'].append(dict(no=f"{m.group(1)}.{m.group(2)}",name=clean(m.group(3)),toc_page=int(m.group(4)) if m.group(4) else None))
    return subs
SORB=['球状活性炭','石油系合成活性炭','ヤシガラ活性炭','活性炭','シリカゲル','ポーラスポリマー','ガラス繊維ろ紙','ろ紙','ミゼットインピンジャー','小型ガス吸収管','インピンジャー','捕集袋','真空捕集瓶','フロリジル','Tenax','XAD','ヒドロキシルアミン','2-ピペリジン','メンブランフィルター','石英繊維','テドラーバッグ']
DET=['FID','ECD','FTD','FPD','PID','TCD','GC-MS','質量分析','紫外吸光','蛍光検出','電気化学','吸光光度','蛍光光度','原子吸光','重量分析','ICP-MS','ICP-AES']
SOLV=['二硫化炭素','アセトニトリル','アセトン','メタノール','エタノール','ヘキサン','トルエン','酢酸エチル','エチルエーテル','ジクロロメタン','水酸化ナトリウム溶液','精製水','塩酸','硫酸','硝酸']
def sections(pg,first_body):
    """本文を、(物質コード, 物質名, 方法番号, 方法名, 本文) の列に分ける"""
    lines=[]
    for p in sorted(pg):
        if p<first_body: continue
        for l in pg[p].split('\n'): lines.append((p,l.strip()))
    out=[]; sub=None; meth=None; buf=[]
    def flush():
        if meth and buf: out.append(dict(**meth,text='\n'.join(b for _,b in buf),pages=sorted({p for p,_ in buf})))
    for p,l in lines:
        m=re.match(r'^(\d{4})\s*(.+)$',l)
        if m and not re.match(r'^\d{4}\s*年',l) and len(m.group(2))<=24 and 'CAS' not in m.group(2):
            sub=(m.group(1),m.group(2).strip()); continue
        m=re.match(r'^(\d{1,2})\.(\d{1,2})\s*(固体|直接|液体|ろ過|検知管|固体捕集|相補)([^\d]{0,40})$',l)
        if m and sub and int(m.group(1))>0:
            flush(); meth=dict(code=sub[0],name=sub[1],no=f'{m.group(1)}.{m.group(2)}',method=(m.group(3)+m.group(4)).strip()); buf=[]; continue
        if meth: buf.append((p,l))
    flush(); return out
def principle(text):
    """方法の『原理』の段落（次の小見出し N.M.2 の手前まで）"""
    m=re.search(r'\d+\.\d+\.1\s*原\s*理\s*\n(.*?)(?=\n\d+\.\d+\.2|\Z)',text,re.S)
    return (m.group(1) if m else text[:600])[:900]
def facts(text):
    t=re.sub(r'\s+','',principle(text).replace('ℓ','L').replace('l/min','L/min'))
    def top(items,n=3):
        c=collections.Counter(items); return [k for k,_ in c.most_common(n)]
    sorb=[x for x in SORB if x in t][:4]
    solv=top(re.findall('('+'|'.join(SOLV)+r')(?:\d*mL)?(?:で|を用いて|を用い)(?:脱着|抽出|溶出)',t),3)
    det=[x for x in DET if x in t][:4]
    wl=top([m+'nm' for m in re.findall(r'(\d{3}(?:\.\d)?)nm',t)],2)
    return dict(捕集材=sorb,脱着_抽出=solv,検出=det,波長=wl)
NAME_FIX={'3031':'ペンタクロルフェノールおよびそのナトリウム塩','3019':"3,3'-ジクロロ-4,4'-ジアミノジフェニルメタン（MOCA）",'3038':'1,1-ジメチルヒドラジン','3011':'オルト-トリジンおよびその塩','3025':'パラ-ジメチルアミノアゾベンゼン','3026':'パラ-ニトロクロルベンゼン','3004':'アルファ-ナフチルアミンおよびその塩','3012':'オルト-フタロジニトリル','3028':'ベータ-プロピオラクトン'}
ALIASES2={'':['鉛'],'弗化水素':['フッ化水素'],'沃化メチル':['ヨウ化メチル'],'ペンタクロルフェノール':['ペンタクロロフェノール'],'パラーニトロクロルベンゼン':['p-ニトロクロロベンゼン','パラ-ニトロクロロベンゼン','p-ニトロクロルベンゼン'],
 'ベータープロピオラクトン':['β-プロピオラクトン','ベータ-プロピオラクトン'],'パラージメチルアミノアゾベンゼン':['p-ジメチルアミノアゾベンゼン','パラ-ジメチルアミノアゾベンゼン'],'ジクロルベンジジン':['ジクロロベンジジン'],
 '1.1-ジメチルヒドラジン':['1,1-ジメチルヒドラジン'],'トリレンジイソシアネート':['トルエンジイソシアネート','TDI'],'3,3\'-ジクロロ-4,4-ジアミノジフェニルメタン':['MOCA','3,3\'-ジクロロ-4,4\'-ジアミノジフェニルメタン'],
 'エチレンオキシド':['酸化エチレン'],'砒素':['ヒ素'],'オルトートリジン':['o-トリジン','オルト-トリジン'],'オルト-フタロジニトリル':['o-フタロジニトリル'],'ジアニシジン':['o-ジアニシジン']}
ALIASES={'アルファーナフチルアミン':['アルファ-ナフチルアミン','α-ナフチルアミン','アルファ―ナフチルアミン'],'ベータ-ナフチルアミン':['β-ナフチルアミン','ベータ―ナフチルアミン'],
 'オルトートリジン':['オルト-トリジン','o-トリジン','オルト―トリジン'],'オルトーフタロジニトリル':['オルト-フタロジニトリル','o-フタロジニトリル','オルト―フタロジニトリル'],
 'パラ-ニトロクロロベンゼン':['p-ニトロクロロベンゼン','パラ―ニトロクロロベンゼン'],'塩素化ビフェニル':['PCB','塩素化ビフェニル（PCB）'],
 '硫酸ジメチル':['硫酸ジメチル'],'ホルムアルデヒド':['ホルムアルデヒド','ホルマリン']}
def _n(x): return re.sub(r'[ー―－\-‐−]','',x)
_ALL={}
for _k,_v in list(ALIASES.items())+list(ALIASES2.items()): _ALL.setdefault(_n(_k),[]).extend(_v)
def key_names(name):
    base=re.sub(r'[（(].*?[）)]','',name); base=re.sub(r'およびその.*$|及びその.*$|および$|及び$','',base).strip()
    if base=='' and '鉛' in name: base='鉛'
    names={base,re.sub(r'[ー―－]','-',base)}|set(_ALL.get(_n(base),[]))
    if '鉛' in name and 'アルキル鉛' in name: names.add('鉛')
    names.discard('')
    return sorted(n for n in names if len(n)>=2 or n=='鉛')
def build(key):
    path,book=SRC[key]; pg=pages(path)
    first=min(p for p,t in pg.items() if p>14 and re.search(r'(^|\n)\s*(3001|4001)',t) and ('アクリルアミド' in t or 'カドミウム' in t))
    tocs=toc(pg); S=sections(pg,first); seen=set(); U=[]
    for x in S:
        k=(x['code'],x['no'])
        if k in seen: continue
        seen.add(k); U.append(x)
    offset=first-int(next((m['toc_page'] for s_ in tocs for m in s_['methods'] if m['toc_page']),first))  # 目次のページ → OCRのページ番号の差
    # 物質名：本文の見出しを優先（OCRの欠落を補う）
    names={}
    for x in U: names.setdefault(x['code'],NAME_FIX.get(x['code'],re.sub(r'\d+$','',x['name'])))
    subs={}
    for x in U:
        d=subs.setdefault(x['code'],dict(code=x['code'],name=names[x['code']],match=key_names(names[x['code']]),methods=[]))
        f=facts(x['text'])
        d['methods'].append(dict(no=x['no'],method=re.sub(r'(?<=法)[―一‐−ー](?=[^\s])','-',x['method']),pages=[x['pages'][0]-offset,x['pages'][-1]-offset],
            捕集材=f['捕集材'],脱着_抽出=f['脱着_抽出'],検出=f['検出'],波長=f['波長']))
    # 目次にあって本文で拾えなかった物質（名前だけ）
    for t in tocs:
        if t['code'] not in subs and t['name'] and re.match(r'^[3-4]0',t['code']):
            subs[t['code']]=dict(code=t['code'],name=t['name'],match=key_names(t['name']),methods=[dict(no=m['no'],method=m['name'],pages=[m['toc_page']] if m['toc_page'] else [],捕集材=[],脱着_抽出=[],検出=[],波長=[]) for m in t['methods']])
    return dict(book=book,description='ガイドブックの目次・本文から作成（OCR）。値は要確認。ページ番号は、本のページ（目次の番号）。',substances=sorted(subs.values(),key=lambda d:d['code']))
if __name__=='__main__':
    for key in SRC:
        d=build(key); open(f'data/master/substances/{key}.yaml','w',encoding='utf-8').write(yaml.safe_dump(d,allow_unicode=True,sort_keys=False,width=1000))
        print(key,'物質',len(d['substances']),'方法',sum(len(x['methods']) for x in d['substances']))
        for x in d['substances']: print('  ',x['code'],x['name'],'/'.join(m['no'] for m in x['methods']))
