"use client";
import { useEffect, useState } from "react";
import { userApi, scanApi } from "@/lib/api";
import NewScanModal from "@/components/NewScanModal";
import ScanCard from "@/components/ScanCard";

interface User {
  id: string;
  email: string;
  github_username: string;
  avatar_url: string;
  plan: string;
  scans_used_this_month: number;
  scan_limit: number;
}

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

export default function Dashboard() {
  const [user, setUser] = useState<User | null>(null);
  const [scans, setScans] = useState<Scan[]>([]);
  const [showNewScan, setShowNewScan] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      window.location.href = "/";
      return;
    }
    loadData();
  }, []);

  // Aktif scan varsa polling yap
  useEffect(() => {
    const hasActive = scans.some(
      (s) => s.status === "pending" || s.status === "running"
    );
    if (!hasActive) return;
    const interval = setInterval(loadScans, 3000);
    return () => clearInterval(interval);
  }, [scans]);

  const loadData = async () => {
    try {
      const [userRes, scansRes] = await Promise.all([
        userApi.getMe(),
        scanApi.list(),
      ]);
      setUser(userRes.data);
      setScans(scansRes.data);
    } finally {
      setLoading(false);
    }
  };

  const loadScans = async () => {
    const { data } = await scanApi.list();
    setScans(data);
  };

  const handleLogout = () => {
    localStorage.clear();
    window.location.href = "/";
  };

  const handleScanCreated = () => {
    setShowNewScan(false);
    loadScans();
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg">

      {/* Navbar */}
      <nav className="border-b border-border px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-accent animate-pulse2" />
          <span className="font-mono text-sm text-text tracking-widest uppercase">DevOps Audit</span>
        </div>

        <div className="flex items-center gap-6">
          {/* Plan badge */}
          <div className={`font-mono text-xs px-3 py-1 rounded-full border ${
            user?.plan === "pro"
              ? "border-accent text-accent"
              : "border-border text-text-dim"
          }`}>
            {user?.plan?.toUpperCase()}
          </div>

          {/* Scan usage */}
          <div className="font-mono text-xs text-text-dim">
            <span className="text-text">{user?.scans_used_this_month}</span>
            /{user?.scan_limit} scans
          </div>

          {/* Avatar */}
          {user?.avatar_url && (
            <img
              src={user.avatar_url}
              alt={user.github_username}
              className="w-7 h-7 rounded-full border border-border"
            />
          )}

          <button
            onClick={handleLogout}
            className="font-mono text-xs text-text-dim hover:text-text transition-colors"
          >
            LOGOUT
          </button>
        </div>
      </nav>

      {/* Main content */}
      <div className="max-w-4xl mx-auto px-8 py-12">

        {/* Header */}
        <div className="flex items-center justify-between mb-10">
          <div>
            <h1 className="font-mono text-2xl font-bold text-text mb-1">
              GM, <span className="text-accent">@{user?.github_username}</span>
            </h1>
            <p className="text-text-dim text-sm">
              {scans.length === 0
                ? "No scans yet. Start your first audit."
                : `${scans.length} scan${scans.length > 1 ? "s" : ""} total`}
            </p>
          </div>

          <button
            onClick={() => setShowNewScan(true)}
            disabled={user ? user.scans_used_this_month >= user.scan_limit : false}
            className="inline-flex items-center gap-2 bg-accent text-bg font-mono font-semibold px-5 py-2.5 rounded-lg text-sm tracking-wider transition-all hover:bg-accent-dim glow-accent disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <span>+</span> NEW SCAN
          </button>
        </div>

        {/* Empty state */}
        {scans.length === 0 && (
          <div className="border border-border border-dashed rounded-xl p-16 text-center animate-fade-in">
            <div className="font-mono text-4xl text-border mb-4">◈</div>
            <p className="font-mono text-text-dim text-sm mb-6">No scans yet</p>
            <button
              onClick={() => setShowNewScan(true)}
              className="font-mono text-xs text-accent hover:text-accent-dim transition-colors"
            >
              START YOUR FIRST SCAN →
            </button>
          </div>
        )}

        {/* Scan list */}
        <div className="space-y-3">
          {scans.map((scan, i) => (
            <div
              key={scan.id}
              className="animate-slide-up"
              style={{ animationDelay: `${i * 60}ms`, animationFillMode: "both" }}
            >
              <ScanCard scan={scan} />
            </div>
          ))}
        </div>

      </div>

      {/* New scan modal */}
      {showNewScan && (
        <NewScanModal
          onClose={() => setShowNewScan(false)}
          onCreated={handleScanCreated}
        />
      )}

    </div>
  );
}
