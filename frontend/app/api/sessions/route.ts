import { NextRequest, NextResponse } from "next/server";

import { createSession } from "@/lib/api";

/**
 * POST /api/sessions
 *
 * BFF proxy: creates a new game session on the backend.
 * Request body: { player_name: string }
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { player_name } = body;

    if (!player_name || typeof player_name !== "string" || !player_name.trim()) {
      return NextResponse.json(
        { detail: "player_name is required" },
        { status: 400 }
      );
    }

    const result = await createSession(player_name.trim());
    return NextResponse.json(result, { status: 201 });
  } catch (error) {
    console.error("Failed to create session:", error);
    const message =
      error instanceof Error ? error.message : "Internal server error";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}
