"""Bounded, read-only repository overview using server-owned GitHub CLI auth."""
import json
import os
import re
import subprocess
from datetime import datetime, timezone

QUERY = '''query($after:String) { viewer { login repositories(first:50,after:$after,
affiliations:[OWNER,COLLABORATOR,ORGANIZATION_MEMBER],orderBy:{field:PUSHED_AT,direction:DESC}) {
nodes { nameWithOwner description isPrivate isArchived viewerPermission
issues(states:OPEN) { totalCount } pullRequests(states:OPEN) { totalCount }
defaultBranchRef { target { ... on Commit { messageHeadline committedDate oid } } } }
pageInfo { hasNextPage endCursor } } } }'''


class ProjectsUnavailable(RuntimeError):
    pass


def _query(after):
    try:
        result = subprocess.run(
            ['gh', 'api', '--hostname', 'github.com', 'graphql', '--input', '-'],
            input=json.dumps({'query': QUERY, 'variables': {'after': after}}),
            capture_output=True, encoding='utf-8', timeout=12,
            env={**os.environ, 'GH_HOST': 'github.com', 'GH_PROMPT_DISABLED': '1'},
            **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}),
        )
        if len(result.stdout) > 4_000_000:
            raise ValueError()
        # gh may return nonzero alongside usable GraphQL partial data.
        data = json.loads(result.stdout)
        if not isinstance(data, dict) or not isinstance(data.get('data'), dict) or not isinstance(data['data'].get('viewer'), dict):
            raise ValueError()
        return data
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        raise ProjectsUnavailable('GitHub overview unavailable. Check the server GitHub CLI sign-in, permissions or rate limit, then refresh.') from None


def _count(value):
    value = value.get('totalCount') if isinstance(value, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _row(node):
    if not isinstance(node, dict) or not node.get('viewerPermission') or not isinstance(node.get('isPrivate'), bool):
        return None
    name = node.get('nameWithOwner')
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', name):
        return None
    branch = node.get('defaultBranchRef')
    target = branch.get('target') if isinstance(branch, dict) else None
    target = target if isinstance(target, dict) else {}
    oid = target.get('oid', '')
    commit = None
    if isinstance(oid, str) and re.fullmatch(r'[a-fA-F0-9]{40,64}', oid):
        date = target.get('committedDate')
        try:
            datetime.fromisoformat(date.replace('Z', '+00:00'))
            commit = {'summary': str(target.get('messageHeadline') or '')[:300], 'date': date, 'url': f'https://github.com/{name}/commit/{oid}'}
        except (AttributeError, TypeError, ValueError):
            pass
    return {'name': name, 'description': str(node.get('description') or '')[:1000],
            'visibility': 'Private' if node['isPrivate'] else 'Public', 'archived': node.get('isArchived') is True,
            'url': f'https://github.com/{name}', 'issues': _count(node.get('issues')),
            'pull_requests': _count(node.get('pullRequests')), 'commit': commit}


def overview(query=None):
    query = query or _query
    rows, account, cursor, partial, limited = {}, None, None, False, False
    for page in range(2):
        try:
            data = query(cursor)
        except ProjectsUnavailable:
            # Never retain old private rows after an auth/transport failure.
            raise
        viewer = data.get('data', {}).get('viewer')
        if not isinstance(viewer, dict) or not isinstance(viewer.get('login'), str):
            raise ProjectsUnavailable('GitHub account unavailable. Refresh after signing in on the server.')
        if account is not None and account != viewer['login']:
            raise ProjectsUnavailable('GitHub account changed. Refresh the overview.')
        account = viewer['login']
        connection = viewer.get('repositories')
        if not isinstance(connection, dict) or not isinstance(connection.get('nodes'), list):
            raise ProjectsUnavailable('GitHub repository discovery unavailable. Refresh later.')
        partial |= bool(data.get('errors'))
        for node in connection['nodes'][:50]:
            row = _row(node)
            if row is None:
                partial = True
                continue
            partial |= row['issues'] is None or row['pull_requests'] is None
            rows[row['name']] = row
        info = connection.get('pageInfo') or {}
        limited = info.get('hasNextPage') is True
        if not limited:
            break
        cursor = info.get('endCursor')
        if not isinstance(cursor, str) or not cursor or len(cursor) > 1024:
            partial = True
            break
    return {'repositories': list(rows.values()), 'account': account, 'partial': partial,
            'limited': limited, 'limit': 100, 'refreshed_at': datetime.now(timezone.utc).isoformat()}
