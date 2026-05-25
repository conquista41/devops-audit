"use client";
import { useRouter } from "next/navigation";

interface Scan {
  id: string;
  scan_type: string;
  status: string;
  target: string;
  score: number | null;
  issues_critical: number;
  issues_warning: number;
  issues_info: number;
  created_at: string;
}

const STATUS_CONFIG = {
  pending:   { label: "QUEUED",   color: "text-text-dim",  dot: "bg-muted" },
  running:   { label: "SCANNING", color: "text-warning",   dot: "bg-warning animate-pulse" },
  completed: { label: "DONE",     color: "text-accent",    dot: "bg-accent" },
  failed:    { label: "FAILED",   color: "text-danger",    dot: "bg-danger" },
} as const;

const TYPE_ICON: Record<string, string> = {
  github:     "◈",
  kubernetes: "⬡",
  container:  "▣",
  cost:       "◎",
  full:       "◉",
};

function ScoreRing({ score }: { score: number }) {
  const r = 20;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  const color = score >= 80 ? "#00FF94" : score >= 60 ? "#FFB800" : "#FF4444";

  return (
    <div className="relative w-14 h-14 flex-shrink-0">
      <svg width="56" height="56" viewBox="0 0 56 56">
        <circle cx="28" cy="28" r={r} fill="none" stroke="#1E1E2E" strokeWidth="3" />
        <circle
          cx="28" cy="28" r={r}
          fill="none"
          stroke={color}
          strokeWidth="3"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 28 28)"
          style={{ transition: "stroke-dashoffset 1s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="font-mono text-xs font-bold" style={{ color }}>{score}</span>
      </div>
    </div>
  );
}

export default function ScanCard({ scan }: { scan: Scan }) {
  const router = useRouter();
  const status = STATUS_CONFIG[scan.status as keyof typeof STATUS_CONFIG] || STATUS_CONFIG.pending;
  const date = new Date(scan.created_at).toLocaleDateString("tr-TR", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit"
  });

  return (
    <div
      onClick={() => router.push(`/scans/${scan.id}`)}
      className="group border border-border rounded-xl p-5 bg-surface hover:border-muted transition-all cursor-pointer flex items-center gap-5"
    >
      {/* Type icon */}
      <div className="w-10 h-10 rounded-lg border border-border flex items-center justify-center font-mono text-accent text-lg flex-shrink-0 group-hover:border-accent/30 transition-colors">
        {TYPE_ICON[scan.scan_type] || "◈"}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-mono text-sm text-text font-medium truncate">{scan.target}</span>
          <span className="font-mono text-xs text-text-dim uppercase flex-shrink-0">{scan.scan_type}</span>
        </div>

        <div className="flex items-center gap-4">
          {/* Status */}
          <div className="flex items-center gap-1.5">
            <div className={`w-1.5 h-1.5 rounded-full ${status.dot}`} />
            <span className={`font-mono text-xs ${status.color}`}>{status.label}</span>
          </div>

          {/* Issues */}
          {scan.status === "completed" && (
            <div className="flex items-center gap-3">
              {scan.issues_critical > 0 && (
                <span className="font-mono text-xs text-danger">{scan.issues_critical} critical</span>
              )}
              {scan.issues_warning > 0 && (
                <span className="font-mono text-xs text-warning">{scan.issues_warning} warning</span>
              )}
              {scan.issues_info > 0 && (
                <span className="font-mono text-xs text-info">{scan.issues_info} info</span>
              )}
            </div>
          )}

          {/* Date */}
          <span className="font-mono text-xs text-muted ml-auto">{date}</span>
        </div>
      </div>

      {/* Score */}
      {scan.score !== null && scan.status === "completed" && (
        <ScoreRing score={scan.score} />
      )}

      {/* Running spinner */}
      {scan.status === "running" && (
        <div className="w-14 h-14 flex items-center justify-center flex-shrink-0">
          <div className="w-6 h-6 border-2 border-warning border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {/* Arrow */}
      <div className="text-muted group-hover:text-text-dim transition-colors flex-shrink-0 font-mono text-sm">→</div>
    </div>
  );
}
