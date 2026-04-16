"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { admin, PalmRunnerConfig, PalmRunnerTestResult } from "@/lib/api";

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

interface PalmRunnerComponent {
  status: string;
  mode?: string;
  palm_version?: string;
  remote_url?: string | null;
  token_configured?: boolean;
  note?: string;
  error?: string;
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

interface AdminUserRow {
  id: number;
  email: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string | null;
}

interface AdminJobRow {
  job_id: number;
  user_id: number;
  project_id: number;
  job_type: string;
  status: string;
  worker_id: string | null;
  priority: number;
  retry_count: number;
  created_at: string | null;
  error_message: string | null;
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
  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [systemJobs, setSystemJobs] = useState<AdminJobRow[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // PALM runner config form state
  const [runnerConfig, setRunnerConfig] = useState<PalmRunnerConfig | null>(null);
  const [formMode, setFormMode] = useState<string>("stub");
  const [formUrl, setFormUrl] = useState<string>("");
  const [formToken, setFormToken] = useState<string>("");
  const [runnerSaving, setRunnerSaving] = useState(false);
  const [runnerTesting, setRunnerTesting] = useState(false);
  const [runnerMessage, setRunnerMessage] = useState<{
    type: "success" | "error" | "info";
    text: string;
  } | null>(null);

  async function saveRunner(e: React.FormEvent) {
    e.preventDefault();
    setRunnerSaving(true);
    setRunnerMessage(null);
    try {
      // Treat empty string as "clear" for URL; for token, treat empty as
      // "keep existing" to avoid accidentally wiping the saved secret.
      const body = {
        mode: formMode || null,
        remote_url: formUrl.trim() === "" ? null : formUrl.trim(),
        remote_token: formToken === "" ? null : formToken,
      };
      // If the user left the token blank AND there's already a saved one,
      // preserve it by sending undefined-equivalent semantics: we send null
      // which clears it — so detect and block that explicitly.
      if (
        body.remote_token === null &&
        runnerConfig?.token_configured &&
        runnerConfig?.remote_token_source === "db"
      ) {
        // Saved token exists; user didn't edit it. Re-fetch the current
        // config after save to preserve it by sending a sentinel null only
        // for fields the user actually changed.
        // Simpler: delete the key so the backend keeps the existing DB row
        // value. But our API treats null as "clear". To really preserve it,
        // omit the field — but pydantic requires all fields. Workaround:
        // we fetch current config and... actually, simplest for users:
        // warn if they'd clear the token.
        const proceed = window.confirm(
          "Leaving the token field blank will CLEAR the saved token. Continue?"
        );
        if (!proceed) {
          setRunnerSaving(false);
          return;
        }
      }
      const cfg = await admin.savePalmRunner(body);
      setRunnerConfig(cfg);
      setFormMode(cfg.mode);
      setFormUrl(cfg.remote_url ?? "");
      setFormToken("");
      setRunnerMessage({ type: "success", text: "Saved. Runs submitted from now on will use the new settings." });
      // Refresh /health so the top panel reflects the change.
      const h = await admin.health();
      setHealth(h);
    } catch (err) {
      setRunnerMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to save runner config",
      });
    } finally {
      setRunnerSaving(false);
    }
  }

  async function testRunner() {
    setRunnerTesting(true);
    setRunnerMessage(null);
    try {
      // If the form has an ad-hoc URL/token, test those; otherwise test
      // whatever is currently saved.
      const override =
        formUrl.trim() !== "" || formToken !== ""
          ? {
              remote_url: formUrl.trim() || undefined,
              remote_token: formToken || undefined,
            }
          : undefined;
      const result: PalmRunnerTestResult = await admin.testPalmRunner(override);
      if (result.ok) {
        const ver =
          (result.worker as { palm_version?: string } | undefined)?.palm_version ??
          "unknown";
        setRunnerMessage({
          type: "success",
          text: `Connected. Worker reports PALM v${ver} at ${result.url ?? ""}.`,
        });
      } else {
        setRunnerMessage({
          type: "error",
          text: result.error || "Connection test failed.",
        });
      }
    } catch (err) {
      setRunnerMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Test failed",
      });
    } finally {
      setRunnerTesting(false);
    }
  }

  async function reloadUsers() {
    setUsers(await admin.listUsers(50, 0));
  }

  async function toggleActive(u: AdminUserRow) {
    try {
      await admin.patchUser(u.id, { is_active: !u.is_active });
      await reloadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update user");
    }
  }

  async function toggleAdmin(u: AdminUserRow) {
    try {
      await admin.patchUser(u.id, { is_admin: !u.is_admin });
      await reloadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update user");
    }
  }

  useEffect(() => {
    async function load() {
      try {
        const [q, h, a, u, j, rc] = await Promise.all([
          admin.queueStats(),
          admin.health(),
          admin.auditLog(30),
          admin.listUsers(50, 0),
          admin.listJobs(50, 0),
          admin.getPalmRunner(),
        ]);
        setQueue(q);
        setHealth(h);
        setAudit(a);
        setUsers(u);
        setSystemJobs(j);
        setRunnerConfig(rc);
        setFormMode(rc.mode);
        setFormUrl(rc.remote_url ?? "");
        setFormToken("");
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

      {/* PALM Runner (ADR-005) */}
      <section className="bg-white rounded-lg border p-4" data-testid="palm-runner-panel">
        <h2 className="text-lg font-semibold mb-3">PALM Execution Backend</h2>
        {health && (() => {
          const runner = health.components.palm_runner as PalmRunnerComponent | undefined;
          if (!runner) {
            return <p className="text-sm text-slate-500">Runner status not reported by backend.</p>;
          }
          const mode = runner.mode ?? "unknown";
          const modeLabel: Record<string, string> = {
            stub: "Stub (synthetic output)",
            remote: "Remote Linux worker",
            local: "In-process mpirun",
          };
          const modeDescription: Record<string, string> = {
            stub: "No real PALM simulation. Outputs are synthetic NetCDF for pipeline testing. Results in the UI and reports are labelled accordingly.",
            remote: "PALM runs on a separate Linux host. Inputs are sent over HTTPS and outputs are fetched back automatically.",
            local: "PALM runs in-process on this host (Linux only).",
          };
          return (
            <div className="space-y-3">
              <div className="flex items-center gap-3 flex-wrap">
                <span
                  className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                    STATUS_COLORS[runner.status] || "text-slate-600 bg-slate-50"
                  }`}
                  data-testid="palm-runner-status"
                >
                  {runner.status.toUpperCase()}
                </span>
                <span className="text-sm">
                  Mode:{" "}
                  <strong data-testid="palm-runner-mode">{modeLabel[mode] ?? mode}</strong>
                </span>
                {runner.palm_version && (
                  <span className="text-sm text-slate-500">PALM v{runner.palm_version}</span>
                )}
              </div>

              {modeDescription[mode] && (
                <p className="text-xs text-slate-500">{modeDescription[mode]}</p>
              )}

              {mode === "remote" && (
                <div className="border rounded p-3 bg-slate-50 text-sm space-y-1">
                  <div>
                    Worker URL:{" "}
                    <code className="text-xs bg-white px-1.5 py-0.5 rounded border">
                      {runner.remote_url || "(not set)"}
                    </code>
                  </div>
                  <div>
                    Shared token:{" "}
                    <span
                      className={
                        runner.token_configured ? "text-green-600" : "text-red-600"
                      }
                    >
                      {runner.token_configured ? "configured" : "missing"}
                    </span>
                  </div>
                </div>
              )}

              {runner.error && (
                <p className="text-sm text-red-600" data-testid="palm-runner-error">
                  {runner.error}
                </p>
              )}

            </div>
          );
        })()}

        {/* Runtime-editable config form */}
        <form
          onSubmit={saveRunner}
          className="mt-4 border-t pt-4 space-y-3"
          data-testid="palm-runner-form"
        >
          <h3 className="text-sm font-semibold">Runtime configuration</h3>
          <p className="text-xs text-slate-500">
            Changes take effect immediately for new runs — no backend restart needed.
            Leave a field blank to fall back to the <code>PALM_RUNNER_MODE</code>,{" "}
            <code>PALM_REMOTE_URL</code>, or <code>PALM_REMOTE_TOKEN</code> environment
            variable.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="text-sm">
              <span className="block text-slate-600 mb-1">Mode</span>
              <select
                value={formMode}
                onChange={(e) => setFormMode(e.target.value)}
                className="w-full border rounded px-2 py-1.5"
                data-testid="runner-mode-select"
              >
                <option value="stub">stub (synthetic)</option>
                <option value="remote">remote (Linux worker)</option>
                <option value="local">local (mpirun)</option>
              </select>
              {runnerConfig && (
                <span className="text-xs text-slate-400 block mt-1">
                  currently from: <code>{runnerConfig.mode_source}</code>
                </span>
              )}
            </label>

            <label className="text-sm md:col-span-2">
              <span className="block text-slate-600 mb-1">Worker URL</span>
              <input
                type="url"
                value={formUrl}
                onChange={(e) => setFormUrl(e.target.value)}
                placeholder="https://palm-worker.example.com"
                className="w-full border rounded px-2 py-1.5 font-mono text-sm"
                data-testid="runner-url-input"
              />
              {runnerConfig && (
                <span className="text-xs text-slate-400 block mt-1">
                  currently from: <code>{runnerConfig.remote_url_source}</code>
                </span>
              )}
            </label>

            <label className="text-sm md:col-span-3">
              <span className="block text-slate-600 mb-1">
                Bearer token{" "}
                {runnerConfig?.token_configured && (
                  <span className="text-xs text-green-600">
                    (a token is already saved — leave blank to keep it)
                  </span>
                )}
              </span>
              <input
                type="password"
                value={formToken}
                onChange={(e) => setFormToken(e.target.value)}
                placeholder={
                  runnerConfig?.token_configured
                    ? "•••••••• (leave blank to keep the saved token)"
                    : "paste the shared secret from the Linux worker"
                }
                className="w-full border rounded px-2 py-1.5 font-mono text-sm"
                data-testid="runner-token-input"
                autoComplete="off"
              />
              {runnerConfig && (
                <span className="text-xs text-slate-400 block mt-1">
                  currently from: <code>{runnerConfig.remote_token_source}</code>
                </span>
              )}
            </label>
          </div>

          <div className="flex gap-2 items-center flex-wrap">
            <button
              type="submit"
              disabled={runnerSaving}
              className="px-4 py-1.5 bg-slate-900 text-white rounded hover:bg-slate-700 disabled:opacity-50"
              data-testid="runner-save-btn"
            >
              {runnerSaving ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              onClick={testRunner}
              disabled={runnerTesting}
              className="px-4 py-1.5 border rounded hover:bg-slate-50 disabled:opacity-50"
              data-testid="runner-test-btn"
            >
              {runnerTesting ? "Testing…" : "Test connection"}
            </button>
            {formMode === "stub" && (
              <span className="text-xs text-amber-700">
                Stub mode — simulations will produce synthetic output only.
              </span>
            )}
          </div>

          {runnerMessage && (
            <div
              className={`text-sm rounded p-2 border ${
                runnerMessage.type === "success"
                  ? "bg-green-50 border-green-200 text-green-800"
                  : runnerMessage.type === "error"
                  ? "bg-red-50 border-red-200 text-red-800"
                  : "bg-slate-50 border-slate-200 text-slate-700"
              }`}
              data-testid="runner-message"
            >
              {runnerMessage.text}
            </div>
          )}
        </form>
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

      {/* Users */}
      <section className="bg-white rounded-lg border p-4" data-testid="users-panel">
        <h2 className="text-lg font-semibold mb-3">Users ({users.length})</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="py-2 pr-3">ID</th>
                <th className="py-2 pr-3">Email</th>
                <th className="py-2 pr-3">Admin</th>
                <th className="py-2 pr-3">Active</th>
                <th className="py-2 pr-3">Created</th>
                <th className="py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b hover:bg-slate-50">
                  <td className="py-2 pr-3 text-xs">{u.id}</td>
                  <td className="py-2 pr-3">{u.email}</td>
                  <td className="py-2 pr-3">{u.is_admin ? "yes" : "no"}</td>
                  <td className="py-2 pr-3">
                    <span className={u.is_active ? "text-green-600" : "text-red-600"}>
                      {u.is_active ? "active" : "deactivated"}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-xs text-slate-400">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : "-"}
                  </td>
                  <td className="py-2 space-x-2">
                    <button
                      onClick={() => toggleActive(u)}
                      className="text-xs px-2 py-1 border rounded hover:bg-slate-100"
                    >
                      {u.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button
                      onClick={() => toggleAdmin(u)}
                      className="text-xs px-2 py-1 border rounded hover:bg-slate-100"
                    >
                      {u.is_admin ? "Demote" : "Promote"}
                    </button>
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-4 text-center text-slate-400">No users</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* System-wide Jobs */}
      <section className="bg-white rounded-lg border p-4" data-testid="system-jobs-panel">
        <h2 className="text-lg font-semibold mb-3">System-wide Jobs ({systemJobs.length})</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="py-2 pr-3">Job</th>
                <th className="py-2 pr-3">User</th>
                <th className="py-2 pr-3">Project</th>
                <th className="py-2 pr-3">Type</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 pr-3">Worker</th>
                <th className="py-2 pr-3">Retries</th>
                <th className="py-2">Created</th>
              </tr>
            </thead>
            <tbody>
              {systemJobs.map((j) => (
                <tr key={j.job_id} className="border-b hover:bg-slate-50">
                  <td className="py-2 pr-3 text-xs">#{j.job_id}</td>
                  <td className="py-2 pr-3 text-xs">{j.user_id}</td>
                  <td className="py-2 pr-3 text-xs">{j.project_id}</td>
                  <td className="py-2 pr-3 text-xs">{j.job_type}</td>
                  <td className="py-2 pr-3 text-xs font-medium">{j.status}</td>
                  <td className="py-2 pr-3 text-xs">{j.worker_id || "-"}</td>
                  <td className="py-2 pr-3 text-xs">{j.retry_count}</td>
                  <td className="py-2 text-xs text-slate-400">
                    {j.created_at ? new Date(j.created_at).toLocaleString() : "-"}
                  </td>
                </tr>
              ))}
              {systemJobs.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-4 text-center text-slate-400">No jobs</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
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
