import { NextRequest } from 'next/server';
import { BACKEND_URL } from '@/lib/engine-path';

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const res = await fetch(`${BACKEND_URL}/api/suites/${id}`, { cache: 'no-store' });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function PUT(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = await req.json();
  const res = await fetch(`${BACKEND_URL}/api/suites/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const res = await fetch(`${BACKEND_URL}/api/suites/${id}`, { method: 'DELETE' });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
