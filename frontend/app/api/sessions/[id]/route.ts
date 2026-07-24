import { NextRequest, NextResponse } from "next/server";

import { getSession } from "@/lib/api";

/**
 * GET /api/sessions/[id]
 *
 * BFF proxy: fetches the current state of a game session.
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

    const result = await getSession(id);
    return NextResponse.json(result);
  } catch (error) {
    console.error("Failed to fetch session:", error);
    const message =
      error instanceof Error ? error.message : "Internal server error";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}
