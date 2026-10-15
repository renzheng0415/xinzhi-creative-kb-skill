#!/usr/bin/env python3
"""Use the same website filters from WorkBuddy, with no employee password."""
from ensure_latest import entrypoint
if __name__ == '__main__':
    entrypoint(__file__)
import argparse,json
from kb_client import KBClient
def main():
    p=argparse.ArgumentParser();p.add_argument('--base-url',default=None);p.add_argument('--query',default='');p.add_argument('--topics',action='append',default=[]);p.add_argument('--collection',choices=['all','cases','ai_images','ai_videos','short_videos','livestreams'],default='all');p.add_argument('--style',action='append',default=[]);p.add_argument('--industry',action='append',default=[]);p.add_argument('--audience',action='append',default=[]);p.add_argument('--outputs',action='append',default=[]);p.add_argument('--visual-tone',action='append',default=[]);p.add_argument('--creative-method',action='append',default=[]);p.add_argument('--limit',type=int,default=8);p.add_argument('--offset',type=int,default=0);p.add_argument('--options',action='store_true');p.add_argument('--include-suggestions',action='store_true');args=p.parse_args()
    client=KBClient(args.base_url)
    if args.options:
        result=client.request('/api/filters')
        result['connection']={'base_url':client.base,'source':'company NAS'}
    else:
        body={'query':args.query,'topics':args.topics,'collection':args.collection,'styles':args.style,'industry':args.industry,'audience':args.audience,'outputs':args.outputs,'visual_tone':args.visual_tone,'creative_methods':args.creative_method,'limit':args.limit,'offset':args.offset,'include_suggestions':args.include_suggestions}
        result=client.search(**body)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
