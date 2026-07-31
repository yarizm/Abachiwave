import re
from difflib import SequenceMatcher
from uuid import UUID

from abachiwave.models.composition import LyricsVersion
from abachiwave.schemas.composition import LyricLine, LyricSection
from abachiwave.schemas.lyrics import (
    LyricDiffSegment,
    LyricRewriteChange,
    LyricsRewriteAction,
    LyricsRewritePreview,
    LyricsRewriteRequest,
    LyricsRewriteScope,
)

_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_TOKEN_PATTERN = re.compile(r"\s+|[A-Za-z]+(?:'[A-Za-z]+)?|[^\sA-Za-z]")
_ENGLISH_FILLERS = re.compile(
    r"\b(?:really|very|just|actually|basically|somehow|maybe|kind of|sort of)\b",
    re.IGNORECASE,
)
_CHINESE_FILLERS = ("真的", "其实", "仿佛", "好像", "慢慢地", "有一点")


class LyricsRewriteTargetError(ValueError):
    pass


def build_lyrics_rewrite_preview(
    version: LyricsVersion,
    payload: LyricsRewriteRequest,
) -> LyricsRewritePreview:
    sections = payload.sections or [
        LyricSection.model_validate(section) for section in version.sections
    ]
    targets = _target_line_ids(sections, payload)
    detected = _detected_banned_phrases(sections, targets, payload.banned_phrases)
    changes: list[LyricRewriteChange] = []
    candidate_sections: list[LyricSection] = []
    for section in sections:
        candidate_lines: list[LyricLine] = []
        for line in section.lines:
            if line.line_id not in targets:
                candidate_lines.append(line)
                continue
            rewritten = _rewrite_line(line, payload)
            candidate_lines.append(rewritten)
            if rewritten.text != line.text or rewritten.rhyme_label != line.rhyme_label:
                changes.append(
                    LyricRewriteChange(
                        section_id=section.section_id,
                        line_id=line.line_id,
                        before=line,
                        after=rewritten,
                        diff=_line_diff(line.text, rewritten.text),
                    )
                )
        candidate_sections.append(
            LyricSection(
                section_id=section.section_id,
                label=section.label,
                text="\n".join(line.text for line in candidate_lines),
                lines=candidate_lines,
            )
        )
    warnings: list[str] = []
    if detected:
        warnings.append("Avoided expressions were detected and removed from rewrite candidates.")
    unused_terms = [
        term
        for term in payload.preferred_terms
        if not any(term.casefold() in change.after.text.casefold() for change in changes)
    ]
    if unused_terms:
        warnings.append(f"Preferred vocabulary not used: {', '.join(unused_terms)}")
    if not changes:
        warnings.append("The deterministic rewrite did not change the selected lines.")
    return LyricsRewritePreview(
        source_lyrics_id=UUID(version.id),
        scope=payload.scope,
        action=payload.action,
        candidate_sections=candidate_sections,
        changes=changes,
        detected_banned_phrases=detected,
        warnings=warnings,
    )


def _target_line_ids(
    sections: list[LyricSection],
    payload: LyricsRewriteRequest,
) -> set[str]:
    if payload.scope == LyricsRewriteScope.all:
        return {line.line_id for section in sections for line in section.lines}
    if payload.scope == LyricsRewriteScope.section:
        section = next(
            (item for item in sections if item.section_id == payload.section_id),
            None,
        )
        if section is None:
            raise LyricsRewriteTargetError("Lyric section not found")
        return {line.line_id for line in section.lines}
    target = next(
        (
            line.line_id
            for section in sections
            for line in section.lines
            if line.line_id == payload.line_id
        ),
        None,
    )
    if target is None:
        raise LyricsRewriteTargetError("Lyric line not found")
    return {target}


def _rewrite_line(line: LyricLine, payload: LyricsRewriteRequest) -> LyricLine:
    text = _remove_banned_phrases(
        line.text,
        payload.banned_phrases,
        payload.preferred_terms[0] if payload.preferred_terms else "",
    )
    if payload.action == LyricsRewriteAction.expand:
        text = _expand_line(text, payload.instruction)
    elif payload.action == LyricsRewriteAction.compress:
        text = _compress_line(text)
    elif payload.action == LyricsRewriteAction.change_rhyme:
        text = _change_rhyme(text, payload.rhyme_ending or "")
    elif payload.action == LyricsRewriteAction.adjust_tone:
        text = _adjust_tone(text, payload.tone or payload.instruction)
    else:
        text = _rewrite_text(text, payload.instruction)
    return LyricLine(
        line_id=line.line_id,
        text=_limit_line(text),
        rhyme_label=payload.rhyme_label or line.rhyme_label,
    )


def _remove_banned_phrases(text: str, banned: list[str], replacement: str) -> str:
    result = text
    for phrase in banned:
        result = re.sub(re.escape(phrase), replacement, result, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", result).strip(" ,;，；") or text


def _rewrite_text(text: str, instruction: str | None) -> str:
    if instruction:
        separator = "，" if _contains_cjk(text + instruction) else "; "
        return f"{text.rstrip(',.!?，。！？')}{separator}{instruction}"
    for separator in ("，", ","):
        if separator in text:
            left, right = text.split(separator, 1)
            return f"{right.strip()}{separator}{left.strip()}"
    if _contains_cjk(text):
        return text.replace("我", "我们", 1) if "我" in text else f"{text}，让画面更近"
    return (
        re.sub(r"^I\b", "We", text, count=1)
        if re.match(r"^I\b", text)
        else f"{text}, now in sharper focus"
    )


def _expand_line(text: str, instruction: str | None) -> str:
    cue = instruction or (
        "让余韵继续向前" if _contains_cjk(text) else "the image keeps moving forward"
    )
    separator = "，" if _contains_cjk(text + cue) else ", while "
    return f"{text.rstrip(',.!?，。！？')}{separator}{cue}"


def _compress_line(text: str) -> str:
    compressed = _ENGLISH_FILLERS.sub("", text)
    for filler in _CHINESE_FILLERS:
        compressed = compressed.replace(filler, "")
    compressed = re.sub(r"\s{2,}", " ", compressed).strip(" ,;，；")
    if compressed != text.strip():
        return compressed
    if _contains_cjk(text):
        target = max(4, int(len(text) * 0.72))
        return text[:target].rstrip("，。！？")
    words = text.split()
    return " ".join(words[: max(3, int(len(words) * 0.72))])


def _change_rhyme(text: str, ending: str) -> str:
    ending = ending.strip()
    if _contains_cjk(text):
        prefix = text.rstrip("，。！？,.!?")
        return f"{prefix[:-1]}{ending}" if prefix else ending
    return re.sub(r"[A-Za-z']+[^A-Za-z']*$", ending, text).strip() or ending


def _adjust_tone(text: str, tone: str | None) -> str:
    cue = tone or ("更克制" if _contains_cjk(text) else "more intimate")
    separator = "，" if _contains_cjk(text + cue) else " - "
    return f"{text.rstrip(',.!?，。！？')}{separator}{cue}"


def _limit_line(text: str) -> str:
    normalized = re.sub(r"\s{2,}", " ", text).strip()
    return normalized[:500].rstrip()


def _detected_banned_phrases(
    sections: list[LyricSection],
    target_ids: set[str],
    banned: list[str],
) -> list[str]:
    target_text = "\n".join(
        line.text for section in sections for line in section.lines if line.line_id in target_ids
    ).casefold()
    return [term for term in banned if term.casefold() in target_text]


def _line_diff(before: str, after: str) -> list[LyricDiffSegment]:
    before_tokens = _TOKEN_PATTERN.findall(before)
    after_tokens = _TOKEN_PATTERN.findall(after)
    matcher = SequenceMatcher(a=before_tokens, b=after_tokens, autojunk=False)
    segments: list[LyricDiffSegment] = []
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag in {"equal", "delete", "replace"}:
            value = "".join(before_tokens[left_start:left_end])
            if value:
                segments.append(
                    LyricDiffSegment(kind="equal" if tag == "equal" else "delete", text=value)
                )
        if tag in {"insert", "replace"}:
            value = "".join(after_tokens[right_start:right_end])
            if value:
                segments.append(LyricDiffSegment(kind="insert", text=value))
    return segments


def _contains_cjk(text: str) -> bool:
    return _CJK_PATTERN.search(text) is not None
