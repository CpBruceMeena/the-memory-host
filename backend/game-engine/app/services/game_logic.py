"""Core game logic — pure Python, no external dependencies.

Handles:
- Word sequence generation per round
- User response validation (case-insensitive, punctuation-stripped)
- Sequence uniqueness tracking
"""

import random
from typing import Optional

from app.core.constants import WORD_POOL


def generate_sequence(
    round_number: int,
    used_sequences: Optional[set[tuple[str, ...]]] = None,
) -> list[str]:
    """Generate a unique word sequence for the given round.

    The number of words = get_words_for_round(round_number).
    E.g. Round 1 -> 1 word, Round 2 -> 2 words, Round 10 -> 10 words.

    Args:
        round_number: Current round (1-indexed).
        used_sequences: Optional set of previously used sequence tuples
                        to avoid repeats.

    Returns:
        A list of randomly selected words.

    Raises:
        ValueError: If the word pool is too small for the requested round.
    """
    word_count = get_words_for_round(round_number)
    pool = WORD_POOL

    if word_count > len(pool):
        raise ValueError(
            f"Cannot generate {word_count} unique words — "
            f"pool only has {len(pool)} words"
        )

    if used_sequences is None:
        return random.sample(pool, word_count)

    # Keep sampling until we find a unique sequence
    max_attempts = 100
    for _ in range(max_attempts):
        sequence = random.sample(pool, word_count)
        seq_key = tuple(sequence)
        if seq_key not in used_sequences:
            used_sequences.add(seq_key)
            return sequence

    # Fallback: just return a random sample (unlikely to hit this)
    return random.sample(pool, word_count)


def compare_word_by_word(
    expected: list[str],
    actual: list[str],
) -> dict:
    """Compare user's response against the expected word sequence word-by-word.

    Each word is matched independently at its position in the sequence.
    Returns the number of correctly matched words and a detailed breakdown.

    Normalizes both sequences by:
    - Stripping whitespace
    - Converting to lowercase
    - Removing trailing punctuation (. , ! ?)

    Args:
        expected: The correct word sequence (list of words).
        actual: The user's spoken words (parsed from transcript buffer).

    Returns:
        A dict with:
            correct_count: Number of words that matched at their position.
            total: Total number of expected words.
            score: Percentage score (0.0 - 1.0).
            is_perfect: True if all words matched correctly.
            details: List of dicts with 'expected', 'actual', 'correct' per position.
    """
    expected_norm = [_normalize_word(w) for w in expected]
    actual_norm = [_normalize_word(w) for w in actual]

    total = len(expected_norm)
    correct_count = 0
    details = []

    for i in range(total):
        user_word = actual_norm[i] if i < len(actual_norm) else ""
        is_correct = user_word == expected_norm[i]
        if is_correct:
            correct_count += 1
        details.append({
            "position": i + 1,
            "expected": expected_norm[i],
            "actual": user_word,
            "correct": is_correct,
        })

    return {
        "correct_count": correct_count,
        "total": total,
        "score": correct_count / total if total > 0 else 0.0,
        "is_perfect": correct_count == total,
        "details": details,
    }


def format_numbered_sequence(words: list[str]) -> str:
    """Format a word sequence as numbered items for TTS.

    Produces: "Word 1: marble. Word 2: chocolate. Word 3: thunder"
    Each word is its own sentence, giving the TTS natural pauses.

    Args:
        words: The word sequence to format.

    Returns:
        A formatted string with numbered words.
    """
    parts = [f"Word {i + 1}: {word}" for i, word in enumerate(words)]
    return ". ".join(parts)


def _normalize_word(word: str) -> str:
    """Normalize a single word for comparison."""
    return word.strip().lower().rstrip(".,!?")


def parse_transcript_to_words(transcript_buffer: list[str]) -> list[str]:
    """Parse a transcript buffer into a flat list of individual words.

    Args:
        transcript_buffer: List of transcript text fragments from STT.

    Returns:
        Flat list of individual words.
    """
    words: list[str] = []
    for fragment in transcript_buffer:
        # Split on whitespace and add each word
        for word in fragment.split():
            cleaned = _normalize_word(word)
            if cleaned:  # Skip empty strings
                words.append(cleaned)
    return words


def get_words_for_round(round_number: int) -> int:
    """Get the number of words for a given round.

    Each level has words equal to the level number:
    Level  1: 1 word
    Level  2: 2 words
    Level  3: 3 words
    ...
    Level 10: 10 words

    Args:
        round_number: 1-indexed round number (1-10).

    Returns:
        Number of words in the sequence for that round.
    """
    return round_number
