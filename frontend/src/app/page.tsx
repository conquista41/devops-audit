"use client";
import { useEffect, useState } from "react";
import { authApi } from "@/lib/api";

export default function Home() {
  const [loading, setLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) window.location.href = "/dashboard";
  }, []);

  const handleLogin = async () => {
    setLoading(true);
    try {
      const { data } = await authApi.getLoginUrl();
      window.location.href = data.url;
    } catch {
      setLoading(false);
    }
  };

  const handleDemo = async () => {
    setDemoLoading(true);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/auth/demo`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error("Demo login failed");
      const data = await res.json();
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      window.location.href = "/dashboard";
    } catch {
      setDemoLoading(false);
    }
  };

  return (
    <main className="min-h-screen grid-bg flex flex-col items-center justify-center relative overflow-hidden">

      {/* Ambient glow */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full"
        style={{ background: "radial-gradient(circle, rgba(0,255,148,0.04) 0%, transparent 70%)" }} />

      {/* Header */}
      <div className="absolute top-8 left-8 flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-accent animate-pulse2" />
        <span className="font-mono text-sm text-text-dim tracking-widest uppercase">DevOps Audit</span>
      </div>

      {/* Hero */}
      <div className="text-center max-w-2xl px-8 animate-fade-in">

        {/* Badge */}
        <div className="inline-flex items-center gap-2 border border-border rounded-full px-4 py-1.5 mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-accent" />
          <span className="font-mono text-xs text-text-dim tracking-wider">DEVOPS SECURITY AUDIT</span>
        </div>

        {/* Title */}
        <h1 className="font-mono text-5xl font-bold text-text mb-4 leading-tight">
          Your infra has
          <br />
          <span className="text-accent text-glow">blind spots.</span>
        </h1>

        <p className="text-text-dim text-lg mb-12 leading-relaxed font-light">
          Scan GitHub repos, Kubernetes configs, and Dockerfiles
          for security issues in minutes. Get a PDF report with fixes.
        </p>

        {/* CTA */}
        <button
          onClick={handleLogin}
          disabled={loading}
          className="group relative inline-flex items-center gap-3 bg-accent text-bg font-mono font-semibold px-8 py-4 rounded-lg text-sm tracking-wider transition-all duration-200 hover:bg-accent-dim glow-accent hover:glow-accent-strong disabled:opacity-50"
        >
          {loading ? (
            <>
              <span className="w-4 h-4 border-2 border-bg border-t-transparent rounded-full animate-spin" />
              CONNECTING...
            </>
          ) : (
            <>
              <GithubIcon />
              SCAN WITH GITHUB
            </>
          )}
        </button>

        <p className="mt-4 text-text-dim text-xs font-mono">
          Free plan · 3 scans/month · No credit card
        </p>

        <button
          onClick={handleDemo}
          disabled={demoLoading}
          className="mt-3 inline-flex items-center gap-2 border border-accent/40 text-accent font-mono text-xs px-5 py-2.5 rounded-lg tracking-wider transition-all duration-200 hover:border-accent hover:bg-accent/5 disabled:opacity-50"
        >
          {demoLoading ? (
            <span className="w-3 h-3 border border-accent border-t-transparent rounded-full animate-spin" />
          ) : null}
          Try Demo →
        </button>
      </div>

      {/* Feature grid */}
      <div className="absolute bottom-12 left-1/2 -translate-x-1/2 w-full max-w-2xl px-8">
        <div className="grid grid-cols-3 gap-4">
          {[
            { icon: "◈", label: "GitHub Scanner", desc: "Workflows, secrets, branch protection" },
            { icon: "⬡", label: "K8s Auditor", desc: "Security context, resource limits" },
            { icon: "▣", label: "Container Sec.", desc: "Dockerfile best practices, CVEs" },
          ].map((f) => (
            <div key={f.label} className="border border-border rounded-lg p-4 bg-surface/50 backdrop-blur">
              <div className="font-mono text-accent text-lg mb-2">{f.icon}</div>
              <div className="font-mono text-xs text-text font-semibold mb-1">{f.label}</div>
              <div className="text-text-dim text-xs">{f.desc}</div>
            </div>
          ))}
        </div>
      </div>

    </main>
  );
}

function GithubIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}
