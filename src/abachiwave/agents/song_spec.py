import re
from collections.abc import Callable, Mapping
from typing import Any

from abachiwave.schemas.song_specs import ClarificationQuestion, SongSpecData

QUESTION_BANK: dict[str, str] = {
    "theme": "What is the song about, and what perspective should it use?",
    "genre": "Which genre or reference style should guide the song?",
    "language": "Which language should the lyrics use?",
    "tempo_bpm": "What BPM should the song target?",
    "key": "Which musical key should the draft use?",
    "time_signature": "What time signature should the song use?",
    "target_duration_seconds": "What target duration should the song have?",
    "mood_curve": "How should the emotion change between verse and chorus?",
    "song_structure": "Which sections should the song include?",
}

FIELD_ORDER = tuple(QUESTION_BANK)
DEFAULT_STRUCTURE = ["intro", "verse", "pre_chorus", "chorus", "bridge", "final_chorus", "outro"]


def build_clarification_questions(
    idea: str,
    answers: Mapping[str, str] | None = None,
) -> list[ClarificationQuestion]:
    song_spec = build_song_spec_from_input(idea, answers or {})
    return [
        ClarificationQuestion(
            id=f"q_{field_name}",
            field=field_name,
            prompt=QUESTION_BANK[field_name],
            required=True,
        )
        for field_name in FIELD_ORDER
        if field_name in song_spec.missing_required_fields()
    ]


def build_song_spec_from_input(
    idea: str,
    answers: Mapping[str, str] | None = None,
) -> SongSpecData:
    normalized_answers = {key.strip(): value.strip() for key, value in (answers or {}).items()}
    text = " ".join([idea, *normalized_answers.values()])
    return SongSpecData(
        theme=_answer_or_parse("theme", normalized_answers, lambda: _parse_theme(idea)),
        genre=_answer_or_parse("genre", normalized_answers, lambda: _parse_genre(text)),
        language=_answer_or_parse("language", normalized_answers, lambda: _parse_language(text)),
        tempo_bpm=_answer_or_parse("tempo_bpm", normalized_answers, lambda: _parse_tempo(text)),
        key=_answer_or_parse("key", normalized_answers, lambda: _parse_key(text)),
        time_signature=_answer_or_parse(
            "time_signature",
            normalized_answers,
            lambda: _parse_time_signature(text),
        ),
        target_duration_seconds=_answer_or_parse(
            "target_duration_seconds",
            normalized_answers,
            lambda: _parse_duration(text),
        ),
        mood_curve=_answer_or_parse(
            "mood_curve",
            normalized_answers,
            lambda: _parse_mood_curve(text),
        ),
        song_structure=_answer_or_parse(
            "song_structure",
            normalized_answers,
            lambda: _parse_song_structure(text),
        ),
    )


def _answer_or_parse(
    field_name: str,
    answers: Mapping[str, str],
    parser: Callable[[], Any],
) -> Any:
    answer = answers.get(field_name) or answers.get(f"q_{field_name}")
    if answer:
        return _coerce_answer(field_name, answer)
    return parser()


def _coerce_answer(field_name: str, answer: str) -> Any:
    match field_name:
        case "genre":
            return _split_list(answer)
        case "tempo_bpm":
            tempo = _parse_tempo(answer)
            return tempo
        case "target_duration_seconds":
            duration = _parse_duration(answer)
            if duration is not None:
                return duration
            if answer.isdigit():
                return int(answer)
            return None
        case "mood_curve":
            return _parse_mood_curve(answer) or {"overall": answer}
        case "song_structure":
            return _parse_song_structure(answer) or _split_list(answer)
        case _:
            return answer.strip() or None


def _parse_theme(idea: str) -> str | None:
    normalized = idea.strip()
    if not normalized:
        return None
    about_match = re.search(r"(?:about|关于)(.+?)(?:的|\.|。|,|，|$)", normalized, re.IGNORECASE)
    if about_match:
        return about_match.group(1).strip(" “\"'，,。.")
    return normalized[:300]


def _parse_genre(text: str) -> list[str] | None:
    candidates: list[str] = []
    genre_patterns = {
        "indie rock": r"indie\s*rock|独立摇滚",
        "j-pop influenced": r"j[-\s]?pop|日系",
        "pop": r"\bpop\b|流行",
        "rock": r"\brock\b|摇滚",
        "folk": r"\bfolk\b|民谣",
        "electronic": r"electronic|电子",
    }
    for genre, pattern in genre_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            candidates.append(genre)
    return candidates or None


def _parse_language(text: str) -> str | None:
    if re.search(r"中文|普通话|mandarin|chinese", text, re.IGNORECASE):
        return "zh-CN"
    if re.search(r"英文|english", text, re.IGNORECASE):
        return "en"
    if re.search(r"日文|japanese", text, re.IGNORECASE):
        return "ja"
    return None


def _parse_tempo(text: str) -> int | None:
    match = re.search(r"(\d{2,3})\s*(?:bpm|BPM)", text)
    if not match:
        return None
    tempo = int(match.group(1))
    if 40 <= tempo <= 240:
        return tempo
    return None


def _parse_key(text: str) -> str | None:
    match = re.search(r"\b([A-G](?:#|b)?\s*(?:major|minor|maj|min))\b", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    chinese_match = re.search(r"([A-G](?:#|b)?)\s*(?:大调|小调)", text)
    if chinese_match:
        suffix = "major" if "大调" in chinese_match.group(0) else "minor"
        return f"{chinese_match.group(1)} {suffix}"
    return None


def _parse_time_signature(text: str) -> str | None:
    match = re.search(r"\b(\d+/\d+)\b", text)
    if match:
        return match.group(1)
    return None


def _parse_duration(text: str) -> int | None:
    colon_match = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
    if colon_match:
        return int(colon_match.group(1)) * 60 + int(colon_match.group(2))
    minute_half_match = re.search(r"(\d+)\s*分(?:半|钟半)", text)
    if minute_half_match:
        return int(minute_half_match.group(1)) * 60 + 30
    minute_match = re.search(r"(\d+)\s*(?:minutes?|分钟|分)", text, re.IGNORECASE)
    if minute_match:
        return int(minute_match.group(1)) * 60
    second_match = re.search(r"(\d{2,3})\s*(?:seconds?|秒)", text, re.IGNORECASE)
    if second_match:
        return int(second_match.group(1))
    return None


def _parse_mood_curve(text: str) -> dict[str, str] | None:
    mood_curve: dict[str, str] = {}
    if re.search(r"(主歌|verse).*?(孤独|克制|restrained|lonely)", text, re.IGNORECASE):
        mood_curve["verse"] = "restrained and lonely"
    if re.search(r"(副歌|chorus).*?(向上|释怀|上扬|hopeful|lifting)", text, re.IGNORECASE):
        mood_curve["chorus"] = "lifting and hopeful"
    if "情绪" in text and not mood_curve:
        mood_curve["overall"] = text[:160]
    return mood_curve or None


def _parse_song_structure(text: str) -> list[str] | None:
    section_keywords = {
        "intro": r"intro|前奏",
        "verse": r"verse|主歌",
        "pre_chorus": r"pre[-\s]?chorus|预副歌|导歌",
        "chorus": r"chorus|副歌",
        "bridge": r"bridge|桥段",
        "outro": r"outro|尾奏",
    }
    sections = [
        section
        for section, pattern in section_keywords.items()
        if re.search(pattern, text, re.IGNORECASE)
    ]
    if len(sections) >= 3:
        return sections
    if re.search(r"标准|完整|standard", text, re.IGNORECASE):
        return DEFAULT_STRUCTURE
    return None


def _split_list(answer: str) -> list[str] | None:
    items = [item.strip() for item in re.split(r"[,，/、\n]+", answer) if item.strip()]
    return items or None
