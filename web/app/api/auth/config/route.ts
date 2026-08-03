import { BACKEND_URL } from '@/lib/engine-path';

export async function GET() {
  const res = await fetch(`${BACKEND_URL}/api/auth/config`);
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function PUT(request: Request) {
  const body = await request.json();
  const res = await fetch(`${BACKEND_URL}/api/auth/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
