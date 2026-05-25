"use client";
import { useState } from "react";
import { scanApi } from "@/lib/api";

const SCAN_TYPES = [
  { value: "github",     icon: "◈", label: "GitHub",     desc: "Actions, secrets, branch protection" },
  { value: "container",  icon: "▣", label: "Container",  desc: "Dockerfile best practices" },
  { value: "kubernetes", icon: "⬡", label: "Kubernetes", desc: "K8s manifests & security" },
  { value: "full",       icon: "◉", label: "Full Audit", desc: "All checks combined" },
];

export default function NewScanModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [scanType, setScanType] = useState("github");
  const [target, setTarget] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!target.trim()) {
      setError("Target is required");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await scanApi.create({ scan_type: scanType, target: target.trim() });
      onCreated();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-bg/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-surface border border-border rounded-2xl p-8 w-full max-w-md animate-slide-up">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <h2 className="font-mono text-lg font-bold text-text">NEW SCAN</h2>
          <button
            onClick={onClose}
            className="text-muted hover:text-text transition-colors font-mono text-lg"
          >✕</button>
        </div>

        {/* Scan type */}
        <div className="mb-6">
          <label className="font-mono text-xs text-text-dim tracking-wider mb-3 block">
            SCAN TYPE
          </label>
          <div className="grid grid-cols-2 gap-2">
            {SCAN_TYPES.map((t) => (
              <button
                key={t.value}
                onClick={() => setScanType(t.value)}
                className={`p-3 rounded-lg border text-left transition-all ${
                  scanType === t.value
                    ? "border-accent bg-accent/5"
                    : "border-border hover:border-muted"
                }`}
              >
                <div className={`font-mono text-base mb-1 ${scanType === t.value ? "text-accent" : "text-text-dim"}`}>
                  {t.icon}
                </div>
                <div className="font-mono text-xs text-text font-semibold">{t.label}</div>
                <div className="text-text-dim text-xs mt-0.5">{t.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Target */}
        <div className="mb-6">
          <label className="font-mono text-xs text-text-dim tracking-wider mb-3 block">
            TARGET
          </label>
          <input
            type="text"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            placeholder={
              scanType === "github" || scanType === "container" || scanType === "full"
                ? "owner/repo"
                : "path/to/manifests"
            }
            className="w-full bg-bg border border-border rounded-lg px-4 py-3 font-mono text-sm text-text placeholder-muted focus:outline-none focus:border-accent transition-colors"
          />
          {error && (
            <p className="font-mono text-xs text-danger mt-2">{error}</p>
          )}
        </div>

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="w-full bg-accent text-bg font-mono font-semibold py-3 rounded-lg text-sm tracking-wider transition-all hover:bg-accent-dim glow-accent disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <span className="w-4 h-4 border-2 border-bg border-t-transparent rounded-full animate-spin" />
              STARTING...
            </>
          ) : (
            "START SCAN →"
          )}
        </button>

      </div>
    </div>
  );
}
