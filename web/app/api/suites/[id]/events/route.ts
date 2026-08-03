import { NextRequest } from 'next/server';
import { BACKEND_URL } from '@/lib/engine-path';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { searchParams } = new URL(req.url);
  const env = searchParams.get('env') ?? '';
  const headed = searchParams.get('headed') ?? 'true';

  let backendUrl = `${BACKEND_URL}/api/suites/${id}/events?headed=${headed}`;
  if (env) backendUrl += `&env=${encodeURIComponent(env)}`;

  const backendRes = await fetch(backendUrl, { headers: { Accept: 'text/event-stream' } });
  if (!backendRes.ok || !backendRes.body) {
    const errText = await backendRes.text().catch(() => '');
    return new Response(errText || 'Backend unavailable', { status: backendRes.status || 502 });
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
