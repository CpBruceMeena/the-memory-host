"""Pipecat voice bot entrypoint for The Memory Host.

Assembles the Pipecat pipeline:
    SmallWebRTCTransport → Deepgram STT → MemoryGameProcessor → Deepgram TTS → Output

Usage:
    # Start the bot (requires an active session and room):
    python -m backend.app.services.bot --session-id <uuid> --room-url <url> --token <token>

Environment Variables:
    DEEPGRAM_API_KEY     Required for STT/TTS
    SMALLWEBRTC_SERVER_URL  Signaling server URL (default: http://localhost:3001)
    BOT_NAME             Bot display name (default: "Memory Game Host")
    MAX_ROUNDS           Max game rounds (default: 10)
    LOG_LEVEL            Logging level (default: INFO)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import uuid
from typing import Any, Optional

from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import (
    LocalSmartTurnAnalyzerV3,
)
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.services.deepgram import DeepgramSTTService, DeepgramTTSService
from pipecat.transports.base_transport import TransportParams

from app.core.cache import GameCache, cache
from app.core.config import settings
from app.services.game_processor import MemoryGameProcessor
from app.services.game_state import GameData
from app.services.prompt_templates import PromptTemplateSelector

logger = logging.getLogger(__name__)


# ── SmallWebRTC Transport ───────────────────────────────────

class SmallWebRTCTransport:
    """Pipecat transport adapter for SmallWebRTC signaling server.

    Provides the input/output frame processors for WebRTC-based
    audio streaming via the SmallWebRTC signaling server.

    In production, replace with DailyTransport from pipecat-ai.
    """

    def __init__(
        self,
        room_url: str,
        token: str,
        bot_name: str = "Memory Game Host",
        params: Optional[TransportParams] = None,
    ) -> None:
        self.room_url = room_url
        self.token = token
        self.bot_name = bot_name
        self.params = params or TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
        )
        self._turn_analyzer: Optional[LocalSmartTurnAnalyzerV3] = None
        self._stop_secs: float = 0.5

    def use_smart_turn(
        self,
        turn_analyzer: Optional[LocalSmartTurnAnalyzerV3] = None,
        stop_secs: float = 0.5,
    ) -> None:
        """Configure SmartTurn for turn-end detection."""
        self._turn_analyzer = turn_analyzer or LocalSmartTurnAnalyzerV3()
        self._stop_secs = stop_secs

    def input(self) -> Any:
        """Return the input frame processor for the pipeline.

        TODO: Replace with actual Pipecat transport input that connects
        to the SmallWebRTC signaling server. For production, use
        DailyTransport from pipecat-ai.

        Refer to Pipecat transport documentation for the appropriate
        transport adapter.
        """
        raise NotImplementedError(
            "SmallWebRTCTransport requires a Pipecat transport adapter. "
            "See Pipecat docs for creating custom transports or use "
            "DailyTransport for production."
        )

    def output(self) -> Any:
        """Return the output frame processor for the pipeline.

        TODO: Replace with actual Pipecat transport output that sends
        audio to the SmallWebRTC signaling server.
        """
        raise NotImplementedError(
            "SmallWebRTCTransport requires a Pipecat transport adapter. "
            "See Pipecat docs for creating custom transports or use "
            "DailyTransport for production."
        )


# ── Pipeline Assembly ───────────────────────────────────────

async def create_and_run_bot(
    session_id: str,
    player_name: str = "Player",
    room_url: Optional[str] = None,
    room_token: Optional[str] = None,
    deepgram_api_key: Optional[str] = None,
    max_rounds: int = 10,
    game_cache: Optional[GameCache] = None,
) -> None:
    """Create and run a Pipecat voice bot for a game session.

    This is the main entrypoint that:
    1. Sets up the WebRTC transport with VAD and turn detection
    2. Initializes Deepgram STT and TTS services
    3. Creates the MemoryGameProcessor with game state
    4. Assembles and runs the Pipecat pipeline

    Args:
        session_id: UUID of the game session.
        player_name: Player's display name.
        room_url: SmallWebRTC room URL for the transport.
        room_token: Room access token.
        deepgram_api_key: Deepgram API key (defaults to env var).
        max_rounds: Maximum number of game rounds.
        game_cache: Cache instance (defaults to singleton).
    """
    api_key = deepgram_api_key or settings.DEEPGRAM_API_KEY
    if not api_key:
        raise ValueError(
            "DEEPGRAM_API_KEY is required. Set it in your .env file or "
            "pass it as deepgram_api_key argument."
        )

    game_cache = game_cache or cache

    # ── Resolve room URL ────────────────────────────────────────
    resolved_room_url = room_url or "http://localhost:3001/default-room"
    resolved_token = room_token or "placeholder-token"

    logger.info(
        "Starting bot for session %s (player: %s, max_rounds: %d)",
        session_id,
        player_name,
        max_rounds,
    )

    # ── Transport ───────────────────────────────────────────────
    transport = SmallWebRTCTransport(
        room_url=resolved_room_url,
        token=resolved_token,
        bot_name=settings.BOT_NAME,
    )

    # Configure SmartTurn for natural turn-end detection
    transport.use_smart_turn(
        turn_analyzer=LocalSmartTurnAnalyzerV3(),
        stop_secs=0.5,
    )

    # ── STT Service ─────────────────────────────────────────────
    stt = DeepgramSTTService(
        api_key=api_key,
        model="nova-2",
        # Sample rate matches the transport configuration
        sample_rate=16000,
    )

    # ── TTS Service ─────────────────────────────────────────────
    tts = DeepgramTTSService(
        api_key=api_key,
        voice="aura-asteria-en",  # Friendly, energetic female voice
        sample_rate=16000,
    )

    # ── Prompt Template Selector ─────────────────────────────────
    prompt_selector = PromptTemplateSelector()

    # ── Game State ──────────────────────────────────────────────
    game_data = GameData(
        session_id=uuid.UUID(session_id),
        player_name=player_name,
        max_rounds=max_rounds,
    )

    # ── Get DB Session ──────────────────────────────────────────
    from app.db.database import async_session_factory

    async with async_session_factory() as db_session:
        # ── Game Processor ───────────────────────────────────────
        game_processor = MemoryGameProcessor(
            game=game_data,
            db_session=db_session,
            cache=game_cache,
            prompt_selector=prompt_selector,
            max_rounds=max_rounds,
        )

        # ── Assemble Pipeline ────────────────────────────────────
        # Order: input audio → STT → game processor → TTS → output audio
        pipeline = Pipeline([
            transport.input(),
            stt,
            game_processor,
            tts,
            transport.output(),
        ])

        # ── Create and Run Task ──────────────────────────────────
        runner = PipelineRunner()

        task = PipelineTask(pipeline)

        logger.info(
            "Bot pipeline assembled and starting — room: %s",
            resolved_room_url,
        )

        try:
            await runner.run(task)
        except asyncio.CancelledError:
            logger.info("Bot task cancelled")
        except NotImplementedError:
            raise
        except Exception:
            logger.exception("Bot pipeline error")
        finally:
            logger.info("Bot pipeline stopped")

            # Commit any pending database changes
            try:
                await db_session.commit()
            except Exception:
                await db_session.rollback()
                logger.exception("Failed to commit session data")

            # Update session status to interrupted if still active
            if game_data.is_active:
                logger.info(
                    "Session %s ended with status: %s",
                    session_id,
                    game_data.state.value,
                )


# ── CLI Entrypoint ──────────────────────────────────────────

def main() -> None:
    """CLI entrypoint for running the bot standalone."""
    parser = argparse.ArgumentParser(
        description="The Memory Host — Voice Bot",
    )
    parser.add_argument(
        "--session-id",
        required=True,
        help="UUID of the game session",
    )
    parser.add_argument(
        "--room-url",
        required=True,
        help="SmallWebRTC room URL to connect to",
    )
    parser.add_argument(
        "--token",
        default="placeholder-token",
        help="Room access token",
    )
    parser.add_argument(
        "--player-name",
        default="Player",
        help="Player's display name",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=settings.MAX_ROUNDS,
        help="Maximum number of game rounds",
    )
    parser.add_argument(
        "--log-level",
        default=settings.LOG_LEVEL,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    asyncio.run(
        create_and_run_bot(
            session_id=args.session_id,
            player_name=args.player_name,
            room_url=args.room_url,
            room_token=args.token,
            max_rounds=args.max_rounds,
        )
    )


if __name__ == "__main__":
    main()
