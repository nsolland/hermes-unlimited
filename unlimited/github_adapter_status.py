"""Host-controlled GitHub Actions status source; no token from adapter input.

Only authoritative completed-success runs for the pinned commit are accepted.
No network calls are made unless the host explicitly installs this provider.
"""
import json
import re
from urllib.request import Request, urlopen


class GitHubAdapterStatus:
    def __init__(self, *, repo, commit_sha, token, timeout=5):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
            raise ValueError('INVALID_REPOSITORY')
        if not re.fullmatch(r'[0-9a-f]{40}', commit_sha):
            raise ValueError('INVALID_COMMIT_SHA')
        if not isinstance(token, str) or not token:
            raise ValueError('GITHUB_TOKEN_REQUIRED')
        self.repo, self.commit_sha, self.token, self.timeout = repo, commit_sha, token, timeout

    def __call__(self, adapter_id, version, digest):
        # GitHub is a CI status source, not the approval authority. An explicit
        # approved manifest remains mandatory and may revoke independently.
        req = Request(
            f'https://api.github.com/repos/{self.repo}/actions/runs?head_sha={self.commit_sha}&per_page=100',
            headers={'Authorization': f'Bearer {self.token}', 'Accept': 'application/vnd.github+json',
                     'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'hermes-unlimited-adapter-gate'})
        with urlopen(req, timeout=self.timeout) as response:
            data = json.load(response)
        runs = data.get('workflow_runs', [])
        if not isinstance(runs, list):
            raise ValueError('INVALID_GITHUB_RESPONSE')
        # Never accept an older success when a newer run for the same SHA failed.
        checks = {}
        for label, workflow in [('unit', 'tests.yml'), ('contract', 'tests.yml'),
                                ('integration', 'release-gate.yml'), ('security', 'codeql.yml')]:
            matching = [r for r in runs if r.get('path', '').endswith('/'+workflow)
                        and r.get('head_sha') == self.commit_sha and r.get('event') in ('push','pull_request')]
            matching.sort(key=lambda r: (r.get('created_at', ''), r.get('id', 0)), reverse=True)
            checks[label] = 'passed' if matching and matching[0].get('status') == 'completed' \
                and matching[0].get('conclusion') == 'success' else 'failed'
        return {'version': version, 'sha256': digest, 'revoked': False, 'checks': checks}
