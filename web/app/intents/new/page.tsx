'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Save, Code, Upload, Loader2, CheckCircle, ExternalLink } from 'lucide-react';
import Link from 'next/link';

type Tab = 'jam' | 'json';

export default function NewIntentPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>('jam');

  const [jamUrl, setJamUrl] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [testName, setTestName] = useState('');
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{
    intent: Record<string, unknown>;
    saved: boolean;
    sources?: {
      details: boolean;
      userEvents: boolean;
      consoleLogs: boolean;
      networkRequests: boolean;
    };
  } | null>(null);

  const [jsonValue, setJsonValue] = useState(
    JSON.stringify(
      {
        id: `test-${Math.random().toString(36).slice(2, 10)}`,
        name: '',
        description: '',
        baseUrl: 'http://localhost:3000',
        tags: [],
        steps: [
          { id: 'step-1', order: 1, type: 'navigate', intent: 'Navigate to page', url: '/' },
        ],
        assertions: [],
        config: {
          timeout: 30000,
          retries: 1,
          viewport: { width: 1280, height: 720 },
          browsers: ['chromium'],
        },
      },
      null,
      2
    )
  );

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function handleJamImport() {
    setError('');
    setImportResult(null);

    if (!jamUrl.trim()) { setError('Jam URL is required'); return; }
    if (!jamUrl.includes('jam.dev/c/')) { setError('Invalid Jam URL. Expected format: https://jam.dev/c/<id>'); return; }

    setImporting(true);
    try {
      const res = await fetch('/api/intents/from-jam', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jamUrl: jamUrl.trim(),
          baseUrl: baseUrl.trim() || undefined,
          testName: testName.trim() || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? 'Import failed');
      setImportResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setImporting(false);
    }
  }

  async function handleJsonSave() {
    setError('');
    setSaving(true);
    try {
      const intent = JSON.parse(jsonValue);
      if (!intent.id || !intent.name) throw new Error('Intent must have an id and name');
      const res = await fetch('/api/intents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(intent),
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

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-7">
        <Link href="/intents" className="text-stone-300 hover:text-stone-600 transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <h1 className="text-[22px] font-bold text-stone-900 tracking-tight">New Intent</h1>
      </div>

      <div className="flex gap-1 bg-stone-100 p-1 rounded-lg w-fit mb-6">
        <button
          onClick={() => { setTab('jam'); setError(''); }}
          className={`flex items-center gap-2 px-4 py-1.5 text-[13px] font-medium rounded-md transition-all ${
            tab === 'jam' ? 'bg-white text-stone-900 shadow-sm' : 'text-stone-400 hover:text-stone-600'
          }`}
        >
          <Upload className="w-3.5 h-3.5" />
          Import from Jam
        </button>
        <button
          onClick={() => { setTab('json'); setError(''); }}
          className={`flex items-center gap-2 px-4 py-1.5 text-[13px] font-medium rounded-md transition-all ${
            tab === 'json' ? 'bg-white text-stone-900 shadow-sm' : 'text-stone-400 hover:text-stone-600'
          }`}
        >
          <Code className="w-3.5 h-3.5" />
          JSON
        </button>
      </div>

      {tab === 'jam' ? (
        <div>
          <div className="bg-white rounded-xl border border-stone-200/60 p-6 space-y-4">
            <div className="flex items-start gap-3 pb-4 border-b border-stone-100">
              <div className="w-9 h-9 bg-violet-50 rounded-lg flex items-center justify-center shrink-0">
                <Upload className="w-[18px] h-[18px] text-violet-500" />
              </div>
              <div>
                <h2 className="font-semibold text-stone-800 text-[14px]">Import from Jam</h2>
                <p className="text-[13px] text-stone-400 mt-0.5 leading-relaxed">
                  Paste a Jam recording link &mdash; we&apos;ll fetch events, console logs &amp; network requests via the Jam MCP API, then convert them into a test intent with AI
                </p>
                <p className="text-[11px] text-stone-300 mt-1.5">
                  Requires <code className="bg-stone-50 px-1 py-0.5 rounded text-stone-500">JAM_ACCESS_TOKEN</code> and <code className="bg-stone-50 px-1 py-0.5 rounded text-stone-500">ANTHROPIC_API_KEY</code> in your <code className="bg-stone-50 px-1 py-0.5 rounded text-stone-500">.env</code>
                </p>
              </div>
            </div>

            <div>
              <label className="block text-[13px] font-medium text-stone-600 mb-1.5">Jam URL *</label>
              <input
                type="text"
                value={jamUrl}
                onChange={e => setJamUrl(e.target.value)}
                placeholder="https://jam.dev/c/abc123"
                disabled={importing}
                className="w-full px-3 py-2.5 bg-white border border-stone-200/60 rounded-lg text-[13px] text-stone-700 placeholder:text-stone-300 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-300 transition-all disabled:bg-stone-50 disabled:text-stone-300"
              />
            </div>

            <div>
              <label className="block text-[13px] font-medium text-stone-600 mb-1.5">
                Test Name <span className="text-stone-300 font-normal">(optional)</span>
              </label>
              <input
                type="text"
                value={testName}
                onChange={e => setTestName(e.target.value)}
                placeholder="Auto-generated from recording"
                disabled={importing}
                className="w-full px-3 py-2.5 bg-white border border-stone-200/60 rounded-lg text-[13px] text-stone-700 placeholder:text-stone-300 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-300 transition-all disabled:bg-stone-50 disabled:text-stone-300"
              />
            </div>

            <div>
              <label className="block text-[13px] font-medium text-stone-600 mb-1.5">
                Base URL <span className="text-stone-300 font-normal">(optional override)</span>
              </label>
              <input
                type="text"
                value={baseUrl}
                onChange={e => setBaseUrl(e.target.value)}
                placeholder="Defaults to URL from recording"
                disabled={importing}
                className="w-full px-3 py-2.5 bg-white border border-stone-200/60 rounded-lg text-[13px] text-stone-700 placeholder:text-stone-300 focus:ring-2 focus:ring-violet-500/20 focus:border-violet-300 transition-all disabled:bg-stone-50 disabled:text-stone-300"
              />
            </div>

            <button
              onClick={handleJamImport}
              disabled={importing || !jamUrl.trim()}
              className="flex items-center gap-2 px-5 py-2.5 bg-stone-900 text-white text-[13px] font-medium rounded-lg hover:bg-stone-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed w-full justify-center"
            >
              {importing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Converting with AI...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4" />
                  Import &amp; Convert
                </>
              )}
            </button>
          </div>

          {importResult && (
            <div className="mt-5 bg-emerald-50/60 border border-emerald-200/50 rounded-xl p-5">
              <div className="flex items-start gap-3 mb-4">
                <CheckCircle className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-emerald-800 text-[14px]">Intent created successfully</p>
                  <p className="text-[13px] text-emerald-600 mt-0.5">
                    {(importResult.intent as Record<string, unknown>).name as string}
                  </p>
                </div>
              </div>

              {importResult.sources && (
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {Object.entries(importResult.sources).map(([key, ok]) => (
                    <span key={key} className={`text-[11px] px-2 py-0.5 rounded-md font-medium ${ok ? 'bg-emerald-100 text-emerald-600' : 'bg-stone-100 text-stone-400'}`}>
                      {ok ? '\u2713' : '\u2717'} {key}
                    </span>
                  ))}
                </div>
              )}

              <div className="bg-white rounded-lg border border-emerald-200/60 overflow-hidden mb-4">
                <div className="bg-stone-50/50 px-4 py-2 border-b border-stone-100">
                  <p className="text-[11px] text-stone-400 font-mono">
                    {(importResult.intent as Record<string, unknown>).id as string}.json
                  </p>
                </div>
                <pre className="px-4 py-3 text-[11px] font-mono text-stone-600 max-h-64 overflow-auto">
                  {JSON.stringify(importResult.intent, null, 2)}
                </pre>
              </div>

              <div className="flex gap-2.5">
                <Link
                  href={`/intents/${(importResult.intent as Record<string, unknown>).id as string}`}
                  className="flex items-center gap-2 px-3.5 py-2 bg-white border border-stone-200 text-stone-700 text-[13px] font-medium rounded-lg hover:bg-stone-50 transition-colors"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  Edit Intent
                </Link>
                <Link
                  href={`/run?intent=${(importResult.intent as Record<string, unknown>).id as string}`}
                  className="flex items-center gap-2 px-3.5 py-2 bg-stone-900 text-white text-[13px] font-medium rounded-lg hover:bg-stone-800 transition-colors"
                >
                  Run Now
                </Link>
                <button
                  onClick={() => { setImportResult(null); setJamUrl(''); setTestName(''); setBaseUrl(''); }}
                  className="px-3.5 py-2 text-[13px] text-stone-400 hover:text-stone-600 transition-colors"
                >
                  Import Another
                </button>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div>
          <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden">
            <div className="bg-stone-50/50 px-4 py-2 border-b border-stone-100">
              <p className="text-[11px] text-stone-400 font-mono">intent.json</p>
            </div>
            <textarea
              value={jsonValue}
              onChange={e => setJsonValue(e.target.value)}
              spellCheck={false}
              className="w-full h-96 px-4 py-4 font-mono text-[12px] text-stone-700 focus:outline-none resize-none"
            />
          </div>

          <div className="flex justify-end gap-3 mt-6">
            <Link
              href="/intents"
              className="px-4 py-2 text-[13px] font-medium text-stone-500 bg-white border border-stone-200 rounded-lg hover:bg-stone-50 transition-colors"
            >
              Cancel
            </Link>
            <button
              onClick={handleJsonSave}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 bg-stone-900 text-white text-[13px] font-medium rounded-lg hover:bg-stone-800 transition-colors disabled:opacity-50"
            >
              <Save className="w-3.5 h-3.5" />
              {saving ? 'Saving...' : 'Save Intent'}
            </button>
          </div>
        </div>
      )}

      {error && (
        <p className="mt-3 text-[13px] text-red-600 bg-red-50/60 border border-red-200/50 px-3 py-2 rounded-lg">{error}</p>
      )}
    </div>
  );
}
