"""Read-only client for the company NAS through the company LAN."""
import json
import ipaddress
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

LAN_URL = 'http://192.168.1.251:8798'
ALLOWED_URLS = (LAN_URL,)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('知识库连接不跟随重定向')


def local_connection_urls(profile=None):
    """Honor previously configured private connections without shipping their addresses."""
    urls = list(ALLOWED_URLS)
    profile = profile or {}
    candidates = [profile.get('base_url')] if profile.get('mode') == 'personal' else []
    local_file = Path(__file__).resolve().parent.parent/'connection.local.json'
    if local_file.is_file():
        candidates.extend(json.loads(local_file.read_text(encoding='utf-8')).get('allowed_base_urls', []))
    for value in candidates:
        if not isinstance(value, str):
            continue
        parsed = urllib.parse.urlsplit(value)
        try:
            address = ipaddress.ip_address(parsed.hostname or '')
            allowed_network = address.is_private or address in ipaddress.ip_network('100.64.0.0/10')
            valid_port = parsed.port is None or 1 <= parsed.port <= 65535
        except ValueError:
            continue
        if parsed.scheme in ('http', 'https') and allowed_network and valid_port and not parsed.username and not parsed.password and parsed.path in ('','/') and not parsed.query and not parsed.fragment:
            urls.append(value.rstrip('/'))
    return tuple(dict.fromkeys(urls))


def validate_base(value, allowed=None):
    value = value.rstrip('/')
    if value not in (allowed or ALLOWED_URLS):
        raise ValueError('只允许公司 NAS 内网地址或本机已配置的私有地址')
    return value


class KBClient:
    def __init__(self, base_url=None):
        # Company traffic must not go through a system HTTP proxy.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        profile = Path(__file__).resolve().parent.parent / 'connection.json'
        settings = json.loads(profile.read_text(encoding='utf-8')) if profile.is_file() else {}
        configured = settings.get('base_url', LAN_URL)
        allowed = local_connection_urls(settings)
        chosen = base_url or os.getenv('XINZHI_KB_URL') or configured
        if chosen != 'auto':
            self.base = validate_base(chosen, allowed)
            return
        for candidate in allowed:
            try:
                self.base = candidate
                health = self.request('/api/health', timeout=2)
                if health.get('service') == 'company-creative-kb-mvp' and health.get('status') == 'ok':
                    return
            except (OSError, ValueError, RuntimeError):
                continue
        raise RuntimeError('公司 NAS 暂时不可达：请接入公司网络。')

    def request(self, path, body=None, timeout=20):
        allowed_static = (
            '/api/health', '/api/filters', '/api/search',
            '/api/reference-options', '/api/references/search',
            '/api/references/brief', '/api/references/read',
        )
        if (
            path not in allowed_static
            and not re.fullmatch(r'/api/assets/[\w-]{1,100}', path)
            and not re.fullmatch(r'/api/projects/[\w-]{1,120}', path)
        ):
            raise ValueError('只允许只读知识库接口')
        if body is not None and path not in ('/api/search', '/api/references/search', '/api/references/brief', '/api/references/read'):
            raise ValueError('此接口只允许读取')
        req = urllib.request.Request(self.base + path,
            data=json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None,
            headers={'Cache-Control': 'no-cache', **({'Content-Type': 'application/json'} if body is not None else {})})
        try:
            with self.opener.open(req, timeout=timeout) as reply:
                raw = reply.read(16 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'知识库接口返回 HTTP {error.code}，请检查案例 ID、分类条件及网络权限') from None
        except OSError:
            raise RuntimeError('无法连接公司 NAS，请检查公司网络') from None
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError('返回资料过大，请缩小读取范围')
        return json.loads(raw)

    def asset(self, asset_id):
        if not re.fullmatch(r'[\w-]{1,100}', asset_id):
            raise ValueError('非法案例 ID')
        return self.request('/api/assets/' + asset_id)

    def file_url(self, relative):
        if not relative:
            return None
        decoded = urllib.parse.unquote(relative)
        parts = PurePosixPath(decoded).parts
        if not parts or parts[0] not in ('images', 'pages', 'originals', 'video-gallery') or '..' in parts or decoded.startswith('/') or '\\' in decoded or '?' in decoded or '#' in decoded:
            raise ValueError('非法知识库资源路径')
        return self.base + '/' + urllib.parse.quote(decoded, safe='/')

    def links(self, asset, page=None):
        media = asset.get('media', {})
        if page is not None:
            picked = next((p for p in asset.get('pages', []) if p['page'] == page), None)
            if picked is None:
                raise ValueError('所选页不存在')
            preview_path = picked.get('image_path')
        else:
            preview_path = asset.get('preview_path') or next(
                (u.get('image_path') for u in asset.get('evidence_units', []) if u.get('image_path')),
                None,
            )
        collection = asset.get('collection', '')
        website = self.base + (
            '/ai-videos' if 'AI生视频' in asset.get('outputs', []) or collection == 'ai_videos'
            else '/ai-images' if 'AI 生图与生视频' in asset.get('topics', []) or collection == 'ai_images'
            else '/'
        )
        if asset.get('gallery_item'):
            website = self.base + '/ai-videos?item=' + urllib.parse.quote(asset['gallery_item'])
        return {'original': self.file_url(asset.get('original_path')),
                'preview': self.file_url(preview_path), 'website': website,
                'video': self.file_url(media['video_path']) if media.get('video_path') else media.get('online_video')}

    def search(self, **body):
        result = self.request('/api/search', body)
        for asset in result['items']:
            asset['links'] = self.links(asset)
            for page in asset.get('evidence_pages', []):
                page['url'] = self.file_url(page.get('image_path'))
        result['connection'] = {'base_url': self.base, 'source': 'company NAS'}
        return result

    def download(self, relative, target):
        target = Path(target)
        url = self.file_url(relative)
        if url is None:
            raise ValueError('此记录没有附件路径')
        try:
            with self.opener.open(url, timeout=30) as reply:
                raw = reply.read(50 * 1024 * 1024 + 1)
        except OSError:
            raise RuntimeError('NAS 附件取回失败，请检查网络或使用原件链接') from None
        if len(raw) > 50 * 1024 * 1024:
            raise ValueError('单个样本超过 50MB，请使用原件链接')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)

    def references(self, **body):
        result = self.request('/api/references/search', body)
        for asset in result['items']:
            asset['links'] = self.links(asset)
            for unit in asset.get('evidence_units', []):
                unit['url'] = self.file_url(unit.get('image_path'))
                for evidence in unit.get('evidence', []):
                    evidence['url'] = self.file_url(evidence.get('image_path'))
        result['connection'] = {'base_url': self.base, 'source': 'company NAS'}
        return result

    def brief_references(self, payload):
        result = self.request('/api/references/brief', payload)
        for need in result.get('needs', []):
            for asset in need.get('items', []):
                asset['links'] = self.links(asset)
                for unit in asset.get('evidence_units', []):
                    unit['url'] = self.file_url(unit.get('image_path'))
        result['connection'] = {'base_url': self.base, 'source': 'company NAS'}
        return result

    def project(self, project_id):
        if not re.fullmatch(r'[\w-]{1,120}', str(project_id or '')):
            raise ValueError('非法项目卡 ID')
        result = self.request('/api/projects/' + project_id)
        proj = result.get('project') if isinstance(result, dict) and 'project' in result else result
        if isinstance(proj, dict):
            proj['preview_url'] = self.file_url(proj.get('preview_path'))
            for items in (proj.get('assets_by_role') or {}).values():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            item['preview_url'] = self.file_url(item.get('preview_path'))
        if isinstance(result, dict):
            result['connection'] = {'base_url': self.base, 'source': 'company NAS'}
        return result

    def context(self, asset_id, page=1, radius=1):
        result = self.request('/api/references/read', {'asset_id': asset_id, 'page': page, 'radius': radius})
        result['original_url'] = self.file_url(result['asset']['original_path'])
        for item in result['pages']:
            item['url'] = self.file_url(item.get('image_path'))
        return result
