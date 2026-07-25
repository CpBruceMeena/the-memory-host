"""Pipecat voice bot entrypoint for The Memory Host — Game Engine Service.

Assembles the Pipecat pipeline:
    SmallWebRTCTransport -> Deepgram STT -> MemoryGameProcessor -> Deepgram TTS -> Output

Uses Pipecat's built-in SmallWebRTCTransport with a WebSocket-based signaling
server for SDP offer/answer exchange and ICE candidate negotiation.

Environment Variables:
    DEEPGRAM_API_KEY           Required for STT/TTS
    SMALLWEBRTC_SERVER_URL     Signaling server URL (default: ws://localhost:3001)
    BOT_NAME                   Bot display name (default: "Memory Game Host")
    MAX_ROUNDS                 Max game rounds (default: 10)
    LOG_LEVEL                  Logging level (default: INFO)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import uuid
from typing import Any, Optional

import aiohttp
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import (
    IceServer,
    SmallWebRTCConnection,
)
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

from app.core.cache import GameCache, cache
from app.core.config import settings
from app.services.custom_tts import SlowerDeepgramTTSService
from app.services.game_processor import MemoryGameProcessor
from app.services.game_state import GameData
from app.services.prompt_templates import PromptTemplateSelector

logger = logging.getLogger(__name__)


# ── WebSocket Signaling Client ─────────────────────────────

class SignalingClient:
    """WebSocket signaling client for SDP exchange with the frontend.

    Connects to a signaling server (SmallWebRTC or custom) to:
    1. Register this bot as a participant
    2. Receive SDP offers from connecting clients
    3. Send SDP answers back
    4. Exchange ICE candidates between peers
    """

    def __init__(
        self,
        server_url: str,
        room_name: str,
        webrtc_connection: SmallWebRTCConnection,
        game_data: Any = None,
    ) -> None:
        self.server_url = server_url
        self.room_name = room_name
        self.webrtc_connection = webrtc_connection
        self.game_data = game_data
        self._ws: Any = None
        self._connected = asyncio.Event()
        self._peer_connected = asyncio.Event()
        self._ice_candidates: list[dict[str, Any]] = []

    async def connect(self, max_retries: int = 5) -> None:
        """Connect to the signaling server via WebSocket.

        Retries with exponential backoff (0.5s, 1s, 2s, 4s, ... up to ~8.5s max)
        so the bot survives the signaling server starting a few seconds late.

        Args:
            max_retries: Maximum number of connection attempts.

        Raises:
            ConnectionRefusedError: If all retries are exhausted.
        """
        import websockets

        ws_url = self.server_url.replace("http://", "ws://").replace(
            "https://", "wss://"
        )
        ws_url = f"{ws_url}/room/{self.room_name}"

        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    "Connecting to signaling server (attempt %d/%d): %s",
                    attempt, max_retries, self.server_url,
                )
                self._ws = await websockets.connect(ws_url)
                self._connected.set()
                logger.info("Connected to signaling server")
                return
            except (OSError, websockets.WebSocketException) as e:
                last_error = e
                if attempt < max_retries:
                    delay = min(0.5 * (2 ** (attempt - 1)), 8.5)
                    logger.warning(
                        "Signaling server not ready (attempt %d/%d), "
                        "retrying in %.1fs: %s",
                        attempt, max_retries, delay, e,
                    )
                    await asyncio.sleep(delay)

        raise ConnectionRefusedError(
            f"Could not connect to signaling server at {self.server_url} "
            f"after {max_retries} attempts. Last error: {last_error}"
        )

    async def negotiate(self) -> None:
        """Handle the full SDP negotiation lifecycle.

        1. Send bot identity via 'join' message
        2. Wait for client to connect (signaling sends the SDP offer)
        3. Set remote description via SmallWebRTCConnection.initialize()
        4. Send SDP answer back
        5. Exchange ICE candidates until connected
        """
        if not self._ws:
            raise RuntimeError("Not connected to signaling server")

        # Register as bot participant
        await self._send({"type": "join", "kind": "bot", "room": self.room_name})

        logger.info("Waiting for client to connect and send SDP offer...")

        # Listen for messages from the signaling server
        async for message in self._ws:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "offer":
                # Client SDP offer received — initialize the connection
                logger.info("Received SDP offer from client — initializing")
                sdp_str = data.get("sdp", data.get("data", ""))
                if isinstance(sdp_str, dict):
                    # Handle both plain SDP string and {sdp, type} object form
                    sdp_str = sdp_str.get("sdp", "")

                # SmallWebRTCConnection.initialize() sets remote description,
                # creates an answer, and stores it in self._answer
                await self.webrtc_connection.initialize(sdp_str, "offer")

                # Extract the answer SDP string from the connection
                answer = self.webrtc_connection.get_answer()
                answer_sdp = answer.get("sdp", "") if answer else ""
                await self._send({"type": "answer", "sdp": answer_sdp})
                logger.info("Sent SDP answer to client")

                # Send any queued ICE candidates
                for candidate in self._ice_candidates:
                    await self._send(
                        {"type": "ice-candidate", "candidate": candidate}
                    )

                self._peer_connected.set()

            elif msg_type == "ice-candidate":
                # ICE candidate from client — add to connection
                candidate = data.get("candidate", data)
                if candidate:
                    await self.webrtc_connection.add_ice_candidate(candidate)

            elif msg_type == "user_done":
                # Push-to-talk released — signal the game processor
                logger.info("Received user_done signal — flagging for validation")
                if self.game_data and hasattr(self.game_data, "user_done_event"):
                    self.game_data.user_done_event.set()

            elif msg_type == "peer_disconnected":
                logger.info("Peer disconnected from room")
                break

    async def _send(self, data: dict[str, Any]) -> None:
        """Send a JSON message over the WebSocket."""
        if self._ws:
            await self._ws.send(json.dumps(data))

    async def wait_for_peer(self, timeout: float = 30.0) -> None:
        """Wait for a peer to connect via the signaling server.

        Args:
            timeout: Maximum time to wait in seconds.

        Raises:
            asyncio.TimeoutError: If no peer connects within the timeout.
        """
        await asyncio.wait_for(self._peer_connected.wait(), timeout=timeout)

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None
            self._connected.clear()


# ── Pipeline Assembly ───────────────────────────────────────

async def create_and_run_bot(
    session_id: str,
    player_name: str = "Player",
    room_url: Optional[str] = None,
    deepgram_api_key: Optional[str] = None,
    max_rounds: int = 10,
    game_cache: Optional[GameCache] = None,
) -> None:
    """Create and run a Pipecat voice bot for a game session.

    This is the main entrypoint that:
    1. Sets up a WebRTC connection with STUN/TURN ICE servers
    2. Connects to the signaling server for SDP exchange
    3. Initializes Deepgram STT and TTS services
    4. Creates the MemoryGameProcessor with game state
    5. Assembles and runs the Pipecat pipeline

    Args:
        session_id: UUID of the game session.
        player_name: Player's display name.
        room_url: WebSocket signaling server URL.
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

    # ── Resolve signaling URL ───────────────────────────────────
    signaling_url = room_url or settings.SMALLWEBRTC_SERVER_URL
    room_name = f"memory-game-{session_id[:8]}"

    logger.info(
        "Starting bot for session %s (player: %s, max_rounds: %d, signaling: %s)",
        session_id,
        player_name,
        max_rounds,
        signaling_url,
    )

    # ── WebRTC Connection ───────────────────────────────────────
    webrtc_connection = SmallWebRTCConnection(
        ice_servers=[
            IceServer(urls=["stun:stun.l.google.com:19302"]),
        ]
    )

    # ── Game State ──────────────────────────────────────────────
    game_data = GameData(
        session_id=uuid.UUID(session_id),
        player_name=player_name,
        max_rounds=max_rounds,
    )

    # ── Signaling Client ────────────────────────────────────────
    signaling = SignalingClient(
        server_url=signaling_url,
        room_name=room_name,
        webrtc_connection=webrtc_connection,
        game_data=game_data,
    )

    # Connect to signaling server and exchange SDP
    await signaling.connect()

    # ── Transport ───────────────────────────────────────────────
    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(
                    confidence=0.5,   # Lower threshold → catches quieter speech
                    start_secs=0.3,   # Slightly longer start to avoid clipping
                    stop_secs=0.5,    # Longer stop to avoid cutting off mid-sentence
                    min_volume=0.3,   # Lower volume threshold → catches softer voices
                ),
            ),
            vad_audio_passthrough=True,
        ),
    )

    # ── STT Service ─────────────────────────────────────────────
    stt = DeepgramSTTService(
        api_key=api_key,
        model="nova-2",
        sample_rate=16000,
    )

    # ── TTS Service ─────────────────────────────────────────────
    # Use SlowerDeepgramTTSService (HTTP-based) with speed=0.8 to
    # make the bot speak 20% slower. The `speed` parameter requires
    # an Aura 2 model (aura-2-*). First-gen Aura models like
    # aura-luna-en don't support speed control.
    http_session = aiohttp.ClientSession()
    tts = SlowerDeepgramTTSService(
        api_key=api_key,
        aiohttp_session=http_session,
        voice="aura-2-pandora-en",  # British English (closest available to Indian English)
        sample_rate=16000,
        speed=0.9,
    )

    # ── Prompt Template Selector ─────────────────────────────────
    prompt_selector = PromptTemplateSelector()

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
            "Bot pipeline assembled, negotiating WebRTC connection..."
        )

        # Start SDP negotiation in the background
        negotiate_task = asyncio.create_task(signaling.negotiate())

        try:
            # Wait for peer to connect before starting pipeline
            await signaling.wait_for_peer(timeout=30.0)
            logger.info("WebRTC peer connected — starting pipeline")

            await runner.run(task)

        except asyncio.TimeoutError:
            logger.error("Timed out waiting for peer to connect")
        except asyncio.CancelledError:
            logger.info("Bot task cancelled")
        except Exception:
            logger.exception("Bot pipeline error")
        finally:
            logger.info("Bot pipeline stopped")

            # Cancel SDP negotiation if still running
            negotiate_task.cancel()
            try:
                await negotiate_task
            except asyncio.CancelledError:
                pass
            await signaling.close()

            # Close the aiohttp session to free connector resources
            await http_session.close()

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
        default=settings.SMALLWEBRTC_SERVER_URL,
        help="WebSocket signaling server URL (default: from env or ws://localhost:3001)",
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
            max_rounds=args.max_rounds,
        )
    )


if __name__ == "__main__":
    main()
