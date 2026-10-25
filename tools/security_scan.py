"""Fail closed on credential candidates; never print matched values or source lines.

Requires the optional requirements-security.txt. Detection/verification stays local.
"""
import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zlib


def reference_values(path):
    """Read reference configuration in memory only, with no values in output."""
    values = []
    if path is not None:
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                value = line.split('=', 1)[1].strip().strip('"').strip("'")
                if len(value) >= 6:
                    values.append(value.encode())
    return values


def inspect_bytes(data, path, values, findings, allowed_git_email=None, compressed_git_object=False):
    if any(value in data for value in values):
        findings.append(dict(path=path, type='Exact private reference value'))
    text = data.decode('utf-8', errors='ignore')
    patterns = {
        'Private key material': r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
        'Personal absolute user path': (r'(?:[A-Z]:[\\/]+Us' r'ers[\\/]+[^\\/\s<>"\']+'
                                        r'|/ho' r'me/[^/\s<>"\']+|/Us' r'ers/[^/\s<>"\']+)'),
        'Email address requiring review': r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',
    }
    for kind, expression in patterns.items():
        # Compressed storage can accidentally resemble an email. Its actual
        # object content is decompressed and inspected separately below.
        if kind == 'Email address requiring review' and compressed_git_object:
            continue
        for match in re.finditer(expression, text, re.IGNORECASE):
            # Permit one explicitly reviewed GitHub noreply identity only in
            # local Git metadata. Working-tree and indexed content stay strict.
            if (kind == 'Email address requiring review' and path.startswith('.git/')
                    and allowed_git_email and match.group() == allowed_git_email):
                continue
            findings.append(dict(path=path, type=kind, line=text[:match.start()].count('\n') + 1))


def run_git(git, root, *args):
    return subprocess.run([git, '-C', str(root), *args], capture_output=True)


def scan(root, git, reference_env=None, require_fresh=False, allowed_git_email=None):
    findings = []
    if allowed_git_email and not re.fullmatch(r'[0-9]+\+[A-Za-z0-9-]+@users[.]noreply[.]github[.]com', allowed_git_email):
        raise ValueError('Only a reviewed GitHub numeric noreply identity may be permitted')
    values = reference_values(reference_env)
    files = sorted(p for p in root.rglob('*') if p.is_file())
    metadata_files = 0
    for path in files:
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        if path.name == '.env' or (path.name.startswith('.env.') and path.name != '.env.example') or path.name == 'credentials.json' or path.suffix.lower() in {'.key', '.pem'}:
            findings.append(dict(path=relative, type='Forbidden private file'))
        if path.suffix.lower() == '.csv':
            columns = set(data.splitlines()[0].decode('utf-8-sig', errors='ignore').strip().lower().split(',')) if data else set()
            if {'open', 'high', 'low', 'close'}.issubset(columns):
                findings.append(dict(path=relative, type='Price-level input or intermediate export requires data rights review'))
        if path.is_symlink():
            findings.append(dict(path=relative, type='Symlink requires manual review'))
        loose_object = bool(re.fullmatch(r'.git/objects/[0-9a-f]{2}/[0-9a-f]{38}', relative))
        inspect_bytes(data, relative, values, findings, allowed_git_email, loose_object)
        if '.git' in path.relative_to(root).parts:
            metadata_files += 1
            # Inspect the actual content of loose staged Git objects as well.
            if loose_object:
                try:
                    inspect_bytes(zlib.decompress(data), relative, values, findings, allowed_git_email)
                except zlib.error:
                    findings.append(dict(path=relative, type='Unreadable loose Git object'))
        if path.suffix == '.py' and relative.startswith(('v3/', 'data/', 'config/')):
            tree = ast.parse(data.decode('utf-8-sig'))
            for node in ast.walk(tree):
                names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ''] if isinstance(node, ast.ImportFrom) else []
                if any(name.split('.')[0] in {'lse', 'dotenv', 'requests', 'httpx', 'urllib', 'socket', 'websockets', 'aiohttp'} for name in names):
                    findings.append(dict(path=relative, type='Unnecessary network/authentication import', line=node.lineno))

    # Capture scanner output in memory. Do not dump its output or stderr.
    completed = subprocess.run([sys.executable, '-m', 'detect_secrets', 'scan', '--all-files', '--no-verify', '.'], cwd=root, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError('detect-secrets did not complete; no scan success is claimed.')
    detected = json.loads(completed.stdout)
    for filename, items in detected.get('results', {}).items():
        for item in items:
            findings.append(dict(path=filename, type=item['type'], line=item['line_number']))

    tracked = run_git(git, root, 'ls-files', '-z')
    if tracked.returncode:
        raise RuntimeError('A Git repository is required to inspect tracked/staged files.')
    paths = [p.decode('utf-8') for p in tracked.stdout.split(b'\0') if p]
    for relative in paths:
        staged = run_git(git, root, 'show', ':' + relative)
        if staged.returncode:
            findings.append(dict(path=relative, type='Cannot read staged blob'))
            continue
        inspect_bytes(staged.stdout, relative + ' (Git index)', values, findings)
        working = root / relative
        if not working.is_file() or working.read_bytes() != staged.stdout:
            findings.append(dict(path=relative, type='Git index differs from scanned working-tree bytes'))
        if relative.startswith(('data/raw/', 'local_results/', 'private_results/')):
            findings.append(dict(path=relative, type='Private input/output staged for publication'))
    remote_names = run_git(git, root, 'remote').stdout.splitlines()
    head = run_git(git, root, 'rev-parse', '--verify', 'HEAD')
    commits = run_git(git, root, 'rev-list', '--all', '--count')
    commit_count = int(commits.stdout.strip() or b'0') if not commits.returncode else 0
    if require_fresh and (head.returncode == 0 or commit_count or remote_names):
        findings.append(dict(path='.git', type='Fresh repository must have no commits or remotes'))
    # A local-repository object pack would require a complete packed-object audit.
    if require_fresh and any((root / '.git/objects/pack').glob('*.pack')):
        findings.append(dict(path='.git/objects/pack', type='Unexpected packed history in fresh repository'))
    return dict(passed=not findings, scanner='detect-secrets ' + importlib.metadata.version('detect-secrets'),
                scanner_plugins=len(detected.get('plugins_used', [])), network_verification=False,
                total_files_read=len(files), git_metadata_files_read=metadata_files,
                tracked_staged_files=len(paths), staged_blobs_match_scanned_files=not any(f['type']=='Git index differs from scanned working-tree bytes' for f in findings),
                commits=commit_count, remotes=len(remote_names), original_history_imported=False if require_fresh and commit_count == 0 else 'not assessed',
                reviewed_github_noreply_identity_allowed_in_git_metadata=allowed_git_email is not None,
                original_private_values_compared=reference_env is not None,
                raw_input_files_present=any(p.is_file() for p in (root / 'data/raw').rglob('*')) if (root / 'data/raw').exists() else False,
                findings=findings,
                scope='All working-tree files, hidden files, binary bytes, eligible text via detect-secrets, loose Git objects and exact staged blobs. Values and matched lines are never displayed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--reference-env', type=Path, help='Optional private local reference; read only in memory')
    parser.add_argument('--git', default=shutil.which('git'))
    parser.add_argument('--require-fresh', action='store_true')
    parser.add_argument('--allowed-git-email', help='Explicitly reviewed numeric GitHub noreply identity; permitted only in Git metadata')
    parser.add_argument('--report', type=Path, help='Write a sanitized report, without matched values')
    args = parser.parse_args()
    if not args.git:
        parser.error('Git must be available on PATH or selected with --git.')
    try:
        result = scan(args.root.resolve(), args.git, args.reference_env, args.require_fresh, args.allowed_git_email)
    except Exception as error:
        # Avoid exposing paths or input fragments from unexpected exceptions.
        print(json.dumps(dict(passed=False, error_type=type(error).__name__, message='Scan incomplete; publication preparation must stop.')))
        return 2
    rendered = json.dumps(result, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + '\n', encoding='utf-8')
    print(rendered)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
