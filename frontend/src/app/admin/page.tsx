"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { admin, auth } from "@/lib/api";

interface QueueStats {
  jobs: Record<string, number>;
  stale_workers: number;
  active_workers: number;
}

interface HealthData {
  status: string;
  timestamp: string;
  components: Record<string, { status: string; [key: string]: unknown }>;
}

interface AuditEntry {
  id: number;
  user_id: number | null;
  action: string;
  resource_type: string;
  resource_id: number | null;
  detail: string | null;
  ip_address: string | null;
  created_at: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  healthy: "text-green-600 bg-green-50",
  degraded: "text-amber-600 bg-amber-50",
  unhealthy: "text-red-600 bg-red-50",
};

export default function AdminDashboard() {
  const router = useRouter();
  const [queue, setQueue] = useState<QueueStats | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [q, h, a] = await Promise.all([
          admin.queueStats(),
          admin.health(),
          admin.auditLog(30),
        ]);
        setQueue(q);
        setHealth(h);
        setAudit(a);
      } catch (err: unknown) {
        if (err instanceof Error && err.message.includes("403")) {
          setError("Admin access required");
        } else {
          setError(err instanceof Error ? err.message : "Failed to load");
        }
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-slate-400">Loading admin dashboard...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 text-lg">{error}</p>
          <button
            onClick={() => router.push("/")}
            className="mt-4 px-4 py-2 bg-slate-200 rounded hover:bg-slate-300"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6" data-testid="admin-dashboard">
      <h1 className="text-2xl font-bold">Operations Dashboard</h1>

      {/* Health Status */}
      <section className="bg-white rounded-lg border p-4" data-testid="health-panel">
        <h2 className="text-lg font-semibold mb-3">System Health</h2>
        {health && (
          <div className="space-y-2">
            <div className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${STATUS_COLORS[health.status] || "text-slate-600 bg-slate-50"}`}>
              {health.status.toUpperCase()}
            </div>
            <div className="grid grid-cols-3 gap-4 mt-3">
              {Object.entries(health.components).map(([name, comp]) => (
                <div key={name} className="border rounded p-3">
                  <div className="text-sm text-slate-500 capitalize">{name}</div>
                  <div className={`text-sm font-medium ${STATUS_COLORS[comp.status] || ""}`}>
                    {comp.status}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Queue Stats */}
      <section className="bg-white rounded-lg border p-4" data-testid="queue-panel">
        <h2 className="text-lg font-semibold mb-3">Job Queue</h2>
        {queue && (
          <div className="space-y-3">
            <div className="grid grid-cols-5 gap-3">
              {["queued", "running", "completed", "failed", "cancelled"].map((status) => (
                <div key={status} className="border rounded p-3 text-center">
                  <div className="text-2xl font-bold">{queue.jobs[status] || 0}</div>
                  <div className="text-xs text-slate-500 capitalize">{status}</div>
                </div>
              ))}
            </div>
            <div className="flex gap-4 text-sm">
              <span>Active workers: <strong>{queue.active_workers}</strong></span>
              <span>
                Stale workers:{" "}
                <strong className={queue.stale_workers > 0 ? "text-red-600" : ""}>
                  {queue.stale_workers}
                </strong>
              </span>
            </div>
          </div>
        )}
      </section>

      {/* Audit Log */}
      <section className="bg-white rounded-lg border p-4" data-testid="audit-panel">
        <h2 className="text-lg font-semibold mb-3">Recent Audit Log</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="py-2 pr-3">Time</th>
                <th className="py-2 pr-3">Action</th>
                <th className="py-2 pr-3">Resource</th>
                <th className="py-2 pr-3">User ID</th>
                <th className="py-2 pr-3">IP</th>
                <th className="py-2">Detail</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((entry) => (
                <tr key={entry.id} className="border-b hover:bg-slate-50">
                  <td className="py-2 pr-3 text-xs text-slate-400">
                    {entry.created_at ? new Date(entry.created_at).toLocaleString() : "-"}
                  </td>
                  <td className="py-2 pr-3 font-mono text-xs">{entry.action}</td>
                  <td className="py-2 pr-3">{entry.resource_type}{entry.resource_id ? `#${entry.resource_id}` : ""}</td>
                  <td className="py-2 pr-3">{entry.user_id ?? "-"}</td>
                  <td className="py-2 pr-3 text-xs">{entry.ip_address || "-"}</td>
                  <td className="py-2 text-xs text-slate-500">{entry.detail || "-"}</td>
                </tr>
              ))}
              {audit.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-4 text-center text-slate-400">No audit entries yet</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
