#!/usr/bin/env python3
"""Read a case or selected source pages from the live NAS."""
import argparse
import json
from kb_client import KBClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default=None)
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--query', default='')
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--detail', action='store_true')
    args = parser.parse_args()
    if args.offset < 0 or not 1 <= args.limit <= 20:
        raise ValueError('无效页范围')
    client = KBClient(args.base_url)
    asset = client.asset(args.case_id)
    asset['links'] = client.links(asset)
    if args.detail:
        result = asset
    else:
        pages = [p for p in asset.get('pages', []) if not args.query or args.query.lower() in p.get('text', '').lower()]
        selected = pages[args.offset:args.offset + args.limit]
        for page in selected:
            page['url'] = client.file_url(page.get('image_path'))
        result = {'id': asset['id'], 'title': asset['title'], 'source_label': asset['source_label'],
                  'pages': selected, 'total': len(pages), 'links': asset['links']}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
