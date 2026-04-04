"use client";

import { useState, useEffect } from "react";
import { AdminTabs } from "./AdminTabs";
import { APP_CONFIG } from "../../../admin.config";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

const ADMIN_PIN_KEY = "admin_dashboard_auth";

function getAdminPin(): string {
  return process.env.NEXT_PUBLIC_ADMIN_PIN ?? APP_CONFIG.adminPin;
}

export function AdminShell({ kits }: { kits: unknown[] }) {
  const [authenticated, setAuthenticated] = useState(false);
  const [pin, setPin] = useState("");
  const [error, setError] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const stored = sessionStorage.getItem(ADMIN_PIN_KEY);
    if (stored === getAdminPin()) {
      setAuthenticated(true);
    }
    setChecking(false);
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (pin === getAdminPin()) {
      sessionStorage.setItem(ADMIN_PIN_KEY, pin);
      setAuthenticated(true);
      setError(false);
    } else {
      setError(true);
      setPin("");
    }
  }

  if (checking) return null;

  // PIN gate
  if (!authenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-slate-900 transition-colors">
        <div className="w-full max-w-xs">
          <div className="rounded-2xl bg-white dark:bg-slate-800 p-8 shadow-sm">
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-[#81D8D0]">
                <svg className="h-6 w-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <h1 className="mt-4 text-lg font-bold text-gray-900 dark:text-white">Admin Access</h1>
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">Enter PIN to continue</p>
            </div>
            <form onSubmit={handleSubmit} className="mt-6">
              <input
                type="password"
                maxLength={16}
                value={pin}
                onChange={(e) => { setPin(e.target.value); setError(false); }}
                placeholder="PIN"
                autoFocus
                className={`w-full rounded-xl border bg-gray-50 dark:bg-slate-700 px-4 py-3 text-center text-lg font-bold tracking-[0.3em] text-gray-900 dark:text-white outline-none transition ${
                  error ? "border-red-300 bg-red-50 dark:bg-red-900/20" : "border-gray-200 dark:border-slate-600 focus:border-[#81D8D0] focus:ring-1 focus:ring-[#81D8D0]"
                }`}
              />
              {error && (
                <p className="mt-2 text-center text-xs text-red-500">Incorrect PIN</p>
              )}
              <button
                type="submit"
                className="mt-4 flex h-11 w-full items-center justify-center rounded-xl bg-[#81D8D0] text-sm font-semibold text-white transition hover:bg-[#5FBFB6] active:scale-[0.98]"
              >
                Enter
              </button>
            </form>
          </div>
          <div className="mt-4 flex items-center justify-center gap-3">
            <p className="text-[10px] text-gray-300 dark:text-gray-600">{APP_CONFIG.name} Internal</p>
            <ThemeToggle />
          </div>
        </div>
      </div>
    );
  }

  // Authenticated — show admin panel
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900 transition-colors print:bg-white">
      {/* Header */}
      <header className="sticky top-0 z-30 border-b border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 print:hidden transition-colors">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#81D8D0]">
              <span className="text-xs font-bold text-white">{APP_CONFIG.shortName}</span>
            </div>
            <div className="hidden sm:block">
              <h1 className="text-sm font-bold text-gray-900 dark:text-white">{APP_CONFIG.name} Admin</h1>
              <p className="text-[10px] text-gray-400 dark:text-gray-500">{APP_CONFIG.tagline}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden text-[10px] text-gray-300 dark:text-gray-600 lg:inline">
              {"\u2318"}1-6 quick nav
            </span>
            <ThemeToggle />
            <button
              onClick={() => {
                sessionStorage.removeItem(ADMIN_PIN_KEY);
                setAuthenticated(false);
                setPin("");
              }}
              className="rounded-lg bg-gray-100 dark:bg-slate-700 px-3 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400 transition hover:bg-gray-200 dark:hover:bg-slate-600"
            >
              Lock
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <div className="mx-auto max-w-[1600px] print:max-w-none">
        <AdminTabs kits={kits} />
      </div>
    </div>
  );
}
