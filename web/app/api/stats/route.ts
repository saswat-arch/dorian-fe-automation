import { BACKEND_URL } from '@/lib/engine-path';

export async function GET() {
  const res = await fetch(`${BACKEND_URL}/api/stats`);
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
