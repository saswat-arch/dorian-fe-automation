import Link from 'next/link';
import {
  FileJson,
  Play,
  BarChart3,
  Database,
  CheckCircle,
  XCircle,
  Zap,
  ArrowRight,
  TrendingUp,
  Shield,
} from 'lucide-react';

async function getStats() {
  try {
    const res = await fetch(`http://localhost:${process.env.PORT ?? 3000}/api/stats`, {
      cache: 'no-store',
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ElementType;
  accent: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-stone-200/60 p-5 hover:shadow-[0_1px_3px_rgba(0,0,0,0.04)] transition-shadow">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[13px] text-stone-400 font-medium">{label}</p>
          <p className="text-2xl font-bold text-stone-900 mt-1.5 tracking-tight">{value}</p>
          {sub && <p className="text-[11px] text-stone-400 mt-1">{sub}</p>}
        </div>
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${accent}`}>
          <Icon className="w-[18px] h-[18px]" strokeWidth={1.75} />
        </div>
      </div>
    </div>
  );
}

function QuickAction({
  href,
  label,
  description,
  icon: Icon,
  accent,
}: {
  href: string;
  label: string;
  description: string;
  icon: React.ElementType;
  accent: string;
}) {
  return (
    <Link
      href={href}
      className="group flex items-start gap-3.5 p-4 bg-white rounded-xl border border-stone-200/60 hover:border-stone-300/80 hover:shadow-[0_1px_3px_rgba(0,0,0,0.04)] transition-all"
    >
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${accent}`}>
        <Icon className="w-[18px] h-[18px]" strokeWidth={1.75} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-stone-800 text-[14px]">{label}</p>
        <p className="text-[13px] text-stone-400 mt-0.5 leading-relaxed">{description}</p>
      </div>
      <ArrowRight className="w-4 h-4 text-stone-300 group-hover:text-stone-500 mt-0.5 shrink-0 transition-colors" />
    </Link>
  );
}

export default async function DashboardPage() {
  const stats = await getStats();

  const passRate = stats?.passRate ?? null;
  const intentCount = stats?.intentCount ?? 0;
  const reportCount = stats?.reportCount ?? 0;
  const lastRunAt = stats?.lastRunAt ? new Date(stats.lastRunAt).toLocaleString() : null;
  const lastRunPassed = stats?.lastRunPassed;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-10">
        <h1 className="text-[26px] font-bold text-stone-900 tracking-tight">Dashboard</h1>
        <p className="text-stone-400 text-[14px] mt-1">AI-powered QA automation with self-healing selectors</p>
      </div>

      {lastRunAt !== null && (
        <div
          className={`flex items-center gap-3 px-4 py-3 rounded-xl mb-7 ${
            lastRunPassed
              ? 'bg-emerald-50/60 border border-emerald-200/50 text-emerald-800'
              : 'bg-red-50/60 border border-red-200/50 text-red-800'
          }`}
        >
          {lastRunPassed ? (
            <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0" />
          ) : (
            <XCircle className="w-4 h-4 text-red-500 shrink-0" />
          )}
          <span className="text-[13px] font-medium">
            Last run: {lastRunPassed ? 'Passed' : 'Failed'} &mdash; {lastRunAt}
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-10">
        <StatCard label="Intents" value={intentCount} sub="test files" icon={FileJson} accent="bg-blue-50 text-blue-500" />
        <StatCard label="Pass Rate" value={passRate !== null ? `${passRate}%` : '—'} sub="last 10 runs" icon={TrendingUp} accent="bg-emerald-50 text-emerald-500" />
        <StatCard label="Total Runs" value={reportCount} sub="reports saved" icon={BarChart3} accent="bg-violet-50 text-violet-500" />
        <StatCard label="Healed" value={stats?.totalHealed ?? '—'} sub="selectors auto-fixed" icon={Zap} accent="bg-amber-50 text-amber-500" />
      </div>

      <p className="text-[11px] font-semibold text-stone-400 uppercase tracking-widest mb-3">Quick Actions</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mb-10">
        <QuickAction href="/run" label="Run Tests" description="Execute intents with real-time output" icon={Play} accent="bg-emerald-50 text-emerald-500" />
        <QuickAction href="/intents/new" label="Create Intent" description="Import from Jam or write JSON" icon={FileJson} accent="bg-blue-50 text-blue-500" />
        <QuickAction href="/auth" label="Auth Setup" description="Configure persistent login state" icon={Shield} accent="bg-amber-50 text-amber-500" />
        <QuickAction href="/reports" label="View Reports" description="Browse historical test results" icon={BarChart3} accent="bg-violet-50 text-violet-500" />
      </div>

      <div className="bg-[#111110] rounded-xl p-6 text-white">
        <h2 className="font-semibold text-[14px] mb-4 flex items-center gap-2 tracking-tight">
          <Zap className="w-4 h-4 text-amber-400" />
          3-Tier Self-Healing Selectors
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { tier: '1', name: 'Cached', desc: 'Previously resolved selectors with high confidence' },
            { tier: '2', name: 'Smart Selector', desc: '8 strategies: testId, role, label, text, css...' },
            { tier: '3', name: 'AI Resolver', desc: 'Claude Vision + DOM analysis to locate elements' },
          ].map(({ tier, name, desc }) => (
            <div key={tier} className="bg-white/[0.05] border border-white/[0.06] rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-5 h-5 bg-amber-400 text-[#111110] rounded-full text-[10px] font-bold flex items-center justify-center">
                  {tier}
                </span>
                <span className="font-medium text-[13px]">{name}</span>
              </div>
              <p className="text-[12px] text-white/40 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
