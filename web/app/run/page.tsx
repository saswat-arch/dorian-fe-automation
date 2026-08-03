'use client';

import { useState, useEffect, useRef, Suspense } from 'react';
import useSWR from 'swr';
import { useSearchParams } from 'next/navigation';
import {
  Play,
  Square,
  CheckCircle,
  XCircle,
  Clock,
  Zap,
  ChevronDown,
  ChevronRight,
  Loader2,
  Shield,
  Link2,
  Globe,
  AlertTriangle,
} from 'lucide-react';
import type { TestIntent, StepResult, EnvironmentConfig, BrowserEvent } from '@/lib/types';

const fetcher = (url: string) => fetch(url).then(r => r.json());

interface LiveStep {
  stepId: string;
  intent: string;
  status: 'passed' | 'failed' | 'healed' | 'running';
  durationMs?: number;
  tier?: string;
  confidence?: number;
  error?: string;
  healedFrom?: string;
  healedTo?: string;
  screenshot?: string;
  browserEvents?: BrowserEvent[];
}

interface LiveTest {
  intentId: string;
  name?: string;
  status: 'queued' | 'running' | 'passed' | 'failed' | 'error';
  steps: LiveStep[];
  error?: string;
  duration?: number;
  browserEvents?: BrowserEvent[];
}

function BrowserEventRow({ evt }: { evt: BrowserEvent }) {
  const colors: Record<string, string> = {
    console_error: 'text-red-600 bg-red-50/60 border-red-200/50',
    page_error: 'text-red-700 bg-red-50/80 border-red-200/60',
    network_error: 'text-amber-700 bg-amber-50/60 border-amber-200/50',
    request_failed: 'text-amber-600 bg-amber-50/50 border-amber-200/40',
  };
  const style = colors[evt.type] ?? 'text-stone-600 bg-stone-50 border-stone-200/50';

  return (
    <div className={`rounded-lg border px-3 py-2 text-[11px] ${style}`}>
      <div className="flex items-center gap-2 mb-0.5">
        <AlertTriangle className="w-3 h-3 shrink-0" />
        <span className="font-medium">{evt.type.replace(/_/g, ' ')}</span>
        <span className="ml-auto font-mono opacity-60">{new Date(evt.timestamp).toLocaleTimeString()}</span>
      </div>
      <p className="font-mono break-all">{evt.message}</p>
      {evt.url && <p className="mt-0.5 opacity-60 truncate">{evt.url}</p>}
    </div>
  );
}

function StepRow({ step }: { step: LiveStep }) {
  const [expanded, setExpanded] = useState(step.status === 'failed');

  const icons = {
    passed: <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />,
    failed: <XCircle className="w-3.5 h-3.5 text-red-500" />,
    healed: <Zap className="w-3.5 h-3.5 text-amber-500" />,
    running: <Loader2 className="w-3.5 h-3.5 text-blue-500 animate-spin" />,
  };

  const eventCount = step.browserEvents?.length ?? 0;
  const hasDetails = step.error || step.healedFrom || step.screenshot || eventCount > 0;

  return (
    <div className="border-b border-stone-100/80 last:border-0">
      <button
        onClick={() => hasDetails && setExpanded(v => !v)}
        className={`w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-stone-50/50 transition-colors ${hasDetails ? 'cursor-pointer' : 'cursor-default'}`}
      >
        <span className="shrink-0">{icons[step.status]}</span>
        <span className="flex-1 text-[13px] text-stone-600">{step.intent}</span>
        {eventCount > 0 && (
          <span className="flex items-center gap-1 text-[10px] font-medium text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded-md">
            <AlertTriangle className="w-3 h-3" />
            {eventCount}
          </span>
        )}
        {step.tier && (
          <span className="text-[11px] text-stone-300 hidden sm:block font-mono">
            {step.tier} &middot; {step.confidence ? `${Math.round(step.confidence * 100)}%` : '—'}
          </span>
        )}
        {step.durationMs !== undefined && (
          <span className="text-[11px] text-stone-300 w-14 text-right font-mono">
            {step.durationMs < 1000 ? `${step.durationMs}ms` : `${(step.durationMs / 1000).toFixed(1)}s`}
          </span>
        )}
        {hasDetails ? (
          expanded ? <ChevronDown className="w-3 h-3 text-stone-300" /> : <ChevronRight className="w-3 h-3 text-stone-300" />
        ) : null}
      </button>

      {expanded && hasDetails && (
        <div className="px-11 pb-3 space-y-2">
          {step.healedFrom && (
            <div className="bg-amber-50/60 border border-amber-200/50 rounded-lg px-3 py-2 text-[11px]">
              <span className="font-medium text-amber-700">Self-healed: </span>
              <span className="font-mono text-amber-600">{step.healedFrom}</span>
              <span className="text-amber-400 mx-1">&rarr;</span>
              <span className="font-mono text-amber-600">{step.healedTo}</span>
            </div>
          )}
          {step.error && (
            <div className="bg-red-50/60 border border-red-200/50 rounded-lg px-3 py-2 text-[11px] text-red-600">
              {step.error}
            </div>
          )}
          {step.browserEvents && step.browserEvents.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[11px] text-stone-400 font-medium">Browser Events</p>
              {step.browserEvents.map((evt, i) => (
                <BrowserEventRow key={i} evt={evt} />
              ))}
            </div>
          )}
          {step.screenshot && (
            <div>
              <p className="text-[11px] text-stone-300 mb-1">Screenshot:</p>
              <p className="text-[11px] font-mono text-stone-400 truncate">{step.screenshot}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TestCard({ test }: { test: LiveTest }) {
  const [collapsed, setCollapsed] = useState(false);

  const statusStyles: Record<string, string> = {
    queued: 'bg-stone-100 text-stone-500',
    running: 'bg-blue-50 text-blue-600',
    passed: 'bg-emerald-50 text-emerald-600',
    failed: 'bg-red-50 text-red-600',
    error: 'bg-red-50 text-red-600',
  };

  const totalBrowserEvents = test.steps.reduce((acc, s) => acc + (s.browserEvents?.length ?? 0), 0)
    + (test.browserEvents?.length ?? 0);

  return (
    <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden">
      <button
        onClick={() => setCollapsed(v => !v)}
        className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-stone-50/40 transition-colors"
      >
        {test.status === 'running' ? (
          <Loader2 className="w-4 h-4 text-blue-500 animate-spin shrink-0" />
        ) : test.status === 'passed' ? (
          <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0" />
        ) : test.status === 'failed' || test.status === 'error' ? (
          <XCircle className="w-4 h-4 text-red-500 shrink-0" />
        ) : (
          <Clock className="w-4 h-4 text-stone-300 shrink-0" />
        )}

        <div className="flex-1 min-w-0">
          <p className="font-medium text-stone-800 text-[14px] truncate">{test.name ?? test.intentId}</p>
          <p className="text-[11px] text-stone-300 font-mono mt-0.5">{test.intentId}</p>
        </div>

        <span className={`text-[11px] font-medium px-2 py-0.5 rounded-md ${statusStyles[test.status]}`}>
          {test.status}
        </span>

        {totalBrowserEvents > 0 && (
          <span className="flex items-center gap-1 text-[10px] font-medium text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded-md">
            <AlertTriangle className="w-3 h-3" />
            {totalBrowserEvents}
          </span>
        )}

        {test.steps.length > 0 && (
          <span className="text-[11px] text-stone-300">{test.steps.length} steps</span>
        )}

        {collapsed ? <ChevronRight className="w-3.5 h-3.5 text-stone-300" /> : <ChevronDown className="w-3.5 h-3.5 text-stone-300" />}
      </button>

      {!collapsed && (
        <div className="border-t border-stone-100">
          {test.error && (
            <div className="px-5 py-3 bg-red-50/60 border-b border-red-100/50 text-[13px] text-red-600">
              {test.error}
            </div>
          )}
          {test.steps.length === 0 && test.status === 'queued' && (
            <p className="px-5 py-3 text-[13px] text-stone-300">Waiting to start...</p>
          )}
          {test.steps.map((step, i) => (
            <StepRow key={`${step.stepId}-${i}`} step={step} />
          ))}
        </div>
      )}
    </div>
  );
}

function RunnerContent() {
  const searchParams = useSearchParams();
  const preselectedIntentId = searchParams.get('intent');

  const { data: intents } = useSWR<TestIntent[]>('/api/intents', fetcher);
  const { data: environments } = useSWR<Record<string, EnvironmentConfig>>('/api/environments', fetcher);
  const [selectedEnv, setSelectedEnv] = useState('staging');
  const [selected, setSelected] = useState<Set<string>>(
    preselectedIntentId ? new Set([preselectedIntentId]) : new Set()
  );
  const [running, setRunning] = useState(false);
  const [tests, setTests] = useState<LiveTest[]>([]);
  const [runComplete, setRunComplete] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (preselectedIntentId && intents) {
      setSelected(new Set([preselectedIntentId]));
    }
  }, [intents, preselectedIntentId]);

  function toggleAll() {
    if (!intents) return;
    setSelected(selected.size === intents.length ? new Set() : new Set(intents.map(i => i.id)));
  }

  function toggleIntent(id: string) {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelected(next);
  }

  function stopRun() {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setRunning(false);
  }

  async function startRun() {
    if (selected.size === 0) return;

    setRunning(true);
    setRunComplete(false);

    const selectedIntents = (intents ?? []).filter(i => selected.has(i.id));
    const authIntents = selectedIntents.filter(i => i.tags.includes('auth'));
    const nonAuthIntents = selectedIntents.filter(i => !i.tags.includes('auth'));
    const intentIds = [...authIntents, ...nonAuthIntents].map(i => i.id);

    setTests(intentIds.map(id => ({ intentId: id, name: intents?.find(i => i.id === id)?.name, status: 'queued', steps: [], browserEvents: [] })));

    const url = `/api/events?intentIds=${intentIds.join(',')}&runId=run-${Date.now()}&env=${encodeURIComponent(selectedEnv)}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.addEventListener('test:start', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setTests(prev => prev.map(t => t.intentId === data.intentId ? { ...t, status: 'running', name: data.name } : t));
    });

    es.addEventListener('step:result', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      const result = data.result as StepResult;
      const liveStep: LiveStep = {
        stepId: result.stepId,
        intent: result.intent,
        status: result.status === 'healed' ? 'healed' : result.status === 'failed' ? 'failed' : 'passed',
        durationMs: result.durationMs,
        tier: result.tier,
        confidence: result.confidence,
        error: result.error,
        healedFrom: result.healedFrom,
        healedTo: result.healedTo,
        screenshot: result.screenshot,
        browserEvents: result.browserEvents,
      };
      setTests(prev => prev.map(t => t.intentId === data.intentId ? { ...t, steps: [...t.steps, liveStep] } : t));
    });

    es.addEventListener('browser:error', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      const evt: BrowserEvent = data;
      setTests(prev => prev.map(t => t.intentId === data.intentId
        ? { ...t, browserEvents: [...(t.browserEvents ?? []), evt] }
        : t
      ));
    });

    es.addEventListener('test:complete', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setTests(prev => prev.map(t =>
        t.intentId === data.intentId ? { ...t, status: data.result?.passed ? 'passed' : 'failed', duration: data.result?.totalDuration } : t
      ));
    });

    es.addEventListener('test:error', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setTests(prev => prev.map(t => t.intentId === data.intentId ? { ...t, status: 'error', error: data.error } : t));
    });

    es.addEventListener('run:complete', () => { setRunning(false); setRunComplete(true); es.close(); });
    es.addEventListener('run:error', (e: MessageEvent) => { console.error('Run error:', JSON.parse(e.data).error); setRunning(false); es.close(); });
    es.onerror = () => { setRunning(false); es.close(); };
  }

  const passedCount = tests.filter(t => t.status === 'passed').length;
  const failedCount = tests.filter(t => t.status === 'failed' || t.status === 'error').length;
  const healedCount = tests.reduce((acc, t) => acc + t.steps.filter(s => s.status === 'healed').length, 0);
  const currentBaseUrl = environments?.[selectedEnv]?.baseUrl ?? '';

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-7">
        <h1 className="text-[22px] font-bold text-stone-900 tracking-tight">Test Runner</h1>
        <p className="text-stone-400 text-[13px] mt-0.5">Select intents and run them with real-time output</p>
      </div>

      {/* Environment selector */}
      <div className="bg-white rounded-xl border border-stone-200/60 px-5 py-4 mb-5 flex items-center gap-4">
        <div className="flex items-center gap-2.5 shrink-0">
          <div className="w-8 h-8 bg-indigo-50 rounded-lg flex items-center justify-center">
            <Globe className="w-[16px] h-[16px] text-indigo-500" />
          </div>
          <span className="text-[13px] font-semibold text-stone-700">Environment</span>
        </div>
        <select
          value={selectedEnv}
          onChange={(e) => setSelectedEnv(e.target.value)}
          disabled={running}
          className="flex-1 max-w-[200px] text-[13px] bg-stone-50 border border-stone-200/60 rounded-lg px-3 py-2 text-stone-700 focus:ring-2 focus:ring-stone-900/10 focus:border-stone-300 disabled:opacity-40"
        >
          {environments ? (
            Object.entries(environments).map(([key, env]) => (
              <option key={key} value={key}>{env.name} ({key})</option>
            ))
          ) : (
            <option value="staging">Staging</option>
          )}
        </select>
        {currentBaseUrl && (
          <span className="text-[12px] text-stone-400 font-mono truncate">{currentBaseUrl}</span>
        )}
      </div>

      {!running && !runComplete && (
        <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden mb-6">
          <div className="flex items-center justify-between px-5 py-3 border-b border-stone-100 bg-stone-50/50">
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={!!intents && selected.size === intents.length && intents.length > 0}
                onChange={toggleAll}
                className="w-3.5 h-3.5 rounded accent-stone-900"
              />
              <span className="text-[13px] font-medium text-stone-500">
                {selected.size} / {intents?.length ?? 0} selected
              </span>
            </div>
            <button
              onClick={startRun}
              disabled={selected.size === 0}
              className="flex items-center gap-2 px-4 py-1.5 bg-stone-900 text-white text-[13px] font-medium rounded-lg hover:bg-stone-800 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <Play className="w-3.5 h-3.5" />
              Run Selected
            </button>
          </div>

          {!intents ? (
            <div className="flex justify-center py-10">
              <Loader2 className="w-5 h-5 text-stone-300 animate-spin" />
            </div>
          ) : intents.length === 0 ? (
            <p className="text-center text-stone-400 text-[13px] py-10">
              No intents found.{' '}
              <a href="/intents/new" className="text-stone-900 font-medium hover:underline">Create one</a>
            </p>
          ) : (
            <div className="divide-y divide-stone-100/80">
              {intents.map(intent => (
                <label key={intent.id} className="flex items-center gap-3 px-5 py-3 hover:bg-stone-50/40 cursor-pointer transition-colors">
                  <input
                    type="checkbox"
                    checked={selected.has(intent.id)}
                    onChange={() => toggleIntent(intent.id)}
                    className="w-3.5 h-3.5 rounded shrink-0 accent-stone-900"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-medium text-stone-700 truncate">{intent.name}</p>
                    <p className="text-[11px] text-stone-300 font-mono mt-0.5 truncate">{intent.baseUrl}</p>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    {intent.tags.includes('auth') && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-emerald-50 text-emerald-600 rounded-md flex items-center gap-0.5 font-medium">
                        <Shield className="w-3 h-3" />login
                      </span>
                    )}
                    {intent.auth?.taskId && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-amber-50 text-amber-600 rounded-md flex items-center gap-0.5 font-medium">
                        <Link2 className="w-3 h-3" />auth
                      </span>
                    )}
                    {intent.tags.filter(t => t !== 'auth').map(tag => (
                      <span key={tag} className="text-[10px] px-1.5 py-0.5 bg-stone-100 text-stone-400 rounded-md">{tag}</span>
                    ))}
                  </div>
                  <span className="text-[11px] text-stone-300 shrink-0">{intent.steps.length} steps</span>
                </label>
              ))}
            </div>
          )}
        </div>
      )}

      {running && (
        <div className="flex items-center justify-between bg-blue-50/60 border border-blue-200/50 rounded-xl px-5 py-3 mb-5">
          <div className="flex items-center gap-3">
            <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
            <span className="text-[13px] font-medium text-blue-700">
              Running {tests.length} test{tests.length !== 1 ? 's' : ''} on {selectedEnv}...
            </span>
          </div>
          <button
            onClick={stopRun}
            className="flex items-center gap-2 px-3 py-1.5 bg-white border border-stone-200 text-red-600 text-[13px] font-medium rounded-lg hover:bg-red-50 transition-colors"
          >
            <Square className="w-3 h-3" />
            Stop
          </button>
        </div>
      )}

      {runComplete && (
        <div className="flex items-center gap-4 bg-white border border-stone-200/60 rounded-xl px-5 py-4 mb-5">
          <div className="flex items-center gap-2 text-emerald-600">
            <CheckCircle className="w-4 h-4" />
            <span className="text-[13px] font-medium">{passedCount} passed</span>
          </div>
          {failedCount > 0 && (
            <div className="flex items-center gap-2 text-red-600">
              <XCircle className="w-4 h-4" />
              <span className="text-[13px] font-medium">{failedCount} failed</span>
            </div>
          )}
          {healedCount > 0 && (
            <div className="flex items-center gap-2 text-amber-600">
              <Zap className="w-4 h-4" />
              <span className="text-[13px] font-medium">{healedCount} healed</span>
            </div>
          )}
          <button
            onClick={() => { setTests([]); setRunComplete(false); }}
            className="ml-auto text-[13px] text-stone-900 font-medium hover:underline"
          >
            Run again
          </button>
        </div>
      )}

      {tests.length > 0 && (
        <div className="space-y-2.5">
          {tests.map(test => (
            <TestCard key={test.intentId} test={test} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function RunPage() {
  return (
    <Suspense fallback={<div className="flex justify-center p-12"><Loader2 className="w-5 h-5 text-stone-300 animate-spin" /></div>}>
      <RunnerContent />
    </Suspense>
  );
}
