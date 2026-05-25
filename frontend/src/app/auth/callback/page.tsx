"use client";
import { useEffect } from "react";
import { useSearchParams } from "next/navigation";

export default function AuthCallback() {
  const params = useSearchParams();

  useEffect(() => {
    const access_token = params.get("access_token");
    const refresh_token = params.get("refresh_token");

    if (access_token && refresh_token) {
      localStorage.setItem("access_token", access_token);
      localStorage.setItem("refresh_token", refresh_token);
      window.location.href = "/dashboard";
    } else {
      window.location.href = "/";
    }
  }, [params]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="font-mono text-text-dim text-sm tracking-wider">AUTHENTICATING...</p>
      </div>
    </div>
  );
}
