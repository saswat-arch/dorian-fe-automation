import { BACKEND_URL } from '@/lib/engine-path';

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  const res = await fetch(`${BACKEND_URL}/api/auth/setup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
