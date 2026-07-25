"""Custom Deepgram TTS service with speed control.

Uses Pipecat's DeepgramHttpTTSService (HTTP-based) instead of the
WebSocket-based DeepgramTTSService, because the `speed` query parameter
is only supported on Deepgram's HTTP /v1/speak endpoint — the WebSocket
endpoint rejects it with HTTP 400.

The HTTP service streams audio chunks as they arrive from Deepgram
(yields TTSAudioRawFrame progressively), so the latency impact vs
WebSocket is minimal (~200-500ms TTFB difference).

Speed range supported by Deepgram: 0.7 (slowest) to 1.5 (fastest).

Usage:
    import aiohttp

    async with aiohttp.ClientSession() as session:
        tts = SlowerDeepgramTTSService(
            api_key=api_key,
            aiohttp_session=session,
            voice="aura-luna-en",
            sample_rate=16000,
            speed=0.8,   # 20% slower than normal
        )
"""

from __future__ import annotations

import logging
from typing import Optional

import aiohttp

from pipecat.services.deepgram.tts import DeepgramHttpTTSService

logger = logging.getLogger(__name__)


class SlowerDeepgramTTSService(DeepgramHttpTTSService):
    """Deepgram HTTP TTS with configurable speed.

    Extends DeepgramHttpTTSService to pass the `speed` query parameter
    (0.7–1.5) when calling the HTTP TTS API. Values below 1.0 slow
    down the speaking rate.
    """

    def __init__(
        self,
        *,
        api_key: str,
        aiohttp_session: aiohttp.ClientSession,
        voice: Optional[str] = None,
        base_url: str = "https://api.deepgram.com",
        sample_rate: Optional[int] = None,
        encoding: str = "linear16",
        mip_opt_out: Optional[bool] = None,
        speed: float = 1.0,
        **kwargs,
    ):
        """Initialize the slower Deepgram HTTP TTS service.

        Args:
            api_key: Deepgram API key.
            aiohttp_session: Shared aiohttp session for HTTP requests.
            voice: Voice model to use (e.g. "aura-luna-en").
            base_url: HTTP base URL for Deepgram API.
            sample_rate: Audio sample rate in Hz.
            encoding: Audio encoding format (default "linear16").
            mip_opt_out: Opt out of Deepgram's Model Improvement Program.
            speed: Speaking rate multiplier (0.7–1.5). 0.8 = 20% slower.
            **kwargs: Passed to parent DeepgramHttpTTSService.
        """
        self._speed = max(0.7, min(1.5, speed))  # Clamp to valid range
        logger.info(
            "SlowerDeepgramTTSService initialized — speed=%.1f (voice=%s)",
            self._speed,
            voice or "aura-2-pandora-en",
        )
        super().__init__(
            api_key=api_key,
            aiohttp_session=aiohttp_session,
            voice=voice,
            base_url=base_url,
            sample_rate=sample_rate,
            encoding=encoding,
            mip_opt_out=mip_opt_out,
            **kwargs,
        )

    async def run_tts(self, text: str, context_id: str):
        """Generate speech with a controlled speaking rate.

        Builds the same request as the parent DeepgramHttpTTSService
        but adds the `speed` query parameter to control the rate.
        """
        # Build URL
        url = f"{self._base_url}/v1/speak"

        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "application/json",
        }

        params = {
            "model": self._settings.voice,
            "encoding": self._encoding,
            "sample_rate": self.sample_rate,
            "container": "none",
            "speed": str(self._speed),  # Deepgram speed parameter (0.7–1.5)
        }

        if self._mip_opt_out is not None:
            params["mip_opt_out"] = str(self._mip_opt_out).lower()

        payload = {"text": text}

        try:
            await self.start_ttfb_metrics()

            from pipecat.frames.frames import ErrorFrame, TTSAudioRawFrame

            async with self._session.post(
                url, headers=headers, json=payload, params=params
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Deepgram TTS HTTP {response.status} (speed={self._speed}): "
                        f"{error_text}"
                    )

                await self.start_tts_usage_metrics(text)

                CHUNK_SIZE = self.chunk_size
                first_chunk = True
                async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                    if first_chunk:
                        await self.stop_ttfb_metrics()
                        first_chunk = False

                    if chunk:
                        yield TTSAudioRawFrame(
                            audio=chunk,
                            sample_rate=self.sample_rate,
                            num_channels=1,
                            context_id=context_id,
                        )

        except Exception as e:
            from pipecat.frames.frames import ErrorFrame

            logger.error("Deepgram HTTP TTS error (speed=%.1f): %s", self._speed, e)
            yield ErrorFrame(f"Error getting audio: {str(e)}")
