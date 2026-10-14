#!/usr/bin/env python3
"""Download selected originals and previews from the company NAS, never Windows."""
from pathlib import Path
import argparse,json,re
from kb_client import KBClient
def main():
    p=argparse.ArgumentParser();p.add_argument('--base-url',default=None);p.add_argument('--case-id',action='append',required=True);p.add_argument('--page',action='append',default=[]);p.add_argument('--out',required=True);args=p.parse_args();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    client=KBClient(args.base_url)
    if len(args.case_id)>10:raise ValueError('每次最多取回10个候选')
    selected={}
    for page in args.page:
        aid,num=page.rsplit(':',1);selected.setdefault(aid,[]).append(int(num))
    records=[];sections=['# 项目参考案例\n\n以下是从公司NAS取回的真实资料。匹配理由应由WorkBuddy根据项目要求补充；不代表已执行效果。']
    for aid in args.case_id:
        if not re.fullmatch(r'[\w-]{1,100}',aid):raise ValueError('非法案例ID')
        a=client.asset(aid);name=re.sub(r'[\\/:*?"<>|]','_',a['title'])[:70]+'_'+aid;original=out/'原件'/(name+Path(a['original_path']).suffix);preview=out/'预览'/(name+Path(a['preview_path']).suffix);client.download(a['original_path'],original);client.download(a['preview_path'],preview)
        media=a.get('media',{});video=None
        if media.get('video_path'):
            video=out/'视频'/(name+Path(media['video_path']).suffix);client.download(media['video_path'],video)
        pages=[]
        for num in selected.get(aid,[]):
            page=next((x for x in a['pages'] if x['page']==num),None)
            if not page:raise ValueError('所选页不存在')
            target=out/'预览'/f'{name}_第{num}页{Path(page["image_path"]).suffix}' if page['image_path'] else out/'正文'/f'{name}_第{num}段.md'
            if page['image_path']:client.download(page['image_path'],target)
            else:target.parent.mkdir(parents=True,exist_ok=True);target.write_text(page['text'],encoding='utf-8')
            pages.append({'page':num,'file':str(target),'text':page['text'],'text_source':page['text_source']})
        records.append({'id':aid,'title':a['title'],'original':str(original),'preview':str(preview),'video':str(video) if video else None,'online_video':media.get('online_video'),'pages':pages,'visual':a.get('visual'),'source':'公司NAS','url':client.file_url(a['original_path'])})
        sections.append(f"## {a['title']}\n\n![原图/预览]({preview.relative_to(out).as_posix()})\n\n[方案原件]({original.relative_to(out).as_posix()}) · [NAS入口]({client.file_url(a['original_path'])})\n\n出处：{a['source_label']}\n\n历史资料，适配条件与执行状态需核对。")
    (out/'参考清单.md').write_text('\n\n'.join(sections),encoding='utf-8');(out/'附件清单.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));print(json.dumps({'references':len(records),'attachment_manifest':str(out/'附件清单.json'),'source':'company NAS only'},ensure_ascii=False))
if __name__=='__main__':main()
