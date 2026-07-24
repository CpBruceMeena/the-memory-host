import { NextResponse } from "next/server";

import { getLeaderboard } from "@/lib/api";

/**
 * GET /api/leaderboard
 *
 * BFF proxy: fetches the leaderboard from the backend.
 */
export async function GET() {
  try {
    const result = await getLeaderboard();
    return NextResponse.json(result);
  } catch (error) {
    console.error("Failed to fetch leaderboard:", error);
    const message =
      error instanceof Error ? error.message : "Internal server error";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}
