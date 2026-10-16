use serde::Serialize;
use serde_json::{json, Value};
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::time::Duration;

#[derive(Debug, Serialize)]
pub struct JournalPolishResponse {
    status: u16,
    body: Value,
    text: String,
}

fn response(status: u16, body: Value) -> JournalPolishResponse {
    let text = body.to_string();
    JournalPolishResponse { status, body, text }
}

fn checklist_states(text: &str) -> Vec<String> {
    text.lines()
        .filter_map(|line| {
            let line = line.trim_start_matches(&[' ', '\t'][..]);
            let (bullet, rest) = line.split_at_checked(1)?;
            if !matches!(bullet, "-" | "*" | "+") {
                return None;
            }
            let rest = rest.trim_start_matches(&[' ', '\t'][..]);
            let marker = rest.get(..3)?;
            let bytes = marker.as_bytes();
            if bytes[0] == b'[' && bytes[2] == b']' && matches!(bytes[1], b' ' | b'x' | b'X' | b'/')
            {
                Some(marker.to_string())
            } else {
                None
            }
        })
        .collect()
}

#[tauri::command]
pub async fn polish_journal_entry(entry: String, section: Option<String>) -> JournalPolishResponse {
    tauri::async_runtime::spawn_blocking(move || {
        polish_journal_entry_blocking(entry, section.unwrap_or_else(|| "sanctum".to_string()))
    })
    .await
    .unwrap_or_else(|error| {
        response(
            503,
            json!({ "detail": format!("Local Ollama request failed: {error}") }),
        )
    })
}

fn polish_journal_entry_blocking(entry: String, section: String) -> JournalPolishResponse {
    let entry = entry.trim();
    if entry.is_empty() {
        return response(422, json!({ "detail": "Journal entry cannot be empty." }));
    }
    if entry.chars().count() > 10_000 {
        return response(
            422,
            json!({ "detail": "Journal entry must be 10,000 characters or fewer." }),
        );
    }

    let section_heading = match section.as_str() {
        "domestic" => "🏠 The Domestic Breach",
        "front" => "⚔️ The High-Velocity Front",
        "gauntlet" => "⚖️ The Bureaucratic Gauntlet",
        "outland" => "🥾 The Kinetic Outland",
        _ => "🏰 The Sanctum",
    };
    let prompt = format!(
        "You copy-edit one personal journal entry. This is an editing task, never a conversation. Return only the edited entry, preserving its existing line and Markdown structure. Preserve meaning, facts, and checklist states. Correct obvious spelling mistakes and accidentally joined words using context. Always capitalize the first word, do not end with a period, and prefix one relevant emoji chosen for BOTH the entry and its journal section. For checklist entries, keep the list and checkbox marker first and put the emoji immediately after the marker. Do not add explanations or facts.\n\nExamples:\nSection: The Sanctum\nDraft: okay this is another test of the msystem\nEdited: 🧪 Okay, this is another test of the system\n\nSection: The Domestic Breach\nDraft: i fixed the broken shelf\nEdited: 🏠 I fixed the broken shelf\n\nSection: {section_heading}\nDraft: {entry}\nEdited:"
    );
    let payload = json!({
        "model": "Kimiko-20B:latest",
        "prompt": prompt,
        "stream": false,
        "keep_alive": "1h",
        "options": { "temperature": 0.2, "num_predict": 1024 },
    });

    let payload = match serde_json::to_vec(&payload) {
        Ok(payload) => payload,
        Err(error) => {
            return response(
                503,
                json!({ "detail": format!("Could not encode local Ollama request: {error}") }),
            );
        }
    };
    let address = SocketAddr::from(([127, 0, 0, 1], 11434));
    let mut stream = match TcpStream::connect_timeout(&address, Duration::from_secs(5)) {
        Ok(stream) => stream,
        Err(error) => {
            return response(
                503,
                json!({ "detail": format!("Could not connect to local Ollama at 127.0.0.1:11434: {error}") }),
            );
        }
    };
    // A cold 20B model can take over a minute to load and draft longer entries.
    // Keep connection and request writes short while allowing generation time.
    if let Err(error) = stream
        .set_read_timeout(Some(Duration::from_secs(300)))
        .and_then(|_| stream.set_write_timeout(Some(Duration::from_secs(30))))
    {
        return response(
            503,
            json!({ "detail": format!("Could not configure the local Ollama connection: {error}") }),
        );
    }
    let request = format!(
        "POST /api/generate HTTP/1.1\r\nHost: 127.0.0.1:11434\r\nContent-Type: application/json\r\nAccept: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        payload.len()
    );
    if let Err(error) = stream
        .write_all(request.as_bytes())
        .and_then(|_| stream.write_all(&payload))
        .and_then(|_| stream.flush())
    {
        return response(
            503,
            json!({ "detail": format!("Could not send the local Ollama request: {error}") }),
        );
    }
    let mut raw_response = Vec::new();
    if let Err(error) = stream.read_to_end(&mut raw_response) {
        return response(
            503,
            json!({ "detail": format!("Could not read the local Ollama response: {error}") }),
        );
    }
    let Some(header_end) = raw_response
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
    else {
        return response(
            503,
            json!({ "detail": "Local Ollama returned an invalid HTTP response." }),
        );
    };
    let headers = String::from_utf8_lossy(&raw_response[..header_end]);
    let status = headers
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(503);
    let response_body = &raw_response[header_end + 4..];
    let decoded_body = if headers.lines().any(|line| {
        line.to_ascii_lowercase().starts_with("transfer-encoding:")
            && line.to_ascii_lowercase().contains("chunked")
    }) {
        match decode_chunked(response_body) {
            Some(body) => body,
            None => {
                return response(
                    503,
                    json!({ "detail": "Local Ollama returned malformed chunked data." }),
                )
            }
        }
    } else {
        response_body.to_vec()
    };
    if !(200..300).contains(&status) {
        let detail = String::from_utf8_lossy(&decoded_body);
        return response(
            503,
            json!({ "detail": format!("Local Ollama could not polish this draft: {}", detail.chars().take(400).collect::<String>()) }),
        );
    }

    let result: Value = match serde_json::from_slice(&decoded_body) {
        Ok(result) => result,
        Err(error) => {
            return response(
                503,
                json!({ "detail": format!("Local Ollama returned an invalid response: {error}") }),
            );
        }
    };
    let suggestion = result["response"].as_str().unwrap_or_default().trim();

    if suggestion.is_empty() {
        return response(
            503,
            json!({ "detail": "Local Ollama returned an empty suggestion. Your draft has not been changed." }),
        );
    }
    if [
        "i'm sorry",
        "i am sorry",
        "i don't understand your response",
        "please rephrase your message",
    ]
    .iter()
    .any(|phrase| suggestion.to_ascii_lowercase().contains(phrase))
    {
        return response(
            503,
            json!({ "detail": "Local Ollama returned a conversational reply instead of a polished draft. Your draft has not been changed." }),
        );
    }
    let suggestion = format_polished_entry(suggestion, entry, &section);
    if checklist_states(entry) != checklist_states(&suggestion) {
        return response(
            503,
            json!({ "detail": "Local Ollama changed checklist formatting. Your draft has not been changed." }),
        );
    }

    response(200, json!({ "suggestion": suggestion }))
}

fn format_polished_entry(suggestion: &str, entry: &str, section: &str) -> String {
    let mut suggestion = suggestion.trim().to_string();
    for prefix in ["Edited:", "Edited entry:", "Polished entry:"] {
        if suggestion
            .get(..prefix.len())
            .is_some_and(|start| start.eq_ignore_ascii_case(prefix))
        {
            suggestion = suggestion[prefix.len()..].trim().to_string();
            break;
        }
    }
    while suggestion.ends_with('.') {
        suggestion.pop();
    }
    suggestion = suggestion.trim_end().to_string();

    if let Some((index, character)) = suggestion.char_indices().find(|(_, ch)| ch.is_alphabetic()) {
        let end = index + character.len_utf8();
        suggestion.replace_range(index..end, &character.to_uppercase().to_string());
    }
    let (mut emoji, remainder) = suggestion
        .chars()
        .next()
        .filter(|ch| matches!(*ch as u32, 0x1F000..=0x1FAFF | 0x2600..=0x27BF))
        .map(|ch| {
            let mut emoji_end = ch.len_utf8();
            if suggestion[emoji_end..].starts_with('\u{FE0F}') {
                emoji_end += '\u{FE0F}'.len_utf8();
            }
            let rest = suggestion[emoji_end..].trim_start();
            (suggestion[..emoji_end].to_string(), rest.to_string())
        })
        .unwrap_or_else(|| {
            (
                polish_fallback_emoji(entry, section).to_string(),
                suggestion,
            )
        });

    let checklist_end = checklist_marker_end(&remainder);
    if let Some(end) = checklist_end {
        let body = remainder[end..].trim_start();
        if let Some(body_emoji_end) = leading_emoji_end(body) {
            emoji = body[..body_emoji_end].to_string();
            suggestion = format!(
                "{}{emoji} {}",
                &remainder[..end],
                body[body_emoji_end..].trim_start()
            );
        } else {
            suggestion = format!("{}{emoji} {body}", &remainder[..end]);
        }
    } else {
        suggestion = format!("{emoji} {remainder}");
    }
    suggestion
}

fn leading_emoji_end(text: &str) -> Option<usize> {
    let character = text.chars().next()?;
    if !matches!(character as u32, 0x1F000..=0x1FAFF | 0x2600..=0x27BF) {
        return None;
    }
    let mut end = character.len_utf8();
    if text[end..].starts_with('\u{FE0F}') {
        end += '\u{FE0F}'.len_utf8();
    }
    Some(end)
}

fn checklist_marker_end(text: &str) -> Option<usize> {
    let trimmed = text.trim_start();
    let indent = text.len() - trimmed.len();
    let mut chars = trimmed.char_indices();
    let (bullet_end, bullet) = chars.next()?;
    if !matches!(bullet, '-' | '*' | '+') {
        return None;
    }
    let marker_start = trimmed[bullet_end + bullet.len_utf8()..].trim_start();
    if !marker_start.starts_with('[') {
        return None;
    }
    let marker = marker_start.get(..3)?;
    let bytes = marker.as_bytes();
    if bytes[0] != b'[' || bytes[2] != b']' || !matches!(bytes[1], b' ' | b'x' | b'X' | b'/') {
        return None;
    }
    let marker_offset = trimmed.len() - marker_start.len();
    let after_marker = marker_offset + 3;
    let rest = trimmed.get(after_marker..)?;
    let whitespace = rest.len() - rest.trim_start().len();
    Some(indent + after_marker + whitespace)
}

fn polish_fallback_emoji(entry: &str, section: &str) -> &'static str {
    let lowered = entry.to_lowercase();
    let words: Vec<&str> = lowered
        .split(|character: char| !character.is_alphanumeric())
        .collect();
    if ["test", "testing", "experiment", "diagnostic"]
        .iter()
        .any(|word| words.contains(word))
    {
        "🧪"
    } else if ["read", "reading", "book", "library"]
        .iter()
        .any(|word| words.contains(word))
    {
        "📚"
    } else if ["watch", "watched", "movie", "film", "episode"]
        .iter()
        .any(|word| words.contains(word))
    {
        "🎬"
    } else if ["workout", "exercise", "training", "lift", "lifting"]
        .iter()
        .any(|word| words.contains(word))
    {
        "💪"
    } else {
        match section {
            "domestic" => "🏠",
            "front" => "⚔️",
            "gauntlet" => "⚖️",
            "outland" => "🥾",
            _ => "🏰",
        }
    }
}

fn decode_chunked(mut body: &[u8]) -> Option<Vec<u8>> {
    let mut decoded = Vec::new();
    loop {
        let line_end = body.windows(2).position(|window| window == b"\r\n")?;
        let size_text = std::str::from_utf8(&body[..line_end])
            .ok()?
            .split(';')
            .next()?
            .trim();
        let chunk_size = usize::from_str_radix(size_text, 16).ok()?;
        body = &body[line_end + 2..];
        if chunk_size == 0 {
            return Some(decoded);
        }
        if body.len() < chunk_size + 2 || &body[chunk_size..chunk_size + 2] != b"\r\n" {
            return None;
        }
        decoded.extend_from_slice(&body[..chunk_size]);
        body = &body[chunk_size + 2..];
    }
}

pub(crate) fn decode_chunked_for_p5(body: &[u8]) -> Option<Vec<u8>> {
    decode_chunked(body)
}
