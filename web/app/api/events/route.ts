import { NextRequest } from 'next/server';
import { BACKEND_URL } from '@/lib/engine-path';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const intentIds = searchParams.get('intentIds') ?? '';
  const runId = searchParams.get('runId') ?? '';
  const env = searchParams.get('env') ?? '';

  if (!intentIds) {
    return new Response('Missing intentIds', { status: 400 });
  }

  let backendUrl = `${BACKEND_URL}/api/events?intentIds=${intentIds}&runId=${runId}&headed=true`;
  if (env) {
    backendUrl += `&env=${encodeURIComponent(env)}`;
  }

  const backendRes = await fetch(backendUrl, {
    headers: { Accept: 'text/event-stream' },
  });

  if (!backendRes.ok || !backendRes.body) {
    return new Response('Backend unavailable', { status: 502 });
  }

  return new Response(backendRes.body, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
}
