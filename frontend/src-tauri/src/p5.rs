use serde_json::{json, Value};
use std::collections::HashMap;
use std::hash::{Hash, Hasher};
use std::io::{BufRead, Read, Write};
#[cfg(test)]
use std::path::Path;
use std::path::PathBuf;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc, Mutex,
};
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::{AppHandle, Emitter, State};

const PORTAL_STARTUP_ACQUIRE_TIMEOUT: std::time::Duration = std::time::Duration::from_secs(30);

#[derive(Default)]
struct PortalCancelGate{cancelled:bool,dispatched:bool}
#[derive(Clone,Default)]
pub struct PortalCancellation{gate:Arc<Mutex<PortalCancelGate>>,sdk:portal_client::Cancellation}
impl PortalCancellation{
    pub fn cancel(&self){if let Ok(mut gate)=self.gate.lock(){gate.cancelled=true;}self.sdk.cancel();}
    pub fn is_cancelled(&self)->bool{self.gate.lock().map(|gate|gate.cancelled).unwrap_or(true)}
    fn begin_dispatch(&self)->bool{let Ok(mut gate)=self.gate.lock()else{return false};if gate.cancelled{return false;}gate.dispatched=true;true}
    fn was_dispatched(&self)->bool{self.gate.lock().map(|gate|gate.dispatched).unwrap_or(true)}
    pub fn sdk(&self)->&portal_client::Cancellation{&self.sdk}
}

#[derive(Clone, Default)]
pub struct PortalForgeState(Arc<Mutex<PortalOperations>>);
#[derive(Default)]
struct PortalOperations{active:HashMap<String,PortalCancellation>,cancel_before_register:HashMap<String,std::time::Instant>,preview_reservations:std::collections::HashSet<String>,previews:HashMap<String,Arc<Mutex<PortalPreviewWorker>>>,preview_children:HashMap<String,Arc<PortalOwnedChild>>,preview_expiries:HashMap<String,std::time::Instant>,reaper_running:bool}
struct PortalOwnedChild{process:Mutex<std::process::Child>,job:Option<isize>}
impl Drop for PortalOwnedChild{fn drop(&mut self){#[cfg(windows)]if let Some(job)=self.job.take(){unsafe{windows_sys::Win32::Foundation::CloseHandle(job as _);}}}}
struct PortalPreviewWorker{child:Arc<PortalOwnedChild>,stdin:std::process::ChildStdin,stdout:std::io::BufReader<std::process::ChildStdout>}

pub fn register_portal_operation(state:&PortalForgeState,operation:&str)->Result<PortalCancellation,ApiResponse>{
    if portal_client::Operation::new(operation).is_err(){return Err(response(400,json!({"detail":{"code":"PORTAL_OPERATION_REQUIRED","billing_state":"not_sent"}})));}
    let mut jobs=state.0.lock().map_err(|_|response(503,json!({"detail":{"code":"PORTAL_OPERATION_STATE_UNAVAILABLE","billing_state":"not_sent"}})))?;
    if jobs.active.len()>=4{return Err(response(429,json!({"detail":{"code":"PORTAL_OPERATION_LIMIT","billing_state":"not_sent"}})));}
    if jobs.active.contains_key(operation){return Err(response(409,json!({"detail":{"code":"PORTAL_OPERATION_ACTIVE","billing_state":"not_sent"}})));}
    if jobs.previews.len()+jobs.preview_reservations.len()>=32{return Err(response(429,json!({"detail":{"code":"PORTAL_PREVIEW_LIMIT","billing_state":"not_sent"}})));}
    let cancel=PortalCancellation::default();
    jobs.cancel_before_register.retain(|_,expires|*expires>std::time::Instant::now());
    if jobs.cancel_before_register.remove(operation).is_some(){cancel.cancel();}
    jobs.active.insert(operation.to_string(),cancel.clone());jobs.preview_reservations.insert(operation.to_string());Ok(cancel)
}

pub fn cancel_portal_operation(state:&PortalForgeState,operation:&str)->Result<Value,String>{
    if portal_client::Operation::new(operation).is_err(){return Err("Invalid Portal operation id".into());}
    let mut jobs=state.0.lock().map_err(|_|"Portal operation state unavailable")?;
    if let Some(cancel)=jobs.active.get(operation){cancel.cancel();}
    else {
        let now=std::time::Instant::now();
        jobs.cancel_before_register.retain(|_,expires|*expires>now);
        if jobs.cancel_before_register.len()<64{jobs.cancel_before_register.insert(operation.to_string(),now+std::time::Duration::from_secs(60));}
        else{return Err("Portal cancellation queue is full".into());}
    }
    Ok(json!({"status":"cancellation_requested","operation_id":operation}))
}

pub fn cancel_all_portal_operations(state:&PortalForgeState){
    if let Ok(mut jobs)=state.0.lock(){
        for cancel in jobs.active.values(){cancel.cancel();}
        jobs.previews.clear();jobs.preview_expiries.clear();
        let children=std::mem::take(&mut jobs.preview_children);
        for child in children.into_values(){kill_portal_child(&child);}
    }
}

fn finish_portal_operation(state:&PortalForgeState,operation:&str){if let Ok(mut jobs)=state.0.lock(){jobs.active.remove(operation);jobs.cancel_before_register.remove(operation);jobs.preview_reservations.remove(operation);}}

async fn acquire_portal_connection(context:&portal_client::lifecycle::SharedPortal,cancel:&PortalCancellation)->Result<portal_client::lifecycle::HostConnection,portal_client::ClientError>{
    context.acquire(PORTAL_STARTUP_ACQUIRE_TIMEOUT,cancel.sdk()).await
}

fn pin_registered_portal_runtime()->Result<(PathBuf,portal_client::lifecycle::PrivatePin),portal_client::ClientError>{
    #[cfg(test)]
    let registered=match std::env::var_os("NAVIS_PORTAL_PROFILE"){
        Some(profile)=>{
            let raw=std::fs::read(profile).expect("generated Portal feature profile");
            let document:Value=serde_json::from_slice(&raw).expect("generated Portal feature profile JSON");
            let release=PathBuf::from(document["portal_release_root"].as_str().expect("fixture release root"));
            let root=release.parent().and_then(Path::parent).expect("fixture host root");
            portal_client::lifecycle::registered_runtime_fixture(root)?
        },
        None=>portal_client::lifecycle::registered_runtime()?,
    };
    #[cfg(not(test))]
    let registered=portal_client::lifecycle::registered_runtime()?;
    let executable=registered.path().to_path_buf();
    let pin=portal_client::lifecycle::pin_registered_runtime(registered)?;
    Ok((executable,pin))
}

fn kill_portal_child(child:&Arc<PortalOwnedChild>){
    if let Ok(mut process)=child.process.lock(){
        #[cfg(windows)]if let Some(job)=child.job{unsafe{windows_sys::Win32::System::JobObjects::TerminateJobObject(job as _,1);}}
        #[cfg(not(windows))]let _=process.kill();
        let _=process.wait();
    }
}

fn portal_child_try_wait(child:&PortalOwnedChild)->std::io::Result<Option<std::process::ExitStatus>>{
    child.process.lock().map_err(|_|std::io::Error::new(std::io::ErrorKind::Other,"Portal child lock poisoned"))?.try_wait()
}

fn portal_retention_error(mut error:ApiResponse,receipt:Option<&Value>)->ApiResponse{
    if let Some(detail)=error.body.get_mut("detail").and_then(Value::as_object_mut){
        if let Some(receipt)=receipt{
            detail.insert("portal_receipt".into(),receipt.clone());
            if let Some(state)=receipt.get("billing_state"){detail.insert("billing_state".into(),state.clone());}
            if let Some(cost)=receipt.get("cost_usd"){detail.insert("cost_usd".into(),cost.clone());}
        }
    }
    response(error.status,error.body.clone())
}

fn retain_portal_preview(state:&PortalForgeState,operation:&str,proposal_id:String,worker:PortalPreviewWorker)->Result<(),ApiResponse>{
    let suffix=proposal_id.strip_prefix("portal-").unwrap_or("");
    if suffix.len()!=32||!suffix.bytes().all(|byte|byte.is_ascii_hexdigit()&& !byte.is_ascii_uppercase()){kill_portal_child(&worker.child);return Err(response(503,json!({"detail":{"code":"PORTAL_PREVIEW_ID_INVALID","billing_state":"unknown","cost_usd":null}})));}
    let mut jobs=match state.0.lock(){Ok(jobs)=>jobs,Err(_)=>{kill_portal_child(&worker.child);return Err(response(503,json!({"detail":{"code":"PORTAL_PREVIEW_STATE_UNAVAILABLE","billing_state":"unresolved","cost_usd":null}})));}};
    let operation_live=jobs.active.get(operation).is_some_and(|cancel|!cancel.is_cancelled());
    if !operation_live{
        jobs.preview_reservations.remove(operation);
        kill_portal_child(&worker.child);
        return Err(response(499,json!({"detail":{"code":"PORTAL_CANCELLED","billing_state":"unresolved","cost_usd":null}})));
    }
    if !jobs.preview_reservations.remove(operation)||jobs.previews.contains_key(&proposal_id){kill_portal_child(&worker.child);return Err(response(503,json!({"detail":{"code":"PORTAL_PREVIEW_ID_CONFLICT","billing_state":"unresolved","cost_usd":null}})));}
    let expires=std::time::Instant::now()+std::time::Duration::from_secs(600);
    let child=worker.child.clone();
    let worker=Arc::new(Mutex::new(PortalPreviewWorker{child:child.clone(),stdin:worker.stdin,stdout:worker.stdout}));
    jobs.preview_expiries.insert(proposal_id.clone(),expires);jobs.preview_children.insert(proposal_id.clone(),child);jobs.previews.insert(proposal_id.clone(),worker);
    let start_reaper=!jobs.reaper_running;
    if start_reaper{jobs.reaper_running=true;}
    drop(jobs);
    if start_reaper{start_portal_preview_reaper(state.clone());}
    Ok(())
}

fn start_portal_preview_reaper(state:PortalForgeState){
    std::thread::spawn(move||loop{
        std::thread::sleep(std::time::Duration::from_millis(250));
        let (expired,done)=if let Ok(mut jobs)=state.0.lock(){
            let now=std::time::Instant::now();let ids:Vec<_>=jobs.preview_expiries.iter().filter_map(|(id,expires)|(*expires<=now).then_some(id.clone())).collect();
            let mut children=Vec::new();
            for id in ids{jobs.previews.remove(&id);jobs.preview_expiries.remove(&id);if let Some(child)=jobs.preview_children.remove(&id){children.push(child);}}
            let done=jobs.previews.is_empty();if done{jobs.reaper_running=false;}(children,done)
        }else{return;};
        for child in expired{kill_portal_child(&child);}
        if done{return;}
    });
}

fn portal_preview_action(state:&PortalForgeState,proposal_id:&str,action:&str,request:Value)->ApiResponse{
    portal_preview_action_with_timeout(state,proposal_id,action,request,std::time::Duration::from_secs(75))
}

fn portal_preview_action_with_timeout(state:&PortalForgeState,proposal_id:&str,action:&str,request:Value,timeout:std::time::Duration)->ApiResponse{
    let suffix=proposal_id.strip_prefix("portal-").unwrap_or("");
    let shape=match action{"approve"=>request.as_object().is_some_and(|value|value.len()==2&&value.get("proposal_id").and_then(Value::as_str)==Some(proposal_id)&&value.get("approved")==Some(&Value::Bool(true))),"discard"=>request.as_object().is_some_and(|value|value.len()==1&&value.get("proposal_id").and_then(Value::as_str)==Some(proposal_id)),_=>false};
    if suffix.len()!=32||!suffix.bytes().all(|byte|byte.is_ascii_hexdigit()&&!byte.is_ascii_uppercase())||!shape{return response(400,json!({"detail":{"code":"PORTAL_PREVIEW_ACTION_INVALID","billing_state":"not_sent"}}));}
    let worker={
        let Ok(mut jobs)=state.0.lock()else{return response(503,json!({"detail":{"code":"PORTAL_PREVIEW_STATE_UNAVAILABLE"}}));};
        if jobs.preview_expiries.get(proposal_id).map_or(true,|expires|std::time::Instant::now()>=*expires){
            jobs.previews.remove(proposal_id);jobs.preview_expiries.remove(proposal_id);
            if let Some(child)=jobs.preview_children.remove(proposal_id){kill_portal_child(&child);}
            return response(410,json!({"detail":{"code":"PORTAL_PREVIEW_EXPIRED","billing_state":"not_sent"}}));
        }
        jobs.previews.get(proposal_id).cloned().unwrap()
    };
    let Ok(mut worker)=worker.lock()else{return response(503,json!({"detail":{"code":"PORTAL_PREVIEW_STATE_UNAVAILABLE"}}));};
    let payload=json!({"action":action,"request":request}).to_string();
    if payload.len()>65536{kill_portal_child(&worker.child);return response(400,json!({"detail":{"code":"PORTAL_PREVIEW_ACTION_LIMIT","billing_state":"not_sent"}}));}
    let child=worker.child.clone();
    let (write_result,line,read_result,timed_out)=std::thread::scope(|scope|{
        let PortalPreviewWorker{stdin,stdout,..}=&mut *worker;
        let writer=scope.spawn(||stdin.write_all(payload.as_bytes()).and_then(|_|stdin.write_all(b"\n")).and_then(|_|stdin.flush()));
        let reader=scope.spawn(||{let mut line=Vec::new();let result=stdout.take((FORGE_STDOUT_LIMIT+1)as u64).read_until(b'\n',&mut line);(line,result)});
        let deadline=std::time::Instant::now()+timeout;let mut timed_out=false;
        while !writer.is_finished()||!reader.is_finished(){
            if std::time::Instant::now()>=deadline{timed_out=true;kill_portal_child(&child);break;}
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        let write=writer.join().unwrap_or_else(|_|Err(std::io::Error::new(std::io::ErrorKind::Other,"Portal preview writer failed")));
        let (line,read)=reader.join().unwrap_or_else(|_|(Vec::new(),Err(std::io::Error::new(std::io::ErrorKind::Other,"Portal preview reader failed"))));
        (write,line,read,timed_out)
    });
    if timed_out||write_result.is_err()||read_result.is_err()||line.len()>FORGE_STDOUT_LIMIT||!line.ends_with(b"\n")||!portal_client::lifecycle::validate_unique_json(&line[..line.len().saturating_sub(1)]){
        kill_portal_child(&worker.child);drop(worker);
        if let Ok(mut jobs)=state.0.lock(){jobs.previews.remove(proposal_id);jobs.preview_expiries.remove(proposal_id);jobs.preview_children.remove(proposal_id);}
        let code=if timed_out{"PORTAL_PREVIEW_ACTION_TIMEOUT"}else{"PORTAL_PREVIEW_RESPONSE_INVALID"};
        return response(503,json!({"detail":{"code":code,"billing_state":"unknown"}}));
    }
    let result:Value=match serde_json::from_slice::<Value>(&line[..line.len()-1]){Ok(value) if value.is_object()=>value,_=>{kill_portal_child(&worker.child);drop(worker);if let Ok(mut jobs)=state.0.lock(){jobs.previews.remove(proposal_id);jobs.preview_expiries.remove(proposal_id);jobs.preview_children.remove(proposal_id);}return response(503,json!({"detail":{"code":"PORTAL_PREVIEW_RESPONSE_INVALID","billing_state":"unknown"}}));}};
    let status=result["http_status"].as_u64().filter(|value|(200..=599).contains(value)).unwrap_or(503)as u16;
    let body=result.get("body").filter(|value|value.is_object()).cloned().unwrap_or_else(||json!({"detail":{"code":"PORTAL_PREVIEW_RESPONSE_INVALID"}}));
    let completed=status<300;
    if completed{kill_portal_child(&worker.child);}
    drop(worker);
    if completed||status==410{if let Ok(mut jobs)=state.0.lock(){jobs.previews.remove(proposal_id);jobs.preview_expiries.remove(proposal_id);jobs.preview_children.remove(proposal_id);}}
    response(status,body)
}

#[derive(Debug, serde::Serialize)]
pub struct ApiResponse {
    pub status: u16,
    pub body: Value,
    pub text: String,
}

fn response(status: u16, body: Value) -> ApiResponse {
    ApiResponse {
        status,
        text: body.to_string(),
        body,
    }
}
fn root() -> PathBuf {
    crate::operations::configured_vault_root()
        .unwrap_or_else(|_| PathBuf::from(r"G:\My Drive\Navis-Vault"))
}
pub(crate) fn unavailable(message: &str) -> ApiResponse {
    response(
        503,
        json!({"status":"unavailable","code":"native_dependency_unavailable","message":message}),
    )
}

const MAX_BANTER_THREADS_PER_RUN: usize = 3;
const USABLE_THREAD_MAX_AGE_SECONDS: f64 = 24.0 * 60.0 * 60.0;

fn banter_db(root: &PathBuf) -> PathBuf {
    let settings_path = root.join("Bridge").join("settings.json");
    let configured = std::fs::read_to_string(settings_path)
        .ok()
        .and_then(|text| serde_json::from_str::<Value>(&text).ok())
        .and_then(|settings| {
            settings
                .pointer("/paths/chronicle_db")?
                .as_str()
                .map(PathBuf::from)
        });
    configured.unwrap_or_else(|| root.join("Journal").join("Chronicle.db"))
}

fn timestamp() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs_f64())
        .unwrap_or_default()
}

fn party_names(status: &Value) -> Vec<String> {
    status
        .get("squad")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|member| member.get("name").and_then(Value::as_str))
        .map(str::trim)
        .filter(|name| !name.is_empty())
        .map(str::to_string)
        .collect()
}

fn read_banter_status(root: &PathBuf) -> Result<Value, &'static str> {
    let path = root.join("Bridge").join("status.json");
    let text = std::fs::read_to_string(&path).map_err(|error| match error.kind() {
        std::io::ErrorKind::NotFound => "Squad status is missing. Restore Bridge/status.json in the configured Vault, then retry.",
        std::io::ErrorKind::InvalidData => "Squad status is malformed. Repair Bridge/status.json in the configured Vault, then retry.",
        _ => "Squad status could not be read. Check Vault access and retry.",
    })?;
    let text = text.strip_prefix('\u{feff}').unwrap_or(&text);
    let status = serde_json::from_str::<Value>(text)
        .map_err(|_| "Squad status is malformed. Repair Bridge/status.json in the configured Vault, then retry.")?;
    if !status.is_object() || !status.get("squad").is_some_and(Value::is_array) {
        return Err("Squad status has an invalid squad field. Repair Bridge/status.json, then retry.");
    }
    Ok(status)
}

fn valid_chain(chain: &Value, participants: &[String]) -> bool {
    let Some(turns) = chain.as_array() else {
        return false;
    };
    if turns.len() != participants.len() {
        return false;
    }
    let speakers: Vec<&str> = turns
        .iter()
        .filter_map(|turn| {
            let speaker = turn.get("speaker")?.as_str()?;
            let text = turn.get("text")?.as_str()?;
            (!text.trim().is_empty()).then_some(speaker)
        })
        .collect();
    speakers.len() == participants.len()
        && speakers
            .iter()
            .copied()
            .collect::<std::collections::HashSet<_>>()
            .len()
            == participants.len()
        && speakers
            .iter()
            .map(|speaker| (*speaker).to_string())
            .eq(participants.iter().cloned())
}

fn usable_recent_thread(conn: &rusqlite::Connection, realm: &str, participants: &[String]) -> bool {
    let Ok(mut statement) = conn.prepare(
        "SELECT chain FROM banter_threads WHERE realm=?1 AND participants=?2 AND timestamp>=?3 ORDER BY timestamp DESC",
    ) else { return false };
    let participant_key = sorted_participant_key(participants);
    let Ok(rows) = statement.query_map(
        rusqlite::params![
            realm,
            participant_key,
            timestamp() - USABLE_THREAD_MAX_AGE_SECONDS
        ],
        |row| row.get::<_, String>(0),
    ) else {
        return false;
    };
    let found = rows.flatten().any(|chain| {
        serde_json::from_str::<Value>(&chain).is_ok_and(|value| valid_chain(&value, participants))
    });
    found
}

fn read_utf8(path: PathBuf) -> String {
    std::fs::read_to_string(path).unwrap_or_default()
}

fn section(content: &str, heading: &str, fallback: &str) -> String {
    let Some(start) = content.find(heading).map(|index| index + heading.len()) else {
        return fallback.to_string();
    };
    let rest = content[start..].trim_start_matches(['\r', '\n', ' ', '\t']);
    let end = rest
        .find("\n##")
        .into_iter()
        .chain(rest.find("\n---"))
        .min()
        .unwrap_or(rest.len());
    rest[..end].trim().to_string()
}

fn local_ollama_generate(prompt: &str) -> Result<String, String> {
    let _ = prompt;
    Err("Legacy native generation is retired; use the configured Python provider route.".into())
}

fn generate_banter(root: &PathBuf, requested_count: usize) -> ApiResponse {
    let status = match read_banter_status(root) {
        Ok(status) => status,
        Err(detail) => return response(503, json!({"detail":detail})),
    };
    let realm = status
        .get("current_realm")
        .and_then(Value::as_str)
        .unwrap_or("Unknown");
    let participants = party_names(&status);
    if participants.len() < 2
        || participants
            .iter()
            .map(|name| name.to_lowercase())
            .collect::<std::collections::HashSet<_>>()
            .len()
            != participants.len()
    {
        return response(
            422,
            json!({"detail":"At least two uniquely named active squad members are required."}),
        );
    }
    let db_path = banter_db(root);
    let conn = match rusqlite::Connection::open(&db_path) {
        Ok(conn) => conn,
        Err(_) => {
            return response(
                503,
                json!({"detail":"Banter history storage is unavailable."}),
            )
        }
    };
    if usable_recent_thread(&conn, realm, &participants) {
        return response(
            200,
            json!({"status":"success","message":"A usable current squad thread is already available."}),
        );
    }
    let count = requested_count.clamp(1, MAX_BANTER_THREADS_PER_RUN);
    let realm_file = root.join("Realms").join(realm).join("Realm.md");
    let realm_content = read_utf8(realm_file);
    let realm_brief = section(
        &realm_content,
        "## 🗣️ Environmental Briefing",
        &realm_content.chars().take(800).collect::<String>(),
    );
    let companion_root = root.join("Companions");
    let mut protocols = Vec::new();
    for name in &participants {
        let first = name.split_whitespace().next().unwrap_or(name);
        let profile = [
            companion_root.join(first).join("Profile.md"),
            companion_root.join(name).join("Profile.md"),
        ]
        .into_iter()
        .find(|path| path.is_file())
        .unwrap_or_else(|| companion_root.join(first).join("Profile.md"));
        let content = read_utf8(profile);
        let protocol = section(&content, "## 🗣️ Banter Protocol", "Standard behavior.");
        protocols.push(format!("NAME: {name}\nPERSONALITY PROTOCOL:\n{protocol}"));
    }
    let names_json = serde_json::to_string(&participants).unwrap_or_else(|_| "[]".into());
    let mut persisted = 0;
    for _ in 0..count {
        let prompt = format!(
            "Act as a role-playing game storyteller. Location: {realm}.\n\nSetting:\n{realm_brief}\n\nParty member protocols:\n{}\n\nWrite one immersive line for each member, once each, in this exact order: {names_json}. Avoid modern military and science-fiction jargon. Keep persona constraints. Speak of the journey and surroundings. Refer to the user as Keeper. Return only a JSON array of objects with string fields speaker and text.",
            protocols.join("\n-----\n")
        );
        let generated = match local_ollama_generate(&prompt) {
            Ok(text) => text,
            Err(error) => return response(503, json!({"detail":error})),
        };
        let json_text = generated
            .find('[')
            .zip(generated.rfind(']'))
            .map(|(start, end)| &generated[start..=end]);
        let chain = json_text.and_then(|text| serde_json::from_str::<Value>(text).ok());
        let Some(chain) = chain.filter(|chain| valid_chain(chain, &participants)) else {
            return response(
                503,
                json!({"detail":"Local Ollama returned malformed banter or an incomplete party thread."}),
            );
        };
        if let Err(_) = persist_banter(&conn, realm, &participants, &chain) {
            return response(
                503,
                json!({"detail":"Could not persist the generated banter thread."}),
            );
        }
        persisted += 1;
    }
    response(
        200,
        json!({"status":"success","message":format!("Generated {persisted} local squad banter thread(s).")}),
    )
}

fn persist_banter(
    conn: &rusqlite::Connection,
    realm: &str,
    participants: &[String],
    chain: &Value,
) -> rusqlite::Result<()> {
    conn.execute_batch("CREATE TABLE IF NOT EXISTS banter_threads (id INTEGER PRIMARY KEY AUTOINCREMENT, realm TEXT, participants TEXT, chain TEXT, timestamp REAL, thread_hash TEXT UNIQUE); CREATE INDEX IF NOT EXISTS idx_realm ON banter_threads(realm);")?;
    let chain_text = chain.to_string();
    let first_text = chain
        .as_array()
        .and_then(|turns| turns.first())
        .and_then(|turn| turn.get("text"))
        .and_then(Value::as_str)
        .unwrap_or_default();
    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    first_text.hash(&mut hasher);
    let hash = format!("{:016x}", hasher.finish());
    conn.execute("BEGIN IMMEDIATE", [])?;
    let participant_key = sorted_participant_key(participants);
    let mut statement =
        conn.prepare("SELECT chain FROM banter_threads WHERE realm=?1 AND participants=?2")?;
    let existing: Vec<String> = statement
        .query_map(rusqlite::params![realm, participant_key], |row| row.get(0))?
        .flatten()
        .collect();
    if existing.iter().any(|saved| {
        serde_json::from_str::<Value>(saved)
            .ok()
            .and_then(|value| {
                value
                    .as_array()
                    .and_then(|turns| turns.first())
                    .and_then(|turn| turn.get("text"))
                    .and_then(Value::as_str)
                    .map(str::to_string)
            })
            .is_some_and(|saved_text| saved_text == first_text)
    }) {
        conn.execute("ROLLBACK", [])?;
        return Ok(());
    }
    conn.execute(
        "INSERT OR IGNORE INTO banter_threads (realm,participants,chain,timestamp,thread_hash) VALUES (?1,?2,?3,?4,?5)",
        rusqlite::params![realm, participant_key, chain_text, timestamp(), hash],
    )?;
    conn.execute(
        "DELETE FROM banter_threads WHERE id IN (SELECT id FROM banter_threads WHERE realm=?1 AND participants=?2 ORDER BY timestamp DESC LIMIT -1 OFFSET 10)",
        rusqlite::params![realm, participant_key],
    )?;
    conn.execute("COMMIT", [])?;
    Ok(())
}

fn sorted_participant_key(participants: &[String]) -> String {
    let mut sorted = participants.to_vec();
    sorted.sort();
    sorted.join(",")
}

fn banter_history(root: &PathBuf) -> ApiResponse {
    let status = match read_banter_status(root) {
        Ok(status) => status,
        Err(detail) => return response(503, json!({"detail":detail})),
    };
    let names = party_names(&status);
    let db_path = banter_db(root);
    if !db_path.is_file() {
        return response(200, json!([]));
    }
    let conn = match rusqlite::Connection::open(db_path) {
        Ok(conn) => conn,
        Err(_) => return response(503, json!({"detail":"Banter history storage is unavailable. Check Vault access and retry."})),
    };
    let has_banter_table: bool = match conn.query_row(
        "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'banter_threads')",
        [],
        |row| row.get(0),
    ) {
        Ok(exists) => exists,
        Err(_) => return response(503, json!({"detail":"Banter history could not be read. Check the Chronicle database and retry."})),
    };
    if !has_banter_table {
        return response(200, json!([]));
    }
    let mut statement = match conn.prepare(
        "SELECT realm,participants,chain,timestamp FROM banter_threads ORDER BY id DESC LIMIT 50",
    ) {
        Ok(statement) => statement,
        Err(_) => return response(503, json!({"detail":"Banter history could not be read. Check the Chronicle database and retry."})),
    };
    let rows = match statement.query_map([], |row| {
        Ok((
            row.get::<_, String>(0)?,
            row.get::<_, String>(1)?,
            row.get::<_, String>(2)?,
            row.get::<_, f64>(3)?,
        ))
    }) {
        Ok(rows) => rows,
        Err(_) => return response(503, json!({"detail":"Banter history could not be read. Check the Chronicle database and retry."})),
    };
    let mut seen = std::collections::HashSet::new();
    let mut messages = Vec::new();
    for row in rows {
        let (realm, participants, serialized, stamp) = match row {
            Ok(row) => row,
            Err(_) => return response(503, json!({"detail":"Banter history contains unreadable records. Check the Chronicle database and retry."})),
        };
        if !participants.split(',').all(|name| {
            names
                .iter()
                .any(|active| active.eq_ignore_ascii_case(name.trim()))
        }) {
            continue;
        }
        let Ok(Value::Array(chain)) = serde_json::from_str::<Value>(&serialized) else {
            continue;
        };
        for turn in chain.iter().rev() {
            let Some(speaker) = turn.get("speaker").and_then(Value::as_str) else {
                continue;
            };
            let Some(text) = turn.get("text").and_then(Value::as_str) else {
                continue;
            };
            if text.trim().is_empty() || !seen.insert(speaker.to_string()) {
                continue;
            }
            let role = companion_role(&root.join("Companions"), speaker);
            let avatar_dir = companion_directory(&root.join("Companions"), speaker);
            let avatar = format!(
                "/api/vault/Companions/{}/Portrait.png",
                percent_encoding::utf8_percent_encode(
                    &avatar_dir,
                    percent_encoding::NON_ALPHANUMERIC
                )
            );
            messages.push(json!({"sender":speaker,"role":role,"text":text,"avatar":avatar,"realm":realm,"timestamp":stamp}));
        }
    }
    messages.reverse();
    response(200, json!(messages))
}

fn companion_directory(root: &PathBuf, speaker: &str) -> String {
    if root.join(speaker).is_dir() {
        return speaker.into();
    }
    speaker
        .split_whitespace()
        .next()
        .unwrap_or(speaker)
        .to_string()
}

fn companion_role(root: &PathBuf, speaker: &str) -> String {
    let persona = std::fs::read_to_string(
        root.join(companion_directory(root, speaker))
            .join("Persona.json"),
    )
    .ok()
    .and_then(|text| serde_json::from_str::<Value>(&text).ok());
    persona
        .and_then(|value| {
            value
                .get("role")
                .and_then(Value::as_str)
                .map(str::to_string)
        })
        .unwrap_or_else(|| "Companion".into())
}

fn latest_history() -> Value {
    let dir = root().join("Reflection Chamber").join("Fridr Hall");
    let Some(path) = std::fs::read_dir(dir).ok().and_then(|entries| {
        entries
            .flatten()
            .map(|e| e.path())
            .filter(|p| p.extension().and_then(|x| x.to_str()) == Some("md"))
            .max_by_key(|p| std::fs::metadata(p).and_then(|m| m.modified()).ok())
    }) else {
        return json!([]);
    };
    let text = std::fs::read_to_string(path).unwrap_or_default();
    let mut messages = Vec::new();
    for line in text.lines() {
        let line = line.trim();
        if let Some(value) = line.strip_prefix("**[") {
            if let Some((stamp, rest)) = value.split_once("] Keeper:**") {
                messages.push(json!({"role":"user","content":format!("[{stamp}] {rest}")}));
            }
            if let Some((stamp, rest)) = value.split_once("] Reid:**") {
                messages.push(json!({"role":"reid","content":format!("[{stamp}] {rest}")}));
            }
        }
    }
    Value::Array(messages)
}

fn biometrics(path: &str) -> ApiResponse {
    let db = root().join("Keeper").join("FitbitChronicle.db");
    if !db.exists() {
        return unavailable("FitbitChronicle.db is not available in the configured Vault");
    }
    let conn = match rusqlite::Connection::open(db) {
        Ok(v) => v,
        Err(e) => return response(500, json!({"status":"error","message":e.to_string()})),
    };
    let route = path.split('?').next().unwrap_or(path);
    let (table, order, limit) = match route {
        "/api/v1/biometrics/vitals/latest" => ("daily_vitals", "date DESC", 1),
        "/api/v1/biometrics/vitals/history" => ("daily_vitals", "date DESC", 7),
        "/api/v1/biometrics/exercises/recent" => ("exercise_logs", "date DESC", 5),
        _ => {
            return response(
                404,
                json!({"status":"error","message":"unsupported biometrics route"}),
            )
        }
    };
    let mut stmt = match conn.prepare(&format!("SELECT * FROM {table} ORDER BY {order} LIMIT ?1")) {
        Ok(v) => v,
        Err(e) => return response(503, json!({"status":"unavailable","message":e.to_string()})),
    };
    let names: Vec<String> = stmt
        .column_names()
        .iter()
        .map(|v| (*v).to_string())
        .collect();
    let rows = stmt
        .query_map([limit], |row| {
            let mut item = serde_json::Map::new();
            for (i, name) in names.iter().enumerate() {
                let value: Result<String, _> = row.get(i);
                item.insert(
                    name.clone(),
                    value.map(Value::String).unwrap_or(Value::Null),
                );
            }
            Ok(Value::Object(item))
        })
        .ok()
        .map(|rows| rows.flatten().collect::<Vec<_>>())
        .unwrap_or_default();
    if route.ends_with("latest") {
        rows.first()
            .cloned()
            .map_or_else(|| unavailable("No vitals found"), |v| response(200, v))
    } else {
        response(200, Value::Array(rows))
    }
}

#[derive(Default)]
pub struct P5OperationState {
    pub jobs: Mutex<HashMap<String, Arc<AtomicBool>>>,
}
const ALLOWED: &[(&str, &str)] = &[
    ("backup", "Engine/sync/backup_protocol.py"),
    ("apply_xp", "Engine/rpg/apply_xp.py"),
    ("daily_rollover", "Engine/sync/daily_rollover.py"),
    ("sync_bridge", "Engine/sync/sync_bridge.py"),
];

fn emit(app: &AppHandle, job: &str, status: &str, phase: &str, message: &str) {
    let _ = app.emit(
        crate::operations::OPERATION_EVENT,
        json!({"job_id":job,"status":status,"phase":phase,"message":message}),
    );
}

#[tauri::command]
pub fn start_p5_operation(
    app: AppHandle,
    state: State<'_, P5OperationState>,
    operation: String,
) -> Result<Value, String> {
    let (_, relative) = ALLOWED
        .iter()
        .find(|(id, _)| *id == operation)
        .ok_or("unsupported operation")?;
    let vault_root = crate::operations::configured_vault_root()?;
    let script = vault_root.join(relative.replace('/', std::path::MAIN_SEPARATOR_STR));
    if !script.starts_with(&vault_root) {
        return Err("operation path escaped Vault root".into());
    }
    if !script.exists() {
        return Err(format!("approved operation is unavailable: {relative}"));
    }
    let backend = crate::operations::backend_root(&app)?;
    let runtime = crate::command::resolve_python_runtime(&backend, !cfg!(debug_assertions))?;
    let job = format!(
        "p5-{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_err(|e| e.to_string())?
            .as_nanos()
    );
    let cancelled = Arc::new(AtomicBool::new(false));
    state
        .jobs
        .lock()
        .map_err(|_| "operation state unavailable")?
        .insert(job.clone(), cancelled.clone());
    let app2 = app.clone();
    let job2 = job.clone();
    std::thread::spawn(move || {
        emit(
            &app2,
            &job2,
            "running",
            "start",
            "Approved operation started",
        );
        let mut command = crate::command::hidden_command(&runtime.to_string_lossy());
        command.arg(script).env_clear();
        for key in ["PATH", "SystemRoot", "TEMP", "TMP", "NAVIS_AI_PROVIDER", "NAVIS_OPENROUTER_CONFIG", "OPENROUTER_API_KEY"] {
            if let Ok(value) = std::env::var(key) {
                command.env(key, value);
            }
        }
        command
            .env("NAVIS_ROOT", &vault_root)
            .env("PYTHONIOENCODING", "utf-8");
        let result = command.spawn().and_then(|mut child| loop {
            if cancelled.load(Ordering::Relaxed) {
                let _ = child.kill();
                let _ = child.wait();
                return Ok(None);
            }
            match child.try_wait()? {
                Some(status) => return Ok(Some(status)),
                None => std::thread::sleep(std::time::Duration::from_millis(100)),
            }
        });
        if cancelled.load(Ordering::Relaxed) {
            emit(
                &app2,
                &job2,
                "cancelled",
                "cancel",
                "Cancellation requested",
            );
        } else {
            match result {
                Ok(Some(output)) if output.success() => emit(
                    &app2,
                    &job2,
                    "completed",
                    "finalize",
                    "Approved operation completed",
                ),
                Ok(Some(output)) => emit(
                    &app2,
                    &job2,
                    "failed",
                    "finalize",
                    &format!("Approved operation exited with code {:?}", output.code()),
                ),
                Ok(None) => emit(&app2, &job2, "cancelled", "cancel", "Operation cancelled"),
                Err(error) => emit(
                    &app2,
                    &job2,
                    "failed",
                    "finalize",
                    &format!("Approved operation failed: {error}"),
                ),
            }
        }
    });
    Ok(json!({"status":"accepted","job_id":job,"operation":operation}))
}

#[tauri::command]
pub fn cancel_p5_operation(
    state: State<'_, P5OperationState>,
    job_id: String,
) -> Result<Value, String> {
    let jobs = state
        .jobs
        .lock()
        .map_err(|_| "operation state unavailable")?;
    let token = jobs.get(&job_id).ok_or("operation not found")?;
    token.store(true, Ordering::Relaxed);
    Ok(json!({"status":"cancellation_requested","job_id":job_id}))
}

/// Shared Forge service: private concepts travel on stdin, never argv or logs.
pub async fn forge_request(app: AppHandle, path: String, method: String, body: Option<Value>, portal_operation:Option<(String,PortalCancellation)>, registry:PortalForgeState) -> Result<ApiResponse, String> {
    let result=forge_request_impl(app,path,method,body,portal_operation.clone(),registry.clone()).await;
    if let Some((operation,_))=portal_operation{finish_portal_operation(&registry,&operation);}
    result
}

async fn forge_request_impl(app: AppHandle, path: String, method: String, body: Option<Value>, portal_operation:Option<(String,PortalCancellation)>,registry:PortalForgeState) -> Result<ApiResponse, String> {
    if matches!((method.as_str(),path.as_str()),("POST","/api/forge/approve")|("POST","/api/forge/discard"))
        && body.as_ref().and_then(|value|value.get("proposal_id")).and_then(Value::as_str).is_some_and(|id|id.starts_with("portal-")) {
        let request=body.unwrap_or_else(||json!({}));
        if request.get("native_binding").is_some()||request.get("native_portal_binding").is_some(){return Ok(response(400,json!({"detail":{"code":"PORTAL_NATIVE_BINDING_RESERVED"}})));}
        let proposal=request["proposal_id"].as_str().unwrap_or("").to_string();
        let action=if path.ends_with("approve"){"approve"}else{"discard"}.to_string();
        return tauri::async_runtime::spawn_blocking(move||portal_preview_action(&registry,&proposal,&action,request)).await.map_err(|error|error.to_string());
    }
    let portal_submit = method == "POST" && path == "/api/forge/submit"
        && body.as_ref().and_then(|value| value.get("provider")).and_then(Value::as_str) == Some("portal");
    if portal_submit {
        let request = body.unwrap_or_else(|| json!({}));
        if request.get("native_portal_binding").is_some() || request.get("native_binding").is_some() {
            return Ok(response(400, json!({"detail":{"code":"PORTAL_NATIVE_BINDING_RESERVED","billing_state":"not_sent"}})));
        }
        if request.get("portal_opt_in") != Some(&Value::Bool(true))
            || request.get("allow_external_text") != Some(&Value::Bool(true)) {
            return Ok(response(403, json!({"detail":{"code":"PORTAL_PRIVACY_OPT_IN_REQUIRED","billing_state":"not_sent"}})));
        }
        let operation = request.get("operation_id").and_then(Value::as_str).unwrap_or("");
        if portal_client::Operation::new(operation).is_err() {
            return Ok(response(400, json!({"detail":{"code":"PORTAL_OPERATION_REQUIRED","billing_state":"not_sent"}})));
        }
        let Some((registered_operation,cancel))=portal_operation else {
            return Ok(response(503,json!({"detail":{"code":"PORTAL_OPERATION_NOT_REGISTERED","billing_state":"not_sent"}})));
        };
        if registered_operation!=operation{return Ok(response(400,json!({"detail":{"code":"PORTAL_OPERATION_MISMATCH","billing_state":"not_sent"}})));}
        if cancel.is_cancelled(){return Ok(response(499,json!({"detail":{"code":"PORTAL_CANCELLED","billing_state":"not_sent"}})));}
        let context=portal_client::lifecycle::SharedPortal::registered();
        let connection = match acquire_portal_connection(&context,&cancel).await {
                Ok(connection) => connection,
                Err(_) if cancel.is_cancelled()=>return Ok(response(499,json!({"detail":{"code":"PORTAL_CANCELLED","billing_state":"not_sent"}}))),
                Err(error) => return Ok(response(503, json!({"detail":{"code":error.code,"billing_state":error.kind}}))),
            };
        let generation = match connection.generation() {
            Some(value) => value.to_string(),
            None => return Ok(response(503, json!({"detail":{"code":"HOST_GENERATION_UNAVAILABLE","billing_state":"not_sent"}}))),
        };
        if cancel.is_cancelled(){return Ok(response(499,json!({"detail":{"code":"PORTAL_CANCELLED","billing_state":"not_sent"}})));}
        return tauri::async_runtime::spawn_blocking(move || {
            // Retain native registration and peer pins until the trusted adapter finishes.
            forge_request_inner(&app, &path, &method, Some(request), Some(generation), Some(connection),Some(cancel),registry)
        }).await.map_err(|error| error.to_string())?;
    }
    tauri::async_runtime::spawn_blocking(move || forge_request_inner(&app, &path, &method, body, None, None,None,registry))
        .await.map_err(|error| error.to_string())?
}

fn forge_request_inner(app: &AppHandle, path: &str, method: &str, body: Option<Value>, generation: Option<String>, _host: Option<portal_client::lifecycle::HostConnection>, cancel:Option<PortalCancellation>,registry:PortalForgeState) -> Result<ApiResponse, String> {
    let action = match (method, path) {
        ("POST", "/api/forge/submit") => "submit",
        ("POST", "/api/forge/approve") => "approve",
        ("POST", "/api/forge/discard") => "discard",
        _ => return Ok(response(400, json!({"detail":"Unsupported Forge action."}))),
    };
    let backend = match crate::operations::backend_root(app) {
        Ok(value) => value,
        Err(_) => return Ok(unavailable("Forge backend resources are unavailable.")),
    };
    let portal_mode = generation.is_some();
    let (runtime,runtime_pin)=if portal_mode{
        match pin_registered_portal_runtime(){
            Ok((runtime,pin))=>(runtime,Some(pin)),
            Err(error)=>return Ok(response(503,json!({"detail":{"code":error.code,"billing_state":error.kind}}))),
        }
    }else{
        match crate::command::resolve_python_runtime(&backend, !cfg!(debug_assertions)){
            Ok(runtime)=>(runtime,None),
            Err(_)=>return Ok(unavailable("Forge requires Python 3.11+ and backend dependencies.")),
        }
    };
    let mut command = crate::command::hidden_command(&runtime.to_string_lossy());
    if portal_mode{command.args(["-m","services.forge_service","portal-worker"]);}
    else{command.args(["-m","services.forge_service",action]);}
    command.current_dir(backend).env_clear();
    for key in ["PATH", "SystemRoot", "TEMP", "TMP"] {
        if let Ok(value) = std::env::var(key) { command.env(key, value); }
    }
    if portal_mode {
        command.env("NAVIS_NATIVE_PORTAL", "1");
        for key in ["NAVIS_PORTAL_ENABLED", "NAVIS_PORTAL_PROFILE"] {
            if let Ok(value) = std::env::var(key) { command.env(key, value); }
        }
    } else {
        for key in ["NAVIS_OLLAMA_URL", "NAVIS_OLLAMA_MODEL", "NAVIS_OLLAMA_TIMEOUT", "NAVIS_AI_PROVIDER", "NAVIS_OPENROUTER_CONFIG", "OPENROUTER_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"] {
            if let Ok(value) = std::env::var(key) { command.env(key, value); }
        }
    }
    command.env("NAVIS_ROOT", root()).env("PYTHONIOENCODING", "utf-8")
        .stdin(std::process::Stdio::piped()).stdout(std::process::Stdio::piped()).stderr(std::process::Stdio::null());
    let operation_id=body.as_ref().and_then(|value|value.get("operation_id")).and_then(Value::as_str).unwrap_or("").to_string();
    let payload_value = if let Some(generation) = generation {
        json!({"request": body.unwrap_or_else(|| json!({})), "native_binding": {"expected_host_generation": generation}})
    } else { body.unwrap_or_else(|| json!({})) };
    let payload=payload_value.to_string().into_bytes();
    if portal_mode{
        let (result,worker)=run_portal_preview_submit(command,payload,cancel);
        drop(runtime_pin);
        drop(_host);
        if result.status<300{
            let Some(proposal_id)=result.body.get("proposal_id").and_then(Value::as_str) else{return Ok(response(503,json!({"detail":{"code":"PORTAL_PREVIEW_ID_MISSING","billing_state":"unknown"}})));};
            let Some(worker)=worker else{return Ok(response(503,json!({"detail":{"code":"PORTAL_PREVIEW_WORKER_MISSING","billing_state":"unknown"}})));};
            if let Err(error)=retain_portal_preview(&registry,&operation_id,proposal_id.to_string(),worker){
                return Ok(portal_retention_error(error,result.body.get("portal_receipt")));
            }
        }
        return Ok(result);
    }
    Ok(run_forge_child(command,payload,cancel,false))
}

const FORGE_STDOUT_LIMIT:usize=65536;

fn run_portal_preview_submit(mut command:std::process::Command,payload:Vec<u8>,cancel:Option<PortalCancellation>)->(ApiResponse,Option<PortalPreviewWorker>){
    if payload.len()>65536{return(response(400,json!({"detail":{"code":"PORTAL_INPUT_LIMIT","billing_state":"not_sent"}})),None);}
    if cancel.as_ref().is_some_and(PortalCancellation::is_cancelled){return(response(499,json!({"detail":{"code":"PORTAL_CANCELLED","billing_state":"not_sent"}})),None);}
    let process=match command.spawn(){Ok(child)=>child,Err(_)=>return(unavailable("Forge runtime could not start."),None)};
    #[cfg(windows)]
    let job=match crate::operations::attach_windows_job(&process){Ok(job)=>Some(job),Err(_)=>{let mut process=process;let _=process.kill();let _=process.wait();return(response(503,json!({"detail":{"code":"PORTAL_CHILD_SUPERVISION_FAILED","billing_state":"not_sent"}})),None);}};
    #[cfg(not(windows))]
    let job:Option<isize>=None;
    let child=Arc::new(PortalOwnedChild{process:Mutex::new(process),job});
    let pipes=child.process.lock().ok().and_then(|mut process|process.stdin.take().zip(process.stdout.take()));
    let Some((stdin,stdout))=pipes else{kill_portal_child(&child);return(unavailable("Forge runtime could not start."),None);};
    let writer_cancel=cancel.clone();
    let writer=std::thread::spawn(move||{
        let mut stdin=stdin;
        if let Some(cancel)=writer_cancel{if !cancel.begin_dispatch(){return(stdin,Err(std::io::Error::new(std::io::ErrorKind::Interrupted,"cancelled before dispatch")));}}
        let result=stdin.write_all(&payload).and_then(|_|stdin.write_all(b"\n")).and_then(|_|stdin.flush());
        (stdin,result)
    });
    let reader=std::thread::spawn(move||{
        let mut reader=std::io::BufReader::new(stdout);
        let mut limited=reader.take((FORGE_STDOUT_LIMIT+1) as u64);let mut line=Vec::new();
        let result=limited.read_until(b'\n',&mut line);reader=limited.into_inner();(reader,line,result)
    });
    let deadline=std::time::Instant::now()+std::time::Duration::from_secs(180);
    loop{
        let canceled=cancel.as_ref().is_some_and(PortalCancellation::is_cancelled);
        let timed_out=std::time::Instant::now()>=deadline;
        if canceled||timed_out{
            kill_portal_child(&child);let _=writer.join();let _=reader.join();
            let sent=cancel.as_ref().is_some_and(PortalCancellation::was_dispatched);
            let code=if canceled{"PORTAL_CANCELLED"}else{"PORTAL_NATIVE_DEADLINE_EXCEEDED"};
            return(if sent{response(409,json!({"detail":{"code":code,"billing_state":"unresolved","cost_usd":null}}))}else{response(499,json!({"detail":{"code":code,"billing_state":"not_sent"}}))},None);
        }
        if reader.is_finished()&&writer.is_finished(){break;}
        if reader.is_finished()&&!writer.is_finished(){
            if portal_child_try_wait(&child).ok().flatten().is_none(){kill_portal_child(&child);}
            let _=writer.join();let _=reader.join();
            return(response(503,json!({"detail":{"code":"PORTAL_NATIVE_INPUT_FAILED","billing_state":"unresolved","cost_usd":null}})),None);
        }
        match portal_child_try_wait(&child){Ok(Some(_))=>{if reader.is_finished(){break;}},Ok(None)=>{},Err(_)=>{kill_portal_child(&child);let _=writer.join();let _=reader.join();return(unavailable("Forge runtime did not complete."),None);}}
        std::thread::sleep(std::time::Duration::from_millis(10));
    }
    let Some((stdout,line,read_result))=reader.join().ok()else{kill_portal_child(&child);let _=writer.join();return(response(503,json!({"detail":{"code":"PORTAL_NATIVE_RESPONSE_INVALID","billing_state":"unresolved"}})),None);};
    let Some((stdin,write_result))=writer.join().ok()else{kill_portal_child(&child);return(response(503,json!({"detail":{"code":"PORTAL_NATIVE_INPUT_FAILED","billing_state":"unresolved"}})),None);};
    if write_result.is_err(){kill_portal_child(&child);let sent=cancel.as_ref().is_some_and(PortalCancellation::was_dispatched);return(if sent{response(503,json!({"detail":{"code":"PORTAL_NATIVE_INPUT_FAILED","billing_state":"unresolved","cost_usd":null}}))}else{response(499,json!({"detail":{"code":"PORTAL_CANCELLED","billing_state":"not_sent"}}))},None);}
    if read_result.is_err()||line.len()>FORGE_STDOUT_LIMIT||!line.ends_with(b"\n")||!portal_client::lifecycle::validate_unique_json(&line[..line.len().saturating_sub(1)]){
        kill_portal_child(&child);return(response(503,json!({"detail":{"code":"PORTAL_NATIVE_RESPONSE_INVALID","billing_state":"unresolved","cost_usd":null}})),None);
    }
    let result:Value=match serde_json::from_slice::<Value>(&line[..line.len()-1]){Ok(value) if value.is_object()=>value,_=>{kill_portal_child(&child);return(response(503,json!({"detail":{"code":"PORTAL_NATIVE_RESPONSE_INVALID","billing_state":"unresolved","cost_usd":null}})),None);}};
    let status=result["http_status"].as_u64().filter(|value|(200..=599).contains(value)).unwrap_or(503)as u16;
    let body=result.get("body").filter(|value|value.is_object()).cloned().unwrap_or_else(||json!({"detail":{"code":"PORTAL_NATIVE_RESPONSE_INVALID","billing_state":"unresolved"}}));
    if status>=300{kill_portal_child(&child);return(response(status,body),None);}
    if portal_child_try_wait(&child).ok().flatten().is_some(){return(response(503,json!({"detail":{"code":"PORTAL_PREVIEW_WORKER_EXITED","billing_state":"unknown"}})),None);}
    (response(status,body),Some(PortalPreviewWorker{child,stdin,stdout}))
}

fn run_forge_child(mut command:std::process::Command,payload:Vec<u8>,cancel:Option<PortalCancellation>,portal_mode:bool)->ApiResponse{
    if payload.len()>65536{return response(400,json!({"detail":"Invalid Forge request."}));}
    if cancel.as_ref().is_some_and(PortalCancellation::is_cancelled){return response(499,json!({"detail":{"code":"PORTAL_CANCELLED","billing_state":"not_sent"}}));}
    let mut child=match command.spawn(){Ok(child)=>child,Err(_)=>return unavailable("Forge runtime could not start.")};
    let Some(mut stdin)=child.stdin.take() else {let _=child.kill();let _=child.wait();return unavailable("Forge runtime could not start.");};
    let Some(mut stdout)=child.stdout.take() else {let _=child.kill();let _=child.wait();return unavailable("Forge runtime could not start.");};
    let output=Arc::new(Mutex::new(Vec::with_capacity(FORGE_STDOUT_LIMIT)));
    let too_large=Arc::new(AtomicBool::new(false));
    let reader_output=output.clone();let reader_too_large=too_large.clone();
    let reader=std::thread::spawn(move||{
        let mut buffer=[0u8;4096];
        loop{match stdout.read(&mut buffer){Ok(0)=>break,Ok(count)=>{if let Ok(mut out)=reader_output.lock(){let room=FORGE_STDOUT_LIMIT.saturating_sub(out.len());let keep=room.min(count);out.extend_from_slice(&buffer[..keep]);if keep<count{reader_too_large.store(true,Ordering::SeqCst);}}},Err(error) if error.kind()==std::io::ErrorKind::Interrupted=>continue,Err(_)=>break}}
    });
    let writer_cancel=cancel.clone();
    let writer=std::thread::spawn(move||{
        if let Some(cancel)=writer_cancel{if !cancel.begin_dispatch(){return Err(std::io::Error::new(std::io::ErrorKind::Interrupted,"cancelled before dispatch"));}}
        stdin.write_all(&payload)
    });
    let deadline=std::time::Instant::now()+std::time::Duration::from_secs(180);
    loop{
        if cancel.as_ref().is_some_and(PortalCancellation::is_cancelled){
            let _=child.kill();let _=child.wait();let _=writer.join();let _=reader.join();
            let sent=cancel.as_ref().is_some_and(PortalCancellation::was_dispatched);
            return if sent{response(409,json!({"detail":{"code":"PORTAL_CANCELLED","billing_state":"unresolved","cost_usd":null}}))}else{response(499,json!({"detail":{"code":"PORTAL_CANCELLED","billing_state":"not_sent"}}))};
        }
        if portal_mode && std::time::Instant::now()>=deadline{
            let _=child.kill();let _=child.wait();let _=writer.join();let _=reader.join();
            let sent=cancel.as_ref().is_some_and(PortalCancellation::was_dispatched);
            return if sent{response(503,json!({"detail":{"code":"PORTAL_NATIVE_DEADLINE_EXCEEDED","billing_state":"unresolved","cost_usd":null}}))}else{response(503,json!({"detail":{"code":"PORTAL_NATIVE_DEADLINE_EXCEEDED","billing_state":"not_sent"}}))};
        }
        match child.try_wait(){Ok(Some(_))=>break,Ok(None)=>{},Err(_)=>{let _=child.kill();let _=child.wait();let _=writer.join();let _=reader.join();return unavailable("Forge runtime did not complete.");}}
        std::thread::sleep(std::time::Duration::from_millis(10));
    }
    let write_result=writer.join().ok().and_then(Result::ok);
    let _=reader.join();
    if write_result.is_none(){
        let sent=cancel.as_ref().is_some_and(PortalCancellation::was_dispatched);
        return if sent{response(503,json!({"detail":{"code":"PORTAL_NATIVE_INPUT_FAILED","billing_state":"unresolved","cost_usd":null}}))}else{response(499,json!({"detail":{"code":"PORTAL_CANCELLED","billing_state":"not_sent"}}))};
    }
    if too_large.load(Ordering::SeqCst){return if portal_mode{response(503,json!({"detail":{"code":"PORTAL_NATIVE_RESPONSE_TOO_LARGE","billing_state":"unresolved","cost_usd":null}}))}else{unavailable("Forge runtime returned an oversized response.")};}
    let raw=output.lock().map(|value|value.clone()).unwrap_or_default();
    if !portal_client::lifecycle::validate_unique_json(&raw){return if portal_mode{response(503,json!({"detail":{"code":"PORTAL_NATIVE_RESPONSE_INVALID","billing_state":"unresolved","cost_usd":null}}))}else{unavailable("Forge runtime returned an invalid response.")};}
    let result:Value=match serde_json::from_slice::<Value>(&raw){Ok(value) if value.is_object()=>value,_=>return if portal_mode{response(503,json!({"detail":{"code":"PORTAL_NATIVE_RESPONSE_INVALID","billing_state":"unresolved","cost_usd":null}}))}else{unavailable("Forge runtime returned an invalid response.")}};
    let status=result["http_status"].as_u64().filter(|status|(200..=599).contains(status)).unwrap_or(503) as u16;
    let body=result.get("body").filter(|value|value.is_object()).cloned().unwrap_or_else(||json!({"detail":{"code":"PORTAL_NATIVE_RESPONSE_INVALID","billing_state":if portal_mode{"unresolved"}else{"not_sent"}}}));
    response(status,body)
}

#[cfg(test)]
mod portal_forge_tests{
    use super::*;
    use std::future::Future;

    fn fixture_python_exe()->PathBuf{
        option_env!("NAVIS_TEST_PYTHON").map(PathBuf::from).unwrap_or_else(||PathBuf::from("python.exe"))
    }
    #[test]
    fn portal_child_no_read_fixture(){
        if let Some(marker)=std::env::var_os("NAVIS_S028_CHILD_READY"){
            std::fs::write(marker,b"ready").unwrap();
            std::thread::sleep(std::time::Duration::from_secs(30));
        }
    }

    fn spawn_portal_preview_fixture()->(ApiResponse,Option<PortalPreviewWorker>){
        let script=r#"import sys
sys.stdin.readline()
sys.stdout.write('{"http_status":200,"body":{"status":"success","proposal_id":"portal-00000000000000000000000000000000"}}\n')
sys.stdout.flush()
sys.stdin.readline()
sys.stdout.write('{"http_status":200,"body":{"status":"success"}}\n')
sys.stdout.flush()
"#;
        let mut command=std::process::Command::new(fixture_python_exe());
        command.args(["-I","-B","-c",script])
            .stdin(std::process::Stdio::piped()).stdout(std::process::Stdio::piped()).stderr(std::process::Stdio::null());
        let envelope=json!({"request":{"provider":"portal","portal_opt_in":true,"allow_external_text":true,"operation_id":"fixture-op"},"native_binding":{"expected_host_generation":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}).to_string().into_bytes();
        run_portal_preview_submit(command,envelope,None)
    }

    #[cfg(windows)]
    fn spawn_portal_preview_descendant_fixture(started:&Path,late:&Path)->(ApiResponse,Option<PortalPreviewWorker>){
        let script=r#"import pathlib,subprocess,sys,time
started,late=sys.argv[1:3]
sys.stdin.readline()
sys.stdout.write('{"http_status":200,"body":{"status":"success","proposal_id":"portal-00000000000000000000000000000000"}}\n')
sys.stdout.flush()
sys.stdin.readline()
child_script="import pathlib,sys,time; time.sleep(8); pathlib.Path(sys.argv[1]).write_text('late',encoding='utf-8')"
child=subprocess.Popen([sys.executable,"-I","-B","-c",child_script,late],creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0x08000000))
pathlib.Path(started).write_text(str(child.pid),encoding="ascii")
time.sleep(30)
"#;
        let mut command=std::process::Command::new(fixture_python_exe());
        command.args(["-I","-B","-c",script]).arg(started.as_os_str()).arg(late.as_os_str())
            .stdin(std::process::Stdio::piped()).stdout(std::process::Stdio::piped()).stderr(std::process::Stdio::null());
        let envelope=json!({"request":{"provider":"portal","portal_opt_in":true,"allow_external_text":true,"operation_id":"fixture-op"},"native_binding":{"expected_host_generation":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}).to_string().into_bytes();
        run_portal_preview_submit(command,envelope,None)
    }

    #[test]
    fn native_python_worker_keeps_proposal_alive_until_approve_or_discard(){
        for action in ["approve","discard"]{
            let state=PortalForgeState::default();let(result,worker)=spawn_portal_preview_fixture();
            assert_eq!(result.status,200,"{}",result.body);let worker=worker.expect("fixture worker remains alive");
            let proposal="portal-00000000000000000000000000000000";
            let _=register_portal_operation(&state,"fixture-op").unwrap_or_else(|_|panic!("reserve fixture preview"));
            retain_portal_preview(&state,"fixture-op",proposal.into(),worker).unwrap_or_else(|_|panic!("retain fixture worker"));
            finish_portal_operation(&state,"fixture-op");
            let request=if action=="approve"{json!({"proposal_id":proposal,"approved":true})}else{json!({"proposal_id":proposal})};
            let result=portal_preview_action(&state,proposal,action,request);
            assert_eq!(result.status,200,"{}",result.body);
            assert!(!state.0.lock().unwrap().previews.contains_key(proposal));
            cancel_all_portal_operations(&state);
        }
    }

    #[test]
    fn app_close_reaps_idle_portal_preview_worker(){
        let state=PortalForgeState::default();let(result,worker)=spawn_portal_preview_fixture();assert_eq!(result.status,200,"{}",result.body);
        let worker=worker.expect("fixture worker remains alive");let child=worker.child.clone();
        let _=register_portal_operation(&state,"fixture-close-op").unwrap_or_else(|_|panic!("reserve close fixture"));
        retain_portal_preview(&state,"fixture-close-op","portal-00000000000000000000000000000000".into(),worker).unwrap_or_else(|_|panic!("retain fixture worker"));
        finish_portal_operation(&state,"fixture-close-op");
        cancel_all_portal_operations(&state);
        assert!(child.process.lock().unwrap().try_wait().unwrap().is_some());
    }

    #[cfg(windows)]
    #[test]
    fn preview_timeout_terminates_started_descendant_process_tree(){
        let root=std::env::temp_dir().join(format!("portal-s028-tree-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();
        let started=root.join("started.pid");let late=root.join("late.flag");
        let state=PortalForgeState::default();let(result,worker)=spawn_portal_preview_descendant_fixture(&started,&late);
        assert_eq!(result.status,200,"preview worker starts: {}",result.body);let worker=worker.expect("idle worker retained");
        let proposal="portal-00000000000000000000000000000000";
        register_portal_operation(&state,"fixture-timeout-op").unwrap();
        retain_portal_preview(&state,"fixture-timeout-op",proposal.into(),worker).unwrap();
        finish_portal_operation(&state,"fixture-timeout-op");
        let action_state=state.clone();let action_proposal=proposal.to_string();
        let action=std::thread::spawn(move||portal_preview_action_with_timeout(&action_state,&action_proposal,"approve",json!({"proposal_id":action_proposal,"approved":true}),std::time::Duration::from_secs(3)));
        let deadline=std::time::Instant::now()+std::time::Duration::from_secs(5);
        while !started.exists()&&std::time::Instant::now()<deadline{std::thread::sleep(std::time::Duration::from_millis(10));}
        assert!(started.exists(),"descendant must start before timeout assertion");
        let pid=std::fs::read_to_string(&started).unwrap().trim().parse::<u32>().unwrap();
        let handle=unsafe{windows_sys::Win32::System::Threading::OpenProcess(windows_sys::Win32::System::Threading::PROCESS_SYNCHRONIZE,0,pid)};
        assert!(!handle.is_null(),"descendant process must be observable alive before timeout");
        let live=unsafe{windows_sys::Win32::System::Threading::WaitForSingleObject(handle,0)==windows_sys::Win32::Foundation::WAIT_TIMEOUT};
        assert!(live,"descendant must still be running before timeout");
        let response=action.join().unwrap();assert_eq!(response.status,503);assert_eq!(response.body["detail"]["code"],"PORTAL_PREVIEW_ACTION_TIMEOUT");
        let exited_deadline=std::time::Instant::now()+std::time::Duration::from_secs(3);
        let mut exited=false;while std::time::Instant::now()<exited_deadline{if unsafe{windows_sys::Win32::System::Threading::WaitForSingleObject(handle,0)}!=windows_sys::Win32::Foundation::WAIT_TIMEOUT{exited=true;break;}std::thread::sleep(std::time::Duration::from_millis(10));}
        unsafe{windows_sys::Win32::Foundation::CloseHandle(handle);}
        assert!(exited,"job close must terminate the started descendant");
        std::thread::sleep(std::time::Duration::from_secs(1));assert!(!late.exists(),"terminated descendant must not write its late marker");
        cancel_all_portal_operations(&state);std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn cancelled_operation_cannot_retain_preview_worker(){
        let state=PortalForgeState::default();
        let _=register_portal_operation(&state,"fixture-cancel-retain").unwrap_or_else(|_|panic!("reserve cancel-retain fixture"));
        let(result,worker)=spawn_portal_preview_fixture();assert_eq!(result.status,200,"{}",result.body);
        let worker=worker.expect("fixture worker remains alive");let child=worker.child.clone();
        cancel_portal_operation(&state,"fixture-cancel-retain").unwrap_or_else(|_|panic!("cancel fixture operation"));
        let error=retain_portal_preview(&state,"fixture-cancel-retain","portal-00000000000000000000000000000000".into(),worker).unwrap_err();
        assert_eq!(error.status,499);assert_eq!(error.body["detail"]["code"],"PORTAL_CANCELLED");
        let settled=json!({"billing_state":"settled","cost_usd":"0.00042","provider":"portal"});
        let error=portal_retention_error(error,Some(&settled));
        assert_eq!(serde_json::from_str::<Value>(&error.text).unwrap(),error.body);
        assert_eq!(error.body["detail"]["portal_receipt"],settled);
        assert_eq!(error.body["detail"]["billing_state"],"settled");
        assert_eq!(error.body["detail"]["cost_usd"],"0.00042");
        assert!(!state.0.lock().unwrap().previews.contains_key("portal-00000000000000000000000000000000"));
        assert!(child.process.lock().unwrap().try_wait().unwrap().is_some());
    }

    #[test]
    fn cancellation_kills_only_owned_child_during_blocked_stdin_write(){
        let marker=std::env::temp_dir().join(format!("portal-s028-{}.flag",uuid::Uuid::new_v4()));
        let mut command=std::process::Command::new(std::env::current_exe().unwrap());
        command.args(["--exact","p5::portal_forge_tests::portal_child_no_read_fixture"])
            .env("NAVIS_S028_CHILD_READY",&marker)
            .stdin(std::process::Stdio::piped()).stdout(std::process::Stdio::piped()).stderr(std::process::Stdio::null());
        let cancel=PortalCancellation::default();let worker_cancel=cancel.clone();
        let worker=std::thread::spawn(move||run_forge_child(command,vec![b'x';65536],Some(worker_cancel),true));
        let deadline=std::time::Instant::now()+std::time::Duration::from_secs(5);
        while (!marker.exists()||!cancel.was_dispatched())&&std::time::Instant::now()<deadline{std::thread::sleep(std::time::Duration::from_millis(10));}
        assert!(marker.exists(),"synthetic child started before cancellation");
        assert!(cancel.was_dispatched(),"synthetic child reached the blocked stdin dispatch");
        cancel.cancel();
        let result=worker.join().unwrap();
        let _=std::fs::remove_file(marker);
        assert_eq!(result.status,409);
        assert_eq!(result.body["detail"]["billing_state"],"unresolved");
    }

    #[test]
    fn app_close_cancels_registered_operation_before_dispatch(){
        let state=PortalForgeState::default();
        let cancel=match register_portal_operation(&state,"synthetic-close-1"){Ok(value)=>value,Err(_)=>panic!("synthetic operation registration failed")};
        cancel_all_portal_operations(&state);
        assert!(cancel.is_cancelled());
        assert!(!cancel.begin_dispatch());
        assert!(cancel_portal_operation(&state,"synthetic-navigation-2").is_ok());
        let pending=match register_portal_operation(&state,"synthetic-navigation-2"){Ok(value)=>value,Err(_)=>panic!("synthetic pending registration failed")};
        assert!(pending.is_cancelled());
        assert!(!pending.begin_dispatch());
    }

    struct Unpark(std::thread::Thread);
    impl std::task::Wake for Unpark{fn wake(self:Arc<Self>){self.0.unpark();}}
    fn block_on_fixture<F:Future>(future:F)->F::Output{
        let waker=std::task::Waker::from(Arc::new(Unpark(std::thread::current())));
        let mut context=std::task::Context::from_waker(&waker);let mut future=Box::pin(future);
        loop{if let std::task::Poll::Ready(value)=future.as_mut().poll(&mut context){return value;}std::thread::park_timeout(std::time::Duration::from_millis(10));}
    }

    #[cfg(windows)]
    struct FixtureProcessHandle(windows_sys::Win32::Foundation::HANDLE);
    #[cfg(windows)]
    impl Drop for FixtureProcessHandle{
        fn drop(&mut self){unsafe{windows_sys::Win32::Foundation::CloseHandle(self.0);}}
    }
    #[cfg(windows)]
    fn open_fixture_process(pid:u32)->FixtureProcessHandle{
        let handle=unsafe{windows_sys::Win32::System::Threading::OpenProcess(
            windows_sys::Win32::System::Threading::PROCESS_SYNCHRONIZE,0,pid)};
        assert!(!handle.is_null(),"fixture Forge worker process must remain queryable after cancellation");
        FixtureProcessHandle(handle)
    }
    #[cfg(windows)]
    fn fixture_process_signaled(handle:&FixtureProcessHandle)->bool{
        let result=unsafe{windows_sys::Win32::System::Threading::WaitForSingleObject(handle.0,0)};
        result==windows_sys::Win32::Foundation::WAIT_OBJECT_0
    }

    #[derive(Clone,Copy)]
    enum S028FixturePhase{Started,Stopped,CancelledAcquire,Acquired,SharedAttach,RunningStatus,SubmitSettled,
        DuplicateUnknown,MissingUsageUnresolved,CloseDispatchStarted,CloseCancelled,HostStillShared,Complete}
    impl S028FixturePhase{
        fn name(self)->&'static str{match self{
            Self::Started=>"started",Self::Stopped=>"stopped",Self::CancelledAcquire=>"cancelled-acquire",
            Self::Acquired=>"acquired",Self::SharedAttach=>"shared-attach",Self::RunningStatus=>"running-status",
            Self::SubmitSettled=>"submit-settled",Self::DuplicateUnknown=>"duplicate-unknown",
            Self::MissingUsageUnresolved=>"missing-usage-unresolved",Self::CloseDispatchStarted=>"close-dispatch-started",
            Self::CloseCancelled=>"close-cancelled",Self::HostStillShared=>"host-still-shared",Self::Complete=>"complete"}}
    }
    fn record_s028_fixture_phase(root:&Path,phase:S028FixturePhase,status:Option<u16>,billing:Option<&'static str>,dispatches:u8){
        if let Some(value)=billing{assert!(matches!(value,"settled"|"unresolved"|"duplicate_unknown"|"not_sent"));}
        assert!(dispatches<=3,"fixture dispatch counter is bounded");
        let path=root.join(format!("native-test-phase-{}.json",phase.name()));
        let mut file=std::fs::OpenOptions::new().write(true).create_new(true).open(path)
            .expect("create-only metadata phase marker");
        serde_json::to_writer(&mut file,&json!({"schema":1,"phase":phase.name(),"status":status,
            "billing_state":billing,"provider_dispatch_count":dispatches})).expect("write bounded phase metadata");
        file.sync_all().expect("flush phase metadata");
    }
    fn record_s028_fixture_acquire_error(root:&Path,error:&portal_client::ClientError){
        let code=match error.code{
            "GUARDIAN_REQUEST_INVALID"|"GUARDIAN_CALLER_REFUSED"|"GUARDIAN_BUSY"|"GUARDIAN_PROFILE_CHANGED"|
            "GUARDIAN_COLD_START_BLOCKED"|"GUARDIAN_BROKER_UNAVAILABLE"|"LIFECYCLE_UNRESOLVED"|
            "HOST_CANCELLED"|"HOST_START_TIMEOUT"|"HOST_LAUNCH_REFUSED"|"HOST_LAUNCH_CLEANUP_PENDING"|
            "HOST_PROFILE_INVALID"|"HOST_IDENTITY_MISMATCH"|"HOST_INCOMPATIBLE"|"HOST_LISTENER_UNTRUSTED"|
            "HOST_UNAVAILABLE"|"HOST_STOP_PENDING"|"HOST_TIMEOUT_INVALID"|"HOST_REGISTRATION_EXISTS"|
            "HOST_SELECTED_RELEASE_REQUIRED"|"HOST_INPUT_PIN_FAILED"|"HOST_PLATFORM_UNSUPPORTED"=>error.code,
            _=>"LIFECYCLE_UNRESOLVED",
        };
        let code_classified=code==error.code;
        let kind=if error.kind=="not_sent"{"not_sent"}else{"unclassified"};
        let path=root.join("native-test-acquire-error.json");
        let mut file=std::fs::OpenOptions::new().write(true).create_new(true).open(path)
            .expect("create-only bounded native acquire error marker");
        serde_json::to_writer(&mut file,&json!({"schema":1,"phase":"acquire","kind":kind,
            "code":code,"code_classified":code_classified,"billing_state":"not_sent"}))
            .expect("write bounded native acquire error marker");
        file.sync_all().expect("flush native acquire error marker");
    }
    #[test]
    fn s028_fixture_acquire_error_marker_is_bounded_and_create_only(){
        let base=PathBuf::from(std::env::var("NAVIS_S028_ACQUIRE_ERROR_TEST_ROOT")
            .expect("private generated diagnostic test root"));
        let known=base.join("known");std::fs::create_dir(&known).expect("create known generated subroot");
        let known_error=portal_client::ClientError{kind:"not_sent",code:"HOST_START_TIMEOUT",
            correlation:Some("synthetic-correlation-not-recorded".to_string())};
        record_s028_fixture_acquire_error(&known,&known_error);
        let known_frame:Value=serde_json::from_slice(&std::fs::read(known.join("native-test-acquire-error.json")).unwrap()).unwrap();
        assert_eq!(known_frame,json!({"schema":1,"phase":"acquire","kind":"not_sent","code":"HOST_START_TIMEOUT",
            "code_classified":true,"billing_state":"not_sent"}));
        let unknown=base.join("unknown");std::fs::create_dir(&unknown).expect("create unknown generated subroot");
        let unknown_error=portal_client::ClientError{kind:"private-kind",code:"PRIVATE_DETAIL",
            correlation:Some("synthetic-correlation-not-recorded".to_string())};
        record_s028_fixture_acquire_error(&unknown,&unknown_error);
        let unknown_frame:Value=serde_json::from_slice(&std::fs::read(unknown.join("native-test-acquire-error.json")).unwrap()).unwrap();
        assert_eq!(unknown_frame["code"],"LIFECYCLE_UNRESOLVED");
        assert_eq!(unknown_frame["kind"],"unclassified");
        assert_eq!(unknown_frame["code_classified"],false);
        let collision=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||record_s028_fixture_acquire_error(&known,&known_error)));
        assert!(collision.is_err(),"diagnostic marker must refuse overwrite");
    }

    #[cfg(windows)]
    #[test]
    fn composed_native_acquire_and_trusted_portal_forge_fixture(){
        let required=|name:&str|std::env::var(name).unwrap_or_else(|_|panic!("missing fixture environment {name}"));
        assert_eq!(required("NAVIS_PORTAL_LIFECYCLE_REQUIRED"),"1","composed fixture must use the guardian broker");
        assert!(std::env::var_os("NAVIS_PORTAL_LIFECYCLE_PIPE").is_some(),"guardian pipe is required; direct fallback is forbidden");
        let profile=PathBuf::from(required("NAVIS_PORTAL_PROFILE"));
        let vault=PathBuf::from(required("NAVIS_ROOT"));
        let feature:Value=serde_json::from_slice(&std::fs::read(&profile).expect("generated feature profile")).expect("feature profile JSON");
        let release=PathBuf::from(feature["portal_release_root"].as_str().expect("feature release root"));
        let root=release.parent().and_then(Path::parent).expect("generated host root").to_path_buf();
        let artifact_path=root.join("fixture-artifacts.json");
        let artifacts:Value=serde_json::from_slice(&std::fs::read(&artifact_path).expect("pinned fixture artifact manifest"))
            .expect("fixture artifact manifest JSON");
        assert_eq!(artifacts["schema"],1);assert_eq!(artifacts["kind"],"portal-s028-native-composed");
        assert_eq!(PathBuf::from(artifacts["host_root"].as_str().unwrap()).canonicalize().unwrap(),root.canonicalize().unwrap());
        assert_eq!(PathBuf::from(artifacts["vault_root"].as_str().unwrap()).canonicalize().unwrap(),vault.canonicalize().unwrap());
        assert_eq!(PathBuf::from(artifacts["profile_path"].as_str().unwrap()).canonicalize().unwrap(),profile.canonicalize().unwrap());
        assert_eq!(PathBuf::from(artifacts["release_path"].as_str().unwrap()).canonicalize().unwrap(),release.canonicalize().unwrap());
        assert_eq!(artifacts["expected_test_count"],1,"only the pinned composed native test may run");
        assert_eq!(artifacts["selected_test_name"],"p5::portal_forge_tests::composed_native_acquire_and_trusted_portal_forge_fixture");
        assert_eq!(artifacts["fixture_guard_seconds"],180,"generated service lifetime is explicitly bounded");
        for field in ["package_sha256","manifest_sha256","host_runtime_sha256","feature_test_runtime_sha256"]{
            assert_eq!(artifacts[field].as_str().map(str::len),Some(64),"fixture artifact {field} must carry a SHA-256");
        }
        assert_eq!(PathBuf::from(artifacts["test_binary_path"].as_str().unwrap()).canonicalize().unwrap(),
            std::env::current_exe().expect("current filtered test binary").canonicalize().unwrap());
        assert_eq!(PathBuf::from(artifacts["composed_test_path"].as_str().unwrap()).canonicalize().unwrap(),
            PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../backend/tests/test_portal_native_composed.py").canonicalize().unwrap());
        let worker=PathBuf::from(artifacts["worker_path"].as_str().unwrap());
        let worker_sha=artifacts["worker_sha256"].as_str().expect("worker hash").to_string();
        let python=PathBuf::from(artifacts["host_runtime_path"].as_str().unwrap());
        let shim=PathBuf::from(artifacts["shim_path"].as_str().unwrap());
        let backend=PathBuf::from(artifacts["backend_path"].as_str().unwrap());
        let release_id=artifacts["release_id"].as_str().expect("pinned release ID").to_string();
        let proposal_cache=PathBuf::from(artifacts["proposal_cache_path"].as_str().unwrap());
        let context=portal_client::lifecycle::SharedPortal::fixture(root.clone(),worker.clone(),worker_sha);
        record_s028_fixture_phase(&root,S028FixturePhase::Started,None,None,0);
        let stopped=block_on_fixture(context.status(std::time::Duration::from_secs(10),&portal_client::Cancellation::default())).expect("generated stopped-host status");
        assert_eq!(stopped.receipt()["state"],"stopped");assert!(stopped.generation().is_none());
        record_s028_fixture_phase(&root,S028FixturePhase::Stopped,None,None,0);

        let cancelled=PortalCancellation::default();cancelled.cancel();
        assert!(block_on_fixture(acquire_portal_connection(&context,&cancelled)).is_err());
        let after_cancel=block_on_fixture(context.status(std::time::Duration::from_secs(10),&portal_client::Cancellation::default())).expect("cancel leaves host stopped");
        assert_eq!(after_cancel.receipt()["state"],"stopped");
        record_s028_fixture_phase(&root,S028FixturePhase::CancelledAcquire,None,Some("not_sent"),0);
        let cancel=PortalCancellation::default();
        let acquired=block_on_fixture(acquire_portal_connection(&context,&cancel));
        let connection=match acquired{
            Ok(connection)=>connection,
            Err(error)=>{
                record_s028_fixture_acquire_error(&root,&error);
                panic!("native SDK acquire failed; see bounded fixture error marker");
            }
        };
        let generation=connection.generation().expect("acquired pinned generation").to_string();
        assert_eq!(generation.len(),32);
        record_s028_fixture_phase(&root,S028FixturePhase::Acquired,None,None,0);
        let attached=block_on_fixture(acquire_portal_connection(&context,&PortalCancellation::default())).expect("second native client shares host");
        assert_eq!(attached.generation(),Some(generation.as_str()));drop(attached);
        record_s028_fixture_phase(&root,S028FixturePhase::SharedAttach,None,None,0);
        let running=block_on_fixture(context.status(std::time::Duration::from_secs(10),&portal_client::Cancellation::default())).expect("running-host status");
        assert_eq!(running.generation(),Some(generation.as_str()));drop(running);
        record_s028_fixture_phase(&root,S028FixturePhase::RunningStatus,None,None,0);

        let command=||{
            let (selected,pin)=pin_registered_portal_runtime().expect("select and pin registered Portal runtime");
            assert_eq!(selected,python,"native Forge must use the registered host runtime");
            let mut command=std::process::Command::new(&selected);command.args(["-I","-B"]).arg(&shim);
            command.current_dir(&backend).env_clear();
            for key in ["SystemRoot","TEMP","TMP","PATH"]{if let Ok(value)=std::env::var(key){command.env(key,value);}}
            command.env("NAVIS_ROOT",&vault).env("NAVIS_PORTAL_PROFILE",&profile).env("NAVIS_PORTAL_ENABLED","1")
                .env("NAVIS_NATIVE_PORTAL","1");
            command.stdin(std::process::Stdio::piped()).stdout(std::process::Stdio::piped()).stderr(std::process::Stdio::null());(command,pin)
        };
        let payload=|operation:&str,name:&str|json!({"request":{"entity_type":"companion","name":name,"prompt":"Generated synthetic character","provider":"portal","portal_opt_in":true,"allow_external_text":true,"operation_id":operation},"native_binding":{"expected_host_generation":generation}}).to_string().into_bytes();
        let state=PortalForgeState::default();
        let submit_cancel=register_portal_operation(&state,"s028-native-operation-1").expect("register operation before actual native dispatch");
        let (submit_command,submit_runtime_pin)=command();
        let (preview,preview_worker)=run_portal_preview_submit(submit_command,payload("s028-native-operation-1","Aster"),Some(submit_cancel));drop(submit_runtime_pin);
        assert_eq!(preview.status,200,"{}",preview.body);assert_eq!(preview.body["portal_receipt"]["billing_state"],"settled");
        record_s028_fixture_phase(&root,S028FixturePhase::SubmitSettled,Some(preview.status),Some("settled"),1);
        let proposal=preview.body["proposal_id"].as_str().expect("volatile proposal id").to_string();
        assert!(preview_worker.is_some());assert!(!vault.join("Companions").exists());
        assert!(!vault.join(".proposals").exists());assert!(!vault.join("proposals").exists());
        retain_portal_preview(&state,"s028-native-operation-1",proposal.clone(),preview_worker.unwrap()).expect("retain actual Python process");
        finish_portal_operation(&state,"s028-native-operation-1");
        // Duplicate native requests reuse the same generation and stable operation ID, without replay,
        // while the first volatile preview still has no manifestation destination.
        let duplicate_cancel=register_portal_operation(&state,"s028-native-operation-1").expect("register duplicate operation before native dispatch");
        let (duplicate_command,duplicate_runtime_pin)=command();
        let (preview,duplicate_worker)=run_portal_preview_submit(duplicate_command,payload("s028-native-operation-1","Aster"),Some(duplicate_cancel));drop(duplicate_runtime_pin);
        assert_eq!(preview.status,409,"{}",preview.body);assert_eq!(preview.body["detail"]["billing_state"],"duplicate_unknown");assert!(duplicate_worker.is_none());
        record_s028_fixture_phase(&root,S028FixturePhase::DuplicateUnknown,Some(preview.status),Some("duplicate_unknown"),1);
        finish_portal_operation(&state,"s028-native-operation-1");
        let approved=portal_preview_action(&state,&proposal,"approve",json!({"proposal_id":proposal,"approved":true}));
        assert_eq!(approved.status,200,"{}",approved.body);assert!(vault.join("Companions/Aster/Profile.md").is_file());
        // This invokes the same cancellation function wired to the main-window close and app-exit handlers.
        let close_operation="s028-native-operation-close";
        let close_cancel=register_portal_operation(&state,close_operation).expect("register before close-case dispatch");
        std::fs::write(root.join("provider-mode.json"),br#"{"mode":"block","name":"Cedar"}"#).expect("select blocking synthetic provider");
        let (close_command,close_runtime_pin)=command();let close_payload=payload(close_operation,"Cedar");
        let active_submit=std::thread::spawn(move||{
            let result=run_portal_preview_submit(close_command,close_payload,Some(close_cancel));
            drop(close_runtime_pin);result
        });
        let deadline=std::time::Instant::now()+std::time::Duration::from_secs(15);
        while (!root.join("provider-dispatch-started.json").exists()||!root.join("portal-cli-blocked-worker.json").exists())
            && std::time::Instant::now()<deadline{std::thread::sleep(std::time::Duration::from_millis(10));}
        assert!(root.join("provider-dispatch-started.json").is_file(),"fake provider must observe the real Forge submit before close");
        record_s028_fixture_phase(&root,S028FixturePhase::CloseDispatchStarted,None,None,2);
        let cli_child:Value=serde_json::from_slice(&std::fs::read(root.join("portal-cli-blocked-worker.json")).expect("actual native Forge child marker"))
            .expect("native Forge child marker JSON");
        let cli_pid=cli_child["pid"].as_u64().expect("native Forge child PID") as u32;
        let cli_process=open_fixture_process(cli_pid);
        assert!(!fixture_process_signaled(&cli_process),"native Forge child must still be active immediately before close");
        cancel_all_portal_operations(&state);
        std::fs::write(root.join("provider-release.flag"),b"release synthetic provider after owned CLI cancellation").expect("unblock fixture service worker");
        let (closed,close_worker)=active_submit.join().expect("active submit thread joins after app-close cancellation");
        assert_eq!(closed.status,409,"{}",closed.body);assert_eq!(closed.body["detail"]["code"],"PORTAL_CANCELLED");
        assert_eq!(closed.body["detail"]["billing_state"],"unresolved");assert!(close_worker.is_none());
        assert!(fixture_process_signaled(&cli_process),"owned Forge CLI child must be reaped by close cancellation");
        record_s028_fixture_phase(&root,S028FixturePhase::CloseCancelled,Some(closed.status),Some("unresolved"),2);
        finish_portal_operation(&state,close_operation);
        let release_deadline=std::time::Instant::now()+std::time::Duration::from_secs(5);
        while !root.join("provider-dispatch-finished.json").exists()&&std::time::Instant::now()<release_deadline{
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        assert!(root.join("provider-dispatch-finished.json").is_file(),"fixture provider must release after the canceled client is reaped");
        let after_close=block_on_fixture(context.status(std::time::Duration::from_secs(10),&portal_client::Cancellation::default()))
            .expect("app close leaves shared host available");
        assert_eq!(after_close.generation(),Some(generation.as_str()));let after_generation=after_close.generation().unwrap().to_string();drop(after_close);drop(connection);
        record_s028_fixture_phase(&root,S028FixturePhase::HostStillShared,None,None,2);
        std::fs::write(root.join("native-close-equivalent-result.json"),json!({
            "scope":"cancel_all_portal_operations called directly; same function is wired to main CloseRequested and RunEvent::Exit",
            "webview_launched":false,"provider_dispatch_observed":true,"forge_cli_child_exited":true,
            "billing_state":closed.body["detail"]["billing_state"],"host_generation_before":generation,
            "host_generation_after_close":after_generation
        }).to_string()).expect("write generated native close-equivalent receipt");
        let _=std::fs::write(root.join("provider-mode.json"),br#"{"mode":"missing-usage","name":"Beryl"}"#);
        let missing_cancel=register_portal_operation(&state,"s028-native-operation-missing-usage").expect("register missing-usage operation");
        let (missing_command,missing_runtime_pin)=command();
        let (missing,missing_worker)=run_portal_preview_submit(missing_command,payload("s028-native-operation-missing-usage","Beryl"),Some(missing_cancel));drop(missing_runtime_pin);
        assert!(matches!(missing.status,409|503),"unexpected missing-usage response: {}",missing.body);
        assert_eq!(missing.body["detail"]["billing_state"],"unresolved");assert!(missing.body["detail"]["cost_usd"].is_null());
        assert!(missing_worker.is_none());
        record_s028_fixture_phase(&root,S028FixturePhase::MissingUsageUnresolved,Some(missing.status),Some("unresolved"),3);
        finish_portal_operation(&state,"s028-native-operation-missing-usage");
        record_s028_fixture_phase(&root,S028FixturePhase::Complete,Some(200),Some("unresolved"),3);
    }
}

fn find_backend() -> Option<PathBuf> {
    if let Ok(root) = std::env::var("NAVIS_BACKEND_DIR").map(PathBuf::from) {
        if root.exists() {
            return Some(root);
        }
    }
    let candidate = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("backend");
    if candidate.exists() {
        return Some(candidate);
    }
    None
}

// Classify stderr without exposing paths, credentials, or private input.
fn conversation_output(stdout: &[u8], stderr: &[u8], success: bool) -> ApiResponse {
    if !success {
        let diagnostic = String::from_utf8_lossy(stderr);
        let message = if diagnostic.contains("ModuleNotFoundError") || diagnostic.contains("ImportError") {
            "Conversation Python dependencies are missing. Install backend requirements in the NAVIS_PYTHON interpreter (including aiohttp), then restart Navis."
        } else {
            "Conversation runtime exited unexpectedly. Verify NAVIS_PYTHON and backend dependencies, then restart Navis."
        };
        return unavailable(message);
    }
    let result: Value = match serde_json::from_slice(stdout) {
        Ok(value) => value,
        Err(_) => return unavailable("Conversation runtime returned an invalid or empty response. Reinstall the current build, verify Python dependencies, and retry."),
    };
    let status = match result["http_status"].as_u64() {
        Some(value) if (200..=599).contains(&value) && result["body"].is_object() => value as u16,
        _ => return unavailable("Conversation runtime returned an invalid response envelope. Reinstall the current build and retry."),
    };
    if status < 300 && !result["body"]["response"].is_string() {
        return unavailable("Conversation runtime returned no message. Check the configured local model and retry.");
    }
    response(status, result["body"].clone())
}

/// Shared Conversation service for Reid, Neural Bridge, and War Room.
pub fn conversation_request(
    backend: &std::path::Path,
    path: &str,
    method: &str,
    body: Option<Value>,
) -> Result<ApiResponse, String> {
    let action = match (method, path) {
        ("POST", "/api/reid/chat") => "reid_chat",
        ("POST", "/api/neural/chat") => "neural_chat",
        ("POST", "/api/neural/warroom/chat") => "warroom_chat",
        _ => return Ok(response(400, json!({"detail":"Unsupported conversation action."}))),
    };
    if !backend.join("services/conversation_runtime.py").is_file()
        || !backend.join("services/conversation_service.py").is_file()
        || !backend.join("services/reid_agent.py").is_file() {
        return Ok(unavailable("Conversation backend files are missing. Reinstall the current Navis desktop build or use a complete development checkout."));
    }
    let runtime = match crate::command::resolve_python_runtime(backend, !cfg!(debug_assertions)) {
        Ok(value) => value,
        Err(_) => return Ok(unavailable("Conversation requires Python 3.11+. Set NAVIS_PYTHON to a supported interpreter with aiohttp installed, then restart Navis.")),
    };
    let mut command = crate::command::hidden_command(&runtime.to_string_lossy());
    command.args(["-m", "services.conversation_runtime", action]).current_dir(backend).env_clear();
    for key in [
        "PATH",
        "SystemRoot",
        "TEMP",
        "TMP",
        "NAVIS_OLLAMA_URL",
        "NAVIS_OLLAMA_MODEL",
        "NAVIS_OLLAMA_TIMEOUT",
        "NAVIS_AI_PROVIDER", "NAVIS_OPENROUTER_CONFIG", "OPENROUTER_API_KEY",
        "NAVIS_REID_NOTE_FILES",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
    ] {
        if let Ok(value) = std::env::var(key) { command.env(key, value); }
    }
    command.env("NAVIS_ROOT", root()).env("PYTHONIOENCODING", "utf-8")
        .stdin(std::process::Stdio::piped()).stdout(std::process::Stdio::piped()).stderr(std::process::Stdio::piped());
    let mut child = match command.spawn() {
        Ok(value) => value,
        Err(_) => return Ok(unavailable("Conversation runtime could not start. Verify NAVIS_PYTHON and restart Navis.")),
    };
    if let Some(mut input) = child.stdin.take() {
        let payload = body.unwrap_or_else(|| json!({})).to_string();
        if payload.len() > 65536 || input.write_all(payload.as_bytes()).is_err() {
            let _ = child.kill(); let _ = child.wait();
            return Ok(response(400, json!({"detail":"Invalid conversation request."})));
        }
    }
    let output = match child.wait_with_output() {
        Ok(value) => value,
        Err(_) => return Ok(unavailable("Conversation runtime did not complete. Restart Navis and retry.")),
    };
    let parsed = conversation_output(&output.stdout, &output.stderr, output.status.success());
    let status = parsed.status;
    let body_val = parsed.body;
    let text = if path == "/api/neural/warroom/chat" {
        body_val.get("response").and_then(Value::as_str).unwrap_or(&body_val.to_string()).to_string()
    } else {
        body_val.to_string()
    };
    Ok(ApiResponse {
        status,
        body: body_val,
        text,
    })
}

pub fn request(path: &str, method: &str, _body: Option<Value>) -> Result<ApiResponse, String> {
    let route = path.split('?').next().unwrap_or(path);
    match (method, route) {
        ("GET", "/api/neural/banter/history") => Ok(banter_history(&root())),
        ("POST", "/api/neural/banter/generate") => {
            let count = path.split_once('?').and_then(|(_, query)| {
                query.split('&').find_map(|part| {
                    let (key, value) = part.split_once('=')?;
                    (key == "count").then(|| value.parse::<usize>().ok()).flatten()
                })
            }).unwrap_or(1);
            Ok(generate_banter(&root(), count))
        }
        ("GET", "/api/reid/history") => Ok(response(200, json!({"status":"success","history":latest_history()}))),
        ("GET", r) if r.starts_with("/api/v1/biometrics/") => Ok(biometrics(path)),
        ("GET", "/api/neural/warroom/history") => {
            let hist_path = root().join("Bridge").join("warroom_history.json");
            let data: Value = std::fs::read_to_string(&hist_path)
                .ok()
                .and_then(|t| serde_json::from_str(&t).ok())
                .unwrap_or_else(|| json!([]));
            Ok(response(200, data))
        }
        ("POST", "/api/neural/warroom/clear") => {
            let bridge_dir = root().join("Bridge");
            let _ = std::fs::create_dir_all(&bridge_dir);
            let hist_path = bridge_dir.join("warroom_history.json");
            let _ = std::fs::write(&hist_path, "[]");
            Ok(response(200, json!({"status": "success"})))
        }
        ("POST", "/api/reid/chat")
        | ("POST", "/api/neural/chat")
        | ("POST", "/api/neural/warroom/chat") => {
            if let Some(backend) = find_backend() {
                conversation_request(&backend, route, method, _body)
            } else {
                Ok(unavailable("Conversation backend resources are unavailable."))
            }
        }
        _ => Err(format!("native P5 route not implemented: {method} {path}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn conversation_output_handles_failures_and_recovery() {
        for output in [b"".as_slice(), b"not json", b"{}", b"{\"http_status\":200,\"body\":{}}"] {
            assert_eq!(conversation_output(output, b"private secret", true).status, 503);
        }
        let missing = conversation_output(b"", b"ModuleNotFoundError: secret", false);
        assert!(missing.text.contains("dependencies"));
        assert!(!missing.text.contains("secret"));
        let crashed = conversation_output(b"{}", b"private prompt", false);
        assert!(!crashed.text.contains("private prompt"));
        let unavailable_model = br#"{"http_status":503,"body":{"detail":"Install configured local model."}}"#;
        assert_eq!(conversation_output(unavailable_model, b"", true).status, 503);
        let recovered = br#"{"http_status":200,"body":{"response":"Ready"}}"#;
        assert_eq!(conversation_output(recovered, b"", true).body["response"], "Ready");
    }

    #[test]
    fn only_approved_operations_are_registered() {
        assert!(ALLOWED.iter().any(|(id, _)| *id == "backup"));
        assert!(!ALLOWED.iter().any(|(id, _)| *id == "rm"));
    }
    #[test]
    fn unavailable_response_redacts_provider_details() {
        let v = unavailable("provider unavailable");
        assert_eq!(v.status, 503);
        assert!(!v.text.contains("API_KEY"));
    }

    #[test]
    fn warroom_history_and_clear_work_with_synthetic_vault() {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time")
            .as_nanos();
        let root = std::env::temp_dir().join(format!("navis-warroom-test-{}-{nonce}", std::process::id()));
        std::fs::create_dir_all(root.join("Bridge")).expect("bridge dir");
        std::fs::create_dir_all(root.join("Journal")).expect("journal dir");
        let initial_history = json!([
            {"role": "user", "content": "Test entry"},
            {"role": "assistant", "content": "Understood."}
        ]);
        std::fs::write(root.join("Bridge").join("warroom_history.json"), initial_history.to_string()).expect("write");
        std::env::set_var("NAVIS_ROOT", &root);

        let res = request("/api/neural/warroom/history", "GET", None).expect("history route");
        assert_eq!(res.status, 200);
        assert_eq!(res.body.as_array().map(Vec::len), Some(2));

        let clear_res = request("/api/neural/warroom/clear", "POST", None).expect("clear route");
        assert_eq!(clear_res.status, 200);

        let empty_res = request("/api/neural/warroom/history", "GET", None).expect("history route after clear");
        assert_eq!(empty_res.status, 200);
        assert_eq!(empty_res.body.as_array().map(Vec::len), Some(0));

        let _ = std::fs::remove_dir_all(root);
        std::env::remove_var("NAVIS_ROOT");
    }

    #[test]
    fn conversation_routes_redact_secrets_when_provider_unavailable() {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time")
            .as_nanos();
        let root = std::env::temp_dir().join(format!("navis-conv-test-{}-{nonce}", std::process::id()));
        std::fs::create_dir_all(root.join("Bridge")).expect("bridge dir");
        std::fs::create_dir_all(root.join("Journal")).expect("journal dir");
        std::fs::write(root.join("Bridge").join("status.json"), r#"{"squad":[],"current_realm":"Unknown"}"#).expect("write");
        std::env::set_var("NAVIS_ROOT", &root);
        std::env::set_var("NAVIS_OLLAMA_URL", "http://127.0.0.1:54321");
        std::env::set_var("NAVIS_OLLAMA_TIMEOUT", "1");
        std::env::set_var("GEMINI_API_KEY", "super_secret_test_key_12345");

        let cases = [
            ("POST", "/api/reid/chat", json!({"message": "Hello Reid"})),
            ("POST", "/api/neural/chat", json!({"message": "Hello Bridge"})),
            ("POST", "/api/neural/warroom/chat", json!({"message": "Hello War Room"})),
        ];
        for (method, path, body) in cases {
            if path == "/api/neural/warroom/chat" {
                // War Room validates its active squad before calling a provider.
                let empty = request(path, method, Some(body.clone())).expect("empty squad validation");
                assert_eq!(empty.status, 400);
                std::fs::write(root.join("Bridge/status.json"), r#"{"squad":[{"name":"Fixture Companion"}],"current_realm":"Unknown"}"#).expect("valid squad fixture");
            }
            let result = request(path, method, Some(body)).expect("route should be handled");
            assert_eq!(result.status, 503, "{method} {path}");
            assert_eq!(result.body["code"], "native_dependency_unavailable");
            assert!(!result.text.contains("super_secret_test_key_12345"));
            assert!(!result.text.contains("GEMINI_API_KEY"));
        }

        let _ = std::fs::remove_dir_all(root);
        std::env::remove_var("NAVIS_ROOT");
        std::env::remove_var("NAVIS_OLLAMA_URL");
        std::env::remove_var("NAVIS_OLLAMA_TIMEOUT");
        std::env::remove_var("GEMINI_API_KEY");
    }

    #[test]
    fn banter_validation_requires_the_full_party_in_order() {
        let party = vec!["Aster".to_string(), "Rowan".to_string()];
        let valid = json!([
            {"speaker":"Aster","text":"The path is quiet."},
            {"speaker":"Rowan","text":"For now."}
        ]);
        let reversed = json!([
            {"speaker":"Rowan","text":"For now."},
            {"speaker":"Aster","text":"The path is quiet."}
        ]);
        let incomplete = json!([{"speaker":"Aster","text":"The path is quiet."}]);
        assert!(valid_chain(&valid, &party));
        assert!(!valid_chain(&reversed, &party));
        assert!(!valid_chain(&incomplete, &party));
    }

    #[test]
    fn configured_banter_section_stops_at_next_heading() {
        let content = "intro\n## 🗣️ Banter Protocol\nSpeak warmly.\n## Other\nIgnore this.";
        assert_eq!(
            section(content, "## 🗣️ Banter Protocol", "fallback"),
            "Speak warmly."
        );
    }

    #[test]
    fn banter_storage_is_idempotent_and_sorts_party_key() {
        let conn = rusqlite::Connection::open_in_memory().expect("memory database");
        let party = vec!["Rowan".to_string(), "Aster".to_string()];
        let chain = json!([
            {"speaker":"Rowan","text":"A quiet trail."},
            {"speaker":"Aster","text":"I agree."}
        ]);
        persist_banter(&conn, "Mosswood", &party, &chain).expect("first insert");
        persist_banter(&conn, "Mosswood", &party, &chain).expect("duplicate is harmless");
        let count: i64 = conn
            .query_row("SELECT COUNT(*) FROM banter_threads", [], |row| row.get(0))
            .expect("count");
        let stored_party: String = conn
            .query_row("SELECT participants FROM banter_threads", [], |row| {
                row.get(0)
            })
            .expect("party");
        assert_eq!(count, 1);
        assert_eq!(stored_party, "Aster,Rowan");
    }

    #[test]
    fn missing_banter_history_does_not_create_a_database() {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time")
            .as_nanos();
        let root = std::env::temp_dir().join(format!(
            "navis-banter-history-{}-{nonce}",
            std::process::id()
        ));
        std::fs::create_dir_all(root.join("Bridge")).expect("bridge directory");
        std::fs::create_dir_all(root.join("Journal")).expect("journal directory");
        std::fs::write(root.join("Bridge").join("status.json"), r#"{"squad":[]}"#)
            .expect("status file");

        let result = banter_history(&root);

        assert_eq!(result.status, 200);
        assert_eq!(result.body, json!([]));
        assert!(!root.join("Journal").join("Chronicle.db").exists());
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn existing_chronicle_without_banter_table_is_empty_history() {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time")
            .as_nanos();
        let root = std::env::temp_dir().join(format!(
            "navis-banter-history-no-table-{}-{nonce}",
            std::process::id()
        ));
        std::fs::create_dir_all(root.join("Bridge")).expect("bridge directory");
        std::fs::create_dir_all(root.join("Journal")).expect("journal directory");
        std::fs::write(
            root.join("Bridge").join("status.json"),
            r#"{"squad":[{"name":"Aster"},{"name":"Rowan"}]}"#,
        )
        .expect("status file");
        let conn = rusqlite::Connection::open(root.join("Journal").join("Chronicle.db"))
            .expect("Chronicle database");
        conn.execute("CREATE TABLE journal_entries (id INTEGER PRIMARY KEY)", [])
            .expect("journal table");
        drop(conn);

        let result = banter_history(&root);

        assert_eq!(result.status, 200);
        assert_eq!(result.body, json!([]));

        let conn = rusqlite::Connection::open(root.join("Journal").join("Chronicle.db"))
            .expect("Chronicle database");
        conn.execute("DROP TABLE journal_entries", [])
            .expect("remove journal table");
        conn.execute("CREATE TABLE banter_threads (id INTEGER PRIMARY KEY)", [])
            .expect("malformed banter table");
        drop(conn);

        let malformed_result = banter_history(&root);
        assert_eq!(malformed_result.status, 503);
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn banter_status_accepts_utf8_bom_and_empty_squad() {
        let root = std::env::temp_dir().join(format!("navis-banter-status-bom-{}", std::process::id()));
        std::fs::create_dir_all(root.join("Bridge")).expect("bridge directory");
        std::fs::write(root.join("Bridge/status.json"), b"\xef\xbb\xbf{\"squad\":[]}").expect("status file");
        let status = read_banter_status(&root).expect("BOM status is valid");
        assert_eq!(party_names(&status), Vec::<String>::new());
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn banter_status_reports_missing_unreadable_and_malformed_files() {
        let root = std::env::temp_dir().join(format!("navis-banter-status-errors-{}", std::process::id()));
        std::fs::create_dir_all(root.join("Bridge")).expect("bridge directory");
        assert!(read_banter_status(&root).unwrap_err().contains("missing"));
        std::fs::write(root.join("Bridge/status.json"), "not-json").expect("malformed status");
        assert!(read_banter_status(&root).unwrap_err().contains("malformed"));
        std::fs::remove_file(root.join("Bridge/status.json")).expect("remove status");
        std::fs::create_dir(root.join("Bridge/status.json")).expect("unreadable status path");
        assert!(read_banter_status(&root).unwrap_err().contains("could not be read"));
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn empty_or_duplicate_active_squad_is_distinct_from_unavailable_status() {
        let root = std::env::temp_dir().join(format!("navis-banter-empty-squad-{}", std::process::id()));
        std::fs::create_dir_all(root.join("Bridge")).expect("bridge directory");
        std::fs::write(root.join("Bridge/status.json"), r#"{"squad":[],"current_realm":"Mosswood"}"#).expect("status file");
        let result = generate_banter(&root, 1);
        assert_eq!(result.status, 422);
        assert!(result.body["detail"].as_str().unwrap().contains("two uniquely named"));
        std::fs::write(root.join("Bridge/status.json"), r#"{"squad":[{"name":"Aster"},{"name":" aStEr "}],"current_realm":"Mosswood"}"#).expect("duplicate status file");
        assert_eq!(generate_banter(&root, 1).status, 422);
        let _ = std::fs::remove_dir_all(root);
    }
}
