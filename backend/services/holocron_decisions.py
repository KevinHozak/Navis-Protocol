"""Bounded, deterministic decision prompts from journal checkbox observations."""
import re
from collections import Counter

from services.holocron_evidence import source_path, journal_source


def decision_review(root, sources):
    observations = []
    for source in sources:
        if source.get("status") != "available" or not source.get("date"):
            continue
        day = source["date"]
        for relative in (f"Journal/{day[:4]}/{day[5:7]}/{day}.md", f"Journal/{day}.md"):
            path = source_path(root, relative)
            if not path or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8-sig")
                if journal_source(root, day).get("fingerprint") != source.get("fingerprint"):
                    break
                items = []
                for line in text.splitlines():
                    line = re.sub(r"<!--.*?-->", "", line).rstrip()
                    match = re.fullmatch(r"\s*- \[([ xX])\] (.{1,240})", line)
                    if match:
                        items.append((match[2], match[1].lower() == "x"))
                labels = Counter(text for text, _ in items)
                items = [(text, checked) for text, checked in items if labels[text] == 1]
                observations.append((day, source["id"], items))
            except (OSError, UnicodeError):
                pass
            break
    changed = "Unknown: two readable days with matching checklist items are needed."
    unresolved = "Unknown: no readable checklist evidence."
    adjustment = "Review the missing evidence before choosing an adjustment."
    refs = []
    if observations:
        first, last = observations[0], observations[-1]
        refs = list(dict.fromkeys([first[1], last[1]]))
        initial = dict(first[2])
        transitions = [(text, checked) for text, checked in last[2] if text in initial and checked != initial[text]]
        if first[0] != last[0] and any(text in initial for text, _ in last[2]):
            changed = f"No matching checkbox changed state between {first[0]} and {last[0]}; intervening activity may differ."
            if transitions:
                text, checked = transitions[0]
                changed = f'“{text}” changed from {"unchecked" if checked else "checked"} ({first[0]}) to {"checked" if checked else "unchecked"} ({last[0]}). This records checkbox state, not an independently verified outcome.'
        pending = next((text for text, checked in last[2] if not checked), None)
        if pending:
            unresolved = f'“{pending}” is unchecked on {last[0]}. Need, urgency, cause and subsequent outcome are unknown.'
            adjustment = f'Review whether “{pending}” still needs action; explicitly retain, defer or remove it.'
        else:
            unresolved = f"No unchecked item was observed on {last[0]}; unrecorded blockers and outcomes remain unknown."
            adjustment = "Check whether the journal omitted any unresolved matter before choosing the next priority."
    return {"kind": "deterministic_review_prompt", "changed": changed, "unresolved": unresolved,
            "adjustment": adjustment, "suggestion_source": "rule_based", "source_ids": refs,
            "limits": "Checklist states and XP do not establish meaningful outcomes, causes or sustainable workload. Suggested adjustments are proposals, not commitments."}
