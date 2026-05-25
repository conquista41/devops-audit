"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { scanApi } from "@/lib/api";

interface Issue {
  severity: string;
  title: string;
  description: string;
  file?: string;
  line?: number;
  fix?: string;
}

interface ScanDetail {
  id: string;
  scan_type: string;
  status: string;
  target: string;
  score: number | null;
  issues_critical: number;
  issues_warning: number;
  issues_info: number;
  results?: { issues: Issue[] };
  error_message?: string;
  created_at: string;
}

const SEV_CONFIG = {
  critical: { color: "text-danger", border: "border-danger/30", bg: "bg-danger/5", label: "CRITICAL" },
  warning:  { color: "text-warning", border: "border-warning/30", bg: "bg-warning/5", label: "WARNING" },
  info:     { color: "text-info",    border: "border-info/30",    bg: "bg-info/5",    label: "INFO" },
};

export default function ScanDetail() {
  const { id } = useParams();
  const router = useRouter();
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    loadScan();
  }, [id]);

  useEffect(() => {
    if (!scan) return;
    if (scan.status === "pending" || scan.status === "running") {
      const t = setTimeout(loadScan, 3000);
      return () => clearTimeout(t);
    }
  }, [scan]);

  const loadScan = async () => {
    try {
      const { data } = await scanApi.get(id as string);
      setScan(data);
      console.log('scan data:', JSON.stringify(data));
    } finally {
      setLoading(false);
    }
  };

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-bg">
      <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (!scan) return (
    <div className="min-h-screen flex items-center justify-center bg-bg">
      <p className="font-mono text-text-dim">Scan not found</p>
    </div>
  );

  const issues: Issue[] = scan.results?.issues || [];
  const filtered = filter === "all" ? issues : issues.filter(i => i.severity === filter);

  const scoreColor = scan.score !== null
    ? scan.score >= 80 ? "#00FF94" : scan.score >= 60 ? "#FFB800" : "#FF4444"
    : "#4A4A6A";

  return (
    <div className="min-h-screen bg-bg">

      {/* Navbar */}
      <nav className="border-b border-border px-8 py-4 flex items-center gap-4">
        <button
          onClick={() => router.push("/dashboard")}
          className="font-mono text-xs text-text-dim hover:text-text transition-colors"
        >← BACK</button>
        <span className="text-border">/</span>
        <span className="font-mono text-xs text-text truncate">{scan.target}</span>
      </nav>

      <div className="max-w-4xl mx-auto px-8 py-12">

        {/* Status banner */}
        {(scan.status === "pending" || scan.status === "running") && (
          <div className="border border-warning/30 bg-warning/5 rounded-xl p-5 mb-8 flex items-center gap-4 animate-fade-in">
            <div className="w-5 h-5 border-2 border-warning border-t-transparent rounded-full animate-spin flex-shrink-0" />
            <div>
              <p className="font-mono text-warning text-sm font-semibold">
                {scan.status === "pending" ? "Queued..." : "Scanning..."}
              </p>
              <p className="text-text-dim text-xs mt-0.5">This usually takes 1-2 minutes. Page auto-refreshes.</p>
            </div>
          </div>
        )}

        {scan.status === "failed" && (
          <div className="border border-danger/30 bg-danger/5 rounded-xl p-5 mb-8">
            <p className="font-mono text-danger text-sm font-semibold mb-1">SCAN FAILED</p>
            <p className="text-text-dim text-xs font-mono">{scan.error_message}</p>
          </div>
        )}

        {/* Header */}
        {scan.status === "completed" && scan.score !== null && (
          <div className="flex items-start gap-8 mb-10 animate-fade-in">

            {/* Big score */}
            <div className="text-center flex-shrink-0">
              <div className="font-mono text-6xl font-bold mb-1" style={{ color: scoreColor }}>
                {scan.score}
              </div>
              <div className="font-mono text-xs text-text-dim">/ 100</div>
            </div>

            {/* Divider */}
            <div className="w-px self-stretch bg-border" />

            {/* Summary */}
            <div className="flex-1">
              <h1 className="font-mono text-xl font-bold text-text mb-2">{scan.target}</h1>
              <p className="text-text-dim text-sm mb-5">{scan.scan_type.toUpperCase()} scan</p>

              <div className="flex gap-6">
                <div>
                  <div className="font-mono text-2xl font-bold text-danger">{scan.issues_critical}</div>
                  <div className="font-mono text-xs text-text-dim">critical</div>
                </div>
                <div>
                  <div className="font-mono text-2xl font-bold text-warning">{scan.issues_warning}</div>
                  <div className="font-mono text-xs text-text-dim">warning</div>
                </div>
                <div>
                  <div className="font-mono text-2xl font-bold text-info">{scan.issues_info}</div>
                  <div className="font-mono text-xs text-text-dim">info</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Filter tabs */}
        {issues.length > 0 && (
          <div className="flex gap-2 mb-6">
            {["all", "critical", "warning", "info"].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`font-mono text-xs px-3 py-1.5 rounded-lg border transition-all ${
                  filter === f
                    ? "border-accent text-accent bg-accent/5"
                    : "border-border text-text-dim hover:border-muted"
                }`}
              >
                {f.toUpperCase()}
                {f !== "all" && (
                  <span className="ml-1.5 opacity-60">
                    {issues.filter(i => i.severity === f).length}
                  </span>
                )}
              </button>
            ))}
          </div>
        )}

        {/* Issues list */}
        <div className="space-y-3">
          {filtered.map((issue, i) => {
            const cfg = SEV_CONFIG[issue.severity as keyof typeof SEV_CONFIG] || SEV_CONFIG.info;
            return (
              <div
                key={i}
                className={`border ${cfg.border} ${cfg.bg} rounded-xl p-5 animate-slide-up`}
                style={{ animationDelay: `${i * 40}ms`, animationFillMode: "both" }}
              >
                <div className="flex items-start gap-3 mb-2">
                  <span className={`font-mono text-xs ${cfg.color} flex-shrink-0 mt-0.5`}>
                    {cfg.label}
                  </span>
                  <h3 className="font-mono text-sm text-text font-semibold">{issue.title}</h3>
                </div>

                <p className="text-text-dim text-sm mb-3 leading-relaxed">{issue.description}</p>

                {(issue.file || issue.line) && (
                  <div className="font-mono text-xs text-muted mb-3">
                    {issue.file}{issue.line ? `:${issue.line}` : ""}
                  </div>
                )}

                {issue.fix && (
                  <div className="border border-border rounded-lg p-3 bg-bg/50">
                    <span className="font-mono text-xs text-accent">FIX → </span>
                    <span className="font-mono text-xs text-text-dim">{issue.fix}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {scan.status === "completed" && issues.length === 0 && (
          <div className="text-center py-16 animate-fade-in">
            <div className="font-mono text-4xl text-accent mb-4">✓</div>
            <p className="font-mono text-accent text-sm">No issues found. Perfect score!</p>
          </div>
        )}

      </div>
    </div>
  );
}
