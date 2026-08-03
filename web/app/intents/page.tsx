'use client';

import { useState } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { Plus, Play, Pencil, Trash2, Tag, Search, FileJson, Shield, Link2 } from 'lucide-react';
import type { TestIntent } from '@/lib/types';

const fetcher = (url: string) => fetch(url).then(r => r.json());

function EmptyState() {
  return (
    <div className="text-center py-20">
      <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center mx-auto mb-4">
        <FileJson className="w-6 h-6 text-blue-400" />
      </div>
      <h3 className="text-[15px] font-semibold text-stone-800 mb-1">No intents yet</h3>
      <p className="text-stone-400 text-[13px] mb-6">Create your first test intent to get started</p>
      <Link
        href="/intents/new"
        className="inline-flex items-center gap-2 px-4 py-2 bg-stone-900 text-white text-[13px] font-medium rounded-lg hover:bg-stone-800 transition-colors"
      >
        <Plus className="w-3.5 h-3.5" />
        Create Intent
      </Link>
    </div>
  );
}

export default function IntentsPage() {
  const { data: intents, mutate, isLoading } = useSWR<TestIntent[]>('/api/intents', fetcher);
  const [search, setSearch] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const filtered = (intents ?? []).filter(intent =>
    intent.name.toLowerCase().includes(search.toLowerCase()) ||
    intent.tags.some(t => t.toLowerCase().includes(search.toLowerCase()))
  );

  async function handleDelete(intent: TestIntent) {
    if (!confirm(`Delete "${intent.name}"?`)) return;
    setDeletingId(intent.id);
    await fetch(`/api/intents/${intent.id}`, { method: 'DELETE' });
    mutate();
    setDeletingId(null);
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-7">
        <div>
          <h1 className="text-[22px] font-bold text-stone-900 tracking-tight">Intents</h1>
          <p className="text-stone-400 text-[13px] mt-0.5">
            {intents?.length ?? 0} test intent{intents?.length !== 1 ? 's' : ''}
          </p>
        </div>
        <Link
          href="/intents/new"
          className="flex items-center gap-2 px-4 py-2 bg-stone-900 text-white text-[13px] font-medium rounded-lg hover:bg-stone-800 transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          New Intent
        </Link>
      </div>

      <div className="relative mb-5">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
        <input
          type="text"
          placeholder="Search by name or tag..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 bg-white border border-stone-200/60 rounded-lg text-[13px] text-stone-700 placeholder:text-stone-300 focus:ring-2 focus:ring-stone-900/10 focus:border-stone-300 transition-all"
        />
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <div className="w-5 h-5 border-2 border-stone-300 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden">
          <table className="w-full text-[13px]">
            <thead className="bg-stone-50/50 border-b border-stone-100">
              <tr>
                <th className="text-left px-5 py-3 text-[11px] font-semibold text-stone-400 uppercase tracking-wider">Name</th>
                <th className="text-left px-5 py-3 text-[11px] font-semibold text-stone-400 uppercase tracking-wider hidden md:table-cell">Tags</th>
                <th className="text-left px-5 py-3 text-[11px] font-semibold text-stone-400 uppercase tracking-wider hidden lg:table-cell">Steps</th>
                <th className="text-left px-5 py-3 text-[11px] font-semibold text-stone-400 uppercase tracking-wider hidden lg:table-cell">Base URL</th>
                <th className="text-right px-5 py-3 text-[11px] font-semibold text-stone-400 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100/80">
              {filtered.map(intent => (
                <tr key={intent.id} className="hover:bg-stone-50/40 transition-colors">
                  <td className="px-5 py-4">
                    <p className="font-medium text-stone-800">{intent.name}</p>
                    <p className="text-[11px] text-stone-300 mt-0.5 font-mono">{intent.id}</p>
                  </td>
                  <td className="px-5 py-4 hidden md:table-cell">
                    <div className="flex flex-wrap gap-1">
                      {intent.tags.includes('auth') && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-emerald-50 text-emerald-600 text-[11px] rounded-md font-medium">
                          <Shield className="w-3 h-3" />
                          login
                        </span>
                      )}
                      {intent.auth?.taskId && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-amber-50 text-amber-600 text-[11px] rounded-md font-medium" title={`Depends on: ${intent.auth.taskId}`}>
                          <Link2 className="w-3 h-3" />
                          uses auth
                        </span>
                      )}
                      {intent.tags.filter(t => t !== 'auth').map(tag => (
                        <span key={tag} className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-stone-100 text-stone-500 text-[11px] rounded-md">
                          <Tag className="w-3 h-3" />
                          {tag}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-5 py-4 hidden lg:table-cell">
                    <span className="text-stone-500">{intent.steps.length} steps</span>
                  </td>
                  <td className="px-5 py-4 hidden lg:table-cell">
                    <span className="text-stone-400 text-[11px] font-mono truncate max-w-[200px] block">
                      {intent.baseUrl}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex items-center justify-end gap-0.5">
                      <Link
                        href={`/run?intent=${intent.id}`}
                        className="p-1.5 rounded-md text-stone-300 hover:text-emerald-600 hover:bg-emerald-50 transition-colors"
                        title="Run"
                      >
                        <Play className="w-3.5 h-3.5" />
                      </Link>
                      <Link
                        href={`/intents/${intent.id}`}
                        className="p-1.5 rounded-md text-stone-300 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                        title="Edit"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </Link>
                      <button
                        onClick={() => handleDelete(intent)}
                        disabled={deletingId === intent.id}
                        className="p-1.5 rounded-md text-stone-300 hover:text-red-600 hover:bg-red-50 transition-colors disabled:opacity-40"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
