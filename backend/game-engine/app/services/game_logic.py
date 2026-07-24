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

    The number of words = round_number + 2.
    E.g. Round 1 -> 3 words, Round 2 -> 4 words, Round 10 -> 12 words.

    Args:
        round_number: Current round (1-indexed).
        used_sequences: Optional set of previously used sequence tuples
                        to avoid repeats.

    Returns:
        A list of randomly selected words.

    Raises:
        ValueError: If the word pool is too small for the requested round.
    """
    word_count = round_number + 2
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


def compare_sequences(
    expected: list[str],
    actual: list[str],
    *,
    exact_order: bool = True,
) -> bool:
    """Compare user's response against the expected word sequence.

    Normalizes both sequences by:
    - Stripping whitespace
    - Converting to lowercase
    - Removing trailing punctuation (. , ! ?)

    Args:
        expected: The correct word sequence.
        actual: The user's spoken words (parsed from transcript).
        exact_order: If True (default), words must be in the same order.
                     If False, words just need to match (any order).

    Returns:
        True if the sequences match according to the comparison rules.
    """
    expected_norm = [_normalize_word(w) for w in expected]
    actual_norm = [_normalize_word(w) for w in actual]

    if exact_order:
        return expected_norm == actual_norm
    else:
        return sorted(expected_norm) == sorted(actual_norm)


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

    Args:
        round_number: 1-indexed round number.

    Returns:
        Number of words in the sequence for that round.
    """
    return round_number + 2
