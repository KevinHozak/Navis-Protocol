"""Shared web/native journal polishing and unchanged output validation."""
import re
from fastapi import HTTPException

JOURNAL_SECTION_HEADINGS = {
    "sanctum": "## 🏰 The Sanctum",
    "domestic": "## 🏠 The Domestic Breach",
    "front": "## ⚔️ The High-Velocity Front",
    "gauntlet": "## ⚖️ The Bureaucratic Gauntlet",
    "outland": "## 🥾 The Kinetic Outland",
}

JOURNAL_SECTION_EMOJIS = {
    "sanctum": "🏰",
    "domestic": "🏠",
    "front": "⚔️",
    "gauntlet": "⚖️",
    "outland": "🥾",
}


def polish_output_emoji(entry: str, section: str) -> str:
    lowered = entry.casefold()
    if re.search(r"\b(test|testing|experiment|diagnostic)\b", lowered):
        return "🧪"
    if re.search(r"\b(read|reading|book|library)\b", lowered):
        return "📚"
    if re.search(r"\b(watch|watched|movie|film|episode)\b", lowered):
        return "🎬"
    if re.search(r"\b(workout|exercise|training|lift|lifting)\b", lowered):
        return "💪"
    return JOURNAL_SECTION_EMOJIS.get(section, JOURNAL_SECTION_EMOJIS["sanctum"])


def format_polished_journal_entry(suggestion: str, entry: str, section: str) -> str:
    suggestion = suggestion.strip()
    suggestion = re.sub(r"(?i)^(?:edited|polished)(?: journal)? entry:\s*", "", suggestion)
    suggestion = re.sub(r"\.+\s*$", "", suggestion).rstrip()

    first_letter = re.search(r"[^\W\d_]", suggestion, flags=re.UNICODE)
    if first_letter:
        start, end = first_letter.span()
        suggestion = suggestion[:start] + suggestion[start:end].upper() + suggestion[end:]

    emoji_pattern = r"^[\U0001F000-\U0001FAFF\u2600-\u27BF]\ufe0f?\s+"
    leading_emoji = re.match(emoji_pattern, suggestion)
    if leading_emoji:
        emoji = leading_emoji.group(0).strip()
        content = suggestion[leading_emoji.end() :]
    else:
        emoji = polish_output_emoji(entry, section)
        content = suggestion

    checklist_prefix = re.match(r"^([ \t]*[-*+][ \t]*\[[ xX/]\][ \t]*)", content)
    if checklist_prefix:
        body = content[checklist_prefix.end() :].lstrip()
        body_emoji = re.match(emoji_pattern, body)
        if body_emoji:
            emoji = body_emoji.group(0).strip()
            body = body[body_emoji.end() :]
        return f"{content[:checklist_prefix.end()]}{emoji} {body}"

    return f"{emoji} {content}"


from services.journal_entry import checked_journal_list_item as checked_journal_list_item



async def polish(entry: str, section: str = "sanctum"):
    entry = entry.strip()
    if not entry:
        raise HTTPException(status_code=422, detail="Journal entry cannot be empty.")
    if len(entry) > 10000:
        raise HTTPException(
            status_code=422,
            detail="Journal entry must be 10,000 characters or fewer.",
        )

    section = section if section in JOURNAL_SECTION_HEADINGS else "sanctum"
    section_heading = JOURNAL_SECTION_HEADINGS[section].removeprefix("## ")
    prompt = (
        "You copy-edit one personal journal entry. This is an editing task, never a "
        "conversation. Return only the edited entry, preserving its existing line and "
        "Markdown structure. Preserve meaning, facts, and checklist states. Correct "
        "obvious spelling mistakes and accidentally "
        "joined words using context. Always capitalize the first word, do not end with "
        "a period, and prefix one relevant emoji chosen for BOTH the entry and its "
        "journal section. For checklist entries, put the emoji immediately after the "
        "existing list and checkbox markers. Do not add explanations or facts.\n\n"
        "Examples:\n"
        "Section: The Sanctum\n"
        "Draft: okay this is another test of the msystem\n"
        "Edited: 🧪 Okay, this is another test of the system\n\n"
        "Section: The Domestic Breach\n"
        "Draft: i fixed the broken shelf\n"
        "Edited: 🏠 I fixed the broken shelf\n\n"
        f"Section: {section_heading}\n"
        f"Draft: {entry}\n"
        "Edited:"
    )
    from services.ai_provider import get_provider, ProviderError
    try:
        text = await get_provider().generate(prompt, feature="polish")
        result = {"response": text}
    except ProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    suggestion = result.get("response", "")
    suggestion = suggestion.strip() if isinstance(suggestion, str) else ""
    if not suggestion:
        raise HTTPException(
            status_code=503,
            detail=(
                "Configured provider returned an empty suggestion. "
                "Your draft has not been changed."
            ),
        )
    if re.search(
        r"(?i)\b(?:i(?:'m| am) sorry|i don['’]t understand your response|please rephrase your message)\b",
        suggestion,
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                "Configured provider returned a conversational reply instead of a polished "
                "draft. Your draft has not been changed."
            ),
        )
    suggestion = format_polished_journal_entry(suggestion, entry, section)
    checklist_pattern = r"(?m)^[ \t]*[-*+][ \t]*\[[ xX/]\]"
    original_checklists = re.findall(checklist_pattern, entry)
    suggested_checklists = re.findall(checklist_pattern, suggestion)
    if original_checklists != suggested_checklists:
        raise HTTPException(
            status_code=503,
            detail=(
                "Configured provider changed checklist formatting. "
                "Your draft has not been changed."
            ),
        )
    return {"suggestion": suggestion}


