#!/usr/bin/env python3
"""Fail-closed checks for Hermes Unlimited release metadata and repository boundary."""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def fail(message):
    print(f'RELEASE BLOCKED: {message}', file=sys.stderr)
    raise SystemExit(1)

def version():
    manifest = (ROOT / 'plugin.yaml').read_text()
    match = re.search(r'^version:\s*["\']?([^\s"\']+)', manifest, re.M)
    if not match:
        fail('plugin.yaml has no version')
    return match.group(1)

def main():
    v = version()
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?', v):
        fail(f'invalid semantic version {v!r}')
    ref = os.environ.get('GITHUB_REF', '')
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    if ref.startswith('refs/tags/'):
        if repo != 'rrglab/hermes-unlimited':
            fail('release tags only permitted in rrglab/hermes-unlimited')
        tag = ref.removeprefix('refs/tags/')
        if tag != 'v' + v:
            fail(f'tag {tag!r} does not match plugin.yaml v{v}')
        if '-' in v:
            fail('prerelease manifest cannot be promoted as stable release')
        if os.environ.get('RELEASE_APPROVED') != 'true':
            fail('explicit release approval missing')
        result = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True, text=True, check=True)
        if result.stdout.strip():
            fail('release working tree is dirty')
    print(f'Manifest version validated: {v}; release tag policy checked')

if __name__ == '__main__':
    main()
