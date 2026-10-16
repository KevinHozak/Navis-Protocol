use serde_json::Value;

#[test]
fn native_and_python_contract_fixtures_match() {
    let raw = include_str!("fixtures/p3_parity.json");
    let fixture: Value = serde_json::from_str(raw).expect("valid parity fixture");
    for name in [
        "battle_state",
        "missions",
        "progression_xp",
        "achievements",
        "progression_talents",
        "sector_cache",
        "squad_deploy",
        "squad_bench",
        "squad_vanguard",
        "combat_target",
        "combat_log",
        "bio_adjust",
    ] {
        let entry = fixture.get(name).expect("fixture entry");
        assert_eq!(
            entry.get("python"),
            entry.get("native"),
            "parity mismatch: {name}"
        );
    }
}
