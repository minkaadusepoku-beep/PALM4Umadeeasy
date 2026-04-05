"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { auth } from "@/lib/api";

type Tab = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      let token: string;
      if (tab === "register") {
        const res = await auth.register(email, password);
        token = res.access_token;
      } else {
        const res = await auth.login(email, password);
        token = res.access_token;
      }
      localStorage.setItem("palm4u_token", token);
      localStorage.setItem("palm4u_email", email);
      router.push("/");
      window.location.href = "/";
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex-1 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-slate-800 rounded-lg shadow-md p-8">
          <h1 className="text-2xl font-bold mb-6 text-center">
            PALM4U<span className="text-blue-400">madeeasy</span>
          </h1>

          {/* Tab toggle */}
          <div className="flex mb-6 bg-slate-700 rounded overflow-hidden">
            <button
              onClick={() => { setTab("login"); setError(""); }}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${
                tab === "login"
                  ? "bg-blue-600 text-white"
                  : "text-slate-300 hover:text-white"
              }`}
            >
              Login
            </button>
            <button
              onClick={() => { setTab("register"); setError(""); }}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${
                tab === "register"
                  ? "bg-blue-600 text-white"
                  : "text-slate-300 hover:text-white"
              }`}
            >
              Register
            </button>
          </div>

          {error && (
            <div className="bg-red-900/30 border border-red-700 rounded p-3 mb-4">
              <p className="text-red-500 text-sm">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label className="block text-sm text-slate-300 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>
            <div className="mb-6">
              <label className="block text-sm text-slate-300 mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
                minLength={6}
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 font-medium disabled:opacity-50 transition-colors"
            >
              {loading
                ? "Please wait..."
                : tab === "login"
                ? "Login"
                : "Create Account"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
