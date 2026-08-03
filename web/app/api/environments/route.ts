import { NextRequest } from 'next/server';
import { BACKEND_URL } from '@/lib/engine-path';

export async function GET() {
  const res = await fetch(`${BACKEND_URL}/api/environments`);
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function PUT(req: NextRequest) {
  const body = await req.json();
  const key = body.key;
  if (!key) return Response.json({ error: 'key is required' }, { status: 400 });

  const res = await fetch(`${BACKEND_URL}/api/environments/${key}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
