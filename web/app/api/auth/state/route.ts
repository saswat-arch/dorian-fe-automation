import { NextRequest } from 'next/server';
import { BACKEND_URL } from '@/lib/engine-path';

export async function DELETE(req: NextRequest) {
  const env = req.nextUrl.searchParams.get('env') ?? '';
  const qs = env ? `?env=${encodeURIComponent(env)}` : '';
  const res = await fetch(`${BACKEND_URL}/api/auth/state${qs}`, {
    method: 'DELETE',
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
