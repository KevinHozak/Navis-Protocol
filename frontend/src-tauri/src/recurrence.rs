use chrono::{Datelike, Days, Local, Months, NaiveDate, Timelike};
use serde_json::{json, Value};

pub fn journal_day<T: chrono::TimeZone>(now: chrono::DateTime<T>) -> String {
    let day = now.date_naive();
    let day = if now.hour() < 3 {
        day.pred_opt().unwrap()
    } else {
        day
    };
    day.to_string()
}

fn date(value: &str) -> Result<NaiveDate, String> {
    let day = NaiveDate::parse_from_str(value, "%Y-%m-%d").map_err(|_| "Expected YYYY-MM-DD")?;
    if day.to_string() != value {
        return Err("Expected YYYY-MM-DD".into());
    }
    Ok(day)
}

pub fn next_due(frequency: &str, last_done: &str) -> Result<String, String> {
    let day = date(last_done)?;
    let frequency = frequency.trim().to_lowercase();
    let result = match frequency.as_str() {
        "daily" => day.checked_add_days(Days::new(1)),
        "weekly" => day.checked_add_days(Days::new(7)),
        "bi-weekly" | "every 2 weeks" => day.checked_add_days(Days::new(14)),
        "every 3 weeks" => day.checked_add_days(Days::new(21)),
        "monthly" => day.checked_add_months(Months::new(1)),
        "bimonthly" | "every 2 months" => day.checked_add_months(Months::new(2)),
        "quarterly" => day.checked_add_months(Months::new(3)),
        "seasonal" => day.checked_add_months(Months::new(6)),
        _ => return Err("Unsupported recurrence frequency".into()),
    }
    .ok_or("Recurrence date out of range")?;
    if result.year() > 9999 {
        return Err("Recurrence date out of range".into());
    }
    Ok(result.to_string())
}

pub fn initialize(task: &mut Value) -> Result<(), String> {
    for field in ["frequency", "next_due"] {
        if let Some(value) = task.get(field).filter(|v| !v.is_null()) {
            value
                .as_str()
                .ok_or_else(|| format!("{field} must be a string"))?;
        }
    }
    let due = task
        .get("next_due")
        .and_then(Value::as_str)
        .map(str::to_owned)
        .unwrap_or_else(|| journal_day(Local::now()));
    let frequency = task
        .get("frequency")
        .and_then(Value::as_str)
        .unwrap_or("daily");
    next_due(frequency, &due)?;
    task["frequency"] = json!(frequency);
    task["last_done"] = Value::Null;
    task["next_due"] = json!(due);
    Ok(())
}

pub fn update(task: &Value, updates: &mut Value) -> Result<(), String> {
    if let Some(value) = updates.get("frequency").filter(|v| !v.is_null()) {
        value.as_str().ok_or("frequency must be a string")?;
    }
    let frequency = updates
        .get("frequency")
        .filter(|v| !v.is_null())
        .or_else(|| task.get("frequency"))
        .and_then(Value::as_str)
        .unwrap_or("daily");
    let completed = updates.get("last_done").filter(|v| !v.is_null());
    let previous = task.get("last_done").and_then(Value::as_str);
    let anchor = completed
        .and_then(Value::as_str)
        .or(previous)
        .map(str::to_owned)
        .unwrap_or_else(|| journal_day(Local::now()));
    let due = next_due(frequency, &anchor)?;
    if completed.is_some() {
        completed
            .unwrap()
            .as_str()
            .ok_or("last_done must be a date string")?;
        updates["next_due"] = json!(due);
    } else if let Some(explicit) = updates.get("next_due").filter(|v| !v.is_null()) {
        date(explicit.as_str().ok_or("next_due must be a date string")?)?;
    } else if updates.get("frequency").filter(|v| !v.is_null()).is_some() && previous.is_some() {
        updates["next_due"] = json!(due);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn recurrence_shared_vectors() {
        let fixture: Value =
            serde_json::from_str(include_str!("../../../tests/recurrence-contract.json")).unwrap();
        for row in fixture["intervals"].as_array().unwrap() {
            assert_eq!(
                next_due(
                    row["frequency"].as_str().unwrap(),
                    row["last_done"].as_str().unwrap()
                )
                .unwrap(),
                row["next_due"].as_str().unwrap()
            );
            let mut task = json!({"frequency":row["frequency"], "next_due":row["last_done"], "last_done":"2099-01-01"});
            initialize(&mut task).unwrap();
            assert!(task["last_done"].is_null());
            for _ in 0..2 {
                let mut updates = json!({"last_done":row["last_done"], "next_due":"2099-01-01"});
                update(&task, &mut updates).unwrap();
                assert_eq!(updates["next_due"], row["next_due"]);
                task["last_done"] = updates["last_done"].clone();
                task["next_due"] = updates["next_due"].clone();
            }
        }
        for row in fixture["instants"].as_array().unwrap() {
            let now = chrono::DateTime::parse_from_rfc3339(row["local"].as_str().unwrap()).unwrap();
            assert_eq!(journal_day(now), row["day"].as_str().unwrap());
        }
        assert!(next_due("unknown", "2026-01-01").is_err());
        assert!(next_due("daily", "2026-02-30").is_err());
        assert!(initialize(&mut json!({"frequency": 7})).is_err());
        assert!(initialize(&mut json!({"frequency":"monthly", "next_due": 7})).is_err());
    }
}
