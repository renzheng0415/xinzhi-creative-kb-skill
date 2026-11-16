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
    parser.add_argument('--project-id')
    parser.add_argument('--query', default='')
    parser.add_argument('--role', action='append', default=[])
    for field in ('industry','audience','outputs','topics','visual-tone','creative-method'):
        parser.add_argument('--'+field, action='append', default=[])
    parser.add_argument('--collection', default='all', choices=['all','cases','ai_images','ai_videos','short_drama_skills','short_videos','livestreams'])
    parser.add_argument('--require-image', action='store_true')
    parser.add_argument('--doc-type', action='append', default=[])
    parser.add_argument('--page-type', action='append', default=[])
    parser.add_argument('--problem', action='append', default=[])
    parser.add_argument('--city', action='append', default=[])
    parser.add_argument('--district', action='append', default=[])
    parser.add_argument('--stage', action='append', default=[])
    parser.add_argument('--year', action='append', default=[])
    parser.add_argument('--year-from', type=int, default=None)
    parser.add_argument('--year-to', type=int, default=None)
    parser.add_argument('--sort', default='relevance', choices=['relevance', 'recent'])
    parser.add_argument('--no-family-group', action='store_true')
    parser.add_argument('--detail', default='brief', choices=['brief', 'full'])
    parser.add_argument('--limit', type=int, default=8)
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--case-id')
    parser.add_argument('--page', type=int, default=1)
    parser.add_argument('--radius', type=int, default=1)
    args = parser.parse_args(); client = KBClient(args.base_url)
    if args.options:
        result = client.request('/api/reference-options')
    elif args.project_id:
        result = client.project(args.project_id)
    elif args.case_id:
        result = client.context(args.case_id, args.page, args.radius)
    else:
        req = dict(query=args.query, material_roles=args.role,
            industry=args.industry, audience=args.audience, outputs=args.outputs, topics=args.topics,
            visual_tone=args.visual_tone, creative_methods=args.creative_method,
            collection=args.collection, require_image=args.require_image, limit=args.limit, offset=args.offset,
            doc_types=args.doc_type, page_types=args.page_type, problems=args.problem,
            cities=args.city, stages=args.stage, group_by_family=not args.no_family_group,
            detail=args.detail)
        if args.district:
            req['districts'] = args.district
        if args.year:
            req['years'] = args.year
        if args.year_from is not None:
            req['year_from'] = args.year_from
        if args.year_to is not None:
            req['year_to'] = args.year_to
        if args.sort != 'relevance':
            req['sort'] = args.sort
        result = client.references(**req)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
