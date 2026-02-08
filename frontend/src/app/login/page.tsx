"use client";

import { useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { LogIn, AlertCircle, Lock, Eye, EyeOff } from "lucide-react";
import { API_BASE } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showKey, setShowKey] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const trimmed = token.trim();
    if (!trimmed) {
      setError("Enter the admin key");
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: trimmed }),
      });

      if (res.ok) {
        // Non-sensitive flag for frontend proxy redirect gate
        document.cookie = "admin_logged_in=true; path=/; max-age=86400; SameSite=Lax";
        router.push("/");
      } else if (res.status === 429) {
        setError("Too many attempts. Try again later.");
      } else {
        setError("Invalid key");
      }
    } catch {
      setError("Connection error");
    }

    setLoading(false);
  }

  return (
    <div className="fixed inset-0 z-50 surface-bg flex items-center justify-center">
      <div className="w-full max-w-[400px] mx-4 animate-fade-in-up">
        {/* Header */}
        <div className="text-center mb-10">
          <Image src="/logo.png" alt="AI School" width={72} height={72} unoptimized className="rounded-2xl mx-auto mb-5 shadow-lg" />
          <h1 className="text-2xl font-semibold text-[#1D1D1F] tracking-tight">
            AI School
          </h1>
          <p className="text-sm text-[#86868B] mt-1">Admin Panel</p>
        </div>

        {/* Card */}
        <form onSubmit={handleSubmit} className="glass rounded-2xl p-7 space-y-5">
          <div>
            <label
              htmlFor="token"
              className="block text-sm font-medium text-[#1D1D1F] mb-2"
            >
              Admin Key
            </label>
            <div className="relative">
              <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#86868B]" />
              <input
                id="token"
                type={showKey ? "text" : "password"}
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Enter admin API key"
                autoFocus
                className="w-full pl-10 pr-10 py-3 rounded-xl glass-input text-[#1D1D1F] placeholder-[#86868B]/60 focus:outline-none text-sm"
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#86868B] hover:text-[#1D1D1F] transition-colors"
              >
                {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-[#FF3B30] text-sm bg-[#FF3B30]/8 px-3 py-2.5 rounded-xl">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span className="font-medium">{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-[#007AFF] text-white font-medium hover:bg-[#006AE0] active:scale-[0.98] disabled:opacity-50 transition-all duration-200 shadow-sm shadow-[#007AFF]/20"
          >
            {loading ? (
              <span>Checking...</span>
            ) : (
              <>
                <LogIn className="w-4 h-4" />
                <span>Sign In</span>
              </>
            )}
          </button>
        </form>

        <p className="text-center text-xs text-[#86868B] mt-6">
          Gen AI Course Assistant
        </p>
      </div>
    </div>
  );
}
