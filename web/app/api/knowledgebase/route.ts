import { NextRequest } from 'next/server';
import { BACKEND_URL } from '@/lib/engine-path';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const page = searchParams.get('page');
  const url = page
    ? `${BACKEND_URL}/api/knowledgebase?page=${encodeURIComponent(page)}`
    : `${BACKEND_URL}/api/knowledgebase`;

  const res = await fetch(url);
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
