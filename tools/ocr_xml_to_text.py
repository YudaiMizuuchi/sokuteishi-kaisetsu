#!/usr/bin/env python3
"""ガイドブックのOCR（XML）を、ページごとのテキストに変換する。
使い方: python3 tools/ocr_xml_to_text.py <入力.xml> <出力.txt>
  例: python3 tools/ocr_xml_to_text.py "/mnt/user-data/uploads/作業環境測定ガイドブック３_特定化学物質関係_金属類を除く__1.xml" /tmp/GB3.txt
      python3 tools/ocr_xml_to_text.py "/mnt/user-data/uploads/作業環境測定ガイドブック４_金属類_1.xml" /tmp/GB4.txt
出力：ページの区切りは <<pN>>（Nは、OCRのページ番号。本のページ番号とは、ずれる）。LINE要素のSTRINGを、ORDER順につなぐ。"""
import re,html,sys
src,dst=sys.argv[1],sys.argv[2]
t=open(src,encoding='utf-8',errors='replace').read()
pages=re.split(r'<PAGE ',t)[1:]; out=[]
for i,pg in enumerate(pages,1):
    lines=sorted(re.findall(r'<LINE [^>]*?ORDER="(\d+)"[^>]*?STRING="([^"]*)"',pg),key=lambda x:int(x[0]))
    out.append(f"<<p{i}>>\n"+'\n'.join(html.unescape(s) for o,s in lines))
open(dst,'w',encoding='utf-8').write('\n'.join(out)); print(len(pages),'ページ')
