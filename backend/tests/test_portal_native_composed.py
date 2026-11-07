"""Source-bound SDK/native/Forge integration; all Portal/Vault paths are generated fixtures."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import replace

import pytest

_REQUIRED_ENV=("PORTAL_S028_EVIDENCE_ROOT","PORTAL_S028_PINNED_SOURCE","PORTAL_S028_PINNED_PACKAGE",
               "PORTAL_S028_PINNED_PACKAGE_SHA256","PORTAL_S028_FIXTURE_TESTS",
               "PORTAL_S028_FEATURE_RUNTIME","PORTAL_S028_HOST_RUNTIME")
_present={name for name in _REQUIRED_ENV if name in os.environ}
if not _present:
    pytest.skip("Portal S028 acceptance fixture is opt-in",allow_module_level=True)
_missing=sorted(set(_REQUIRED_ENV)-_present)
if _missing:
    raise RuntimeError("PORTAL_S028_FIXTURE_CONTEXT_INCOMPLETE:"+",".join(_missing))

OUTER=Path(os.environ["PORTAL_S028_EVIDENCE_ROOT"]).resolve()
PROTOCOL=Path(__file__).resolve().parents[2]
PINNED_SOURCE=Path(os.environ["PORTAL_S028_PINNED_SOURCE"]).resolve()
PINNED_PACKAGE=Path(os.environ["PORTAL_S028_PINNED_PACKAGE"]).resolve()
PINNED_PACKAGE_SHA256=os.environ["PORTAL_S028_PINNED_PACKAGE_SHA256"]
PINNED_RELEASE_ID=os.environ.get("PORTAL_S028_PINNED_RELEASE_ID")
PORTAL_TESTS=Path(os.environ["PORTAL_S028_FIXTURE_TESTS"]).resolve()
RUNTIME=Path(os.environ["PORTAL_S028_FEATURE_RUNTIME"]).resolve()
HOST_RUNTIME=Path(os.environ["PORTAL_S028_HOST_RUNTIME"]).resolve()
APP_KEY="synthetic-protocol-app-key-01234567890123456789"
UPSTREAM_KEY="synthetic-protocol-upstream-no-network"
MODEL="portal-fixture/byte-chat-v1"
NOW=1_800_000_000_000
BACKEND_MODULES=("services/__init__.py","services/ai_provider.py","services/forge_service.py",
                 "services/portal_forge.py","services/portal_bootstrap.py","services/portal_private_files.py",
                 "services/forge_volatile.py","services/online_ai.py","scripts/forge/forge_companion.py",
                 "scripts/forge/forge_character.py")
COMPOSED_TEST_NAME="p5::portal_forge_tests::composed_native_acquire_and_trusted_portal_forge_fixture"
PREBUILT_BINARY_PATH=(OUTER/"portal-s030-review"/"private"/"s028-native-test-build-06"/
                      "reviewed-test-binary.exe").absolute()

def _prebuilt_binary_path(path_text,expected_sha,selector,*,allowed_path=PREBUILT_BINARY_PATH):
    if selector!=COMPOSED_TEST_NAME:
        raise ValueError("PREBUILT_TEST_SELECTOR_MISMATCH")
    expected_sha=expected_sha if isinstance(expected_sha,str) else ""
    if len(expected_sha)!=64 or any(ch not in "0123456789abcdef" for ch in expected_sha):
        raise ValueError("PREBUILT_TEST_SHA_INVALID")
    if not isinstance(path_text,str) or not path_text:
        raise ValueError("PREBUILT_TEST_PATH_REQUIRED")
    candidate=Path(path_text).absolute()
    if os.path.normcase(os.path.normpath(str(candidate)))!=os.path.normcase(os.path.normpath(str(allowed_path))):
        raise ValueError("PREBUILT_TEST_PATH_MISMATCH")
    try:
        for part in (candidate,*candidate.parents):
            info=part.lstat()
            if part.is_symlink() or getattr(info,"st_file_attributes",0) & 0x400:
                raise ValueError("PREBUILT_TEST_REPARSE_POINT")
        if not candidate.is_file():raise ValueError("PREBUILT_TEST_FILE_REQUIRED")
        observed=hashlib.sha256(candidate.read_bytes()).hexdigest()
    except ValueError:
        raise
    except OSError:
        raise ValueError("PREBUILT_TEST_FILE_UNAVAILABLE") from None
    if observed!=expected_sha:raise ValueError("PREBUILT_TEST_SHA_MISMATCH")
    return candidate,observed

def _select_composed_test_binary(mode,compile_binary,*,path_text=None,expected_sha=None,selector=None,
                                 allowed_path=PREBUILT_BINARY_PATH):
    if mode=="prebuilt":
        return _prebuilt_binary_path(path_text,expected_sha,selector,allowed_path=allowed_path)
    if mode=="compile":
        return compile_binary()
    raise ValueError("COMPOSED_TEST_BINARY_MODE_REQUIRED")

def fixture_environment(extra=None):
    allowed=("SystemRoot","WINDIR","TEMP","TMP","LOCALAPPDATA","APPDATA","USERPROFILE",
             "PROGRAMFILES","PROGRAMFILES(X86)","PROGRAMDATA")
    env={key:os.environ[key] for key in allowed if key in os.environ}
    env["PATH"]=str(Path(env.get("SystemRoot",r"C:\Windows"))/"System32")
    if extra:env.update(extra)
    return env

def fixture_background_record_matches(generation,supervisor,record):
    return (isinstance(record,dict) and record.get("generation")==generation
        and record.get("supervisor")==supervisor)

def test_s028_cleanup_generation_matcher():
    generation="0123456789abcdef0123456789abcdef"
    supervisor={"pid":123,"created":456,"executable":r"C:\\Python314\\python.exe","sid":"S-1-5-18"}
    assert not fixture_background_record_matches(generation,supervisor,None)
    assert not fixture_background_record_matches(generation,supervisor,{"generation":generation,"supervisor":None})
    assert not fixture_background_record_matches(generation,supervisor,{"generation":"f"*32,"supervisor":supervisor})
    assert not fixture_background_record_matches(generation,supervisor,{"generation":generation,"supervisor":{**supervisor,"pid":124}})
    assert fixture_background_record_matches(generation,supervisor,{"generation":generation,"supervisor":supervisor})

def test_s028_prebuilt_binary_selection_never_compiles_or_supervises(tmp_path,monkeypatch):
    binary=tmp_path/"reviewed-test.exe";binary.write_bytes(b"synthetic test executable")
    digest=hashlib.sha256(binary.read_bytes()).hexdigest()
    calls=[]
    selected=_select_composed_test_binary("prebuilt",lambda:calls.append("cargo"),
        path_text=str(binary),expected_sha=digest,selector=COMPOSED_TEST_NAME,allowed_path=binary)
    assert selected==(binary,digest) and calls==[]
    with pytest.raises(ValueError,match="PREBUILT_TEST_SHA_MISMATCH"):
        _select_composed_test_binary("prebuilt",lambda:calls.append("cargo"),
            path_text=str(binary),expected_sha="0"*64,selector=COMPOSED_TEST_NAME,allowed_path=binary)
    assert calls==[]
    with pytest.raises(ValueError,match="PREBUILT_TEST_SELECTOR_MISMATCH"):
        _select_composed_test_binary("prebuilt",lambda:calls.append("cargo"),
            path_text=str(binary),expected_sha=digest,selector="other-test",allowed_path=binary)
    assert calls==[]
    with pytest.raises(ValueError,match="PREBUILT_TEST_PATH_MISMATCH"):
        _select_composed_test_binary("prebuilt",lambda:calls.append("cargo"),
            path_text=str(tmp_path/"other.exe"),expected_sha=digest,selector=COMPOSED_TEST_NAME,allowed_path=binary)
    assert calls==[]
    original_lstat=Path.lstat
    class ReparseStat:
        st_file_attributes=0x400
    monkeypatch.setattr(Path,"lstat",lambda path:ReparseStat() if path==binary else original_lstat(path))
    with pytest.raises(ValueError,match="PREBUILT_TEST_REPARSE_POINT"):
        _select_composed_test_binary("prebuilt",lambda:calls.append("cargo"),
            path_text=str(binary),expected_sha=digest,selector=COMPOSED_TEST_NAME,allowed_path=binary)
    assert calls==[]

def test_s028_prebuilt_mismatch_fails_before_native_setup(monkeypatch):
    calls=[]
    monkeypatch.setenv("PORTAL_S028_TEST_BINARY_MODE","prebuilt")
    monkeypatch.setenv("PORTAL_S028_PREBUILT_TEST_BINARY_PATH",str(OUTER/"not-reviewed.exe"))
    monkeypatch.setenv("PORTAL_S028_PREBUILT_TEST_BINARY_SHA256","0"*64)
    monkeypatch.setenv("PORTAL_S028_PREBUILT_TEST_SELECTOR",COMPOSED_TEST_NAME)
    monkeypatch.setattr(subprocess,"run",lambda *args,**kwargs:calls.append("native-or-cargo"))
    with pytest.raises(ValueError,match="PREBUILT_TEST_PATH_MISMATCH"):
        test_composed_native_acquire_and_real_trusted_forge_worker(monkeypatch)
    assert calls==[]

def assert_real_forge_refuses_existing_destination(forge_service,root):
    from services.forge_service import ForgeError
    root=Path(root).resolve();destination=forge_service.destination(root,"companion","Collision")
    destination.mkdir(parents=True);marker=destination/"fixture-only.txt";marker.write_text("synthetic existing destination",encoding="utf-8")
    provider_calls=[]
    class Provider:
        async def generate(self,*_args,**_kwargs):provider_calls.append(1);raise AssertionError("existing destination reached provider")
    try:
        coroutine=forge_service.submit(root,{"entity_type":"companion","name":"Collision","prompt":"synthetic precondition"},provider=Provider())
        coroutine.send(None)
    except ForgeError:
        pass
    else:
        if 'coroutine' in locals():coroutine.close()
        raise AssertionError("Forge must refuse an existing destination")
    assert not provider_calls and marker.read_text(encoding="utf-8")=="synthetic existing destination"
    assert not (root/".proposals").exists()

def proposal_cache_contains_only_destination_lock(cache, target):
    """Accept only the target-specific lock retained by Forge on this platform."""
    cache = Path(cache)
    target = Path(target)
    try:
        if cache.is_symlink() or not cache.is_dir():
            return False
        for candidate in (cache, *cache.parents):
            info = candidate.lstat()
            if candidate.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                return False
        target_info = target.lstat()
        if target.is_symlink() or getattr(target_info, "st_file_attributes", 0) & 0x400:
            return False
        target = target.resolve(strict=True)
        expected_name = hashlib.sha256(str(target).encode()).hexdigest() + ".lock"
        cache = cache.resolve(strict=True)
        entries = list(cache.iterdir())
        if len(entries) != 1 or entries[0].name != expected_name:
            return False
        lock = entries[0]
        info = lock.lstat()
        if (not stat.S_ISREG(info.st_mode) or lock.is_symlink()
                or getattr(info, "st_file_attributes", 0) & 0x400):
            return False
        expected_bytes = b"0" if os.name == "nt" else b""
        if info.st_size != len(expected_bytes):
            return False
        with lock.open("rb") as stream:
            if stream.read(len(expected_bytes) + 1) != expected_bytes:
                return False
        return True
    except OSError:
        return False

GUARDIAN_RUNNER=r'''import hashlib,json,os,sys
from pathlib import Path
root,release,binary,binary_sha,worker,worker_sha,report,backend=map(Path,sys.argv[1:9])
root=root.resolve(strict=True);release=release.resolve(strict=True);binary=binary.resolve(strict=True)
worker=worker.resolve(strict=True);report=report.resolve();backend=backend.resolve(strict=True)
artifacts=json.loads((root/'fixture-artifacts.json').read_text(encoding='utf-8'))
vault=Path(artifacts['vault_root']).resolve(strict=True)
profile=Path(artifacts['profile_path']).resolve(strict=True)
if Path(artifacts['release_path']).resolve(strict=True)!=release or Path(artifacts['host_root']).resolve(strict=True)!=root:
    raise SystemExit('FIXTURE_ARTIFACT_ROOT_MISMATCH')
if profile.parent!=vault/'private':raise SystemExit('FIXTURE_PROFILE_ROOT_MISMATCH')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
if (sha(binary)!=sys.argv[4] or sha(worker)!=sys.argv[6]
        or Path(artifacts['test_binary_path']).resolve(strict=True)!=binary
        or artifacts['test_binary_sha256']!=sys.argv[4]
        or Path(artifacts['worker_path']).resolve(strict=True)!=worker
        or artifacts['worker_sha256']!=sys.argv[6]
        or artifacts['expected_test_count']!=1
        or artifacts['selected_test_name']!='p5::portal_forge_tests::composed_native_acquire_and_trusted_portal_forge_fixture'):
    raise SystemExit('FIXTURE_BINARY_OR_WORKER_CHANGED')
if (Path(sys.executable).resolve(strict=True)!=Path(artifacts['host_runtime_path']).resolve(strict=True)
        or sha(Path(sys.executable))!=artifacts['host_runtime_sha256']):
    raise SystemExit('FIXTURE_HOST_RUNTIME_CHANGED')
if (artifacts['release_id']!=release.name
        or sha(release/'manifest.json')!=artifacts['manifest_sha256']):
    raise SystemExit('FIXTURE_RELEASE_MANIFEST_CHANGED')
if sha(Path(__file__).resolve(strict=True))!=artifacts['guardian_runner_sha256']:
    raise SystemExit('FIXTURE_GUARDIAN_RUNNER_CHANGED')
if (Path(artifacts['guardian_runner_path']).resolve(strict=True)!=Path(__file__).resolve(strict=True)
        or Path(artifacts['backend_path']).resolve(strict=True)!=backend
        or sha(Path(artifacts['shim_path']).resolve(strict=True))!=artifacts['shim_sha256']):
    raise SystemExit('FIXTURE_HELPER_SOURCE_CHANGED')
if sha(Path(artifacts['package_path']).resolve(strict=True))!=artifacts['package_sha256']:
    raise SystemExit('FIXTURE_PACKAGE_ARCHIVE_CHANGED')
source_root=Path(artifacts['source_root']).resolve(strict=True)
for relative,expected in artifacts['source_files'].items():
    if sha(source_root/relative)!=expected:raise SystemExit('FIXTURE_PORTAL_SOURCE_CHANGED')
for relative,expected in artifacts['backend_sources'].items():
    if sha(backend/relative)!=expected:raise SystemExit('FIXTURE_BACKEND_SOURCE_CHANGED')
if sha(Path(artifacts['composed_test_path']).resolve(strict=True))!=artifacts['composed_test_sha256']:
    raise SystemExit('FIXTURE_COMPOSED_TEST_CHANGED')
if sha(Path(artifacts['p5_source_path']).resolve(strict=True))!=artifacts['p5_source_sha256']:
    raise SystemExit('FIXTURE_P5_SOURCE_CHANGED')
sys.path.insert(0,str(release))
from portal_gateway import host_native,host_profile,background_host
from portal_client import crash_isolation
from portal_client import consumer_launch
from portal_client import consumer_launch
host_native.canonical_root=lambda:root
doc=host_profile.specification()
actual_create_suspended_process=host_native.create_suspended_process
def fixture_create_suspended_process(argv,cwd,environment):
    selected=host_profile.selected_command(doc)
    if (argv!=selected+['background-supervise','--state',doc['state'],'--generation',argv[-1]]
            or not isinstance(argv[-1],str) or len(argv[-1])!=32
            or any(ch not in '0123456789abcdef' for ch in argv[-1])
            or Path(cwd).resolve()!=Path(doc['release']).resolve()
            or environment!=crash_isolation.minimal_environment({})):
        raise RuntimeError('FIXTURE_CONTROLLER_INPUT_MISMATCH')
    command=[doc['runtime']['executable'],'-I','-B',str(worker),'supervise',str(root),str(release),argv[-1]]
    child=actual_create_suspended_process(command,release,environment)
    descriptor=None
    receipt_path=Path(artifacts['controller_receipt_path'])
    try:
        identity=child.identity()
        if identity.get('pid')!=child.pid or type(identity.get('created')) is not int or identity.get('created')<=0:
            raise RuntimeError('FIXTURE_CONTROLLER_IDENTITY_INVALID')
        payload=json.dumps({'schema':1,'generation':argv[-1],'identity':identity,'state':'created_suspended'},sort_keys=True)
        descriptor=os.open(str(receipt_path),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(descriptor,'w',encoding='utf-8',newline='\n') as stream:
            descriptor=None
            stream.write(payload);stream.flush();os.fsync(stream.fileno())
        return child
    except BaseException:
        if descriptor is not None:
            try:os.close(descriptor)
            except OSError:pass
        try:child.terminate_and_wait()
        except Exception:
            host_native.retain_pending_suspended(child)
            raise RuntimeError('FIXTURE_CONTROLLER_CLEANUP_PENDING') from None
        try:child.close()
        except Exception:
            host_native.retain_pending_suspended(child)
            raise RuntimeError('FIXTURE_CONTROLLER_CLEANUP_PENDING') from None
        raise
host_native.create_suspended_process=fixture_create_suspended_process
result=crash_isolation.supervise(str(binary),['--exact',
    'p5::portal_forge_tests::composed_native_acquire_and_trusted_portal_forge_fixture','--nocapture'],
    sys.argv[4],report,seconds=240,
    extra_env={'NAVIS_ROOT':str(vault),'NAVIS_PORTAL_PROFILE':str(profile),
               'NAVIS_PORTAL_ENABLED':'1'},working_directory=release,managed_profile=True,
    portal_lifecycle_broker={'schema_version':1,'enabled':True})
summary={'status':result.get('status'),'root_exit_code':result.get('root_exit_code'),
         'created_processes':result.get('created_processes'),'all_debugged_processes_exited':result.get('all_debugged_processes_exited'),
         'target_memory_read':result.get('target_memory_read'),'dump_written':result.get('dump_written'),
         'credential_environment_inherited':result.get('credential_environment_inherited'),
         'job_breakaway_allowed':result.get('job_breakaway_allowed'),
         'supervisor_payload_read':result.get('supervisor_payload_read'),
         'stdio_forwarded_by_handles':result.get('stdio_forwarded_by_handles'),'report_path':str(report)}
(root/'guardian-runner-result.json').write_text(json.dumps(summary,sort_keys=True),encoding='utf-8')
print(json.dumps(summary,sort_keys=True))
raise SystemExit(0 if summary['status']=='exited' and summary['root_exit_code']==0 else 2)
'''

HOST_WORKER=r'''import hashlib,json,os,socket,subprocess,sys,threading,time
from dataclasses import replace
from pathlib import Path
APP_KEY='synthetic-protocol-app-key-01234567890123456789'
UPSTREAM_KEY='synthetic-protocol-upstream-no-network'
MODEL='portal-fixture/byte-chat-v1'
NOW=1800000000000
role,root,release=sys.argv[1:4]
root=Path(root).resolve(strict=True);release=Path(release).resolve(strict=True);sys.dont_write_bytecode=True
sys.path.insert(0,str(release))
from portal_gateway import service,host_profile,background_host as host,host_native
from portal_gateway.private_files import verify_private_path
from portal_client.crash_isolation import minimal_environment
canonical=host_native.canonical_root().resolve(strict=False)
marker=root/'service-fixture.json'
def safe_error(exc):
    allowed={'HOST_CANCELLED','HOST_START_TIMEOUT','HOST_LAUNCH_REFUSED','HOST_PROFILE_INVALID','HOST_IDENTITY_MISMATCH',
             'HOST_INCOMPATIBLE','HOST_LISTENER_UNTRUSTED','HOST_UNAVAILABLE','HOST_STOP_PENDING','HOST_TIMEOUT_INVALID',
             'HOST_REGISTRATION_EXISTS','HOST_SELECTED_RELEASE_REQUIRED','HOST_INPUT_PIN_FAILED','HOST_PLATFORM_UNSUPPORTED'}
    args=getattr(exc,'args',())
    code=args[0] if args and isinstance(args[0],str) and args[0] in allowed else 'OTHER'
    winerror=getattr(exc,'winerror',None)
    return {'error_type':type(exc).__name__,'code':code,'winerror':winerror if type(winerror) is int else None}
verify_private_path(root);verify_private_path(marker)
fixture=json.loads(marker.read_text(encoding='utf-8'))
if root==canonical or fixture!={'kind':'portal-s028','synthetic_only':True}:raise SystemExit('GENERATED_ROOT_REQUIRED')
host_native.canonical_root=lambda:root
if role=='register':
    print(json.dumps(host_profile.register(_root=root)));raise SystemExit(0)
if role=='status':print(json.dumps(host.status(_root=root,timeout_ms=5000)));raise SystemExit(0)
if role=='incompatible-status':
    registration=host_profile.paths(_root=root)['profile']
    original=registration.read_bytes();expected=json.loads((root/'fixture-artifacts.json').read_text(encoding='utf-8'))['host_profile_sha256']
    if hashlib.sha256(original).hexdigest()!=expected:raise SystemExit('FIXTURE_REGISTRATION_CHANGED_BEFORE_NEGATIVE')
    changed=service.document(registration);changed['release_id']='0'*64 if changed['release_id']!='0'*64 else '1'*64
    acquire_calls=[];actual_acquire=host.acquire
    try:
        service.atomic(registration,changed,replace_attempts=1)
        host.acquire=lambda **kwargs:(acquire_calls.append(1) or (_ for _ in ()).throw(RuntimeError('STATUS_MUST_NOT_ACQUIRE')))
        try:
            host.status(_root=root,timeout_ms=5000);code='UNEXPECTEDLY_ACCEPTED'
        except Exception as exc:
            args=getattr(exc,'args',());candidate=args[0] if args and isinstance(args[0],str) else ''
            code=candidate if candidate in {'HOST_PROFILE_INVALID','HOST_INCOMPATIBLE','HOST_IDENTITY_MISMATCH'} else 'OTHER'
    finally:
        host.acquire=actual_acquire
        restore=registration.with_name(registration.name+'.s028-restore')
        with restore.open('xb') as stream:stream.write(original);stream.flush();os.fsync(stream.fileno())
        os.replace(restore,registration);verify_private_path(registration)
    restored=hashlib.sha256(registration.read_bytes()).hexdigest()
    print(json.dumps({'state':'refused' if code=='HOST_PROFILE_INVALID' else 'unexpected',
        'error_code':code,'acquire_calls':len(acquire_calls),'registration_restored':restored==expected,
        'registration_sha256':restored,'status_only':True}));raise SystemExit(0 if code=='HOST_PROFILE_INVALID' and not acquire_calls and restored==expected else 3)
if role=='stop':print(json.dumps(host.stop(sys.argv[4],_root=root,timeout_ms=10000)));raise SystemExit(0)
if role=='run':
    from portal_gateway.gateway import Gateway
    fields=('name','role','gender','height','home_realm','voice_id','personality','atmosphere','description')
    def fake(payload,key,timeout):
        if key!=UPSTREAM_KEY:raise RuntimeError('SYNTHETIC_UPSTREAM_KEY_MISMATCH')
        counter=root/'provider-dispatch-count.json'
        count=json.loads(counter.read_text(encoding='utf-8'))['count'] if counter.exists() else 0
        service.atomic(counter,{'count':count+1})
        mode_doc={'mode':'success'}
        marker=root/'provider-mode.json'
        if marker.exists():mode_doc=json.loads(marker.read_text(encoding='utf-8'))
        mode=mode_doc['mode']
        blueprint={field:'Generated fixture' for field in fields};blueprint.update(name=mode_doc.get('name','Aster'),voice_id='en-US-JennyNeural')
        content=json.dumps(blueprint,separators=(',',':'))
        prompt=2+sum(2+len(message['content'].encode()) for message in payload['messages'])
        output=len(content.encode())
        result={'model':MODEL,'choices':[{'index':0,'message':{'role':'assistant','content':content},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':prompt,'completion_tokens':output,'total_tokens':prompt+output,
                         'cost':str((prompt*3+output*12)/10**7)}}
        if mode=='missing-usage':result.pop('usage')
        if mode=='block':
            service.atomic(root/'provider-dispatch-started.json',{'pid':os.getpid(),'model':MODEL})
            deadline=time.monotonic()+25
            while not (root/'provider-release.flag').exists():
                if time.monotonic()>=deadline:raise RuntimeError('S028_FIXTURE_PROVIDER_DEADLINE')
                time.sleep(.005)
            service.atomic(root/'provider-dispatch-finished.json',{'pid':os.getpid(),'model':MODEL})
            raise OSError('S028_SYNTHETIC_DISPATCH_INTERRUPTED')
        return json.dumps(result,separators=(',',':')).encode()
    raw=service.document(root/'portal-state/config.json')
    from portal_gateway.config import Config
    cfg=Config.from_dict(raw,root/'portal-state',{})
    gateway=Gateway(replace(cfg,credential_namespace=None,metadata=None),{'test-app':APP_KEY},UPSTREAM_KEY,
                    transport=fake,clock_ms=lambda:NOW)
    service.run(root/'portal-state',gateway_factory=lambda _cfg:gateway)
    raise SystemExit(0)
if role=='supervise':
    from portal_client.crash_isolation import supervise as actual_guard
    generation=sys.argv[4]
    def fixture_guard(executable,arguments,*args,**kwargs):
        doc=host_profile.specification()
        selected=host_profile.selected_command(doc)
        if (executable!=selected[0] or arguments!=selected[1:]+['run','--state',doc['state']]
                or not args or args[0]!=doc['runtime']['sha256']
                or kwargs.get('seconds')!=0 or kwargs.get('managed_profile') is not True):
            raise RuntimeError('S028_FIXTURE_GUARDED_SERVICE_COMMAND_MISMATCH')
        artifacts=json.loads((root/'fixture-artifacts.json').read_text(encoding='utf-8'))
        fixture_seconds=artifacts.get('fixture_guard_seconds')
        if type(fixture_seconds) is not int or fixture_seconds!=180:
            raise RuntimeError('S028_FIXTURE_GUARD_BOUND_MISMATCH')
        return actual_guard(executable,['-I','-B',str(Path(__file__).resolve()),'run',str(root),str(release)],
            args[0],args[1],seconds=fixture_seconds,working_directory=release,managed_profile=True,
            created_callback=kwargs.get('created_callback'))
    try:report=host.supervise(generation,_root=root,_guard=fixture_guard)
    except Exception as exc:
        service.atomic(root/'supervisor-result.json',safe_error(exc))
        raise
    service.atomic(root/'supervisor-result.json',{'root_exit_code':report.get('root_exit_code'),
        'status':report.get('status'),'created_processes':report.get('created_processes'),
        'all_debugged_processes_exited':report.get('all_debugged_processes_exited'),
        'target_memory_read':report.get('target_memory_read'),'dump_written':report.get('dump_written'),
        'credential_environment_inherited':report.get('credential_environment_inherited'),
        'job_breakaway_allowed':report.get('job_breakaway_allowed'),
        'stdio_forwarded_by_handles':report.get('stdio_forwarded_by_handles'),
        'supervisor_payload_read':report.get('supervisor_payload_read')})
    raise SystemExit(0 if report.get('root_exit_code')==0 else 2)
raise SystemExit(2)
'''

CLI_SHIM=r'''import contextlib,hashlib,importlib,json,os,runpy,sys
from pathlib import Path
backend=Path.cwd().resolve()
if not (backend/'services'/'forge_service.py').is_file():raise RuntimeError('S028_BACKEND_WORKDIR_INVALID')
sys.path.insert(0,str(backend))
profile_path=Path(os.environ['NAVIS_PORTAL_PROFILE']).resolve(strict=True)
feature=json.loads(profile_path.read_text(encoding='utf-8'))
root=Path(feature['portal_state']).resolve().parent
release=Path(feature['portal_release_root']).resolve(strict=True);sys.path.insert(0,str(release))
artifacts=json.loads((root/'fixture-artifacts.json').read_text(encoding='utf-8'))
if Path(artifacts['backend_path']).resolve(strict=True)!=backend:raise RuntimeError('S028_BACKEND_ROOT_MISMATCH')
if Path(__file__).resolve(strict=True)!=Path(artifacts['shim_path']).resolve(strict=True):raise RuntimeError('S028_SHIM_PATH_MISMATCH')
if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=artifacts['shim_sha256']:raise RuntimeError('S028_SHIM_SOURCE_CHANGED')
for relative,expected in artifacts['backend_sources'].items():
    if hashlib.sha256((backend/relative).read_bytes()).hexdigest()!=expected:raise RuntimeError('S028_BACKEND_SOURCE_CHANGED')
mode_path=root/'provider-mode.json'
if mode_path.exists() and json.loads(mode_path.read_text(encoding='utf-8')).get('mode')=='block':
    (root/'portal-cli-blocked-worker.json').write_text(json.dumps({'pid':os.getpid(),'role':'forge-cli'}),encoding='utf-8')
from portal_gateway import background_host,host_profile,host_native
from portal_gateway.credentials import WindowsCredentialBroker
original_reviewed=host_profile.reviewed;original_paths=host_profile.paths;original_status=background_host.status
host_profile.reviewed=lambda **_kwargs:original_reviewed(_root=root)
def fixture_paths(*args,_root=None):
    if len(args)>1:raise RuntimeError("S028_HOST_ROOT_ARGUMENT_COUNT")
    requested=args[0] if args else _root
    if args and _root is not None and Path(args[0]).resolve()!=Path(_root).resolve():
        raise RuntimeError("S028_HOST_ROOT_CONFLICT")
    if requested is not None and Path(requested).resolve()!=root:
        raise RuntimeError("S028_HOST_ROOT_MISMATCH")
    return original_paths(_root=root)
host_profile.paths=fixture_paths
background_host.status=lambda **kwargs:original_status(_root=root,**kwargs)
def forbidden_acquire(*_args,**_kwargs):raise RuntimeError('NATIVE_GENERATION_REQUIRED_NO_PYTHON_ACQUIRE')
background_host.acquire=forbidden_acquire
host_native.canonical_root=lambda:root
def read_only_synthetic_credential(_self,target):
    if target=='Navis-Portal/Protocol/s028-synthetic-only':return b'synthetic-protocol-app-key-01234567890123456789'
    raise RuntimeError('S028_CREDENTIAL_TARGET_NOT_ALLOWED')
WindowsCredentialBroker.read=read_only_synthetic_credential
sys.argv=['services.forge_service','portal-worker']
runpy.run_module('services.forge_service',run_name='__main__')
'''


@pytest.mark.skipif(os.name!="nt",reason="published Rust SDK host fixtures are Windows-only")
def test_composed_native_acquire_and_real_trusted_forge_worker(monkeypatch):
    if not RUNTIME.is_file():pytest.skip("offline Python 3.14.8 fixture runtime unavailable")
    binary_mode=os.environ.get("PORTAL_S028_TEST_BINARY_MODE")
    prebuilt_binary=None
    if binary_mode=="prebuilt":
        prebuilt_binary=_select_composed_test_binary("prebuilt",lambda:(_ for _ in ()).throw(
            AssertionError("Cargo is forbidden in reviewed prebuilt mode")),
            path_text=os.environ.get("PORTAL_S028_PREBUILT_TEST_BINARY_PATH"),
            expected_sha=os.environ.get("PORTAL_S028_PREBUILT_TEST_BINARY_SHA256"),
            selector=os.environ.get("PORTAL_S028_PREBUILT_TEST_SELECTOR"))
    elif binary_mode not in (None,"compile"):
        raise ValueError("COMPOSED_TEST_BINARY_MODE_INVALID")
    import socket as _socket
    sys.path.insert(0,str(PORTAL_TESTS));sys.path.insert(0,str(PINNED_SOURCE));sys.path.insert(0,str(PROTOCOL/"backend"))
    target=OUTER/"portal-s030-review"/"private"
    assert target.is_dir(),"protected private evidence folder must already exist"
    run=target/f"s028-native-composed-{uuid.uuid4().hex[:8]}"
    host_root=run/"host";vault=run/"empty-vault";private=vault/"private"
    profile_path=private/"portal-profile.json"
    monkeypatch.setenv("NAVIS_ROOT",str(vault));monkeypatch.setenv("NAVIS_PORTAL_PROFILE",str(profile_path))
    monkeypatch.setenv("NAVIS_PORTAL_ENABLED","1")
    backend_path=PROTOCOL/"backend"
    backend_sources={relative:hashlib.sha256((backend_path/relative).read_bytes()).hexdigest() for relative in BACKEND_MODULES}
    from portal_gateway.private_files import create_private_directory
    create_private_directory(run);create_private_directory(host_root);create_private_directory(vault);create_private_directory(private)
    proposal_cache=Path(tempfile.gettempdir())/"navis-forge"/hashlib.sha256(str(vault.resolve()).encode()).hexdigest()[:24]
    from portal_gateway import service
    from portal_gateway.commitment import commitment
    from portal_gateway.config import Config
    from portal_gateway.store import BudgetStore
    from services import forge_service
    from test_gateway import config

    assert_real_forge_refuses_existing_destination(forge_service,run/"forge-existing-destination")

    (vault/"Bridge").mkdir()
    (vault/"Bridge/ai_experiments.json").write_text(json.dumps({"enabled":True,"allow_vault_content":True,"monthly_budget_usd":1}),encoding="utf-8")
    host_state=host_root/"portal-state";releases=host_root/"portal-releases"
    host_runtime_sha=hashlib.sha256(HOST_RUNTIME.read_bytes()).hexdigest()
    venv_runtime_sha=hashlib.sha256(RUNTIME.read_bytes()).hexdigest()
    original_runtime=service.runtime
    service.runtime=lambda:{"executable":str(HOST_RUNTIME.resolve()),"sha256":host_runtime_sha}
    try:service.initialize(host_state,releases)
    finally:service.runtime=original_runtime
    raw=config(host_state/"ledger.sqlite3",calls=100,input_cap=16384)
    raw["limits"]["max_output_tokens_per_call"]=1024
    raw["apps"][0]["data_class"]="public"
    raw["apps"][0].pop("key_env",None)
    route=raw["routes"][0]
    route.update(model_id=MODEL,canonical_model_id=MODEL,provider_only="fixture/local",endpoint_tag="fixture/local",
                 token_profile="fixture-byte-chat-v1",max_output_tokens=1024)
    route["evidence"].update(model_id=MODEL,canonical_model_id=MODEL,provider_only="fixture/local",endpoint_tag="fixture/local")
    raw.pop("upstream_api_key_env",None)
    raw["credentials"]={"backend":"windows","namespace":"s028-synthetic-no-read"}
    with _socket.socket() as free:free.bind(("127.0.0.1",0));raw["listen"]["port"]=free.getsockname()[1]
    service.atomic(host_state/"config.json",raw)
    sha=hashlib.sha256(PINNED_PACKAGE.read_bytes()).hexdigest()
    assert sha==PINNED_PACKAGE_SHA256,"pinned Portal package archive hash differs from the explicit fixture receipt"
    service.runtime=lambda:{"executable":str(HOST_RUNTIME.resolve()),"sha256":host_runtime_sha}
    try:release_id=service.install(PINNED_PACKAGE,sha,host_state,releases)
    finally:service.runtime=original_runtime
    if PINNED_RELEASE_ID is not None:assert release_id==PINNED_RELEASE_ID,"installed release differs from pinned current package receipt"
    release=releases/release_id
    package_manifest=json.loads((release/"manifest.json").read_text(encoding="utf-8"))
    source_files={}
    for relative,expected in sorted(package_manifest["files"].items()):
        source_file=PINNED_SOURCE/Path(relative)
        assert source_file.is_file(),f"pinned source snapshot lacks packaged file {relative}"
        observed=hashlib.sha256(source_file.read_bytes()).hexdigest()
        assert observed==expected,f"source snapshot and installed package differ for {relative}"
        source_files[relative]=observed
    manifest_sha=hashlib.sha256((release/"manifest.json").read_bytes()).hexdigest()
    service.atomic(host_root/"service-fixture.json",{"kind":"portal-s028","synthetic_only":True})
    create_private_directory(host_root/"launches")
    worker=host_root/"s028-host-worker.py";worker.write_text(HOST_WORKER,encoding="utf-8",newline="\n")
    worker_sha=hashlib.sha256(worker.read_bytes()).hexdigest()
    # Register with the exact protected profile shape expected by the published host-fixture constructor.
    environment=fixture_environment({"NAVIS_ROOT":str(vault),"NAVIS_PORTAL_ENABLED":"1"})
    register=subprocess.run([str(HOST_RUNTIME),"-I","-B",str(worker),"register",str(host_root),str(release),str(HOST_RUNTIME),host_runtime_sha],
        capture_output=True,text=True,env=environment,timeout=30)
    assert register.returncode==0,register.stdout+register.stderr
    accounting=run/"accounting"
    create_private_directory(accounting)
    feature_ledger=accounting/"portal-forge.sqlite3"
    cfg=Config.from_dict(raw,host_state,{})
    profile={"schema_version":2,"feature":"forge","host_mode":"shared","portal_release_root":str(release),
        "portal_release_id":release_id,"portal_state":str(host_state),"app_key_target":"Navis-Portal/Protocol/s028-synthetic-only",
        "commitment":commitment(replace(cfg,credential_namespace=None,metadata=None),"test-app","deepseek-small")[1],"alias":"deepseek-small","canonical_model_id":MODEL,
        "endpoint_tag":"fixture/local","feature_ledger":str(feature_ledger),"feature_caps":{"usd_micros":30000,"calls":5,"tokens":30000},
        "max_input_bytes":12000,"max_input_tokens":12000,"max_tokens":1024,"timeout_seconds":5,"call_ceiling_micros":10000}
    service.atomic(profile_path,profile)
    binding_probe = r'''import json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve(strict=True); release=Path(sys.argv[2]).resolve(strict=True)
expected_runtime=Path(sys.argv[3]).resolve(strict=True); expected_runtime_sha=sys.argv[4]
sys.path.insert(0,str(release))
from portal_gateway import host_native
from portal_gateway import host_profile,background_host
from portal_client import crash_isolation,consumer_launch,guardian_lifecycle
host_native.canonical_root=lambda:root
binding=None
try:
 binding=guardian_lifecycle.capture_host_binding()
 identity=binding.get("identity",{})
 if (identity.get("release_id")!=release.name
     or Path(identity.get("runtime",{}).get("executable","")).resolve()!=expected_runtime
     or identity.get("runtime",{}).get("sha256")!=expected_runtime_sha):
  raise RuntimeError("BINDING_PREFLIGHT_IDENTITY")
 profile_sha=identity.get("profile_sha256")
 if not isinstance(profile_sha,str) or len(profile_sha)!=64:raise RuntimeError("BINDING_PREFLIGHT_PROFILE")
 binding["pins"].__exit__(None,None,None);binding=None
 print(json.dumps({"status":"passed","release_id":release.name,"profile_sha256":profile_sha,"consumer_launch_loaded":"portal_client.consumer_launch" in sys.modules,"pins_released":True},sort_keys=True,separators=(",",":")))
finally:
 if binding is not None:binding["pins"].__exit__(None,None,None)
'''
    probe = subprocess.run([str(HOST_RUNTIME),"-I","-B","-c",binding_probe,str(host_root),str(release),str(HOST_RUNTIME),host_runtime_sha],
        cwd=release,env=fixture_environment(),capture_output=True,text=True,timeout=45)
    assert probe.returncode==0 and not probe.stderr.strip(),"generated guardian binding preflight failed"
    binding_result=json.loads(probe.stdout)
    assert (binding_result.get("status")=="passed" and binding_result.get("release_id")==release_id
            and binding_result.get("consumer_launch_loaded") is True and binding_result.get("pins_released") is True
            and isinstance(binding_result.get("profile_sha256"),str) and len(binding_result["profile_sha256"])==64)
    service.atomic(host_root/"guardian-binding-preflight.json",binding_result)
    shim=run/"portal-s028-cli-shim.py";shim.write_text(CLI_SHIM,encoding="utf-8",newline="\n")
    artifacts={"schema":1,"kind":"portal-s028-native-composed","host_root":str(host_root.resolve()),
        "vault_root":str(vault.resolve()),"profile_path":str(profile_path.resolve()),"release_id":release_id,
        "release_path":str(release.resolve()),"package_path":str(PINNED_PACKAGE.resolve()),"package_sha256":sha,
        "source_root":str(PINNED_SOURCE.resolve()),"manifest_sha256":manifest_sha,
        "source_files":source_files,"worker_path":str(worker.resolve()),"worker_sha256":worker_sha,
        "shim_path":str(shim.resolve()),"shim_sha256":hashlib.sha256(shim.read_bytes()).hexdigest(),
        "backend_path":str(backend_path.resolve()),"backend_sources":backend_sources,
        "host_runtime_path":str(HOST_RUNTIME.resolve()),"host_runtime_sha256":host_runtime_sha,
        "feature_test_runtime_path":str(RUNTIME.resolve()),"feature_test_runtime_sha256":venv_runtime_sha,
        "host_profile_sha256":hashlib.sha256((host_root/"launches"/"portal-background.json").read_bytes()).hexdigest(),
        "fixture_guard_seconds":180,
        "controller_receipt_path":str((host_root/"fixture-controller.json").resolve()),
        "proposal_cache_path":str(proposal_cache.resolve()),
        "fixture_test_file_sha256":hashlib.sha256((PORTAL_TESTS/"test_gateway.py").read_bytes()).hexdigest(),
        "composed_test_path":str(Path(__file__).resolve()),
        "composed_test_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "p5_source_path":str((PROTOCOL/"frontend/src-tauri/src/p5.rs").resolve()),
        "p5_source_sha256":hashlib.sha256((PROTOCOL/"frontend/src-tauri/src/p5.rs").read_bytes()).hexdigest()}
    service.atomic(host_root/"fixture-artifacts.json",artifacts)
    def host_worker_role(role,label,*args,timeout=25):
        role_env=fixture_environment({"NAVIS_ROOT":str(vault),"NAVIS_PORTAL_ENABLED":"1"})
        proc=subprocess.run([str(HOST_RUNTIME),"-I","-B",str(worker),role,str(host_root),str(release),*args],
            capture_output=True,text=True,env=role_env,cwd=release,timeout=timeout)
        (run/f"host-{label}.log").write_text(proc.stdout+proc.stderr,encoding="utf-8")
        (run/f"host-{label}.log.exit").write_text(str(proc.returncode),encoding="ascii")
        assert proc.returncode==0,f"generated host {role} failed: {proc.stdout}{proc.stderr}"
        return json.loads(proc.stdout)
    controller_path=host_root/"fixture-controller.json"
    cleanup_path=run/"owned-host-stop.json"
    def cleanup_owned_generation():
        if not controller_path.is_file():
            return {"state":"controller_not_created"}
        stage="controller_receipt"
        try:
            controller=json.loads(controller_path.read_text(encoding="utf-8"))
            if (set(controller)!={"schema","generation","identity","state"} or controller["schema"]!=1
                    or controller["state"]!="created_suspended" or type(controller["generation"]) is not str  # noqa: E721 - exact JSON scalar type required
                    or len(controller["generation"])!=32
                    or any(ch not in "0123456789abcdef" for ch in controller["generation"])):
                raise ValueError("FIXTURE_CONTROLLER_RECEIPT_INVALID")
            identity=controller["identity"]
            if (not isinstance(identity,dict) or set(identity)!={"pid","created","executable","sid"}
                    or type(identity["pid"]) is not int  # noqa: E721 - exact JSON scalar type required
                    or identity["pid"]<1 or type(identity["created"]) is not int  # noqa: E721 - exact JSON scalar type required
                    or identity["created"]<1
                    or not isinstance(identity["executable"],str) or not isinstance(identity["sid"],str)):
                raise ValueError("FIXTURE_CONTROLLER_IDENTITY_INVALID")
            stage="starting_record_wait"
            generation=controller["generation"]
            record_path=host_state/"background.json"
            deadline=time.monotonic()+15.0
            observed=None
            current=None
            attempts=0
            while time.monotonic()<deadline:
                if record_path.exists():
                    current=json.loads(record_path.read_text(encoding="utf-8"))
                    if not fixture_background_record_matches(generation,identity,current):
                        raise ValueError("FIXTURE_OWNED_CONTROLLER_RECORD_MISMATCH")
                attempts+=1
                remaining=deadline-time.monotonic()
                try:
                    observed=host_worker_role("status",f"status-before-stop-{attempts}",timeout=max(1.0,min(7.0,remaining)))
                except Exception:
                    observed=None
                if (current is not None and observed is not None
                        and observed.get("state") in ("running","stopped")):
                    break
                time.sleep(min(0.25,max(0.0,deadline-time.monotonic())))
            if current is None or observed is None or observed.get("state") not in ("running","stopped"):
                raise TimeoutError("FIXTURE_OWNED_RECORD_NOT_READY")
            if observed.get("state")=="running":
                if observed.get("generation")!=controller["generation"]:
                    raise ValueError("FIXTURE_OWNED_CONTROLLER_GENERATION_MISMATCH")
                stage="stop_exact_generation"
                stopped=host_worker_role("stop","stop-owned-generation",controller["generation"])
                if stopped.get("state")!="stopped" or stopped.get("generation")!=controller["generation"]:
                    raise ValueError("FIXTURE_OWNED_STOP_UNCONFIRMED")
            elif observed.get("state")!="stopped":
                raise ValueError("FIXTURE_OWNED_HOST_NOT_READY_FOR_STOP")
            stage="status_after_stop"
            final=host_worker_role("status","status-after-stop")
            if final.get("state")!="stopped":raise ValueError("FIXTURE_OWNED_HOST_STILL_RUNNING")
            retained=json.loads((host_state/"background.json").read_text(encoding="utf-8"))
            if retained.get("generation")!=controller["generation"] or retained.get("supervisor")!=identity:
                raise ValueError("FIXTURE_STOPPED_HISTORY_CHANGED")
            return {"state":"stopped","generation":controller["generation"],"supervisor":identity,
                    "history_retained":True,"instance_retained":(host_state/"instance.json").is_file()}
        except Exception as exc:
            return {"state":"cleanup_pending","stage":stage,"error_type":type(exc).__name__}
    def save_cleanup_receipt(value):
        with cleanup_path.open("x",encoding="utf-8",newline="\n") as stream:
            json.dump({"schema":1,"cleanup":value},stream,sort_keys=True);stream.write("\n")
    out_dir=PROTOCOL/"frontend"/"out";made_out=not out_dir.exists()
    if made_out:
        out_dir.mkdir();(out_dir/"index.html").write_text("<!doctype html><title>fixture</title>",encoding="utf-8")
    try:
        if prebuilt_binary is not None:
            test_binary,test_binary_sha=prebuilt_binary
            binary_selection="reviewed_prebuilt_no_cargo"
        else:
            def compile_binary():
                cargo=shutil.which("cargo")
                assert cargo,"Cargo unavailable"
                cargo_env=fixture_environment({"CARGO_HOME":os.environ.get("CARGO_HOME",str(Path.home()/".cargo")),
                    "RUSTUP_HOME":os.environ.get("RUSTUP_HOME",str(Path.home()/".rustup")),
                    "CARGO_TARGET_DIR":str(OUTER/"portal-s028-review"/"target")})
                result=subprocess.run([cargo,"test","--release","--manifest-path",str(PROTOCOL/"frontend/src-tauri/Cargo.toml"),
                    "--offline","--locked","--no-run","--message-format=json"],
                    capture_output=True,text=True,env=cargo_env,cwd=PROTOCOL,timeout=600)
                (run/"cargo-build-test-binary.log").write_text(result.stdout+result.stderr,encoding="utf-8")
                (run/"cargo-build-test-binary.log.exit").write_text(str(result.returncode),encoding="ascii")
                assert result.returncode==0,result.stdout+result.stderr
                artifacts_json=[]
                for line in result.stdout.splitlines():
                    try:event=json.loads(line)
                    except json.JSONDecodeError:continue
                    target_doc=event.get("target",{})
                    if (event.get("reason")=="compiler-artifact" and target_doc.get("name")=="navis_protocol_lib"
                            and event.get("profile",{}).get("test") is True and event.get("executable")):
                        artifacts_json.append(Path(event["executable"]).resolve())
                assert len(artifacts_json)==1,"could not identify exactly one filtered Rust test executable"
                selected=artifacts_json[0];selected_sha=hashlib.sha256(selected.read_bytes()).hexdigest()
                expected_test_binary_sha=os.environ.get("PORTAL_S028_EXPECTED_TEST_BINARY_SHA256","")
                assert (len(expected_test_binary_sha)==64 and all(ch in "0123456789abcdef" for ch in expected_test_binary_sha)
                        and selected_sha==expected_test_binary_sha),"selected release test binary differs from the pre-reviewed hash"
                return selected,selected_sha
            test_binary,test_binary_sha=_select_composed_test_binary("compile",compile_binary)
            binary_selection="cargo_compile_then_hash_gate"
        guardian_runner=run/"s028-guardian-runner.py"
        guardian_runner.write_text(GUARDIAN_RUNNER,encoding="utf-8",newline="\n")
        guardian_runner_sha=hashlib.sha256(guardian_runner.read_bytes()).hexdigest()
        artifacts.update({"test_binary_path":str(test_binary),"test_binary_sha256":test_binary_sha,
            "selected_test_name":COMPOSED_TEST_NAME,"test_binary_selection":binary_selection,
            "expected_test_count":1,"guardian_runner_path":str(guardian_runner.resolve()),
            "guardian_runner_sha256":guardian_runner_sha})
        service.atomic(host_root/"fixture-artifacts.json",artifacts)
        assert hashlib.sha256((release/"manifest.json").read_bytes()).hexdigest()==manifest_sha
        supervisor_report=host_root/"guardian-report.json"
        minimal=fixture_environment()
        guardian=None
        invocation_marker=run/"native-guard-invocation-attempted.json"
        with invocation_marker.open("x",encoding="utf-8",newline="\n") as marker:
            json.dump({"schema":1,"stage":"guardian_supervise_invocation_attempted",
                       "test_binary_sha256":test_binary_sha,"selected_test_name":COMPOSED_TEST_NAME},marker,sort_keys=True)
            marker.write("\n");marker.flush();os.fsync(marker.fileno())
        try:
            guardian=subprocess.run([str(HOST_RUNTIME),"-I","-B",str(guardian_runner),str(host_root),str(release),
                str(test_binary),test_binary_sha,str(worker),worker_sha,str(supervisor_report),str(PROTOCOL/"backend")],
                capture_output=True,text=True,env=minimal,cwd=release,timeout=270)
            (run/"guardian-composed.log").write_text(guardian.stdout+guardian.stderr,encoding="utf-8")
            (run/"guardian-composed.log.exit").write_text(str(guardian.returncode),encoding="ascii")
        except subprocess.TimeoutExpired as exc:
            stdout=exc.stdout.decode("utf-8","replace") if isinstance(exc.stdout,bytes) else (exc.stdout or "")
            stderr=exc.stderr.decode("utf-8","replace") if isinstance(exc.stderr,bytes) else (exc.stderr or "")
            (run/"guardian-composed.log").write_text(stdout+stderr,encoding="utf-8")
            (run/"guardian-composed.log.exit").write_text("timeout",encoding="ascii")
            raise
        finally:
            cleanup=cleanup_owned_generation()
            save_cleanup_receipt(cleanup)
            if cleanup["state"]=="cleanup_pending":
                raise RuntimeError("FIXTURE_OWNED_HOST_CLEANUP_PENDING")
        if guardian is not None and guardian.returncode==0:
            assert cleanup["state"]=="stopped","successful composed test must stop its exact generated host"
        assert guardian.returncode==0,guardian.stdout+guardian.stderr
        runner_result=json.loads((host_root/"guardian-runner-result.json").read_text(encoding="utf-8"))
        assert runner_result["status"]=="exited" and runner_result["root_exit_code"]==0
        assert runner_result["all_debugged_processes_exited"] is True
        assert runner_result["target_memory_read"] is False
        assert runner_result["dump_written"] is False
        assert runner_result["credential_environment_inherited"] is False
        assert runner_result["job_breakaway_allowed"] is False
        assert runner_result["supervisor_payload_read"] is False
        assert runner_result["stdio_forwarded_by_handles"] is False
        host_guard=json.loads((host_root/"supervisor-result.json").read_text(encoding="utf-8"))
        assert host_guard["status"]=="exited" and host_guard["root_exit_code"]==0
        assert type(host_guard["created_processes"]) is int and host_guard["created_processes"]>0  # noqa: E721 - exact JSON scalar type required
        assert host_guard["all_debugged_processes_exited"] is True
        assert host_guard["target_memory_read"] is False and host_guard["dump_written"] is False
        assert host_guard["credential_environment_inherited"] is False
        assert host_guard["job_breakaway_allowed"] is False and host_guard["supervisor_payload_read"] is False
        assert host_guard["stdio_forwarded_by_handles"] is False
        assert all(hashlib.sha256((backend_path/relative).read_bytes()).hexdigest()==expected
            for relative,expected in backend_sources.items()),"pinned Python backend sources changed during native flow"
        close_result=json.loads((host_root/"native-close-equivalent-result.json").read_text(encoding="utf-8"))
        assert close_result["webview_launched"] is False and close_result["provider_dispatch_observed"] is True
        assert close_result["host_generation_before"]==close_result["host_generation_after_close"]
        expected_phases={
            "started":(None,None,0),"stopped":(None,None,0),"cancelled-acquire":(None,"not_sent",0),
            "acquired":(None,None,0),"shared-attach":(None,None,0),"running-status":(None,None,0),
            "submit-settled":(200,"settled",1),"duplicate-unknown":(409,"duplicate_unknown",1),
            "close-dispatch-started":(None,None,2),"close-cancelled":(409,"unresolved",2),
            "host-still-shared":(None,None,2),"missing-usage-unresolved":((409,503),"unresolved",3),
            "complete":(200,"unresolved",3)}
        assert not (host_root/"native-test-acquire-error.json").exists(),"successful acquire must not leave an error marker"
        phase_files=list(host_root.glob("native-test-phase-*.json"))
        assert len(phase_files)==len(expected_phases),"exactly one pinned native test must leave its complete phase set"
        for phase,(expected_status,expected_billing,expected_dispatches) in expected_phases.items():
            phase_path=host_root/f"native-test-phase-{phase}.json"
            value=json.loads(phase_path.read_text(encoding="utf-8"))
            assert value["schema"]==1 and value["phase"]==phase
            if isinstance(expected_status,tuple):assert value["status"] in expected_status
            else:assert value["status"]==expected_status
            assert value["billing_state"]==expected_billing and value["provider_dispatch_count"]==expected_dispatches
        assert cleanup["state"]=="stopped" and cleanup["generation"]==close_result["host_generation_after_close"]
        assert cleanup["history_retained"] is True and cleanup["instance_retained"] is True
        incompatible=host_worker_role("incompatible-status","incompatible-release")
        assert incompatible=={"state":"refused","error_code":"HOST_PROFILE_INVALID","acquire_calls":0,
            "registration_restored":True,"registration_sha256":artifacts["host_profile_sha256"],"status_only":True}
        after_incompatible=host_worker_role("status","status-after-incompatible")
        assert after_incompatible["state"]=="stopped"
        assert hashlib.sha256((host_root/"launches"/"portal-background.json").read_bytes()).hexdigest()==artifacts["host_profile_sha256"]
    finally:
        if made_out:
            (out_dir/"index.html").unlink(missing_ok=True);out_dir.rmdir()
    # The composed Rust test covers native stop/start/share, duplicate and missing-usage requests,
    # plus app-close-equivalent cancellation of an active synthetic dispatch.
    feature_book=BudgetStore(feature_ledger)
    try:feature_calls=feature_book.snapshot()["calls"]
    finally:feature_book.close()
    assert sorted(call["status"] for call in feature_calls)==["settled","unresolved","unresolved"]
    assert [call["reserved_usd"] for call in feature_calls if call["status"]=="unresolved"]==[10000,10000]
    assert json.loads((host_root/"provider-dispatch-count.json").read_text(encoding="utf-8"))["count"]==3
    approved_target=forge_service.destination(vault,"companion","Aster")
    assert proposal_cache_contains_only_destination_lock(proposal_cache,approved_target),"proposal cache may retain only the exact approved-target OS lock"
    receipt={"status":"passed","release_id":release_id,"host_worker_sha256":worker_sha,
        "portal_source_identity":"unshipped source snapshot pinned by package archive SHA and manifest-listed file hashes",
        "portal_package_sha256":sha,"portal_manifest_sha256":manifest_sha,
        "portal_source_files_sha256":source_files,
        "host_runtime":{"path":str(HOST_RUNTIME.resolve()),"sha256":host_runtime_sha,"role":"registered SDK/host interpreter"},
        "feature_test_runtime":{"path":str(RUNTIME.resolve()),"sha256":venv_runtime_sha,"role":"pytest and private fixture setup only"},
        "cli_shim_sha256":hashlib.sha256(shim.read_bytes()).hexdigest(),"profile_sha256":hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        "close_equivalent_receipt_sha256":hashlib.sha256((host_root/"native-close-equivalent-result.json").read_bytes()).hexdigest(),
        "incompatible_release_refusal":incompatible,
        "target":str(target/"target"),"fixture_root":str(run)}
    receipt_path=run/"composed-receipt.json"
    receipt_path.write_text(json.dumps(receipt,indent=2),encoding="utf-8")
