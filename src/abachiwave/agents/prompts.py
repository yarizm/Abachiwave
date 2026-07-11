SONG_SPEC_SYSTEM_CONTRACT = """Build a structured SongSpec only from supplied user input.
Do not invent missing musical parameters. Missing required fields must remain null."""

CLARIFICATION_PROMPT_TEMPLATE = """Ask targeted questions for missing SongSpec fields:
theme, genre, language, tempo_bpm, key, time_signature, target_duration_seconds,
mood_curve, and song_structure."""
