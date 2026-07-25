"""MemoryGameProcessor — custom Pipecat FrameProcessor for the memory game.

This is the central orchestrator of the game:
- Manages game state transitions (IDLE -> START_GAME -> SPEAK_SEQUENCE -> LISTEN ->
  VALIDATE -> ROUND_PASS / GAME_OVER -> ENDED)
- Intercepts user transcript frames and validates game responses
- Selects random prompt templates for bot speech
- Generates word sequences per round
- Prevents double-scoring
- Handles interruptions gracefully
- Persists rounds to the database and updates cache
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from pipecat.frames.frames import (
    EndFrame,
    Frame,
    StartFrame,
    TextFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.services.game_logic import (
    compare_sequences,
    generate_sequence,
    get_words_for_round,
    parse_transcript_to_words,
)
from app.services.game_state import GameData, GameState

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.cache import GameCache
    from app.services.prompt_templates import PromptTemplateSelector

logger = logging.getLogger(__name__)

MIN_TRANSCRIPT_THRESHOLD = 5
"""Minimum transcript fragments before inline validation triggers.

Accounts for STT producing multiple fragments per word (interim +
final transcriptions). Higher values reduce premature validation.
"""


class MemoryGameProcessor(FrameProcessor):
    """Custom Pipecat FrameProcessor that implements the memory game engine.

    This processor sits between STT and TTS in the Pipecat pipeline:
        STT -> MemoryGameProcessor -> TTS

    It intercepts frames to:
    1. Control game state transitions
    2. Validate user responses against expected word sequences
    3. Generate random prompt templates for bot dialog
    4. Persist round data to database
    5. Handle interruptions (user speaking while bot is talking)
    """

    def __init__(
        self,
        game: GameData,
        db_session: AsyncSession,
        cache: GameCache,
        prompt_selector: PromptTemplateSelector,
        *,
        max_rounds: int = 10,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.game = game
        self.db = db_session
        self.cache = cache
        self.prompt_selector = prompt_selector
        self.game.max_rounds = max_rounds

        # Internal state tracking
        self._started: bool = False
        self._interrupted: bool = False
        # Protects the initial welcome + round announcement phase from accidental
        # interruption. User speech during this window is silently ignored.
        self._announcing_phase: bool = False
        # Transcript timeout fallback: triggers validation after 4 seconds
        # of silence (when VAD doesn't emit UserStoppedSpeakingFrame).
        self._validate_task: Any = None
        self._last_transcript_time: float = 0.0

        logger.info(
            "MemoryGameProcessor initialized (max_rounds=%d)", max_rounds
        )

    # ── Frame Processing ──────────────────────────────────────

    async def process_frame(
        self, frame: Frame, direction: FrameDirection
    ) -> None:
        """Process incoming frames and forward them through the pipeline."""
        await super().process_frame(frame, direction)

        # IMPORTANT: Forward the frame FIRST before handling game logic.
        # This ensures downstream processors (like TTS) receive the
        # StartFrame to initialize BEFORE any TextFrames we push in
        # _on_start(). Otherwise TextFrames arrive at an uninitialized
        # TTS and get silently dropped = no audible bot speech.
        await self.push_frame(frame, direction)

        # === HANDLE FRAME TYPES ===

        if isinstance(frame, StartFrame):
            await self._on_start()

        elif isinstance(frame, EndFrame):
            await self._on_end()

        elif isinstance(frame, UserStartedSpeakingFrame):
            await self._on_user_started_speaking()

        elif isinstance(frame, UserStoppedSpeakingFrame):
            await self._on_user_stopped_speaking()

        elif isinstance(frame, TranscriptionFrame):
            await self._on_transcript(frame)

    # ── Start / End ────────────────────────────────────────────

    async def _on_start(self) -> None:
        """Handle session start — begin the game."""
        if self._started:
            return
        self._started = True

        logger.info(
            "Game starting — player: %s, max_rounds: %d",
            self.game.player_name,
            self.game.max_rounds,
        )

        # Reset game state for new game
        self.game.reset()

        # Transition to START_GAME
        self.game.state = GameState.START_GAME

        # Generate the first sequence
        self.game.current_round = 1
        self.game.expected_sequence = generate_sequence(
            round_number=self.game.current_round,
            used_sequences=self.game.used_sequences,
        )

        logger.info(
            "Round %d sequence: %s",
            self.game.current_round,
            self.game.expected_sequence,
        )

        # Update cache immediately so the frontend's polling sees
        # current_round > 0 and doesn't show the 30-second timeout.
        await self._update_cache()

        # Protect initial announcement from accidental interruption
        self._announcing_phase = True

        # Select a random start/welcome prompt
        prompt = self.prompt_selector.get(
            "start",
            default="Welcome to the Memory Host! Let's begin!",
            player_name=self.game.player_name,
        )
        await self._say(prompt)

        # Announce the first round — words are embedded directly in the
        # template via the {sequence} placeholder with period separators.
        # This is a single synchronous TextFrame push so the words are
        # guaranteed to be spoken by TTS (no background task required).
        self.game.state = GameState.SPEAK_SEQUENCE
        await self._announce_round()

        # Clear the announcing phase flag before transitioning to LISTEN.
        # From here on, user speech will trigger validation normally.
        self._announcing_phase = False

        # Bot has finished speaking the sequence — listen for user response
        self.game.state = GameState.LISTEN
        logger.debug("Transitioned to LISTEN — awaiting user response")

    async def _on_end(self) -> None:
        """Handle session end — clean up game state."""
        await self._cancel_validate()
        if self.game.state != GameState.ENDED:
            logger.info(
                "Game ending — final state: %s, score: %d, round: %d",
                self.game.state.value,
                self.game.score,
                self.game.current_round,
            )
            self.game.state = GameState.ENDED

    # ── Interruption Handling ─────────────────────────────────

    async def _on_user_started_speaking(self) -> None:
        """Handle user interrupting or beginning to speak.

        If the bot is currently speaking (SPEAK_SEQUENCE or ROUND_PASS),
        the user's speech is treated as an interruption. The bot
        stops talking and transitions to LISTEN mode.

        During the _announcing_phase (initial welcome + word announcement),
        user speech is silently ignored to prevent accidental interruption
        from responding to the welcome message (e.g. saying "okay" or
        clearing throat during the first few seconds).
        """
        if self._announcing_phase:
            logger.debug(
                "Ignoring speech during announcing phase (state=%s)",
                self.game.state.value if self.game.state else "None",
            )
            self.game.user_transcript_buffer = []
            return

        if self.game.state in (GameState.SPEAK_SEQUENCE, GameState.ROUND_PASS):
            # User interrupted bot mid-speech
            self._interrupted = True
            self.game.state = GameState.LISTEN
            self.game.user_transcript_buffer = []

            logger.info("User interrupted bot — transitioning to LISTEN")

        elif self.game.state == GameState.LISTEN:
            # User is already in listen mode, reset buffer for new utterance
            self.game.user_transcript_buffer = []

    async def _on_user_stopped_speaking(self) -> None:
        """User finished their turn — transition to validation.

        Only triggers when the game is in LISTEN state and validation
        is not already in progress (anti-double-scoring guard).
        """
        if self.game.state == GameState.LISTEN and not self.game.is_validating:
            self.game.state = GameState.VALIDATE
            await self._validate_response()

        elif self._interrupted and self.game.state == GameState.VALIDATE:
            # User finished speaking after interruption
            self._interrupted = False

    # ── Transcript Processing ──────────────────────────────────

    async def _on_transcript(self, frame: TranscriptionFrame) -> None:
        """Collect transcribed words from user speech.

        Accumulates transcript text fragments while in LISTEN state.
        These are later parsed into a flat word list during validation.

        Uses a two-layer approach to detect when the user has finished:
        1. Inline threshold: if enough fragments accumulate (>= 5),
           trigger validation directly (push_frame works here).
        2. Timer fallback: 4-second silence window via background task.
           If push_frame doesn't work from the task, game state still
           updates silently (frontend picks it up via polling).
        """
        if self.game.state == GameState.LISTEN:
            now = time.monotonic()
            gap = now - self._last_transcript_time if self._last_transcript_time > 0 else 0
            self._last_transcript_time = now

            self.game.user_transcript_buffer.append(frame.text)
            # Log at INFO level so we can see transcripts in the app log
            logger.info(
                "Transcript collected: '%s' (buffer size: %d, gap: %.1fs)",
                frame.text,
                len(self.game.user_transcript_buffer),
                gap,
            )

            # Reset the timer-based fallback on each transcript
            if self._validate_task and not self._validate_task.done():
                self._validate_task.cancel()
            if not self.game.is_validating:
                self._validate_task = asyncio.create_task(
                    self._timer_validate()
                )

            # Inline threshold: if enough fragments have accumulated,
            # trigger validation right now (reliable push_frame context).
            threshold = max(
                MIN_TRANSCRIPT_THRESHOLD,
                len(self.game.expected_sequence) + 2,
            )
            if (
                len(self.game.user_transcript_buffer) >= threshold
                and not self.game.is_validating
            ):
                logger.info(
                    "Transcript threshold reached (%d) — triggering validation",
                    len(self.game.user_transcript_buffer),
                )
                self.game.state = GameState.VALIDATE
                await self._validate_response()
        else:
            logger.warning(
                "Transcript received but not in LISTEN state (state=%s): '%s'",
                self.game.state.value if self.game.state else "None",
                frame.text,
            )

    # ── Validation (Core Game Logic) ───────────────────────────

    async def _validate_response(self) -> None:
        """Core validation logic — pure Python, NOT LLM-dependent.

        Compares the user's spoken words against the expected sequence,
        updates score, saves round to DB, and transitions to the next
        game state.
        """
        # Layer 1: In-memory guard against double-scoring
        if self.game.is_validating:
            logger.warning("Validation already in progress — skipping")
            return

        self.game.is_validating = True

        try:
            # Parse user transcript into flat word list
            user_words = parse_transcript_to_words(
                self.game.user_transcript_buffer
            )
            expected = self.game.expected_sequence

            # Cancel pending timer fallback since we're validating now
            await self._cancel_validate()

            logger.info(
                "Validating — expected: %s, user: %s",
                expected,
                user_words,
            )

            # === COMPARE ===
            is_correct = compare_sequences(expected, user_words)

            # === LAYER 3: APPLICATION-LEVEL DOUBLE-SCORING CHECK ===
            already_scored = await self._check_already_scored()
            if already_scored:
                logger.warning(
                    "Double-scoring attempt blocked for "
                    "session=%s round=%d",
                    self.game.session_id,
                    self.game.current_round,
                )
                return

            # === RECORD ROUND IN DATABASE ===
            await self._save_round_to_db(
                round_number=self.game.current_round,
                word_sequence=expected,
                user_response=user_words,
                is_correct=is_correct,
            )

            # === UPDATE CACHE ===
            await self._update_cache()

            if is_correct:
                await self._on_round_pass(user_words)
            else:
                await self._on_game_over(user_words, expected)

        except Exception:
            logger.exception("Error during validation")
            self.game.state = GameState.GAME_OVER
        finally:
            # Reset for next round
            self.game.user_transcript_buffer = []
            self.game.is_validating = False

    async def _on_round_pass(
        self, user_words: list[str]
    ) -> None:
        """Handle a correct answer — advance to next round.

        Updates score, generates new sequence, announces next round.
        """
        # Calculate score for this round
        round_score = self.game.current_round
        self.game.score += round_score
        self.game.current_round += 1

        logger.info(
            "Round pass! Score: +%d = %d, next round: %d",
            round_score,
            self.game.score,
            self.game.current_round,
        )

        if self.game.current_round > self.game.max_rounds:
            # Game won — completed all rounds!
            await self._on_game_won()
            return

        # Generate the next sequence
        self.game.expected_sequence = generate_sequence(
            round_number=self.game.current_round,
            used_sequences=self.game.used_sequences,
        )

        logger.info(
            "Next sequence (round %d): %s",
            self.game.current_round,
            self.game.expected_sequence,
        )

        # Build a single announcement string with words embedded via period
        # separators. This guarantees the words are spoken by TTS (no
        # background task required).
        sequence_str = ". ".join(self.game.expected_sequence)
        prompt = self.prompt_selector.get(
            "success",
            default=(
                "Correct! Moving to round {round_number}. "
                "Score: {score}. Your words are. {sequence}. "
                "Now repeat those words back."
            ),
            round_number=self.game.current_round,
            score=self.game.score,
            sequence=sequence_str,
        )
        await self._say(prompt)

        # Prompt the user to repeat the words (the success templates don't
        # include this, unlike the round_intro templates)
        await self._say("Now repeat those words back.")

        # Bot has finished speaking the next sequence — listen for user
        self.game.state = GameState.LISTEN

    async def _on_game_over(
        self, user_words: list[str], expected: list[str]
    ) -> None:
        """Handle a wrong answer — end the game."""
        self.game.incorrect_round_data = {
            "expected": expected,
            "user_said": user_words,
            "round": self.game.current_round,
            "score": self.game.score,
        }
        self.game.state = GameState.GAME_OVER

        logger.info(
            "Game over — wrong answer. Score: %d, round: %d",
            self.game.score,
            self.game.current_round,
        )

        # Select random failure prompt with period-separated words
        prompt = self.prompt_selector.get(
            "failure",
            default=(
                "Sorry, that wasn't correct. "
                "The sequence was: {correct_sequence}. "
                "Final score: {score}."
            ),
            correct_sequence=". ".join(expected),
            user_said=", ".join(user_words),
            score=self.game.score,
            round_number=self.game.current_round,
        )
        await self._say(prompt)

        # End the session
        await self._end_session()

    async def _on_game_won(self) -> None:
        """Handle game won — all rounds completed successfully."""
        self.game.state = GameState.GAME_OVER

        logger.info(
            "Game won! Perfect score: %d across %d rounds",
            self.game.score,
            self.game.max_rounds,
        )

        # Select random game_over (win) prompt
        prompt = self.prompt_selector.get(
            "game_over",
            default=(
                "Congratulations! You've completed all rounds! "
                "Final score: {score}."
            ),
            score=self.game.score,
            player_name=self.game.player_name,
            round_number=self.game.max_rounds,
        )
        await self._say(prompt)

        # End the session
        await self._end_session()

    # ── Helper Methods ─────────────────────────────────────────

    async def _announce_round(self) -> None:
        """Announce the current round and word sequence to the user.

        The words are embedded directly into the prompt template via the
        {sequence} placeholder, formatted with period separators. TTS
        naturally pauses at each period boundary (~300ms), and the words
        are guaranteed to be spoken since they're part of a single
        synchronous TextFrame push.
        """
        sequence_str = ". ".join(self.game.expected_sequence)
        prompt = self.prompt_selector.get(
            "round_intro",
            default="Round {round_number}. Listen carefully. {sequence}.",
            round_number=self.game.current_round,
            sequence=sequence_str,
        )
        await self._say(prompt)

    async def _say(self, text: str) -> None:
        """Push a TextFrame with the bot's speech into the pipeline.

        The TextFrame flows downstream to TTS -> audio output.
        """
        await self.push_frame(TextFrame(text))

    async def _cancel_validate(self) -> None:
        """Cancel the pending timer-based validation task."""
        if self._validate_task and not self._validate_task.done():
            self._validate_task.cancel()
            try:
                await self._validate_task
            except asyncio.CancelledError:
                pass
        self._validate_task = None

    async def _timer_validate(self) -> None:
        """Fallback: wait 4 seconds, then trigger validation.

        Runs as a background asyncio task. Cancelled and restarted on
        each new transcript. If push_frame doesn't route the result
        TextFrame from this context, the game state still updates
        silently and the frontend picks it up via polling.
        """
        try:
            await asyncio.sleep(4.0)
            if (
                self.game.state == GameState.LISTEN
                and not self.game.is_validating
                and len(self.game.user_transcript_buffer) >= 1
            ):
                logger.info(
                    "Transcript timeout (4s) — triggering validation "
                    "with %d fragments",
                    len(self.game.user_transcript_buffer),
                )
                self.game.state = GameState.VALIDATE
                await self._validate_response()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Error in timer validation")

    async def _check_already_scored(self) -> bool:
        """Check if this round already has a response recorded.

        Layer 3 application-level double-scoring prevention.
        Checks the database if a response already exists for this
        session + round combination.
        """
        from sqlalchemy import select

        from app.models.round import Round

        if not self.game.session_id:
            return False

        result = await self.db.execute(
            select(Round).where(
                Round.session_id == self.game.session_id,
                Round.round_number == self.game.current_round,
                Round.user_response.isnot(None),
            )
        )
        return result.scalar_one_or_none() is not None

    async def _save_round_to_db(
        self,
        round_number: int,
        word_sequence: list[str],
        user_response: list[str],
        is_correct: bool,
    ) -> None:
        """Persist a round record to the database.

        Also invalidates the leaderboard cache since scores changed.
        """
        from datetime import datetime, timezone

        from app.models.round import Round

        round_record = Round(
            session_id=self.game.session_id,
            round_number=round_number,
            word_sequence=word_sequence,
            user_response=user_response,
            is_correct=is_correct,
            answered_at=datetime.now(timezone.utc),
        )
        self.db.add(round_record)
        await self.db.flush()

        logger.debug(
            "Round saved: session=%s round=%d correct=%s",
            self.game.session_id,
            round_number,
            is_correct,
        )

    async def _update_cache(self) -> None:
        """Update the in-memory cache with current session state."""
        if not self.game.session_id:
            return

        session_data = {
            "session_id": str(self.game.session_id),
            "player_name": self.game.player_name,
            "status": (
                "active"
                if self.game.state not in (GameState.GAME_OVER, GameState.ENDED)
                else "completed"
            ),
            "score": self.game.score,
            "current_round": self.game.current_round,
            "max_rounds": self.game.max_rounds,
        }
        self.cache.set_session(str(self.game.session_id), session_data)

        # Invalidate leaderboard cache since scores changed
        self.cache.invalidate_leaderboard()

    async def _end_session(self) -> None:
        """Update session status to completed in database and cache."""
        from datetime import datetime, timezone

        from sqlalchemy import select

        from app.models.session import Session

        if not self.game.session_id:
            return

        result = await self.db.execute(
            select(Session).where(Session.id == self.game.session_id)
        )
        db_session = result.scalar_one_or_none()
        if db_session:
            db_session.status = "completed"
            db_session.score = self.game.score
            db_session.current_round = self.game.current_round
            db_session.ended_at = datetime.now(timezone.utc)
            await self.db.flush()

        # Remove from active cache
        self.cache.remove_session(str(self.game.session_id))

        # Mark game as ended
        self.game.state = GameState.ENDED

        logger.info(
            "Session %s ended — score: %d, round: %d",
            self.game.session_id,
            self.game.score,
            self.game.current_round,
        )
