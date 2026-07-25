"""Game state machine — enum and dataclass for the memory game.

Defines all game states and the mutable game data that flows through
the MemoryGameProcessor.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class GameState(str, Enum):
    """Enum of all possible game states.

    Transitions:
        IDLE -> START_GAME -> SPEAK_SEQUENCE -> LISTEN -> VALIDATE
            -> ROUND_PASS -> SPEAK_SEQUENCE (loop)
            -> GAME_OVER -> ENDED
    """

    IDLE = "idle"
    START_GAME = "start_game"
    SPEAK_SEQUENCE = "speak_sequence"
    LISTEN = "listen"
    VALIDATE = "validate"
    ROUND_PASS = "round_pass"
    GAME_OVER = "game_over"
    ENDED = "ended"


@dataclass
class GameData:
    """Mutable game state shared across the pipeline processors.

    This dataclass is mutated by MemoryGameProcessor as the game
    progresses through rounds.
    """

    # State machine
    state: GameState = GameState.IDLE

    # Round tracking
    current_round: int = 0
    max_rounds: int = 10
    score: int = 0

    # Word sequences
    expected_sequence: list[str] = field(default_factory=list)

    # User input buffer (accumulated transcript fragments)
    user_transcript_buffer: list[str] = field(default_factory=list)

    # Session info
    session_id: Optional[str] = None
    player_name: str = "Player"

    # Guards
    is_validating: bool = False  # Prevents re-entry during validation

    # Last round data (for game over display)
    incorrect_round_data: Optional[dict] = None

    # Used sequences cache (set of tuples for uniqueness)
    used_sequences: set[tuple[str, ...]] = field(default_factory=set)

    # Push-to-talk signal: set by signaling client when user releases
    # the hold-to-speak button. Checked by game_processor to trigger
    # validation without waiting for VAD or transcript threshold.
    user_done_event: Any = field(default_factory=asyncio.Event)

    # Retry tracking: how many attempts left for the current round
    retries_remaining: int = 3
    max_retries_per_round: int = 3

    def reset(self):
        """Reset game data for a new game (keeps session_id + player_name)."""
        self.state = GameState.IDLE
        self.current_round = 0
        self.score = 0
        self.expected_sequence = []
        self.user_transcript_buffer = []
        self.is_validating = False
        self.incorrect_round_data = None
        self.used_sequences = set()
        self.retries_remaining = self.max_retries_per_round

    @property
    def is_active(self) -> bool:
        """Check if the game is still in progress."""
        return self.state not in (GameState.GAME_OVER, GameState.ENDED)

    @property
    def is_listening(self) -> bool:
        """Check if the bot is currently listening for user input."""
        return self.state == GameState.LISTEN

    def __repr__(self) -> str:
        return (
            f"GameData(state={self.state.value}, "
            f"round={self.current_round}, "
            f"score={self.score}, "
            f"active={self.is_active})"
        )
