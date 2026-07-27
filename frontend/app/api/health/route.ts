import { NextResponse } from "next/server";

// Frontend liveness probe (PRD repo structure).
export async function GET() {
  return NextResponse.json({ status: "ok" });
}
