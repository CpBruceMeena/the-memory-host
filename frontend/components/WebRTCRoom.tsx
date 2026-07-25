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
            const stream = audioRef.current.srcObject;
            if (stream instanceof MediaStream) {
              // Add new track to existing stream
              stream.addTrack(event.track);
            } else {
              const newStream = new MediaStream([event.track]);
              audioRef.current.srcObject = newStream;
            }
            setStatus("connected");
          }
        };

        // Create a data channel so the bot's data channel can negotiate
        // properly. Without this, the SDP offer won't include a data m=
        // section, and the bot's data channel never opens.
        const dc = pc.createDataChannel("game");

        dc.onopen = () => console.log("Client data channel opened");
        dc.onmessage = (event) => console.log("Client data channel message:", event.data);

        // Listen for the bot's data channel (created by SmallWebRTCTransport
        // on the bot side). The bot sends game state updates (round info,
        // scores, status) through its own data channel, which fires this
        // ondatachannel event on our peer connection.
        pc.ondatachannel = (event) => {
          const botChannel = event.channel;
          console.log("Bot data channel received:", botChannel.label);
          botChannel.onmessage = (msgEvent) => {
            try {
              const data = JSON.parse(msgEvent.data);
              console.log("Bot app message:", data);
            } catch {
              console.log("Bot data channel message:", msgEvent.data);
            }
          };
          botChannel.onopen = () => console.log("Bot data channel opened");
        };

        // First, create an explicit sendrecv transceiver so the SDP offer
        // signals that we want to both SEND audio (user → bot for STT) and
        // RECEIVE audio (bot → user for TTS). Without this explicit direction,
        // the offer defaults to sendonly and the bot won't send audio back.
        pc.addTransceiver("audio", { direction: "sendrecv" });

        // Capture the user's microphone and add the track to the existing
        // transceiver. addTrack() on a connection with an existing audio
        // transceiver reuses that transceiver (does NOT create a new one).
        const userStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
        for (const track of userStream.getAudioTracks()) {
          pc.addTrack(track, userStream);
        }

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

        // Timeout: if no signaling message arrives within 15 seconds
        // after the WebSocket opens, the bot probably never joined.
        let signalingTimeout: ReturnType<typeof setTimeout> | null = null;

        const startSignalingTimeout = () => {
          signalingTimeout = setTimeout(() => {
            if (cancelled) return;
            setStatus("error");
            setErrorMsg(
              "The game bot didn't join the voice room. " +
              "Check that the backend server is running " +
              "and DEEPGRAM_API_KEY is set in .env"
            );
            // Don't close ws/pc here — the cleanup return function
            // handles disconnection when the component unmounts.
            // Closing here would trigger onclose/oniceconnectionstatechange
            // which would override the "error" state we just set.
          }, 15_000);
        };

        const clearSignalingTimeout = () => {
          if (signalingTimeout !== null) {
            clearTimeout(signalingTimeout);
            signalingTimeout = null;
          }
        };

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

          // Start the timeout — bot should respond within 15s
          startSignalingTimeout();
        };

        ws.onmessage = async (event) => {
          if (cancelled) return;

          // Any message from signaling means the bot is alive
          clearSignalingTimeout();

          try {
            const msg = JSON.parse(event.data);

            if (msg.type === "create_offer" && pc) {
              // Signaling server tells us (the client) to create an SDP offer
              console.log("Creating SDP offer...");
              const offer = await pc.createOffer();
              await pc.setLocalDescription(offer);

              ws.send(
                JSON.stringify({
                  type: "offer",
                  sdp: pc.localDescription,
                })
              );
              console.log("Sent SDP offer to signaling server");
            } else if (msg.type === "answer" && pc) {
              // Bot's SDP answer received — set as remote description
              // RTCSessionDescription expects { type, sdp }, not a raw SDP string
              await pc.setRemoteDescription(
                new RTCSessionDescription({
                  type: "answer",
                  sdp: msg.sdp,
                })
              );
              console.log("SDP answer set — waiting for audio track...");
            } else if (msg.type === "ice-candidate" && pc && msg.candidate) {
              await pc.addIceCandidate(new RTCIceCandidate(msg.candidate));
            }
          } catch (err) {
            console.error("WebRTC signaling error:", err);
          }
        };

        ws.onerror = () => {
          if (cancelled) return;
          clearSignalingTimeout();
          // onerror fires first, then onclose follows — defer to onclose
          // for the actual error message since it carries the close code
          setStatus("error");
        };

        ws.onclose = (event) => {
          if (cancelled) return;
          clearSignalingTimeout();
          // Close code 1006 = abnormal closure (server not reachable)
          if (event.code === 1006) {
            setStatus("error");
            setErrorMsg(
              "Could not connect to the voice room. " +
              "Make sure the backend server is running on port 8000"
            );
          } else {
            setStatus("disconnected");
          }
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
