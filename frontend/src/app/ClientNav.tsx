"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export function ClientNav() {
  const [email, setEmail] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    const stored = localStorage.getItem("palm4u_email");
    if (stored) setEmail(stored);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("palm4u_token");
    localStorage.removeItem("palm4u_email");
    setEmail(null);
    router.push("/login");
  };

  return (
    <nav className="bg-slate-800 border-b border-slate-700 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-8">
        <Link href="/" className="text-xl font-bold text-white tracking-tight">
          PALM4U<span className="text-blue-400">madeeasy</span>
        </Link>
        <Link
          href="/"
          className="text-sm text-slate-300 hover:text-white transition-colors"
        >
          Dashboard
        </Link>
      </div>
      <div className="flex items-center gap-4">
        {email ? (
          <>
            <span className="text-sm text-slate-400">{email}</span>
            <button
              onClick={handleLogout}
              className="text-sm text-slate-300 hover:text-white transition-colors"
            >
              Logout
            </button>
          </>
        ) : (
          <Link
            href="/login"
            className="text-sm bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 transition-colors"
          >
            Login
          </Link>
        )}
      </div>
    </nav>
  );
}
