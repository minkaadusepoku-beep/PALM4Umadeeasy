"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { projects as projectsApi } from "@/lib/api";
import type { Project } from "@/lib/types";

export default function DashboardPage() {
  const [authenticated, setAuthenticated] = useState(false);
  const [projectList, setProjectList] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("palm4u_token");
    if (!token) {
      setAuthenticated(false);
      setLoading(false);
      return;
    }
    setAuthenticated(true);
    loadProjects();
  }, []);

  async function loadProjects() {
    try {
      const data = await projectsApi.list();
      setProjectList(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    setError("");
    try {
      const created = await projectsApi.create(newName, newDesc);
      setProjectList((prev) => [created, ...prev]);
      setNewName("");
      setNewDesc("");
      setShowForm(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setCreating(false);
    }
  }

  if (!authenticated) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-3xl font-bold mb-4">PALM4Umadeeasy</h1>
          <p className="text-slate-400 mb-6">
            Urban microclimate decision support platform
          </p>
          <Link
            href="/login"
            className="bg-blue-600 hover:bg-blue-700 text-white rounded px-6 py-3 text-lg transition-colors"
          >
            Login to get started
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 p-8 max-w-5xl mx-auto w-full">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">Projects</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 transition-colors"
        >
          {showForm ? "Cancel" : "New Project"}
        </button>
      </div>

      {error && <p className="text-red-500 mb-4">{error}</p>}

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="bg-slate-800 rounded-lg shadow-md p-6 mb-6"
        >
          <div className="mb-4">
            <label className="block text-sm text-slate-300 mb-1">
              Project Name
            </label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="e.g. Cologne Ehrenfeld Study"
              required
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm text-slate-300 mb-1">
              Description
            </label>
            <textarea
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={2}
              placeholder="Brief description of the study area and goals"
            />
          </div>
          <button
            type="submit"
            disabled={creating}
            className="bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 disabled:opacity-50 transition-colors"
          >
            {creating ? "Creating..." : "Create Project"}
          </button>
        </form>
      )}

      {loading ? (
        <p className="text-slate-400">Loading projects...</p>
      ) : projectList.length === 0 ? (
        <div className="bg-slate-800 rounded-lg shadow-md p-8 text-center">
          <p className="text-slate-400">
            No projects yet. Create one to get started.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {projectList.map((project) => (
            <Link
              key={project.id}
              href={`/projects/${project.id}`}
              className="bg-slate-800 rounded-lg shadow-md p-6 hover:bg-slate-750 hover:ring-1 hover:ring-blue-500 transition-all block"
            >
              <h2 className="text-lg font-semibold mb-1">{project.name}</h2>
              <p className="text-sm text-slate-400 mb-3">
                {project.description || "No description"}
              </p>
              <div className="flex items-center gap-4 text-xs text-slate-500">
                <span>
                  {project.scenario_count ?? 0} scenario
                  {project.scenario_count !== 1 ? "s" : ""}
                </span>
                <span>
                  Created{" "}
                  {new Date(project.created_at).toLocaleDateString()}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
