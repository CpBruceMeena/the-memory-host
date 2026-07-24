#!/usr/bin/env python3
"""
signaling_server.py — SmallWebRTC WebSocket signaling server.

Relays SDP offers/answers and ICE candidates between bot and client peers
that join the same room. Each room needs exactly two peers (bot + client)
to establish a WebRTC connection.

Protocol:
  1. Peer connects to ws://<host>:<port>/room/<room_name>
  2. Peer sends {"type": "join", "kind": "bot"|"receiver", ...}
  3. When two peers are in a room, signaling tells the client to create
     an SDP offer ({"type": "create_offer"})
  4. Client sends {"type": "offer", "sdp": ...}
  5. Signaling relays offer to bot
  6. Bot sends {"type": "answer", "sdp": ...}
  7. Signaling relays answer to client
  8. ICE candidates are relayed bidirectionally
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any

import websockets

logger = logging.getLogger("signaling")


# ── Room Manager ─────────────────────────────────────────────

class Room:
    """A signaling room holding two peer WebSocket connections."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.bot_ws: websockets.WebSocketServerProtocol | None = None
        self.client_ws: websockets.WebSocketServerProtocol | None = None

    @property
    def is_full(self) -> bool:
        return self.bot_ws is not None and self.client_ws is not None

    @property
    def peer_count(self) -> int:
        return (1 if self.bot_ws else 0) + (1 if self.client_ws else 0)

    def add_peer(
        self, ws: websockets.WebSocketServerProtocol, kind: str
    ) -> None:
        if kind == "bot":
            self.bot_ws = ws
        else:
            self.client_ws = ws
        logger.info("Peer '%s' joined room '%s' (%d/%d)", kind, self.name, self.peer_count, 2)

    def remove_peer(
        self, ws: websockets.WebSocketServerProtocol
    ) -> str | None:
        """Remove a peer and return the kind ('bot' or 'receiver')."""
        if ws == self.bot_ws:
            self.bot_ws = None
            return "bot"
        if ws == self.client_ws:
            self.client_ws = None
            return "receiver"
        return None

    def get_other(
        self, ws: websockets.WebSocketServerProtocol
    ) -> websockets.WebSocketServerProtocol | None:
        """Get the other peer's WebSocket, or None."""
        if ws == self.bot_ws:
            return self.client_ws
        if ws == self.client_ws:
            return self.bot_ws
        return None


class RoomManager:
    """Manages all active signaling rooms."""

    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}

    def get_or_create(self, name: str) -> Room:
        if name not in self._rooms:
            self._rooms[name] = Room(name)
        return self._rooms[name]

    def remove_if_empty(self, name: str) -> None:
        room = self._rooms.get(name)
        if room and room.peer_count == 0:
            del self._rooms[name]
            logger.info("Removed empty room '%s'", name)


# ── WebSocket Handler ───────────────────────────────────────

rooms = RoomManager()


async def handle_connection(
    ws: websockets.WebSocketServerProtocol,
) -> None:
    """Handle a single WebSocket connection lifecycle."""

    # Extract room name from path: /room/<room_name>
    path = getattr(ws, "path", None)
    if path is None:
        path = getattr(getattr(ws, "request", None), "path", "/")
    room_name = "default"
    if "/room/" in path:
        room_name = path.split("/room/", 1)[1].split("/")[0].strip()

    room = rooms.get_or_create(room_name)
    peer_kind: str | None = None

    try:
        # Peers must send an initial 'join' message
        async for message in ws:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from %s: %s", peer_kind, message[:100])
                continue

            msg_type = data.get("type")

            if msg_type == "join":
                kind = data.get("kind", "receiver")
                peer_kind = kind
                room.add_peer(ws, kind)

                # When both peers are in the room, signal the client
                # to create an SDP offer (bot is always the answerer)
                if room.is_full:
                    logger.info(
                        "Room '%s' is full — signaling client to create offer",
                        room_name,
                    )
                    if room.client_ws:
                        await safe_send(
                            room.client_ws,
                            {"type": "create_offer"},
                        )

            elif msg_type == "offer":
                # Client sent an SDP offer — relay to bot
                logger.info("Received SDP offer in room '%s' — relaying to bot", room_name)
                other = room.get_other(ws)
                if other:
                    await safe_send(other, {"type": "offer", "sdp": data.get("sdp")})

            elif msg_type == "answer":
                # Bot sent an SDP answer — relay to client
                logger.info(
                    "Received SDP answer in room '%s' — relaying to client", room_name
                )
                other = room.get_other(ws)
                if other:
                    await safe_send(other, {"type": "answer", "sdp": data.get("sdp")})

            elif msg_type == "ice-candidate":
                # ICE candidate — relay to other peer
                other = room.get_other(ws)
                if other:
                    await safe_send(
                        other,
                        {"type": "ice-candidate", "candidate": data.get("candidate")},
                    )

            else:
                logger.debug("Unknown message type '%s' from %s", msg_type, peer_kind)

    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket connection closed in room '%s'", room_name)
    except Exception:
        logger.exception("Error in room '%s'", room_name)
    finally:
        # Clean up disconnected peer
        if peer_kind:
            room.remove_peer(ws)
            other = room.get_other(ws)
            if other:
                await safe_send(other, {"type": "peer_disconnected"})

            room.remove_if_empty(room_name)


async def safe_send(
    ws: websockets.WebSocketServerProtocol | None,
    data: dict[str, Any],
) -> None:
    """Send a JSON message to a WebSocket if it's still open."""
    if ws is None:
        return
    try:
        await ws.send(json.dumps(data))
    except websockets.exceptions.ConnectionClosed:
        pass


# ── Entrypoint ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="SmallWebRTC Signaling Server")
    parser.add_argument("--host", default="0.0.0.0", help="Listen host")
    parser.add_argument("--port", type=int, default=3001, help="Listen port")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info(
        "Starting signaling server on ws://%s:%d", args.host, args.port
    )

    async def serve() -> None:
        async with websockets.serve(handle_connection, args.host, args.port):
            await asyncio.Future()  # Run forever

    asyncio.run(serve())


if __name__ == "__main__":
    main()
