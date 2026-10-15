#!/usr/bin/env python3
"""Check the fixed public Skill repository and safely update this installation only."""
import argparse
import ast
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid

NAME = 'xinzhi-creative-kb'
REPOSITORY = 'renzheng0415/xinzhi-creative-kb-skill'
RAW = 'https://raw.githubusercontent.com/' + REPOSITORY
MANIFEST = 'release.json'
MAX_FILE = 1024 * 1024
MAX_TOTAL = 8 * MAX_FILE
REQUIRED = {'SKILL.md', 'scripts/ensure_latest.py', 'scripts/kb_client.py',
            'scripts/query_cases.py', 'scripts/find_references.py', 'scripts/inspect_case.py',
            'scripts/fetch_references.py', 'scripts/prepare_project.py'}


class UpdateError(Exception):
    pass


class UnsafeInstallation(UpdateError):
    """The caller must stop; a safe active version could not be established."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise UpdateError('unexpected_redirect')


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise UpdateError('invalid_version')
    return tuple(int(x) for x in value.split('.'))


def safe_relative(value):
    if not isinstance(value, str) or '\\' in value or ':' in value:
        raise UpdateError('invalid_path')
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix() or any(x in ('..', '.') or x.startswith('.') for x in path.parts):
        raise UpdateError('invalid_path')
    if value == 'SKILL.md':
        return path
    if len(path.parts) < 2 or path.parts[0] not in ('scripts', 'references', 'agents') or path.suffix not in ('.py', '.md', '.json', '.yaml'):
        raise UpdateError('unmanaged_path')
    if any(x.lower().startswith('connection') for x in path.parts):
        raise UpdateError('configuration_in_release')
    return path


def validate_manifest(data):
    if not isinstance(data, dict) or data.get('schema') != 1 or data.get('name') != NAME:
        raise UpdateError('invalid_manifest')
    version_tuple(data.get('version'))
    minimum = data.get('min_python')
    if not isinstance(minimum, list) or len(minimum) != 2 or any(type(x) is not int or x < 0 for x in minimum):
        raise UpdateError('invalid_python_requirement')
    if tuple(sys.version_info[:2]) < tuple(minimum):
        raise UpdateError('python_upgrade_required')
    files = data.get('files')
    if not isinstance(files, list) or not 1 <= len(files) <= 64:
        raise UpdateError('invalid_file_list')
    seen = set(); total = 0
    for item in files:
        if not isinstance(item, dict):
            raise UpdateError('invalid_file_entry')
        path = str(safe_relative(item.get('path')))
        if path in seen or not re.fullmatch(r'[0-9a-f]{64}', str(item.get('sha256', ''))):
            raise UpdateError('invalid_file_digest')
        if type(item.get('bytes')) is not int or not 0 <= item['bytes'] <= MAX_FILE:
            raise UpdateError('invalid_file_size')
        seen.add(path); total += item['bytes']
    if not REQUIRED.issubset(seen) or total > MAX_TOTAL:
        raise UpdateError('incomplete_or_oversized_release')
    return data


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


class GitHubRelease:
    """No repository URL, credentials, or download target is supplied by remote metadata."""
    def __init__(self):
        self.opener = urllib.request.build_opener(NoRedirect())

    def get(self, url, limit):
        request = urllib.request.Request(url, headers={'User-Agent': 'xinzhi-skill-updater', 'Cache-Control': 'no-cache'})
        with self.opener.open(request, timeout=6) as response:
            data = response.read(limit + 1)
        if len(data) > limit:
            raise UpdateError('download_too_large')
        return data

    def latest(self):
        url = RAW + '/main/' + NAME + '/' + MANIFEST + '?check=' + str(int(time.time()))
        return validate_manifest(json.loads(self.get(url, 128 * 1024)))

    def pin(self):
        data = json.loads(self.get('https://api.github.com/repos/' + REPOSITORY + '/commits/main', 512 * 1024))
        commit = data.get('sha', '')
        if not re.fullmatch(r'[0-9a-f]{40}', commit):
            raise UpdateError('invalid_commit')
        manifest = validate_manifest(json.loads(self.file(commit, MANIFEST, 128 * 1024)))
        return commit, manifest

    def file(self, commit, relative, limit=MAX_FILE):
        if relative != MANIFEST:
            safe_relative(relative)
        if not re.fullmatch(r'[0-9a-f]{40}', commit):
            raise UpdateError('invalid_commit')
        return self.get(RAW + '/' + commit + '/' + NAME + '/' + relative, limit)


def work_root(root):
    profile = read_json(root/'connection.json')
    base = profile.get('work_root')
    if not isinstance(base, str) or not base:
        raise UpdateError('missing_work_root')
    result = Path(base).expanduser().resolve()/'Skill自动更新'
    if result == root or root in result.parents:
        raise UpdateError('backup_inside_skill')
    result.mkdir(parents=True, exist_ok=True, mode=0o700)
    return result


@contextmanager
def update_lock(path, timeout=30):
    if path.is_symlink():
        raise UpdateError('lock_is_symlink')
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(descriptor, 'r+b') as stream:
        if stream.seek(0, 2) == 0:
            stream.write(b'0'); stream.flush()
        start = time.monotonic(); locked = False
        while not locked:
            try:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError:
                if time.monotonic()-start >= timeout:
                    raise UnsafeInstallation('another_update_is_running')
                time.sleep(0.1)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def safe_target(root, relative):
    path = root/str(safe_relative(relative))
    for candidate in [path, *path.parents]:
        if candidate == root:
            break
        if candidate.is_symlink():
            raise UpdateError('managed_path_is_symlink')
    return path


def file_map(manifest):
    return {entry['path']: entry for entry in manifest['files']}


def verify_files(root, manifest):
    for item in manifest['files']:
        path = safe_target(root, item['path'])
        if not path.is_file() or path.stat().st_size != item['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise UpdateError('local_managed_files_changed')


def smoke_check(stage):
    for path in (stage/'scripts').glob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    code = 'import sys;sys.path.insert(0,sys.argv[1]);from kb_client import KBClient;assert callable(KBClient.request)'
    result = subprocess.run([sys.executable, '-B', '-c', code, str(stage/'scripts')],
                            capture_output=True, timeout=12, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    if result.returncode:
        raise UpdateError('new_version_import_failed')


def install_release(root, old_manifest, new_manifest, commit, remote, storage, validator=smoke_check):
    verify_files(root, old_manifest)
    old_files = set(file_map(old_manifest)); new_files = set(file_map(new_manifest))
    obsolete = old_files-new_files
    for relative in new_files:
        target = safe_target(root, relative)
        if relative not in old_files and target.exists():
            raise UpdateError('new_managed_path_conflicts_with_local_file')
    stage = Path(tempfile.mkdtemp(prefix='.'+NAME+'-candidate-', dir=root.parent))
    previous = root.parent/('.'+NAME+'-previous-'+uuid.uuid4().hex)

    def ignore(directory, names):
        prefix = Path(directory).relative_to(root)
        return [name for name in names if name == '__pycache__' or name.endswith('.pyc') or (prefix/name).as_posix() in obsolete]

    switched = False
    try:
        shutil.copytree(root, stage, symlinks=True, ignore=ignore, dirs_exist_ok=True)
        for item in new_manifest['files']:
            raw = remote.file(commit, item['path'])
            if len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
                raise UpdateError('download_hash_mismatch')
            text = raw.decode('utf-8')
            if item['path'].endswith('.py'):
                ast.parse(text, filename=item['path'])
            destination = safe_target(stage, item['path'])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
        (stage/MANIFEST).write_text(json.dumps(new_manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        if 'name: '+NAME not in (stage/'SKILL.md').read_text(encoding='utf-8'):
            raise UpdateError('skill_identity_changed')
        verify_files(stage, new_manifest)
        validator(stage)
        # Existing connection files and user additions were copied verbatim, never sourced remotely.
        os.replace(root, previous)
        try:
            os.replace(stage, root)
            switched = True
            verify_files(root, new_manifest)
        except Exception:
            try:
                if root.exists():
                    failed = root.parent/('.'+NAME+'-failed-'+uuid.uuid4().hex)
                    os.replace(root, failed)
                os.replace(previous, root)
            except OSError as error:
                raise UnsafeInstallation('restore_failed_backup_preserved') from error
            switched = False
            raise UpdateError('activation_failed_old_version_restored')
    except Exception:
        if previous.exists() and not root.exists():
            try:
                os.replace(previous, root)
            except OSError as error:
                raise UnsafeInstallation('restore_failed_backup_preserved') from error
        if not switched and stage.exists():
            failed = storage/'未完成更新'/stage.name
            failed.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(stage), str(failed))
            except OSError:
                pass  # The isolated candidate stays beside the Skill; the active version is intact.
        raise
    backup = storage/'备份'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8])/NAME
    backup.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(previous), str(backup))
    except OSError:
        backup = previous  # Keep the exact rollback copy if moving it across volumes fails.
    return {'status': 'updated', 'from_version': old_manifest['version'], 'version': new_manifest['version'],
            'commit': commit, 'backup': str(backup), 'reread_skill': True}


def ensure_latest(root=None, remote=None, validator=smoke_check):
    root = Path(root).resolve() if root else Path(__file__).resolve().parents[1]
    if not (root/'connection.json').is_file():
        return {'status': 'not_installed', 'notice': '开发或下载目录不自动替换；安装后的Skill启用更新'}
    if not (root/MANIFEST).is_file():
        return {'status': 'bootstrap_required', 'notice': '旧版没有更新清单，请先更新一次安装包'}
    try:
        local = validate_manifest(read_json(root/MANIFEST))
        storage = work_root(root)
    except (OSError, ValueError, UpdateError) as error:
        raise UnsafeInstallation('local_update_metadata_invalid') from error
    lock = storage/(hashlib.sha256(str(root).encode()).hexdigest()[:16]+'.lock')
    remote = remote or GitHubRelease()
    try:
        with update_lock(lock):
            local = validate_manifest(read_json(root/MANIFEST))
            newest = remote.latest()
            validate_manifest(newest)
            if version_tuple(newest['version']) < version_tuple(local['version']):
                result = {'status': 'remote_older', 'version': local['version']}
            elif newest['version'] == local['version']:
                if file_map(newest) != file_map(local):
                    raise UpdateError('same_version_content_conflict')
                result = {'status': 'up_to_date', 'version': local['version']}
            else:
                commit, pinned = remote.pin()
                validate_manifest(pinned)
                if version_tuple(pinned['version']) < version_tuple(newest['version']):
                    raise UpdateError('release_changed_during_check')
                result = install_release(root, local, pinned, commit, remote, storage, validator)
    except UnsafeInstallation:
        raise
    except (OSError, ValueError, UpdateError, subprocess.SubprocessError, SyntaxError) as error:
        result = {'status': 'kept_current', 'version': local['version'], 'reason': str(error) if isinstance(error, UpdateError) else type(error).__name__,
                  'notice': '本次更新未完成，已保留当前版本；没有向GitHub发送项目资料或连接配置'}
    result['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
    report = storage/(hashlib.sha256(str(root).encode()).hexdigest()[:16]+'-latest.json')
    try:
        temporary = report.with_suffix('.next-'+uuid.uuid4().hex+'.json')
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        os.replace(temporary, report)
    except OSError:
        pass  # Reporting failure must not undo a validated installation.
    return result


def entrypoint(script):
    """Run before client imports; restart the same command once after installing a release."""
    root = Path(script).resolve().parents[1]
    if os.environ.pop('_XINZHI_UPDATED_PROCESS', '') == str(root):
        return
    try:
        result = ensure_latest(root)
    except UnsafeInstallation as error:
        print('心智Skill正在更新或需要恢复：'+str(error), file=sys.stderr)
        raise SystemExit(3)
    if result['status'] == 'updated':
        print('心智Skill已自动更新至 '+result['version']+'；请重新读取SKILL.md和项目工作流。继续执行原命令。', file=sys.stderr)
        environment = {**os.environ, '_XINZHI_UPDATED_PROCESS': str(root)}
        os.execve(sys.executable, [sys.executable, str(root/'scripts'/Path(script).name), *sys.argv[1:]], environment)
    elif result['status'] in ('kept_current','bootstrap_required'):
        print('心智Skill更新提示：'+result.get('notice',result['status']), file=sys.stderr)


def main():
    argparse.ArgumentParser(description='检查并自动更新当前心智Skill，保留本机配置').parse_args()
    try:
        result = ensure_latest()
    except UnsafeInstallation as error:
        print(json.dumps({'status':'blocked','reason':str(error)},ensure_ascii=False))
        raise SystemExit(3)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
