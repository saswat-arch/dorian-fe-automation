'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { Database, Globe, Layers, Navigation, ArrowRight, ChevronDown, ChevronRight, Wifi } from 'lucide-react';
import type { PageRecord, ComponentRecord, NavigationRecord, ApiEndpointRecord, KnowledgebaseStats } from '@/lib/types';

const fetcher = (url: string) => fetch(url).then(r => r.json());

interface KbData {
  stats: KnowledgebaseStats;
  pages?: PageRecord[];
  endpoints?: ApiEndpointRecord[];
  page?: PageRecord;
  components?: ComponentRecord[];
  navigation?: NavigationRecord[];
  message?: string;
}

function StatChip({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <div className={`px-4 py-3 rounded-lg ${accent}`}>
      <p className="text-[22px] font-bold tracking-tight">{value}</p>
      <p className="text-[11px] mt-0.5 opacity-60 font-medium">{label}</p>
    </div>
  );
}

function ComponentBadge({ comp }: { comp: ComponentRecord }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 px-3 py-2 bg-stone-50/50 border border-stone-200/60 rounded-lg text-[11px]">
      <span className="font-mono font-medium text-stone-600">&lt;{comp.tag}&gt;</span>
      {comp.text && <span className="text-stone-400">&quot;{comp.text}&quot;</span>}
      {comp.test_id && (
        <span className="bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded-md font-medium">testId=&quot;{comp.test_id}&quot;</span>
      )}
      {comp.role && (
        <span className="bg-violet-50 text-violet-600 px-1.5 py-0.5 rounded-md font-medium">role={comp.role}</span>
      )}
      {comp.label && (
        <span className="bg-emerald-50 text-emerald-600 px-1.5 py-0.5 rounded-md font-medium">aria-label=&quot;{comp.label}&quot;</span>
      )}
      {comp.type && (
        <span className="bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded-md font-medium">type={comp.type}</span>
      )}
    </div>
  );
}

function PageRow({ page, onSelect }: { page: PageRecord; onSelect: (path: string) => void }) {
  return (
    <button
      onClick={() => onSelect(page.path)}
      className="w-full flex items-center gap-3 px-4 py-3 hover:bg-blue-50/40 transition-colors text-left group"
    >
      <Globe className="w-4 h-4 text-stone-300 group-hover:text-blue-500 shrink-0 transition-colors" />
      <div className="flex-1 min-w-0">
        <p className="text-[13px] font-mono font-medium text-stone-700 truncate">{page.path}</p>
        {page.title && <p className="text-[11px] text-stone-300 mt-0.5 truncate">{page.title}</p>}
      </div>
      <span className="text-[11px] text-stone-300 shrink-0 font-mono">{page.visit_count}x</span>
      <ArrowRight className="w-3.5 h-3.5 text-stone-200 group-hover:text-blue-500 transition-colors" />
    </button>
  );
}

function PageDetail({ path, onBack }: { path: string; onBack: () => void }) {
  const { data, isLoading } = useSWR<KbData>(`/api/knowledgebase?page=${encodeURIComponent(path)}`, fetcher);
  const [showNavigation, setShowNavigation] = useState(true);

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="w-5 h-5 border-2 border-stone-300 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div>
      <button onClick={onBack} className="flex items-center gap-2 text-[13px] text-stone-900 font-medium hover:underline mb-4">
        &larr; Back to all pages
      </button>

      <div className="flex items-center gap-3 mb-5">
        <div className="w-9 h-9 bg-blue-50 rounded-lg flex items-center justify-center">
          <Globe className="w-[18px] h-[18px] text-blue-500" />
        </div>
        <div>
          <h2 className="text-[15px] font-bold text-stone-800 font-mono">{path}</h2>
          {data?.page?.title && <p className="text-[13px] text-stone-400">{data.page.title}</p>}
        </div>
      </div>

      <div className="mb-5">
        <h3 className="text-[13px] font-semibold text-stone-600 mb-2 flex items-center gap-2">
          <Layers className="w-4 h-4 text-stone-400" />
          Components ({data?.components?.length ?? 0})
        </h3>
        {data?.components && data.components.length > 0 ? (
          <div className="space-y-1.5">
            {data.components.map((comp, i) => (
              <ComponentBadge key={comp.id ?? i} comp={comp} />
            ))}
          </div>
        ) : (
          <p className="text-[13px] text-stone-300 italic">No components recorded</p>
        )}
      </div>

      {data?.navigation && data.navigation.length > 0 && (
        <div>
          <button
            onClick={() => setShowNavigation(v => !v)}
            className="flex items-center gap-2 text-[13px] font-semibold text-stone-600 mb-2"
          >
            <Navigation className="w-4 h-4 text-stone-400" />
            Navigation ({data.navigation.length})
            {showNavigation ? <ChevronDown className="w-3 h-3 text-stone-300" /> : <ChevronRight className="w-3 h-3 text-stone-300" />}
          </button>
          {showNavigation && (
            <div className="space-y-1.5">
              {data.navigation.map((nav, i) => (
                <div key={i} className="flex items-center gap-2 text-[11px] px-3 py-2 bg-stone-50/50 border border-stone-200/60 rounded-lg">
                  <span className="font-mono text-stone-400 truncate">{nav.trigger}</span>
                  <ArrowRight className="w-3 h-3 text-stone-300 shrink-0" />
                  <span className="font-mono font-medium text-stone-600">{nav.to_path}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function KnowledgebasePage() {
  const { data, isLoading } = useSWR<KbData>('/api/knowledgebase', fetcher);
  const [selectedPage, setSelectedPage] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="flex justify-center py-16 p-8">
        <div className="w-5 h-5 border-2 border-stone-300 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const stats = data?.stats ?? { pageCount: 0, componentCount: 0, navigationCount: 0, apiEndpointCount: 0 };
  const isEmpty = stats.pageCount === 0;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-7">
        <div className="w-9 h-9 bg-amber-50 rounded-lg flex items-center justify-center">
          <Database className="w-[18px] h-[18px] text-amber-500" />
        </div>
        <div>
          <h1 className="text-[22px] font-bold text-stone-900 tracking-tight">Knowledgebase</h1>
          <p className="text-stone-400 text-[13px] mt-0.5">What QA Autopilot knows about your app</p>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mb-6">
        <StatChip label="Pages" value={stats.pageCount} accent="bg-blue-50 text-blue-700" />
        <StatChip label="Components" value={stats.componentCount} accent="bg-violet-50 text-violet-700" />
        <StatChip label="Navigation" value={stats.navigationCount} accent="bg-emerald-50 text-emerald-700" />
        <StatChip label="API Endpoints" value={stats.apiEndpointCount} accent="bg-amber-50 text-amber-700" />
      </div>

      {isEmpty ? (
        <div className="text-center py-20 bg-white rounded-xl border border-stone-200/60">
          <div className="w-12 h-12 bg-amber-50 rounded-xl flex items-center justify-center mx-auto mb-4">
            <Database className="w-6 h-6 text-amber-400" />
          </div>
          <h3 className="text-[15px] font-semibold text-stone-800 mb-1">No knowledge yet</h3>
          <p className="text-stone-400 text-[13px] max-w-md mx-auto leading-relaxed">
            {data?.message ?? 'Run tests to build the knowledgebase. QA Autopilot will learn your app structure over time.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden">
            <div className="px-5 py-3 bg-stone-50/50 border-b border-stone-100">
              <h2 className="font-semibold text-stone-700 text-[13px] flex items-center gap-2">
                <Globe className="w-4 h-4 text-stone-400" />
                {selectedPage ? 'Page Details' : `Discovered Pages (${stats.pageCount})`}
              </h2>
            </div>
            <div className="divide-y divide-stone-100/80 max-h-[500px] overflow-auto p-4">
              {selectedPage ? (
                <PageDetail path={selectedPage} onBack={() => setSelectedPage(null)} />
              ) : (
                data?.pages?.map(page => (
                  <PageRow key={page.path} page={page} onSelect={setSelectedPage} />
                ))
              )}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden">
            <div className="px-5 py-3 bg-stone-50/50 border-b border-stone-100">
              <h2 className="font-semibold text-stone-700 text-[13px] flex items-center gap-2">
                <Wifi className="w-4 h-4 text-stone-400" />
                API Endpoints ({stats.apiEndpointCount})
              </h2>
            </div>
            <div className="divide-y divide-stone-100/80 max-h-[500px] overflow-auto">
              {!data?.endpoints || data.endpoints.length === 0 ? (
                <p className="text-[13px] text-stone-300 italic p-5">No API calls observed yet</p>
              ) : (
                (data.endpoints as ApiEndpointRecord[]).map((ep, i) => (
                  <div key={i} className="flex items-center gap-3 px-4 py-3">
                    <span className={`text-[10px] font-bold font-mono px-1.5 py-0.5 rounded-md shrink-0 ${
                      ep.method === 'GET' ? 'bg-emerald-50 text-emerald-600' :
                      ep.method === 'POST' ? 'bg-blue-50 text-blue-600' :
                      ep.method === 'PUT' ? 'bg-amber-50 text-amber-600' :
                      ep.method === 'DELETE' ? 'bg-red-50 text-red-600' :
                      'bg-stone-100 text-stone-500'
                    }`}>
                      {ep.method}
                    </span>
                    <span className="text-[13px] font-mono text-stone-600 truncate flex-1">{ep.url_pattern}</span>
                    {ep.last_status && (
                      <span className={`text-[11px] font-medium shrink-0 ${ep.last_status < 400 ? 'text-emerald-500' : 'text-red-500'}`}>
                        {ep.last_status}
                      </span>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
