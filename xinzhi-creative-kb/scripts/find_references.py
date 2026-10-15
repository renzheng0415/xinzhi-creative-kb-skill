#!/usr/bin/env python3
"""Read live purpose/page evidence; the calling agent interprets the project brief."""
from ensure_latest import entrypoint
if __name__ == '__main__':
    entrypoint(__file__)
import argparse
import json
from kb_client import KBClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url')
    parser.add_argument('--options', action='store_true')
    parser.add_argument('--query', default='')
    parser.add_argument('--role', action='append', default=[])
    for field in ('industry','audience','outputs','topics','visual-tone','creative-method'):
        parser.add_argument('--'+field, action='append', default=[])
    parser.add_argument('--collection', default='all', choices=['all','cases','ai_images','ai_videos','short_videos','livestreams'])
    parser.add_argument('--require-image', action='store_true')
    parser.add_argument('--limit', type=int, default=8)
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--case-id')
    parser.add_argument('--page', type=int, default=1)
    parser.add_argument('--radius', type=int, default=1)
    args = parser.parse_args(); client = KBClient(args.base_url)
    if args.options:
        result = client.request('/api/reference-options')
    elif args.case_id:
        result = client.context(args.case_id, args.page, args.radius)
    else:
        result = client.references(query=args.query, material_roles=args.role,
            industry=args.industry, audience=args.audience, outputs=args.outputs, topics=args.topics,
            visual_tone=args.visual_tone, creative_methods=args.creative_method,
            collection=args.collection, require_image=args.require_image, limit=args.limit, offset=args.offset)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
