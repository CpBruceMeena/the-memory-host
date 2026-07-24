"use client";

import { useEffect, useRef, useState } from "react";

interface WebRTCRoomProps {
  /** SmallWebRTC room URL (from the backend). */
  roomUrl: string;
  /** Room access token. */
  token: string;
}

/**
 * WebRTC audio component for connecting to the SmallWebRTC room.
 *
 * This is a client-only component that:
 * 1. Creates a WebRTC peer connection with STUN server
 * 2. Connects to the signaling server via WebSocket
 * 3. Receives audio tracks from the bot and plays them
 *
 * For production, replace with the Daily.co client (@daily-co/daily-js).
 */
export function WebRTCRoom({ roomUrl, token }: WebRTCRoomProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const peerRef = useRef<RTCPeerConnection | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<
    "connecting" | "connected" | "error" | "disconnected"
  >("connecting");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!roomUrl) return;

    let cancelled = false;

    const initWebRTC = async () => {
      try {
        // Extract WebSocket URL from the room URL
        const wsUrl = roomUrl.replace(/^http/, "ws");
        setStatus("connecting");

        // Create RTCPeerConnection with Google's public STUN server
        const pc = new RTCPeerConnection({
          iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
        });
        peerRef.current = pc;

        // When a remote track is received, attach it to the audio element
        pc.ontrack = (event) => {
          if (cancelled) return;
          if (event.track.kind === "audio" && audioRef.current) {
            const stream = new MediaStream([event.track]);
            audioRef.current.srcObject = stream;
            setStatus("connected");
          }
        };

        // Log ICE connection state changes
        pc.oniceconnectionstatechange = () => {
          if (cancelled) return;
          if (
            pc.iceConnectionState === "disconnected" ||
            pc.iceConnectionState === "failed"
          ) {
            setStatus("disconnected");
          }
        };

        // Connect to the SmallWebRTC signaling server via WebSocket
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          if (cancelled) return;

          // Send authentication with token
          ws.send(
            JSON.stringify({
              type: "join",
              token: token,
              kind: "receiver",
            })
          );
        };

        ws.onmessage = async (event) => {
          if (cancelled) return;

          try {
            const msg = JSON.parse(event.data);

            if (msg.type === "offer" && pc) {
              await pc.setRemoteDescription(
                new RTCSessionDescription(msg.sdp)
              );

              const answer = await pc.createAnswer();
              await pc.setLocalDescription(answer);

              ws.send(
                JSON.stringify({
                  type: "answer",
                  sdp: pc.localDescription,
                })
              );
            } else if (msg.type === "ice-candidate" && pc && msg.candidate) {
              await pc.addIceCandidate(new RTCIceCandidate(msg.candidate));
            }
          } catch (err) {
            console.error("WebRTC signaling error:", err);
          }
        };

        ws.onerror = () => {
          if (cancelled) return;
          setStatus("error");
          setErrorMsg("WebSocket connection error");
        };

        ws.onclose = () => {
          if (cancelled) return;
          setStatus("disconnected");
        };
      } catch (err) {
        if (cancelled) return;
        console.error("WebRTC initialization error:", err);
        setStatus("error");
        setErrorMsg(
          err instanceof Error ? err.message : "Failed to initialize WebRTC"
        );
      }
    };

    initWebRTC();

    return () => {
      cancelled = true;
      wsRef.current?.close();
      peerRef.current?.close();
    };
  }, [roomUrl, token]);

  return (
    <div className="glass rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Voice Connection
        </h3>
        <StatusBadge status={status} />
      </div>

      {/* Hidden audio element for bot's voice */}
      <audio ref={audioRef} autoPlay className="hidden" />

      {status === "error" && errorMsg && (
        <div className="px-4 py-3 rounded-xl bg-red-900/20 border border-red-800/30 text-sm text-red-400">
          {errorMsg}
        </div>
      )}

      {status === "connected" && (
        <div className="text-center py-6">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-green-900/20 border border-green-800/30 text-sm text-green-400">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            Connected — listening for voice
          </div>
          <p className="text-xs text-gray-500 mt-3">
            The Memory Host bot will speak through this connection.
            Make sure your microphone is enabled.
          </p>
        </div>
      )}

      {status === "connecting" && (
        <div className="text-center py-6">
          <div className="inline-flex items-center gap-2 text-sm text-gray-400">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Connecting to voice room...
          </div>
        </div>
      )}

      {status === "disconnected" && (
        <div className="text-center py-6">
          <p className="text-sm text-yellow-400">
            Voice connection disconnected.
          </p>
        </div>
      )}
    </div>
  );
}

function StatusBadge({
  status,
}: {
  status: "connecting" | "connected" | "error" | "disconnected";
}) {
  const config: Record<string, { color: string; label: string }> = {
    connecting: {
      color: "bg-yellow-900/30 text-yellow-400 border-yellow-800/30",
      label: "Connecting",
    },
    connected: {
      color: "bg-green-900/30 text-green-400 border-green-800/30",
      label: "Connected",
    },
    error: {
      color: "bg-red-900/30 text-red-400 border-red-800/30",
      label: "Error",
    },
    disconnected: {
      color: "bg-gray-800/30 text-gray-400 border-gray-700/30",
      label: "Disconnected",
    },
  };

  const c = config[status];
  return (
    <span
      className={`px-2.5 py-1 rounded-full text-xs font-medium border ${c.color}`}
    >
      {c.label}
    </span>
  );
}

/**
 * SSR-safe dynamic import wrapper.
 *
 * Usage in a page:
 * ```tsx
 * import dynamic from "next/dynamic";
 * const WebRTCRoom = dynamic(() => import("@/components/WebRTCRoom").then(m => m.WebRTCRoom), {
 *   ssr: false,
 *   loading: () => <LoadingSkeleton variant="card" />,
 * });
 * ```
 *
 * The `ssr: false` ensures the WebRTC code only runs in the browser.
 */
