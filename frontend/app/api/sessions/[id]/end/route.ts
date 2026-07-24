import { NextRequest, NextResponse } from "next/server";

import { endSession } from "@/lib/api";

/**
 * POST /api/sessions/[id]/end
 *
 * BFF proxy: ends a game session on the backend.
 * Request body (optional): { reason?: string }
 */
export async function POST(
  request: NextRequest,
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

    const body = await request.json().catch(() => ({}));
    const result = await endSession(id, body.reason);
    return NextResponse.json(result);
  } catch (error) {
    console.error("Failed to end session:", error);
    const message =
      error instanceof Error ? error.message : "Internal server error";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}
