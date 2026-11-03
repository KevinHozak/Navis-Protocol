import json
import subprocess
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from services import projects


def node(name='fixture/repo'):
    return {'nameWithOwner': name, 'description': 'Synthetic project', 'isPrivate': True,
            'viewerPermission': 'READ', 'isArchived': False, 'issues': {'totalCount': 3},
            'pullRequests': {'totalCount': 2}, 'defaultBranchRef': {'target': {
                'oid': 'a'*40, 'messageHeadline': 'Synthetic commit', 'committedDate': '2026-11-03T00:00:00Z'}}}


def response(nodes, more=False, errors=None):
    return {'data': {'viewer': {'login': 'fixture', 'repositories': {'nodes': nodes,
            'pageInfo': {'hasNextPage': more, 'endCursor': 'cursor'}}}}, 'errors': errors}


def test_counts_links_and_default_branch_commit_are_separate():
    value = projects.overview(lambda _: response([node()]))
    row = value['repositories'][0]
    assert row['issues'] == 3 and row['pull_requests'] == 2
    assert row['commit']['url'] == 'https://github.com/fixture/repo/commit/'+'a'*40
    assert row['visibility'] == 'Private' and not value['partial']
    assert 'viewerPermission' not in json.dumps(value)


def test_partial_data_keeps_successes_but_omits_unauthorized_nodes():
    denied = node('secret/denied'); denied['viewerPermission'] = None
    partial = node('fixture/partial'); partial['issues'] = None
    value = projects.overview(lambda _: response([node(), denied, partial, None], errors=[{'message': 'RAW SECRET'}]))
    assert len(value['repositories']) == 2 and value['partial']
    assert value['repositories'][1]['issues'] is None
    assert 'secret/denied' not in json.dumps(value) and 'RAW SECRET' not in json.dumps(value)


def test_discovery_is_bounded_and_empty_is_valid():
    calls=[]
    value=projects.overview(lambda cursor: (calls.append(cursor) or response([node()], more=True)))
    assert calls == [None, 'cursor'] and value['limited'] and value['limit']==100
    assert projects.overview(lambda _: response([]))['repositories']==[]


def test_account_change_or_later_failure_never_returns_old_private_rows():
    calls=[]
    def query(cursor):
        calls.append(cursor)
        if cursor: raise projects.ProjectsUnavailable('Unavailable')
        return response([node()],more=True)
    with pytest.raises(projects.ProjectsUnavailable): projects.overview(query)
    def switched(cursor):
        data=response([node()],more=not cursor)
        if cursor: data['data']['viewer']['login']='different'
        return data
    with pytest.raises(projects.ProjectsUnavailable,match='account changed'): projects.overview(switched)


@pytest.mark.parametrize('failure', [FileNotFoundError(), subprocess.TimeoutExpired('gh',12)])
def test_cli_failures_are_safe(monkeypatch,failure):
    def run(*a,**kw): raise failure
    monkeypatch.setattr(projects.subprocess,'run',run)
    with pytest.raises(projects.ProjectsUnavailable,match='sign-in'): projects.overview()


def test_cli_command_pins_host_and_query_without_shell(monkeypatch):
    def run(argv,**options):
        assert argv==['gh','api','--hostname','github.com','graphql','--input','-']
        assert options['timeout']==12 and options['env']['GH_HOST']=='github.com'
        assert 'mutation' not in json.loads(options['input'])['query']
        return SimpleNamespace(stdout=json.dumps(response([node()])),returncode=0)
    monkeypatch.setattr(projects.subprocess,'run',run)
    assert len(projects.overview()['repositories'])==1


@pytest.mark.parametrize('raw', ['not json','{"data":null}', '{"errors":[{"message":"raw token"}]}'])
def test_malformed_auth_or_rate_limit_data_is_not_exposed(monkeypatch,raw):
    monkeypatch.setattr(projects.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=raw,returncode=1))
    with pytest.raises(projects.ProjectsUnavailable) as error: projects.overview()
    assert 'raw token' not in str(error.value)


def test_http_adapter_and_existing_auth_boundary(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    monkeypatch.setenv('NAVIS_API_KEY','synthetic-app-key')
    # Replace with a closed synthetic snapshot; no CLI invocation or Vault startup.
    monkeypatch.setattr(projects,'overview',lambda: {'repositories':[], 'account':'fixture','refreshed_at':'2026-11-03T00:00:00Z'})
    client=TestClient(app)
    assert client.get('/api/projects').status_code==401
    assert client.get('/api/projects',headers={'X-Vanguard-Key':'synthetic-app-key'}).json()['repositories']==[]


def test_copied_packaged_native_adapter_has_no_vault_writes(tmp_path):
    repo=Path(__file__).resolve().parents[2]
    conf=repo/'frontend/src-tauri/tauri.conf.json'
    for source,target in json.loads(conf.read_text())['bundle']['resources'].items():
        dest=tmp_path/target;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((conf.parent/source).read_bytes())
    script="import sys,runpy; sys.path.insert(0,'backend'); from services import projects; projects._query=lambda _: "+repr(response([node()]))+"; runpy.run_path('backend/native_projects.py',run_name='__main__')"
    result=subprocess.run([sys.executable,'-B','-c',script],input='{"path":"/api/projects"}',cwd=tmp_path,
                          env={**os.environ,'NAVIS_ROOT':str(tmp_path/'never-create-vault')},capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    value=json.loads(result.stdout)
    assert value['status']==200 and value['body']['repositories'][0]['issues']==3
    assert not (tmp_path/'never-create-vault').exists()
