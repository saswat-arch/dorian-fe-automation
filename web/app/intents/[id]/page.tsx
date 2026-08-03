'use client';

import { useEffect, useState, use } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Save, Play, Trash2 } from 'lucide-react';
import Link from 'next/link';
import type { TestIntent } from '@/lib/types';

export default function EditIntentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [jsonValue, setJsonValue] = useState('');
  const [intent, setIntent] = useState<TestIntent | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch(`/api/intents/${id}`)
      .then(r => r.json())
      .then((data: TestIntent) => {
        setIntent(data);
        setJsonValue(JSON.stringify(data, null, 2));
        setLoading(false);
      })
      .catch(() => {
        setError('Failed to load intent');
        setLoading(false);
      });
  }, [id]);

  async function handleSave() {
    setError('');
    setSaving(true);
    try {
      const parsed = JSON.parse(jsonValue);
      const res = await fetch(`/api/intents/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(parsed),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error ?? 'Failed to save');
      }
      router.push('/intents');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete "${intent?.name}"?`)) return;
    await fetch(`/api/intents/${id}`, { method: 'DELETE' });
    router.push('/intents');
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-5 h-5 border-2 border-stone-300 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-7">
        <div className="flex items-center gap-3">
          <Link href="/intents" className="text-stone-300 hover:text-stone-600 transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-[22px] font-bold text-stone-900 tracking-tight">{intent?.name ?? id}</h1>
            <p className="text-[11px] text-stone-300 font-mono mt-0.5">{id}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href={`/run?intent=${id}`}
            className="flex items-center gap-2 px-3 py-1.5 text-[13px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200/60 rounded-lg hover:bg-emerald-100/80 transition-colors"
          >
            <Play className="w-3.5 h-3.5" />
            Run
          </Link>
          <button
            onClick={handleDelete}
            className="flex items-center gap-2 px-3 py-1.5 text-[13px] font-medium text-red-600 bg-red-50 border border-red-200/60 rounded-lg hover:bg-red-100/80 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Delete
          </button>
        </div>
      </div>

      {intent && (
        <div className="flex flex-wrap gap-1.5 mb-5">
          <span className="px-2 py-1 bg-stone-100 text-stone-500 text-[11px] rounded-md font-mono">{intent.baseUrl}</span>
          <span className="px-2 py-1 bg-blue-50 text-blue-600 text-[11px] rounded-md font-medium">{intent.steps.length} steps</span>
          {intent.tags.map(tag => (
            <span key={tag} className="px-2 py-1 bg-violet-50 text-violet-600 text-[11px] rounded-md font-medium">{tag}</span>
          ))}
        </div>
      )}

      <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden">
        <div className="bg-stone-50/50 px-4 py-2 border-b border-stone-100 flex items-center justify-between">
          <p className="text-[11px] text-stone-400 font-mono">{id}.json</p>
          <p className="text-[11px] text-stone-300">Edit the JSON directly</p>
        </div>
        <textarea
          value={jsonValue}
          onChange={e => setJsonValue(e.target.value)}
          spellCheck={false}
          className="w-full h-[500px] px-4 py-4 font-mono text-[12px] text-stone-700 focus:outline-none resize-none"
        />
      </div>

      {error && (
        <p className="mt-3 text-[13px] text-red-600 bg-red-50/60 border border-red-200/50 px-3 py-2 rounded-lg">{error}</p>
      )}

      <div className="flex justify-end gap-3 mt-6">
        <Link
          href="/intents"
          className="px-4 py-2 text-[13px] font-medium text-stone-500 bg-white border border-stone-200 rounded-lg hover:bg-stone-50 transition-colors"
        >
          Cancel
        </Link>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-stone-900 text-white text-[13px] font-medium rounded-lg hover:bg-stone-800 transition-colors disabled:opacity-50"
        >
          <Save className="w-3.5 h-3.5" />
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
}
