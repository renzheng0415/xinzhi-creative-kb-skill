#!/usr/bin/env python3
"""Create a complete file inventory and untruncated text chunks for WorkBuddy."""
from ensure_latest import entrypoint
if __name__ == '__main__':
    entrypoint(__file__)
from pathlib import Path
import argparse,hashlib,json,re,zipfile
import xml.etree.ElementTree as ET

def text_blocks(path):
    ext=path.suffix.lower()
    if ext in ('.txt','.md','.csv','.html','.htm'):
        raw=path.read_bytes()
        for enc in ('utf-8-sig','gb18030','utf-16'):
            try:return [('正文',raw.decode(enc))],[]
            except UnicodeError:continue
        raise ValueError('文字编码无法识别')
    if ext=='.pdf':
        from pypdf import PdfReader
        reader=PdfReader(path);blocks=[];needs=[]
        for i,p in enumerate(reader.pages,1):
            t=p.extract_text() or '';blocks.append((f'第{i}页',t))
            if len(t.strip())<12:needs.append(f'第{i}页需视觉核查，可能为空页、图片页或扫描页')
        return blocks,needs
    if ext in ('.docx','.pptx','.xlsx'):
        with zipfile.ZipFile(path) as z:
            if sum(i.file_size for i in z.infolist())>200*1024*1024:raise ValueError('Office解压体量超过200MB，需原生工具读取')
            if ext=='.docx':names=['word/document.xml']
            elif ext=='.pptx':names=sorted([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)],key=lambda n:int(re.search(r'(\d+)\.xml',n).group(1)))
            else:names=[n for n in z.namelist() if n=='xl/sharedStrings.xml' or re.fullmatch(r'xl/worksheets/sheet\d+\.xml',n)]
            blocks=[]
            for i,n in enumerate(names,1):
                root=ET.fromstring(z.read(n));t='\n'.join(x.text or '' for x in root.iter() if x.tag.endswith('}t') or (ext=='.xlsx' and x.tag.endswith('}v')))
                blocks.append((f'第{i}页/结构单元',t))
            return blocks,['Office图表、插图和版式需由WorkBuddy回看原件；XLSX数字引用需回到单元格核对']
    raise ValueError('此格式需用WorkBuddy原生工具、相应Office技能或视觉读取，不能标作已读')

def main():
    p=argparse.ArgumentParser();p.add_argument('--project-root',required=True);p.add_argument('--out',required=True);args=p.parse_args()
    root=Path(args.project_root).resolve();out=Path(args.out).resolve()
    if not root.is_dir() or root==Path(root.anchor):raise ValueError('必须指定具体项目文件夹')
    out.mkdir(parents=True,exist_ok=True);records=[]
    for source in sorted(root.rglob('*')):
        if not source.is_file() or source.is_relative_to(out):continue
        rel=source.relative_to(root)
        if any(x in ('.git','node_modules','__pycache__','.ssh') for x in rel.parts) or source.name.startswith(('.env','._')) or source.name in ('.DS_Store','id_rsa'):continue
        record={'source':str(source),'relative_path':str(rel),'bytes':source.stat().st_size,'chunks':[],'issues':[]}
        if source.is_symlink():record.update(status='未读',issues=['软链接需确认归属，不跟随到其它项目'])
        else:
            try:
                blocks,issues=text_blocks(source);record['issues']=issues
                key=hashlib.sha256(str(rel).encode()).hexdigest()[:12];folder=out/'全文分块'/key;folder.mkdir(parents=True,exist_ok=True)
                for n,(label,text) in enumerate(blocks,1):
                    # Every character is retained across ordered chunks.
                    for part,start in enumerate(range(0,max(1,len(text)),9000),1):
                        f=folder/f'{n:04d}-{part:03d}.md';f.write_text(f'# {rel} · {label} · 分块{part}\n\n'+text[start:start+9000],encoding='utf-8');record['chunks'].append(str(f))
                record['status']='文字已提取，智能体待阅读'
                if not any(text.strip() for _,text in blocks):record['status']='未读：无文字，需视觉/OCR'
            except (OSError,ValueError,ImportError,zipfile.BadZipFile,ET.ParseError) as error:record.update(status='未读',issues=[str(error)])
        records.append(record)
    result={'project_root':str(root),'files':records,'file_count':len(records),'unread_count':sum(r['status'].startswith('未读') for r in records),'all_read_by_agent':False,'note':'提取不等于智能体读完。逐文件/分块阅读并补足视觉和原生格式后，才能确认全部项目资料覆盖。'}
    (out/'资料覆盖清单.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    (out/'需求提炼模板.md').write_text('# 项目需求提炼\n\n填写产品事实、客群、业务命题、甲方要求、必备出品、视觉要求、禁止项和预算/排期。每项注明原文件、页码或条款；事实与推断分开。\n\n未读资料、冲突资料和待确认项必须列出；当前为空模板，不代表已完成提炼。\n')
    print(json.dumps({'file_count':result['file_count'],'unread_count':result['unread_count'],'manifest':str(out/'资料覆盖清单.json')},ensure_ascii=False))
if __name__=='__main__':main()
