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
from datetime import datetime, timezone
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
from sqlalchemy import select

from app.core.cache import GameCache
from app.models.round import Round
from app.models.session import Session
from app.services.game_logic import (
    compare_word_by_word,
    generate_sequence,
    get_words_for_round,
    parse_transcript_to_words,
)
from app.services.game_state import GameData, GameState
from app.services.prompt_templates import PromptTemplateSelector

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

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
        # Polling task: checks user_done_event every 500ms to catch PTT
        # release even when no TranscriptionFrames arrive.
        self._poll_task: Any = None

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

        # Clear any stale user_done_event from a previous session
        if self.game.user_done_event:
            self.game.user_done_event.clear()

        # Update cache immediately so the frontend's polling sees
        # current_round > 0 and doesn't show the 30-second timeout.
        await self._update_cache()

        # Also write current_round to the database directly so the
        # REST API (which has its own in-memory cache) can read it.
        await self._init_round_in_db()

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

        # Start polling task that catches user_done_event even when no
        # TranscriptionFrames arrive after the button is released.
        self._poll_task = asyncio.create_task(self._poll_user_done())

    async def _on_end(self) -> None:
        """Handle session end — clean up game state."""
        await self._cancel_validate()
        await self._cancel_poll()
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

        Uses a three-layer approach to detect when the user has finished:
        1. Push-to-talk: user_done_event signals immediate validation
           (most reliable — user explicitly indicates they're done).
        2. Inline threshold: if enough fragments accumulate (>= 5),
           trigger validation directly (push_frame works here).
        3. Timer fallback: 4-second silence window via background task.
        """
        if self.game.state == GameState.LISTEN:
            now = time.monotonic()
            gap = now - self._last_transcript_time if self._last_transcript_time > 0 else 0
            self._last_transcript_time = now

            self.game.user_transcript_buffer.append(frame.text)
            logger.info(
                "Transcript collected: '%s' (buffer size: %d, gap: %.1fs)",
                frame.text,
                len(self.game.user_transcript_buffer),
                gap,
            )

            # ── Layer 1: Push-to-talk signal ──────────────────────
            # If the user released the hold-to-speak button, validate
            # immediately with whatever transcripts we have.
            if (
                self.game.user_done_event
                and self.game.user_done_event.is_set()
            ):
                self.game.user_done_event.clear()
                if not self.game.is_validating and len(self.game.user_transcript_buffer) >= 1:
                    logger.info(
                        "User done signal — triggering validation with %d fragments",
                        len(self.game.user_transcript_buffer),
                    )
                    await self._cancel_validate()
                    self.game.state = GameState.VALIDATE
                    await self._validate_response()
                    return

            # ── Layer 2: Inline threshold ─────────────────────────
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
                await self._cancel_validate()
                self.game.state = GameState.VALIDATE
                await self._validate_response()
                return

            # ── Layer 3: Timer fallback ───────────────────────────
            # Reset the 4-second silence window on each new transcript
            if not self.game.is_validating:
                await self._cancel_validate()
                self._validate_task = asyncio.create_task(
                    self._timer_validate()
                )
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

            # === COMPARE WORD-BY-WORD (PARTIAL SCORING) ===
            result = compare_word_by_word(expected, user_words)

            logger.info(
                "Word-by-word comparison: %d/%d correct (perfect=%s)",
                result["correct_count"],
                result["total"],
                result["is_perfect"],
            )

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

            if result["is_perfect"]:
                # === PERFECT: save to DB, advance to next round ===
                await self._save_round_to_db(
                    round_number=self.game.current_round,
                    word_sequence=expected,
                    user_response=user_words,
                    is_correct=True,
                )
                await self._on_round_pass(user_words, result)

                # Update cache AND database AFTER _on_round_pass adds the
                # score and advances the round number. This ensures the
                # REST API (separate process, separate cache) can read the
                # updated score on the next frontend poll.
                await self._update_cache()
                await self._update_db_session()
            elif self.game.retries_remaining > 0:
                # === PARTIAL: retry the same round ===
                # Track the best attempt across all retries so we
                # save the user's highest score, not just the last try.
                if result["correct_count"] > self.game.best_retry_count:
                    self.game.best_retry_count = result["correct_count"]
                    self.game.best_retry_words = user_words
                    logger.info(
                        "New best retry: %d/%d correct",
                        result["correct_count"],
                        result["total"],
                    )

                self.game.retries_remaining -= 1
                logger.info(
                    "Partial score — %d retries remaining for round %d",
                    self.game.retries_remaining,
                    self.game.current_round,
                )
                await self._on_retry(user_words, expected, result)
            else:
                # === NO RETRIES LEFT: game over ===
                # Use the best result from retries, not the last attempt
                best_words = (
                    self.game.best_retry_words
                    if self.game.best_retry_words
                    else user_words
                )
                await self._save_round_to_db(
                    round_number=self.game.current_round,
                    word_sequence=expected,
                    user_response=best_words,
                    is_correct=False,
                )

                # Apply best retry score to total score
                if self.game.best_retry_count > 0:
                    self.game.score += self.game.best_retry_count

                await self._update_cache()
                await self._update_db_session()
                await self._on_game_over(user_words, expected)

        except Exception:
            logger.exception("Error during validation")
            self.game.state = GameState.GAME_OVER
        finally:
            # Reset for next round
            self.game.user_transcript_buffer = []
            self.game.is_validating = False

    async def _on_round_pass(
        self, user_words: list[str], result: dict
    ) -> None:
        """Handle a perfect answer — advance to next round.

        Awards partial score based on correctly matched word positions,
        generates new sequence, announces next round.

        Args:
            user_words: Parsed words from the user's speech.
            result: Comparison result dict from compare_word_by_word().
        """
        # Calculate score based on correctly matched words
        round_score = result["correct_count"]
        self.game.score += round_score
        self.game.current_round += 1

        # Reset retries for the next round
        self.game.retries_remaining = self.game.max_retries_per_round

        logger.info(
            "Round pass! +%d points (total: %d), next round: %d",
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

        # Announce the next round — congratulation message first,
        # then each word individually with pauses, then instruction.
        intro, outro = self.prompt_selector.get_split(
            "success",
            default_intro=(
                "Correct! Moving to round {round_number}. "
                "Score: {score}."
            ),
            default_outro="Say them back to me.",
            round_number=self.game.current_round,
            score=self.game.score,
        )

        # 1. Congratulation + score
        await self._say(intro)

        # 2. Each word individually with pauses
        await self._say_words_with_pauses(self.game.expected_sequence)

        # 3. Instruction
        if outro:
            await self._say(outro)

        # Pause 3 seconds before listening so the user has time
        # to process the new words before their turn.
        await asyncio.sleep(3.0)

        # Bot has finished speaking the next sequence — listen for user
        self.game.state = GameState.LISTEN

    async def _on_retry(
        self, user_words: list[str], expected: list[str], result: dict
    ) -> None:
        """Handle a partial score — retry the same round.

        Tells the user how many words they got correct, re-announces
        the same word sequence, and transitions back to LISTEN.

        Args:
            user_words: Parsed words from the user's speech.
            expected: The expected word sequence.
            result: Comparison result dict from compare_word_by_word().
        """
        self.game.state = GameState.SPEAK_SEQUENCE

        logger.info(
            "Round %d retry — %d/%d correct, %d retries remaining",
            self.game.current_round,
            result["correct_count"],
            result["total"],
            self.game.retries_remaining,
        )

        # Retry prompt: feedback first, then words individually, then instruction.
        intro, outro = self.prompt_selector.get_split(
            "retry",
            default_intro=(
                "Good try! You got {correct_count} out of {total} correct. "
                "Let's try again."
            ),
            default_outro="Repeat them back to me.",
            correct_count=result["correct_count"],
            total=result["total"],
        )

        # 1. Feedback
        await self._say(intro)

        # 2. Each word individually with pauses
        await self._say_words_with_pauses(expected)

        # 3. Instruction
        if outro:
            await self._say(outro)

        # Pause 3 seconds before listening so the user has time
        # to process the words before their turn.
        await asyncio.sleep(3.0)

        # Go back to listening for user response
        self.game.state = GameState.LISTEN

    async def _on_game_over(
        self, user_words: list[str], expected: list[str]
    ) -> None:
        """Handle all retries exhausted — end the game."""
        self.game.incorrect_round_data = {
            "expected": expected,
            "user_said": user_words,
            "round": self.game.current_round,
            "score": self.game.score,
        }
        self.game.state = GameState.GAME_OVER

        logger.info(
            "Game over — all retries exhausted. Score: %d, round: %d",
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

        Each word is spoken as a separate TextFrame with a 1-second
        pause between them, giving the user time to hear and process
        each word before the next one starts (addressing the "bot
        stops immediately" issue). After all words, the user is
        prompted to repeat them back, followed by a 3-second pause.
        """
        # Get the intro and outro from the template (split on
        # {numbered_sequence}) so we can insert individual word
        # announcements with pauses between them.
        intro, outro = self.prompt_selector.get_split(
            "round_intro",
            default_intro="Round {round_number}. Here are your words.",
            default_outro="Now repeat them back to me.",
            round_number=self.game.current_round,
        )

        # 1. Say the intro (e.g. "Round 1. Here are your words.")
        await self._say(intro)

        # 2. Say each word individually with a 1-second pause between
        #    them so the user can hear and process each one clearly.
        await self._say_words_with_pauses(self.game.expected_sequence)

        # 3. Say the outro (e.g. "Now repeat them back to me.")
        if outro:
            await self._say(outro)

        # Pause 3 seconds before listening so the user has time
        # to mentally process the words before their turn.
        await asyncio.sleep(3.0)

    async def _say(self, text: str) -> None:
        """Push a TextFrame with the bot's speech into the pipeline.

        The TextFrame flows downstream to TTS -> audio output.
        """
        await self.push_frame(TextFrame(text))

    async def _say_words_with_pauses(self, words: list[str]) -> None:
        """Announce each word individually with a 1-second pause between them.

        Instead of sending all words in one TextFrame (which makes TTS
        speak them as a single continuous utterance), each word is sent
        as its own TextFrame with a deliberate delay. This creates
        audible pauses between words so the user can hear and process
        each one before the next starts.

        Args:
            words: The word sequence to announce.
        """
        for i, word in enumerate(words):
            await self._say(f"Word {i + 1}: {word}.")
            await asyncio.sleep(1.0)

    async def _cancel_validate(self) -> None:
        """Cancel the pending timer-based validation task."""
        if self._validate_task and not self._validate_task.done():
            self._validate_task.cancel()
            try:
                await self._validate_task
            except asyncio.CancelledError:
                pass
        self._validate_task = None

    async def _cancel_poll(self) -> None:
        """Cancel the user_done polling task."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        self._poll_task = None

    async def _poll_user_done(self) -> None:
        """Poll user_done_event every 500ms. Catches PTT release even
        when no TranscriptionFrames arrive after the button is released."""
        try:
            while True:
                await asyncio.sleep(0.5)
                if (
                    self.game.user_done_event
                    and self.game.user_done_event.is_set()
                    and self.game.state == GameState.LISTEN
                    and not self.game.is_validating
                    and len(self.game.user_transcript_buffer) >= 1
                ):
                    self.game.user_done_event.clear()
                    logger.info(
                        "User done poll — triggering validation "
                        "with %d fragments",
                        len(self.game.user_transcript_buffer),
                    )
                    self.game.state = GameState.VALIDATE
                    await self._validate_response()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Error in user_done poll task")

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

    async def _init_round_in_db(self) -> None:
        """Write current_round to the database so the REST API can see it.

        The REST API runs in a separate process with its own in-memory
        cache. Writing to the database ensures the frontend's polling
        (which hits the REST API) sees current_round > 0 immediately
        instead of timing out with 'Game Didn't Start'.
        """
        if not self.game.session_id:
            return

        try:
            result = await self.db.execute(
                select(Session).where(Session.id == self.game.session_id)
            )
            db_session = result.scalar_one_or_none()
            if db_session:
                db_session.current_round = self.game.current_round
                await self.db.flush()
                logger.debug(
                    "Updated db session %s current_round=%d",
                    self.game.session_id,
                    self.game.current_round,
                )
        except Exception:
            logger.warning(
                "Failed to init round in db for session %s",
                self.game.session_id,
            )

        # Commit immediately so the REST API (running in a separate
        # process with its own DB connection) can see the updated
        # current_round value on the next frontend poll.
        # Without this commit, PostgreSQL's READ COMMITTED isolation
        # hides the change until the entire pipeline stops and the
        # async with session context manager commits.
        try:
            await self.db.commit()
        except Exception:
            logger.warning("Failed to commit init round in db")
            await self.db.rollback()

    async def _update_db_session(self) -> None:
        """Write current score and round number to the database.

        Called after each successful round pass so the REST API
        (separate process, separate cache) can read the updated
        score and round on the next frontend poll. Without this,
        the score stays at 0 in the DB until _end_session commits.
        """
        if not self.game.session_id:
            return

        try:
            result = await self.db.execute(
                select(Session).where(Session.id == self.game.session_id)
            )
            db_session = result.scalar_one_or_none()
            if db_session:
                db_session.score = self.game.score
                db_session.current_round = self.game.current_round
                await self.db.flush()
                logger.debug(
                    "Updated db session %s score=%d round=%d",
                    self.game.session_id,
                    self.game.score,
                    self.game.current_round,
                )
        except Exception:
            logger.warning(
                "Failed to update db session for %s",
                self.game.session_id,
            )

        # Commit so the REST API sees the change immediately
        try:
            await self.db.commit()
        except Exception:
            logger.warning("Failed to commit db session update")
            await self.db.rollback()

    async def _check_already_scored(self) -> bool:
        """Check if this round already has a response recorded.

        Layer 3 application-level double-scoring prevention.
        Checks the database if a response already exists for this
        session + round combination.
        """
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
        """Update session status to completed in database and cache.

        Critical: must commit() after flush() so the REST API
        (which runs in a separate process with its own DB connection)
        can see the status change. Without commit(), PostgreSQL's
        READ COMMITTED isolation hides the update from other
        connections until the entire pipeline stops.
        """
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

        # Commit so the REST API can see the status change immediately.
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            logger.exception("Failed to commit session end")

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
