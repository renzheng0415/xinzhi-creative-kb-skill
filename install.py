#!/usr/bin/env python3
"""Install this one Skill for the invoking agent and validate live NAS access."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent
NAME = 'xinzhi-creative-kb'
SOURCE = ROOT / NAME
sys.path.insert(0, str(SOURCE / 'scripts'))
from kb_client import KBClient, LAN_URL

CLIENT_ROOTS = {
    'workbuddy': '.codebuddy/skills',
    'claude-code': '.claude/skills',
    'dsh': '.dsh/skills',
    'antigravity': '.gemini/config/skills',
    'antigravity-cli': '.gemini/antigravity-cli/skills',
    'grok-build': '.grok/skills',
    'codex': '.agents/skills',
}


def invoking_client(explicit=None):
    if explicit:
        return explicit
    value = os.getenv('XINZHI_INSTALL_CLIENT', '').lower()
    if value in CLIENT_ROOTS:
        return value
    # Presence of an installed application is not evidence that it is the caller.
    indicators = [('claude-code', 'CLAUDECODE'), ('codex', 'CODEX_THREAD_ID'),
                  ('dsh', 'DSH_SESSION_ID'), ('workbuddy', 'WORKBUDDY_SESSION_ID')]
    found = [name for name, key in indicators if os.getenv(key)]
    if len(found) == 1:
        return found[0]
    raise ValueError('执行安装的智能体应自动传入自己的 --client 名称；无需用户选择或填写配置。')


def work_directory(explicit, home):
    if explicit:
        return Path(explicit).expanduser().absolute()
    for candidate in [home / 'Documents/一人公司/公司知识库搭建', home / 'Documents/公司知识库搭建']:
        if candidate.is_dir():
            return candidate / '智能体安装'
    return home / 'Documents/公司知识库搭建/智能体安装'


def source_files():
    files = []
    for path in sorted(SOURCE.rglob('*')):
        rel = path.relative_to(SOURCE)
        if '__pycache__' in rel.parts or path.suffix == '.pyc' or rel.name in ('connection.json','connection.local.json'):
            continue
        if path.is_symlink():
            raise ValueError('安装包不应包含软链接')
        if path.is_file():
            files.append((path, rel))
    if not any(rel.as_posix() == 'SKILL.md' for _, rel in files):
        raise ValueError('安装包缺少 SKILL.md')
    return files


def prepare_python(client_work, existing):
    if existing:
        python = str(Path(existing).expanduser().absolute())
        subprocess.run([python, '-c', 'import sys,pypdf; assert sys.version_info >= (3,10)'], check=True,
                       stdout=subprocess.DEVNULL)
        return python
    if sys.version_info < (3, 10):
        raise ValueError('请由当前智能体准备 Python 3.10+ 后继续安装')
    runtime = client_work / 'python-runtime'
    python = runtime / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(runtime)
    check = subprocess.run([str(python), '-c', 'import pypdf'], capture_output=True)
    if check.returncode:
        subprocess.run([str(python), '-m', 'pip', 'install', '--no-cache-dir', 'pypdf==6.19.0'], check=True)
    return str(python)


def install(client, home, work, mode, python, check=True):
    if mode != 'company':
        raise ValueError('员工公开安装包只支持公司内网')
    base = LAN_URL
    files = source_files()
    target = home / CLIENT_ROOTS[client] / NAME
    if target.is_symlink():
        raise ValueError('已有同名 Skill 是软链接，请由当前智能体核实归属后选用已确认的技能目录')
    saved_connections = {name: (target/name).read_bytes() for name in ('connection.json','connection.local.json') if (target/name).is_file()}
    existing_profile = json.loads(saved_connections['connection.json']) if 'connection.json' in saved_connections else None
    client_work = work / client
    client_work.mkdir(parents=True, exist_ok=True)
    reusable = python or ((existing_profile or {}).get('python'))
    runtime_python = prepare_python(client_work, reusable)
    profile = {'base_url': base, 'mode': mode, 'client': client, 'python': runtime_python,
               'work_root': str(work), 'data_source': 'live NAS API', 'result_cache': False}
    if existing_profile:
        profile = {**profile, **existing_profile}
        if python:
            profile['python'] = runtime_python
    target.parent.mkdir(parents=True, exist_ok=True)
    expected = {rel.as_posix(): hashlib.sha256(src.read_bytes()).hexdigest() for src, rel in files}
    unchanged = target.is_dir() and all((target / rel).is_file() and hashlib.sha256((target / rel).read_bytes()).hexdigest() == digest for rel, digest in expected.items())
    backup = None
    if not unchanged:
        # Move the exact old Skill to a durable backup; unrelated skills are untouched.
        if target.exists():
            old_manifest = target / 'SKILL.md'
            if not old_manifest.is_file() or 'name: ' + NAME not in old_manifest.read_text(encoding='utf-8'):
                raise ValueError('同名目录并非可确认的心智 Skill，安装停止')
            backup = client_work / '备份' / datetime.now().strftime('%Y%m%d-%H%M%S-%f') / NAME
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(backup))
        try:
            target.mkdir()
            if backup is not None:
                shutil.copytree(backup, target, dirs_exist_ok=True, symlinks=True,
                                ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            for src, rel in files:
                dest = target / rel
                if any(p.is_symlink() for p in [dest, *dest.parents] if p != target and target in p.parents):
                    raise ValueError('新版文件与本机软链接冲突，已保留旧版')
                dest.parent.mkdir(parents=True, exist_ok=True)
                with src.open('rb') as incoming, dest.open('wb') as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
        except Exception:
            # Keep a partial copy for diagnosis and restore the saved Skill.
            if target.exists():
                failed = client_work / '未完成安装' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
                failed.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target), str(failed))
            if backup is not None:
                shutil.move(str(backup), str(target))
            raise
    for name, content in saved_connections.items():
        (target/name).write_bytes(content)
    profile_path = target / 'connection.json'
    old_profile = json.loads(profile_path.read_text(encoding='utf-8')) if profile_path.exists() else None
    if old_profile != profile:
        if old_profile is not None:
            saved = client_work / '备份' / ('connection-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_text(json.dumps(old_profile, ensure_ascii=False, indent=2), encoding='utf-8')
        profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding='utf-8')
    assert all(hashlib.sha256((target / rel).read_bytes()).hexdigest() == digest for rel, digest in expected.items())
    report = {'installed': True, 'client': client, 'skill_directory': str(target), 'mode': mode,
              'base_url': base, 'backup': str(backup) if backup else None, 'unchanged': unchanged,
              'live_connection_verified': False, 'client_discovery_verified': False,
              'content_updates_need_reinstall': False, 'mcp_settings_modified': False}
    # Invoke the installed copy so package extraction is no longer a dependency.
    if check:
        try:
            result = subprocess.run([runtime_python, str(target / 'scripts/query_cases.py'), '--options'],
                capture_output=True, text=True, encoding='utf-8', timeout=30, check=True,
                env={k: v for k, v in os.environ.items() if k != 'XINZHI_KB_URL'})
            filters = json.loads(result.stdout)
            client_api = KBClient(base)
            health = client_api.request('/api/health')
            sample = client_api.search(collection='cases', limit=1)
            if health.get('status') != 'ok' or health.get('service') != 'company-creative-kb-mvp' or not filters.get('options') or not sample.get('items'):
                raise ValueError('NAS 身份、分类或案例检索未通过')
            asset = client_api.asset(sample['items'][0]['id'])
            preview = client_work / '验收样本' / Path(asset['preview_path']).name
            client_api.download(asset['preview_path'], preview)
            if preview.stat().st_size <= 0:
                raise ValueError('预览下载为空')
            report.update(live_connection_verified=True, assets=health['stats']['assets'],
                          example={'id': asset['id'], 'title': asset['title']}, preview_download_verified=True)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            report['connection_issue'] = type(error).__name__ + ': NAS 分类或检索未通过，请检查当前公司网络'
    report_path = client_work / '安装验收.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    report['report'] = str(report_path)
    return report


def main():
    parser = argparse.ArgumentParser(description='交给智能体执行的心智知识库自动安装器')
    parser.add_argument('--client', choices=list(CLIENT_ROOTS))
    parser.add_argument('--mode', choices=['company'])
    parser.add_argument('--python', help='复用稳定且已安装 pypdf 的 Python，保留 venv 入口')
    parser.add_argument('--work-root', help='所有依赖、备份与验收文件的持久目录')
    parser.add_argument('--home', help=argparse.SUPPRESS)
    args = parser.parse_args()
    client = invoking_client(args.client)
    home = Path(args.home).expanduser().absolute() if args.home else Path.home()
    config = json.loads((ROOT / 'install-profile.json').read_text(encoding='utf-8')) if (ROOT / 'install-profile.json').exists() else {'mode': 'company'}
    report = install(client, home, work_directory(args.work_root, home), args.mode or config['mode'], args.python)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report['live_connection_verified']:
        sys.exit(2)


if __name__ == '__main__':
    main()
