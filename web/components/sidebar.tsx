'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  FileJson,
  Play,
  BarChart3,
  Database,
  Shield,
  Zap,
  Layers,
} from 'lucide-react';

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/intents', label: 'Intents', icon: FileJson },
  { href: '/suites', label: 'Suites', icon: Layers },
  { href: '/run', label: 'Test Runner', icon: Play },
  { href: '/reports', label: 'Reports', icon: BarChart3 },
  { href: '/auth', label: 'Auth Setup', icon: Shield },
  { href: '/knowledgebase', label: 'Knowledgebase', icon: Database },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-[220px] bg-[#111110] text-white flex flex-col h-full shrink-0">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="w-7 h-7 bg-amber-400/90 rounded-lg flex items-center justify-center">
          <Zap className="w-4 h-4 text-[#111110]" />
        </div>
        <span className="font-semibold text-[13px] tracking-tight">Dorian FE Agent</span>
      </div>

      <nav className="flex-1 px-3 pt-2 space-y-0.5">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== '/' && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-2.5 px-3 py-[9px] rounded-lg text-[13px] transition-all duration-150 ${active
                ? 'bg-white/[0.08] text-white font-medium'
                : 'text-white/50 hover:bg-white/[0.04] hover:text-white/80'
                }`}
            >
              <Icon className="w-[15px] h-[15px]" strokeWidth={active ? 2 : 1.5} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="px-5 py-4">
        <p className="text-[11px] text-white/20 tracking-wide">v0.1.0</p>
      </div>
    </aside>
  );
}
