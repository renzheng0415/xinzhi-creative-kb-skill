#!/usr/bin/env python3
"""Submit a structured Brief demand sheet to /api/references/brief (or inspect options / project card)."""
from ensure_latest import entrypoint
if __name__ == '__main__':
    entrypoint(__file__)
import argparse
import json
from pathlib import Path
from kb_client import KBClient


def build_payload_from_args(args):
    if args.brief_file:
        return json.loads(Path(args.brief_file).read_text(encoding='utf-8'))
    if args.brief_json:
        return json.loads(args.brief_json)
    if not args.query and not args.problem:
        raise ValueError('请提供 --brief-file、--brief-json，或至少传入一个 --query / --problem')
    need = {
        'label': args.label or (args.query[0] if args.query else args.problem[0]),
        'task': args.task,
        'queries': args.query,
        'problems': args.problem,
        'page_types': args.page_type,
    }
    if args.role:
        need['material_roles'] = args.role
    if args.require_image:
        need['require_image'] = True
    prefer = {}
    if args.prefer_industry:
        prefer['industry'] = args.prefer_industry
    if args.prefer_stage:
        prefer['stages'] = args.prefer_stage
    if args.prefer_audience:
        prefer['audience'] = args.prefer_audience
    if args.prefer_city:
        prefer['cities'] = args.prefer_city
    if args.prefer_recent:
        prefer['recent'] = True
    payload = {
        'needs': [need],
        'prefer': prefer,
        'collection': args.collection,
        'limit_per_need': args.limit_per_need,
    }
    if args.industry:
        payload['industry'] = args.industry
    if args.city:
        payload['cities'] = args.city
    if args.stage:
        payload['stages'] = args.stage
    if args.year_from is not None:
        payload['year_from'] = args.year_from
    if args.audience:
        payload['audience'] = args.audience
    if args.require_image:
        payload['require_image'] = True
    return payload


def main():
    parser = argparse.ArgumentParser(description='按结构化 Brief 需求单一次检索参考或读取同项目卡片')
    parser.add_argument('--base-url')
    parser.add_argument('--options', action='store_true', help='读取用途、难题/阶段/页型释义与覆盖统计')
    parser.add_argument('--project-id', help='读取项目卡及同项目策略案/主画面/楼书/VI清单')
    parser.add_argument('--brief-file', help='结构化需求单 JSON 文件路径')
    parser.add_argument('--brief-json', help='结构化需求单内联 JSON 字符串')
    parser.add_argument('--label', default='', help='单项需求的描述（命令行快捷模式）')
    parser.add_argument('--task', default='strategy', choices=['strategy', 'positioning', 'campaign', 'visual'])
    parser.add_argument('--query', action='append', default=[], help='1-4个短查询（可重复传入）')
    parser.add_argument('--problem', action='append', default=[], help='业务难题枚举（可重复传入）')
    parser.add_argument('--page-type', action='append', default=[], help='目标页面类型（可重复传入）')
    parser.add_argument('--role', action='append', default=[], help='指定资料用途（可选覆盖）')
    parser.add_argument('--industry', action='append', default=[], help='硬条件：业态（明确要求时才传）')
    parser.add_argument('--city', action='append', default=[], help='硬条件：城市（明确要求时才传）')
    parser.add_argument('--stage', action='append', default=[], help='硬条件：阶段（明确要求时才传）')
    parser.add_argument('--year-from', type=int, default=None, help='硬条件：起始年份（明确要求时才传）')
    parser.add_argument('--audience', action='append', default=[], help='硬条件：客群（明确要求时才传）')
    parser.add_argument('--prefer-industry', default='', help='软偏好：同业态加分并标注异同，不过滤')
    parser.add_argument('--prefer-stage', action='append', default=[], help='软偏好：同阶段加分并标注异同，不过滤')
    parser.add_argument('--prefer-audience', action='append', default=[], help='软偏好：同客群加分并标注异同，不过滤')
    parser.add_argument('--prefer-city', action='append', default=[], help='软偏好：同城加分，不过滤')
    parser.add_argument('--prefer-recent', action='store_true', help='软偏好：年份较新加分')
    parser.add_argument('--collection', default='cases', choices=['all', 'cases', 'ai_images', 'ai_videos', 'short_drama_skills', 'short_videos', 'livestreams'])
    parser.add_argument('--require-image', action='store_true')
    parser.add_argument('--limit-per-need', type=int, default=5)
    args = parser.parse_args()
    client = KBClient(args.base_url)
    if args.options:
        result = client.request('/api/reference-options')
    elif args.project_id:
        result = client.project(args.project_id)
    else:
        payload = build_payload_from_args(args)
        result = client.brief_references(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
