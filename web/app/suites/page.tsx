'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import useSWR from 'swr';
import {
  Layers,
  Play,
  Plus,
  Trash2,
  GripVertical,
  X,
  Check,
  Loader2,
  CircleDot,
  MinusCircle,
  Bug,
  Flame,
  GitPullRequest,
  ShieldCheck,
  Beaker,
  Globe,
  Eye,
  EyeOff,
} from 'lucide-react';
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { EnvironmentConfig, Suite, TestIntent } from '@/lib/types';

const fetcher = (url: string) => fetch(url).then(r => r.json());

type SuiteRunStatus = 'idle' | 'running' | 'passed' | 'failed';
type IntentRunStatus = 'pending' | 'running' | 'passed' | 'failed' | 'skipped';

interface IntentProgress {
  status: IntentRunStatus;
  reason?: string;
  passed?: number;
  failed?: number;
}

function presetIcon(id: string) {
  switch (id) {
    case 'suite-smoke':
      return Flame;
    case 'suite-regression':
      return ShieldCheck;
    case 'suite-pr':
      return GitPullRequest;
    case 'suite-bugs':
      return Bug;
    default:
      return Beaker;
  }
}

function SuiteListItem({
  suite,
  active,
  onSelect,
}: {
  suite: Suite;
  active: boolean;
  onSelect: () => void;
}) {
  const Icon = presetIcon(suite.id);
  return (
    <button
      onClick={onSelect}
      className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-[13px] transition-colors ${
        active
          ? 'bg-stone-900 text-white'
          : 'text-stone-600 hover:bg-stone-100'
      }`}
    >
      <Icon className={`w-4 h-4 shrink-0 ${active ? 'text-amber-300' : 'text-stone-400'}`} strokeWidth={1.75} />
      <span className="flex-1 truncate">{suite.name}</span>
      <span className={`text-[11px] ${active ? 'text-white/60' : 'text-stone-400'}`}>
        {suite.intentIds.length}
      </span>
    </button>
  );
}

function SortableIntentRow({
  intent,
  progress,
  onRemove,
  disabled,
}: {
  intent: TestIntent;
  progress?: IntentProgress;
  onRemove: () => void;
  disabled: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: intent.id,
    disabled,
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
  } as React.CSSProperties;

  const status = progress?.status ?? 'pending';
  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-2 px-2 py-2 bg-white border border-stone-200/70 rounded-lg group ${
        isDragging ? 'shadow-lg' : ''
      }`}
    >
      <button
        type="button"
        className="p-1 text-stone-300 hover:text-stone-600 cursor-grab active:cursor-grabbing"
        aria-label="Drag to reorder"
        {...attributes}
        {...listeners}
      >
        <GripVertical className="w-4 h-4" />
      </button>
      <div className="flex-1 min-w-0">
        <div className="text-[13px] font-medium text-stone-800 truncate">{intent.name}</div>
        <div className="text-[11px] text-stone-400 truncate">
          {intent.steps.length} steps · {intent.baseUrl}
        </div>
      </div>
      <IntentStatusBadge status={status} reason={progress?.reason} />
      <button
        type="button"
        onClick={onRemove}
        className="p-1.5 text-stone-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
        aria-label="Remove intent from suite"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

function IntentStatusBadge({ status, reason }: { status: IntentRunStatus; reason?: string }) {
  const cfg: Record<IntentRunStatus, { label: string; className: string; icon: typeof Check }> = {
    pending: { label: 'Pending', className: 'bg-stone-100 text-stone-400', icon: CircleDot },
    running: { label: 'Running', className: 'bg-blue-50 text-blue-600', icon: Loader2 },
    passed: { label: 'Passed', className: 'bg-green-50 text-green-600', icon: Check },
    failed: { label: 'Failed', className: 'bg-red-50 text-red-600', icon: X },
    skipped: { label: 'Skipped', className: 'bg-amber-50 text-amber-600', icon: MinusCircle },
  };
  const { label, className, icon: Icon } = cfg[status];
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10.5px] font-medium ${className}`}
      title={reason}
    >
      <Icon className={`w-3 h-3 ${status === 'running' ? 'animate-spin' : ''}`} />
      {label}
    </span>
  );
}

function AddIntentDialog({
  open,
  onClose,
  allIntents,
  existingIds,
  onAdd,
}: {
  open: boolean;
  onClose: () => void;
  allIntents: TestIntent[];
  existingIds: string[];
  onAdd: (ids: string[]) => void;
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (!open) {
      setSelected(new Set());
      setQuery('');
    }
  }, [open]);

  if (!open) return null;

  const candidates = allIntents.filter(
    i =>
      !existingIds.includes(i.id) &&
      (i.name.toLowerCase().includes(query.toLowerCase()) ||
        i.tags.some(t => t.toLowerCase().includes(query.toLowerCase()))),
  );

  return (
    <div className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-100">
          <div>
            <h2 className="text-[15px] font-semibold text-stone-900">Add intents to suite</h2>
            <p className="text-[12px] text-stone-400 mt-0.5">
              {candidates.length} available · {selected.size} selected
            </p>
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-700">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-5 py-3 border-b border-stone-100">
          <input
            type="text"
            placeholder="Search by name or tag..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            className="w-full px-3 py-2 bg-stone-50 border border-stone-200 rounded-lg text-[13px] focus:ring-2 focus:ring-stone-900/10 focus:border-stone-300 transition-all"
          />
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
          {candidates.length === 0 ? (
            <div className="text-center text-[13px] text-stone-400 py-8">
              {allIntents.length === 0
                ? 'No intents exist yet. Create one first.'
                : 'All intents are already in this suite (or no match).'}
            </div>
          ) : (
            candidates.map(intent => {
              const isSel = selected.has(intent.id);
              return (
                <button
                  key={intent.id}
                  type="button"
                  onClick={() =>
                    setSelected(prev => {
                      const next = new Set(prev);
                      if (next.has(intent.id)) next.delete(intent.id);
                      else next.add(intent.id);
                      return next;
                    })
                  }
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors ${
                    isSel ? 'bg-stone-900 text-white' : 'hover:bg-stone-50 text-stone-700'
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded border shrink-0 flex items-center justify-center ${
                      isSel ? 'bg-white border-white' : 'border-stone-300'
                    }`}
                  >
                    {isSel && <Check className="w-3 h-3 text-stone-900" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-medium truncate">{intent.name}</div>
                    <div className={`text-[11px] truncate ${isSel ? 'text-white/60' : 'text-stone-400'}`}>
                      {intent.steps.length} steps · {intent.tags.join(', ') || 'no tags'}
                    </div>
                  </div>
                </button>
              );
            })
          )}
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-stone-100">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-[13px] text-stone-600 hover:text-stone-900"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              onAdd(Array.from(selected));
              onClose();
            }}
            disabled={selected.size === 0}
            className="px-4 py-1.5 bg-stone-900 text-white text-[13px] font-medium rounded-lg hover:bg-stone-800 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Add {selected.size > 0 ? `(${selected.size})` : ''}
          </button>
        </div>
      </div>
    </div>
  );
}

function NewSuiteInline({ onCreate, onCancel }: { onCreate: (name: string) => void; onCancel: () => void }) {
  const [name, setName] = useState('');
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-100">
      <input
        autoFocus
        type="text"
        value={name}
        onChange={e => setName(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' && name.trim()) onCreate(name.trim());
          if (e.key === 'Escape') onCancel();
        }}
        placeholder="New suite name..."
        className="flex-1 bg-transparent text-[13px] text-stone-800 placeholder:text-stone-400 focus:outline-none"
      />
      <button
        onClick={() => name.trim() && onCreate(name.trim())}
        disabled={!name.trim()}
        className="text-green-600 hover:text-green-700 disabled:opacity-40"
      >
        <Check className="w-4 h-4" />
      </button>
      <button onClick={onCancel} className="text-stone-400 hover:text-stone-700">
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

export default function SuitesPage() {
  const { data: suites = [], mutate: mutateSuites, isLoading } = useSWR<Suite[]>('/api/suites', fetcher);
  const { data: allIntents = [] } = useSWR<TestIntent[]>('/api/intents', fetcher);
  const { data: environments } = useSWR<Record<string, EnvironmentConfig>>('/api/environments', fetcher);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [creatingNew, setCreatingNew] = useState(false);
  const [runStatus, setRunStatus] = useState<SuiteRunStatus>('idle');
  const [progress, setProgress] = useState<Record<string, IntentProgress>>({});
  const [selectedEnv, setSelectedEnv] = useState('staging');
  const [headed, setHeaded] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  const selected = suites.find(s => s.id === selectedId) ?? suites[0];
  useEffect(() => {
    if (!selectedId && suites.length > 0) setSelectedId(suites[0].id);
  }, [selectedId, suites]);

  const intentMap = useMemo(() => new Map(allIntents.map(i => [i.id, i])), [allIntents]);
  const orderedIntents = useMemo(
    () => (selected?.intentIds ?? []).map(id => intentMap.get(id)).filter((x): x is TestIntent => !!x),
    [selected, intentMap],
  );

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));

  async function saveIntentIds(suiteId: string, intentIds: string[]) {
    await fetch(`/api/suites/${suiteId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intentIds }),
    });
    mutateSuites();
  }

  async function handleDragEnd(evt: DragEndEvent) {
    if (!selected || !evt.over || evt.active.id === evt.over.id) return;
    const oldIndex = selected.intentIds.indexOf(String(evt.active.id));
    const newIndex = selected.intentIds.indexOf(String(evt.over.id));
    if (oldIndex < 0 || newIndex < 0) return;
    const next = arrayMove(selected.intentIds, oldIndex, newIndex);
    mutateSuites(
      suites.map(s => (s.id === selected.id ? { ...s, intentIds: next } : s)),
      { revalidate: false },
    );
    await saveIntentIds(selected.id, next);
  }

  async function handleRemove(intentId: string) {
    if (!selected) return;
    const next = selected.intentIds.filter(id => id !== intentId);
    mutateSuites(
      suites.map(s => (s.id === selected.id ? { ...s, intentIds: next } : s)),
      { revalidate: false },
    );
    await saveIntentIds(selected.id, next);
  }

  async function handleAdd(ids: string[]) {
    if (!selected) return;
    const next = [...selected.intentIds, ...ids.filter(id => !selected.intentIds.includes(id))];
    await saveIntentIds(selected.id, next);
  }

  async function handleCreate(name: string) {
    setCreatingNew(false);
    const res = await fetch('/api/suites', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (res.ok) {
      const suite: Suite = await res.json();
      mutateSuites();
      setSelectedId(suite.id);
    }
  }

  async function handleDeleteSuite() {
    if (!selected || selected.isPreset) return;
    if (!confirm(`Delete suite "${selected.name}"? Intents remain, only the suite is removed.`)) return;
    await fetch(`/api/suites/${selected.id}`, { method: 'DELETE' });
    setSelectedId(null);
    mutateSuites();
  }

  function handleRun() {
    if (!selected || selected.intentIds.length === 0) return;
    eventSourceRef.current?.close();

    setRunStatus('running');
    setProgress(Object.fromEntries(selected.intentIds.map(id => [id, { status: 'pending' as IntentRunStatus }])));

    const params = new URLSearchParams({
      headed: headed ? 'true' : 'false',
      env: selectedEnv,
    });
    const es = new EventSource(`/api/suites/${selected.id}/events?${params.toString()}`);
    eventSourceRef.current = es;

    const setIntentStatus = (intentId: string, patch: Partial<IntentProgress>) => {
      setProgress(prev => ({ ...prev, [intentId]: { ...prev[intentId], ...patch } as IntentProgress }));
    };

    es.addEventListener('test:queued', evt => {
      const data = JSON.parse((evt as MessageEvent).data);
      setIntentStatus(data.intentId, { status: 'running' });
    });
    es.addEventListener('test:complete', evt => {
      const data = JSON.parse((evt as MessageEvent).data);
      const passed = data.result?.passed;
      setIntentStatus(data.intentId, { status: passed ? 'passed' : 'failed' });
    });
    es.addEventListener('test:error', evt => {
      const data = JSON.parse((evt as MessageEvent).data);
      setIntentStatus(data.intentId, { status: 'failed', reason: data.error });
    });
    es.addEventListener('test:skipped', evt => {
      const data = JSON.parse((evt as MessageEvent).data);
      setIntentStatus(data.intentId, { status: 'skipped', reason: data.reason });
    });
    es.addEventListener('suite:complete', evt => {
      const data = JSON.parse((evt as MessageEvent).data);
      setRunStatus(data.suitePassed ? 'passed' : 'failed');
      es.close();
      eventSourceRef.current = null;
    });
    es.onerror = () => {
      setRunStatus('failed');
      es.close();
      eventSourceRef.current = null;
    };
  }

  function handleStop() {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setRunStatus('idle');
  }

  useEffect(() => () => eventSourceRef.current?.close(), []);

  const presets = suites.filter(s => s.isPreset);
  const custom = suites.filter(s => !s.isPreset);
  const isRunning = runStatus === 'running';

  return (
    <div className="flex h-full">
      {/* Suites list */}
      <div className="w-[280px] border-r border-stone-200/60 bg-stone-50/50 flex flex-col">
        <div className="px-5 py-5 border-b border-stone-200/60">
          <div className="flex items-center gap-2 mb-1">
            <Layers className="w-4 h-4 text-stone-700" />
            <h1 className="text-[15px] font-semibold text-stone-900">Suites</h1>
          </div>
          <p className="text-[12px] text-stone-400">
            {suites.length} suite{suites.length !== 1 ? 's' : ''} · group intents to run in order
          </p>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-3 space-y-3">
          <div>
            <div className="px-2 pb-1.5 text-[10px] font-semibold text-stone-400 tracking-wider uppercase">
              Presets
            </div>
            <div className="space-y-0.5">
              {presets.map(s => (
                <SuiteListItem
                  key={s.id}
                  suite={s}
                  active={s.id === selected?.id}
                  onSelect={() => setSelectedId(s.id)}
                />
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between px-2 pb-1.5">
              <span className="text-[10px] font-semibold text-stone-400 tracking-wider uppercase">
                Custom
              </span>
              {!creatingNew && (
                <button
                  onClick={() => setCreatingNew(true)}
                  className="text-stone-400 hover:text-stone-700"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
            {creatingNew && (
              <div className="px-1 pb-1.5">
                <NewSuiteInline onCreate={handleCreate} onCancel={() => setCreatingNew(false)} />
              </div>
            )}
            {custom.length === 0 && !creatingNew ? (
              <div className="px-2 py-2 text-[12px] text-stone-400">
                No custom suites yet.
              </div>
            ) : (
              <div className="space-y-0.5">
                {custom.map(s => (
                  <SuiteListItem
                    key={s.id}
                    suite={s}
                    active={s.id === selected?.id}
                    onSelect={() => setSelectedId(s.id)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Suite detail */}
      <div className="flex-1 overflow-y-auto p-8 max-w-3xl mx-auto">
        {isLoading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="w-5 h-5 animate-spin text-stone-400" />
          </div>
        ) : !selected ? (
          <div className="text-center py-24 text-stone-400">Select a suite to view its intents.</div>
        ) : (
          <>
            <div className="flex items-start justify-between mb-6">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h2 className="text-[22px] font-bold text-stone-900 tracking-tight">
                    {selected.name}
                  </h2>
                  {selected.isPreset && (
                    <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 text-[10px] font-medium rounded uppercase tracking-wider">
                      Preset
                    </span>
                  )}
                </div>
                {selected.description && (
                  <p className="text-[13px] text-stone-500 mt-1">{selected.description}</p>
                )}
                <p className="text-[12px] text-stone-400 mt-1.5">
                  {selected.intentIds.length} intent{selected.intentIds.length !== 1 ? 's' : ''} ·{' '}
                  Run mode: {selected.runMode}
                  {selected.metadata.lastRun && (
                    <> · Last run {new Date(selected.metadata.lastRun).toLocaleString()}</>
                  )}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => setAddOpen(true)}
                  disabled={isRunning}
                  className="flex items-center gap-1.5 px-3 py-2 text-[13px] font-medium text-stone-700 border border-stone-200 rounded-lg hover:bg-stone-50 disabled:opacity-40"
                >
                  <Plus className="w-3.5 h-3.5" /> Add Intents
                </button>
                {isRunning ? (
                  <button
                    onClick={handleStop}
                    className="flex items-center gap-1.5 px-4 py-2 bg-red-600 text-white text-[13px] font-medium rounded-lg hover:bg-red-700"
                  >
                    <X className="w-3.5 h-3.5" /> Stop
                  </button>
                ) : (
                  <button
                    onClick={handleRun}
                    disabled={selected.intentIds.length === 0}
                    className="flex items-center gap-1.5 px-4 py-2 bg-stone-900 text-white text-[13px] font-medium rounded-lg hover:bg-stone-800 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <Play className="w-3.5 h-3.5" /> Run Suite
                  </button>
                )}
                {!selected.isPreset && (
                  <button
                    onClick={handleDeleteSuite}
                    disabled={isRunning}
                    className="p-2 text-stone-400 hover:text-red-500 disabled:opacity-40"
                    title="Delete suite"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>

            {/* Environment + headed toggle */}
            <div className="bg-white rounded-xl border border-stone-200/60 px-5 py-4 mb-5 flex items-center gap-4">
              <div className="flex items-center gap-2.5 shrink-0">
                <div className="w-8 h-8 bg-indigo-50 rounded-lg flex items-center justify-center">
                  <Globe className="w-[16px] h-[16px] text-indigo-500" />
                </div>
                <span className="text-[13px] font-semibold text-stone-700">Environment</span>
              </div>
              <select
                value={selectedEnv}
                onChange={e => setSelectedEnv(e.target.value)}
                disabled={isRunning}
                className="max-w-[200px] text-[13px] bg-stone-50 border border-stone-200/60 rounded-lg px-3 py-2 text-stone-700 focus:ring-2 focus:ring-stone-900/10 focus:border-stone-300 disabled:opacity-40"
              >
                {environments ? (
                  Object.entries(environments).map(([key, env]) => (
                    <option key={key} value={key}>
                      {env.name} ({key})
                    </option>
                  ))
                ) : (
                  <option value="staging">Staging</option>
                )}
              </select>
              {environments?.[selectedEnv]?.baseUrl && (
                <span className="text-[12px] text-stone-400 font-mono truncate flex-1">
                  {environments[selectedEnv].baseUrl}
                </span>
              )}
              <button
                type="button"
                onClick={() => setHeaded(v => !v)}
                disabled={isRunning}
                className={`flex items-center gap-1.5 px-3 py-2 text-[13px] font-medium rounded-lg border transition-colors disabled:opacity-40 ${
                  headed
                    ? 'bg-amber-50 border-amber-200 text-amber-700'
                    : 'bg-stone-50 border-stone-200 text-stone-600 hover:bg-stone-100'
                }`}
                title={headed ? 'Browser will be visible' : 'Browser runs headless'}
              >
                {headed ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                {headed ? 'Headed' : 'Headless'}
              </button>
            </div>

            {runStatus !== 'idle' && (
              <div
                className={`mb-5 px-4 py-3 rounded-lg border text-[13px] ${
                  runStatus === 'running'
                    ? 'bg-blue-50 border-blue-200 text-blue-700'
                    : runStatus === 'passed'
                    ? 'bg-green-50 border-green-200 text-green-700'
                    : 'bg-red-50 border-red-200 text-red-700'
                }`}
              >
                {runStatus === 'running' && 'Suite running…'}
                {runStatus === 'passed' && 'Suite passed — all intents green.'}
                {runStatus === 'failed' && 'Suite failed. See per-intent status below.'}
              </div>
            )}

            {orderedIntents.length === 0 ? (
              <div className="text-center py-16 border border-dashed border-stone-200 rounded-lg">
                <div className="text-[13px] text-stone-400">
                  No intents in this suite yet. Click "Add Intents" to build it.
                </div>
              </div>
            ) : (
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={handleDragEnd}
              >
                <SortableContext
                  items={orderedIntents.map(i => i.id)}
                  strategy={verticalListSortingStrategy}
                >
                  <div className="space-y-1.5">
                    {orderedIntents.map(intent => (
                      <SortableIntentRow
                        key={intent.id}
                        intent={intent}
                        progress={progress[intent.id]}
                        onRemove={() => handleRemove(intent.id)}
                        disabled={isRunning}
                      />
                    ))}
                  </div>
                </SortableContext>
              </DndContext>
            )}
          </>
        )}
      </div>

      <AddIntentDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        allIntents={allIntents}
        existingIds={selected?.intentIds ?? []}
        onAdd={handleAdd}
      />
    </div>
  );
}
