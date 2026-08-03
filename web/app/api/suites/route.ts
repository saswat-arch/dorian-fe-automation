import { NextRequest } from 'next/server';
import { BACKEND_URL } from '@/lib/engine-path';

export async function GET() {
  const res = await fetch(`${BACKEND_URL}/api/suites`, { cache: 'no-store' });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const res = await fetch(`${BACKEND_URL}/api/suites`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
