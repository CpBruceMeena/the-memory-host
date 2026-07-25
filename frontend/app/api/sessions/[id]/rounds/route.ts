import { NextRequest, NextResponse } from "next/server";

import { getSessionRounds } from "@/lib/api";

/**
 * GET /api/sessions/[id]/rounds
 *
 * BFF proxy: fetches round history for a game session from the backend.
 */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    if (!id) {
      return NextResponse.json(
        { detail: "Session ID is required" },
        { status: 400 }
      );
    }

    const result = await getSessionRounds(id);
    return NextResponse.json(result);
  } catch (error) {
    console.error("Failed to fetch rounds:", error);
    const message =
      error instanceof Error ? error.message : "Internal server error";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}
