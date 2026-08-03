'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import useSWR from 'swr';
import {
  Shield, ShieldCheck, ShieldAlert, RefreshCw, Trash2, Play, Settings, Clock, Mail, Globe
} from 'lucide-react';
import type { EnvironmentConfig } from '@/lib/types';

const fetcher = (url: string) => fetch(url).then(r => r.json());

interface AuthStatus {
  authenticated: boolean;
  fresh?: boolean;
  email?: string;
  createdAt?: string;
  ageHours?: number;
  maxAgeHours?: number;
  reason?: string;
  environment?: string | null;
}

interface AuthConfig {
  baseUrl: string;
  method: string;
  steps: Record<string, Record<string, string>>;
  waitAfterAuth: number;
  maxAgeHours: number;
}

export default function AuthPage() {
  const { data: environments } = useSWR<Record<string, EnvironmentConfig>>('/api/environments', fetcher);
  const [selectedEnv, setSelectedEnv] = useState('staging');
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [editingConfig, setEditingConfig] = useState(false);
  const [configJson, setConfigJson] = useState('');
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const statusPollRef = useRef<NodeJS.Timeout | null>(null);

  const fetchStatus = useCallback(async (env?: string) => {
    const envParam = env ?? selectedEnv;
    try {
      const res = await fetch(`/api/auth/status?env=${encodeURIComponent(envParam)}`);
      const data = await res.json();
      setStatus(data);
    } catch {
      setStatus({ authenticated: false, reason: 'fetch_failed' });
    }
  }, [selectedEnv]);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch('/api/auth/config');
      const data = await res.json();
      setConfig(data);
      setConfigJson(JSON.stringify(data, null, 2));
    } catch { /* config fetch failed */ }
  }, []);

  useEffect(() => {
    Promise.all([fetchStatus(), fetchConfig()]).finally(() => setLoading(false));
  }, [fetchStatus, fetchConfig]);

  useEffect(() => {
    fetchStatus(selectedEnv);
  }, [selectedEnv, fetchStatus]);

  const runAuthSetup = async () => {
    setRunning(true);
    setMessage(null);
    try {
      const res = await fetch('/api/auth/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ environment: selectedEnv }),
      });
      const data = await res.json();
      if (data.started) {
        setMessage({
          type: 'success',
          text: 'Browser opening — complete login in the window, then wait for status to update.',
        });
        // Poll auth status until fresh or timeout
        let attempts = 0;
        statusPollRef.current = setInterval(async () => {
          attempts++;
          await fetchStatus(selectedEnv);
          if (attempts >= 90) {
            if (statusPollRef.current) clearInterval(statusPollRef.current);
            setRunning(false);
          }
        }, 2000);
      } else {
        setMessage({ type: 'error', text: data.error || 'Auth setup failed' });
        setRunning(false);
      }
    } catch (e: any) {
      setMessage({ type: 'error', text: e.message || 'Network error' });
      setRunning(false);
    }
  };

  useEffect(() => {
    if (status?.fresh && running) {
      if (statusPollRef.current) clearInterval(statusPollRef.current);
      setRunning(false);
      setMessage({ type: 'success', text: `Auth saved for ${selectedEnv}!` });
    }
  }, [status?.fresh, running, selectedEnv]);

  useEffect(() => {
    return () => {
      if (statusPollRef.current) clearInterval(statusPollRef.current);
    };
  }, []);

  const clearAuthState = async () => {
    try {
      await fetch(`/api/auth/state?env=${encodeURIComponent(selectedEnv)}`, { method: 'DELETE' });
      setMessage({ type: 'success', text: `Auth state cleared for ${selectedEnv}` });
      await fetchStatus(selectedEnv);
    } catch {
      setMessage({ type: 'error', text: 'Failed to clear auth state' });
    }
  };

  const saveConfig = async () => {
    try {
      const parsed = JSON.parse(configJson);
      const res = await fetch('/api/auth/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(parsed),
      });
      if (res.ok) {
        setConfig(parsed);
        setEditingConfig(false);
        setMessage({ type: 'success', text: 'Config saved' });
      }
    } catch {
      setMessage({ type: 'error', text: 'Invalid JSON' });
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center gap-2 text-stone-400 text-[13px]">
        <RefreshCw className="w-4 h-4 animate-spin" />
        Loading auth status...
      </div>
    );
  }

  const isAuthenticated = status?.authenticated;
  const isFresh = status?.fresh;
  const currentBaseUrl = environments?.[selectedEnv]?.baseUrl ?? '';

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-9 h-9 bg-amber-50 rounded-lg flex items-center justify-center">
          <Shield className="w-[18px] h-[18px] text-amber-500" />
        </div>
        <div>
          <h1 className="text-[22px] font-bold text-stone-900 tracking-tight">Auth Setup</h1>
          <p className="text-[13px] text-stone-400 mt-0.5">
            Manage per-environment authentication state for test runs.
          </p>
        </div>
      </div>

      {message && (
        <div
          className={`mb-6 px-4 py-3 rounded-lg text-[13px] font-medium ${message.type === 'success'
              ? 'bg-emerald-50/60 text-emerald-700 border border-emerald-200/50'
              : 'bg-red-50/60 text-red-600 border border-red-200/50'
            }`}
        >
          {message.text}
        </div>
      )}

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

      <div className="bg-white rounded-xl border border-stone-200/60 p-6 mb-5">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-[14px] font-semibold text-stone-700">Auth State — {selectedEnv}</h2>
          <button onClick={() => fetchStatus(selectedEnv)} className="text-stone-300 hover:text-stone-500 transition-colors" title="Refresh status">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center gap-4 mb-6">
          {isAuthenticated && isFresh ? (
            <div className="flex items-center gap-2.5 text-emerald-600">
              <div className="w-8 h-8 bg-emerald-50 rounded-lg flex items-center justify-center">
                <ShieldCheck className="w-[18px] h-[18px]" />
              </div>
              <span className="font-medium text-[14px]">Authenticated</span>
            </div>
          ) : isAuthenticated && !isFresh ? (
            <div className="flex items-center gap-2.5 text-amber-600">
              <div className="w-8 h-8 bg-amber-50 rounded-lg flex items-center justify-center">
                <ShieldAlert className="w-[18px] h-[18px]" />
              </div>
              <span className="font-medium text-[14px]">Expired</span>
            </div>
          ) : (
            <div className="flex items-center gap-2.5 text-stone-400">
              <div className="w-8 h-8 bg-stone-100 rounded-lg flex items-center justify-center">
                <Shield className="w-[18px] h-[18px]" />
              </div>
              <span className="font-medium text-[14px]">Not Authenticated</span>
            </div>
          )}
        </div>

        {isAuthenticated && (
          <div className="grid grid-cols-2 gap-3 mb-6">
            {status?.email && (
              <div className="flex items-center gap-2.5 text-[13px] text-stone-500 bg-stone-50/50 rounded-lg px-3 py-2.5">
                <Mail className="w-4 h-4 text-stone-300" />
                <span>{status.email}</span>
              </div>
            )}
            {status?.ageHours !== undefined && (
              <div className="flex items-center gap-2.5 text-[13px] text-stone-500 bg-stone-50/50 rounded-lg px-3 py-2.5">
                <Clock className="w-4 h-4 text-stone-300" />
                <span>{status.ageHours}h old (max {status.maxAgeHours}h)</span>
              </div>
            )}
          </div>
        )}

        <div className="flex gap-2.5">
          <button
            onClick={runAuthSetup}
            disabled={running}
            className="flex items-center gap-2 px-4 py-2 bg-stone-900 text-white rounded-lg text-[13px] font-medium hover:bg-stone-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {running ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                Waiting for login...
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" />
                {isAuthenticated ? 'Refresh Auth' : 'Run Auth Setup'}
              </>
            )}
          </button>
          {isAuthenticated && (
            <button
              onClick={clearAuthState}
              className="flex items-center gap-2 px-4 py-2 border border-stone-200 text-stone-500 rounded-lg text-[13px] font-medium hover:bg-stone-50 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Clear State
            </button>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-stone-200/60 p-6 mb-5">
        <h2 className="text-[14px] font-semibold text-stone-700 mb-4">How It Works</h2>
        <ol className="space-y-2.5">
          {[
            'Click "Run Auth Setup" — a browser window opens on your machine',
            'Log in normally (email, OTP, etc.) in that browser',
            'When login succeeds, auth state is saved to .auth/{env}/',
            'Tests reuse cached auth for 24h — no re-login until it expires',
            'Or run from terminal: pnpm auth:setup',
          ].map((text, i) => (
            <li key={i} className="flex gap-3 text-[13px] text-stone-500 leading-relaxed">
              <span className="w-5 h-5 bg-stone-100 text-stone-400 rounded-md text-[11px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                {i + 1}
              </span>
              {text}
            </li>
          ))}
        </ol>
      </div>

      <div className="bg-white rounded-xl border border-stone-200/60 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <Settings className="w-4 h-4 text-stone-400" />
            <h2 className="text-[14px] font-semibold text-stone-700">Auth Config</h2>
          </div>
          <button
            onClick={() => setEditingConfig(!editingConfig)}
            className="text-[13px] text-stone-900 font-medium hover:underline"
          >
            {editingConfig ? 'Cancel' : 'Edit'}
          </button>
        </div>

        {editingConfig ? (
          <div>
            <textarea
              value={configJson}
              onChange={(e) => setConfigJson(e.target.value)}
              rows={16}
              className="w-full font-mono text-[12px] bg-stone-50/50 border border-stone-200/60 rounded-lg p-4 text-stone-600 focus:ring-2 focus:ring-stone-900/10 focus:border-stone-300 transition-all"
              spellCheck={false}
            />
            <div className="flex gap-2 mt-3">
              <button
                onClick={saveConfig}
                className="px-4 py-2 bg-stone-900 text-white rounded-lg text-[13px] font-medium hover:bg-stone-800 transition-colors"
              >
                Save Config
              </button>
              <button
                onClick={() => { setConfigJson(JSON.stringify(config, null, 2)); setEditingConfig(false); }}
                className="px-4 py-2 border border-stone-200 text-stone-500 rounded-lg text-[13px] font-medium hover:bg-stone-50 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-0">
            {[
              { label: 'Base URL', value: config?.baseUrl || '—' },
              { label: 'Method', value: config?.method || '—' },
              { label: 'Max Age', value: `${config?.maxAgeHours || 24} hours` },
              { label: 'Wait After Auth', value: `${config?.waitAfterAuth || 5000}ms` },
            ].map(({ label, value }, i, arr) => (
              <div key={label} className={`flex items-center justify-between py-3 ${i < arr.length - 1 ? 'border-b border-stone-100/80' : ''}`}>
                <span className="text-[13px] text-stone-400">{label}</span>
                <span className="text-[13px] font-mono text-stone-700">{value}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
