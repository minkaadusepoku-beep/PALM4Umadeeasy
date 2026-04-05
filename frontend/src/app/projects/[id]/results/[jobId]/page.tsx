"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import { jobs as jobsApi, exports_ } from "@/lib/api";
import type {
  Job,
  ComfortStatistics,
  PETClassification,
  DeltaStatistics,
  ThresholdImpact,
  DataQualityTier,
} from "@/lib/types";

// VDI 3787 PET class colours
const PET_COLORS: Record<string, string> = {
  "extreme_cold_stress": "bg-blue-900",
  "strong_cold_stress": "bg-blue-700",
  "moderate_cold_stress": "bg-blue-500",
  "slight_cold_stress": "bg-blue-300",
  "no_thermal_stress": "bg-green-500",
  "slight_heat_stress": "bg-yellow-400",
  "moderate_heat_stress": "bg-orange-400",
  "strong_heat_stress": "bg-red-500",
  "extreme_heat_stress": "bg-red-800",
};

function tierBadge(tier: DataQualityTier) {
  const colors: Record<DataQualityTier, string> = {
    screening: "bg-red-600",
    project: "bg-amber-600",
    research: "bg-green-600",
  };
  return (
    <span className={`${colors[tier]} text-white text-xs font-bold px-2 py-0.5 rounded uppercase`}>
      {tier}
    </span>
  );
}

interface ConfidenceData {
  headline: string;
  detail: string;
  caveats: string[];
  suitable_for: string[];
  not_suitable_for: string[];
  tier?: string;
  level?: string;
}

interface ResultsData {
  type?: string;
  // From executor: statistics as dict keyed by variable name
  statistics?: Record<string, {
    mean: number; median: number; std: number;
    p05: number; p95: number; min_val: number; max_val: number; n_valid: number;
  }>;
  // Or as array
  comfort_statistics?: ComfortStatistics[];
  pet_classification?: PETClassification;
  data_quality_tier?: DataQualityTier;
  confidence?: ConfidenceData;
  timesteps?: number[];
  n_timesteps?: number;
  green_roofs?: { building_id: string }[];
  domain?: { west: number; south: number; east: number; north: number; epsg: number };
  // Comparison fields (embedded in same response)
  delta_statistics?: Record<string, DeltaStatistics> | DeltaStatistics[];
  threshold_impacts?: ThresholdImpact[];
  ranked_improvements?: { variable: string; region_description: string; mean_delta: number; area_m2: number }[];
  intervention_statistics?: Record<string, {
    mean: number; median: number; std: number;
    p05: number; p95: number; min_val: number; max_val: number; n_valid: number;
  }>;
}

export default function ResultsPage() {
  const params = useParams();
  const projectId = Number(params.id);
  const jobId = Number(params.jobId);

  const [job, setJob] = useState<Job | null>(null);
  const [results, setResults] = useState<ResultsData | null>(null);
  const [error, setError] = useState("");
  const [timestep, setTimestep] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval>>(undefined);

  useEffect(() => {
    loadJob();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [jobId]);

  async function loadJob() {
    try {
      const j = await jobsApi.get(jobId);
      setJob(j);
      if (j.status === "completed") {
        loadResults(j);
      } else if (j.status === "pending" || j.status === "running") {
        pollRef.current = setInterval(async () => {
          const updated = await jobsApi.get(jobId);
          setJob(updated);
          if (updated.status === "completed" || updated.status === "failed") {
            if (pollRef.current) clearInterval(pollRef.current);
            if (updated.status === "completed") loadResults(updated);
          }
        }, 3000);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load job");
    }
  }

  async function loadResults(j: Job) {
    try {
      const r = (await jobsApi.getResults(j.job_id)) as unknown as ResultsData;
      setResults(r);
      if (r.timesteps && r.timesteps.length > 0) setTimestep(0);

      // For comparison jobs, the comparison data is in the same result object
      // (executor embeds delta_statistics, threshold_impacts, ranked_improvements)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load results");
    }
  }

  const dataTier: DataQualityTier = results?.data_quality_tier || "screening";

  // Pending / running states
  if (!job) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-slate-400">{error || "Loading..."}</p>
      </div>
    );
  }

  if (job.status === "pending" || job.status === "running") {
    return (
      <div className="flex-1 flex items-center justify-center" data-testid="job-monitor">
        <div className="text-center">
          <div className="animate-spin w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-lg font-medium" data-testid="job-status">Simulation {job.status}...</p>
          <p className="text-sm text-slate-400 mt-1">
            Job #{job.job_id || job.id} &mdash; polling for updates
          </p>
        </div>
      </div>
    );
  }

  if (job.status === "failed") {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-md">
          <p className="text-red-500 text-lg font-medium mb-2">
            Simulation Failed
          </p>
          <p className="text-sm text-slate-400">
            {job.error_message || "Unknown error"}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 max-w-6xl mx-auto w-full" data-testid="results-page">
      {/* SCREENING watermark */}
      {dataTier === "screening" && (
        <div className="fixed inset-0 pointer-events-none flex items-center justify-center z-50">
          <span className="text-red-500/10 text-[8rem] font-black rotate-[-30deg] select-none">
            SCREENING
          </span>
        </div>
      )}

      {error && <p className="text-red-500 mb-4">{error}</p>}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Simulation Results</h1>
          <p className="text-sm text-slate-400">
            Job #{job.job_id || job.id} &mdash; {job.job_type} &mdash; completed{" "}
            {job.completed_at
              ? new Date(job.completed_at).toLocaleString()
              : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {tierBadge(dataTier)}
        </div>
      </div>

      {/* Confidence panel */}
      {results?.confidence && (
        <div className="bg-slate-800 rounded-lg shadow-md p-6 mb-6 border-l-4 border-amber-500">
          <h2 className="text-lg font-bold mb-2 text-amber-400" data-testid="confidence-heading">
            Confidence Assessment
          </h2>
          <p className="font-semibold text-white mb-1">
            {results.confidence.headline}
          </p>
          <p className="text-sm text-slate-300 mb-3">
            {results.confidence.detail}
          </p>
          {results.confidence.caveats.length > 0 && (
            <div className="mb-3">
              <h4 className="text-xs uppercase text-slate-500 font-semibold mb-1">
                Caveats
              </h4>
              <ul className="list-disc list-inside text-sm text-amber-500 space-y-0.5">
                {results.confidence.caveats.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="text-xs uppercase text-green-500 font-semibold mb-1">
                Suitable For
              </h4>
              <ul className="text-sm text-slate-300 space-y-0.5">
                {results.confidence.suitable_for.map((s, i) => (
                  <li key={i}>+ {s}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-xs uppercase text-red-500 font-semibold mb-1">
                Not Suitable For
              </h4>
              <ul className="text-sm text-slate-300 space-y-0.5">
                {results.confidence.not_suitable_for.map((s, i) => (
                  <li key={i}>- {s}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Green roofs warning */}
      {results?.green_roofs && results.green_roofs.length > 0 && (
        <div className="bg-red-900/20 border border-red-700 rounded-lg p-4 mb-6">
          <p className="text-red-500 font-bold text-sm">
            Green Roofs (NOT YET SIMULATED — ignored in PALM input)
          </p>
          <p className="text-xs text-slate-400 mt-1">
            {results.green_roofs.length} green roof(s) defined but excluded
            from simulation.
          </p>
        </div>
      )}

      {/* Summary statistics */}
      {(results?.statistics || results?.comfort_statistics) && (
        <section className="mb-6" data-testid="summary-statistics">
          <h2 className="text-lg font-bold mb-3">Summary Statistics</h2>
          <div className="grid gap-4 md:grid-cols-3">
            {(() => {
              const stats = results.statistics
                ? Object.entries(results.statistics).map(([variable, s]) => ({ variable, ...s }))
                : results.comfort_statistics || [];
              return stats.map((stat) => (
                <div
                  key={stat.variable}
                  className="bg-slate-800 rounded-lg shadow-md p-4"
                >
                  <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">
                    {stat.variable}
                  </h3>
                  <div className="text-2xl font-bold">
                    {stat.mean.toFixed(1)}
                    <span className="text-sm text-slate-400 ml-1">mean</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 mt-2 text-xs text-slate-400">
                    <div>
                      <span className="block text-slate-500">Median</span>
                      {stat.median.toFixed(1)}
                    </div>
                    <div>
                      <span className="block text-slate-500">P05</span>
                      {stat.p05.toFixed(1)}
                    </div>
                    <div>
                      <span className="block text-slate-500">P95</span>
                      {stat.p95.toFixed(1)}
                    </div>
                  </div>
                </div>
              ));
            })()}
          </div>
        </section>
      )}

      {/* PET Classification */}
      {results?.pet_classification && (
        <section className="mb-6">
          <h2 className="text-lg font-bold mb-3">
            PET Classification (VDI 3787)
          </h2>
          <div className="bg-slate-800 rounded-lg shadow-md p-4">
            <div className="space-y-2">
              {Object.entries(results.pet_classification.class_fractions).map(
                ([cls, frac]) => (
                  <div key={cls} className="flex items-center gap-3">
                    <div
                      className={`w-4 h-4 rounded ${
                        PET_COLORS[cls] || "bg-slate-500"
                      }`}
                    />
                    <span className="text-sm flex-1">
                      {cls.replace(/_/g, " ")}
                    </span>
                    <span className="text-sm font-mono">
                      {((frac as number) * 100).toFixed(1)}%
                    </span>
                  </div>
                )
              )}
            </div>
            <div className="mt-3 pt-3 border-t border-slate-700 text-sm">
              <span className="text-slate-400">Dominant class: </span>
              <span className="font-medium">
                {results.pet_classification.dominant_class.replace(/_/g, " ")}
              </span>
              <span className="text-slate-400 ml-4">Stress level: </span>
              <span className="font-medium">
                {results.pet_classification.stress_level}
              </span>
            </div>
          </div>
        </section>
      )}

      {/* Time slider + map */}
      <section className="mb-6" data-testid="spatial-results">
        <h2 className="text-lg font-bold mb-3">Spatial Results</h2>
        {results?.timesteps && results.timesteps.length > 1 && (
          <div className="mb-3 flex items-center gap-4">
            <label className="text-sm text-slate-400">Timestep:</label>
            <input
              type="range"
              min={0}
              max={results.timesteps.length - 1}
              value={timestep}
              onChange={(e) => setTimestep(Number(e.target.value))}
              className="flex-1"
            />
            <span className="text-sm font-mono text-slate-300 w-16 text-right">
              {results.timesteps[timestep]}s
            </span>
          </div>
        )}
        <div
          id="result-map"
          className="bg-slate-900 rounded-lg border border-slate-700 flex items-center justify-center"
          style={{ minHeight: 400 }}
        >
          <p className="text-slate-600 text-sm">
            Result overlay map container (MapLibre)
          </p>
        </div>
      </section>

      {/* Downloads */}
      <section className="mb-6 flex gap-3">
        <a
          href={exports_.pdfUrl(jobId)}
          target="_blank"
          rel="noopener noreferrer"
          data-testid="download-pdf"
          className="bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 text-sm transition-colors"
        >
          Download PDF
        </a>
        <a
          href={exports_.geotiffUrl(jobId, "pet")}
          target="_blank"
          rel="noopener noreferrer"
          data-testid="download-geotiff"
          className="bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 text-sm transition-colors"
        >
          Download GeoTIFF
        </a>
      </section>

      {/* Comparison results (if comparison job) */}
      {results?.type === "comparison" && results.delta_statistics && (
        <>
          <hr className="border-slate-700 my-8" />
          <h2 className="text-xl font-bold mb-4" data-testid="comparison-heading">Comparison Results</h2>

          {/* Delta statistics */}
          <section className="mb-6">
            <h3 className="text-lg font-bold mb-3">Delta Statistics</h3>
            <div className="bg-slate-800 rounded-lg shadow-md overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
                    <th className="px-4 py-2 text-left">Variable</th>
                    <th className="px-4 py-2 text-right">Mean Delta</th>
                    <th className="px-4 py-2 text-right">Max Improvement</th>
                    <th className="px-4 py-2 text-right">Max Worsening</th>
                    <th className="px-4 py-2 text-right">% Improved</th>
                    <th className="px-4 py-2 text-right">% Worsened</th>
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    const deltas = Array.isArray(results.delta_statistics)
                      ? results.delta_statistics
                      : Object.entries(results.delta_statistics).map(([variable, d]) => ({ variable, ...d }));
                    return deltas.map((d) => (
                      <tr key={d.variable} className="border-b border-slate-700/50">
                        <td className="px-4 py-2">{d.variable}</td>
                        <td
                          className={`px-4 py-2 text-right font-mono ${
                            d.mean_delta < 0
                              ? "text-green-500"
                              : d.mean_delta > 0
                              ? "text-red-500"
                              : "text-slate-300"
                          }`}
                        >
                          {d.mean_delta > 0 ? "+" : ""}
                          {d.mean_delta.toFixed(2)}
                        </td>
                        <td className="px-4 py-2 text-right font-mono text-green-500">
                          {d.max_improvement.toFixed(2)}
                        </td>
                        <td className="px-4 py-2 text-right font-mono text-red-500">
                          {d.max_worsening.toFixed(2)}
                        </td>
                        <td className="px-4 py-2 text-right font-mono text-green-500">
                          {d.pct_improved.toFixed(1)}%
                        </td>
                        <td className="px-4 py-2 text-right font-mono text-red-500">
                          {d.pct_worsened.toFixed(1)}%
                        </td>
                      </tr>
                    ));
                  })()}
                </tbody>
              </table>
            </div>
          </section>

          {/* Threshold impacts */}
          {results.threshold_impacts && (
            <section className="mb-6">
              <h3 className="text-lg font-bold mb-3">Threshold Impacts</h3>
              <div className="bg-slate-800 rounded-lg shadow-md overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
                      <th className="px-4 py-2 text-left">Threshold</th>
                      <th className="px-4 py-2 text-right">Value</th>
                      <th className="px-4 py-2 text-right">Cells Above (Baseline)</th>
                      <th className="px-4 py-2 text-right">Cells Above (Intervention)</th>
                      <th className="px-4 py-2 text-right">% Improved</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.threshold_impacts.map((t, i) => (
                      <tr key={i} className="border-b border-slate-700/50">
                        <td className="px-4 py-2">{t.threshold_name}</td>
                        <td className="px-4 py-2 text-right font-mono">
                          {t.threshold_value}
                        </td>
                        <td className="px-4 py-2 text-right font-mono">
                          {t.cells_above_baseline}
                        </td>
                        <td className="px-4 py-2 text-right font-mono">
                          {t.cells_above_intervention}
                        </td>
                        <td className="px-4 py-2 text-right font-mono text-green-500">
                          {t.pct_improved.toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* Ranked improvements */}
          {results.ranked_improvements && (
            <section className="mb-6">
              <h3 className="text-lg font-bold mb-3">Ranked Improvements</h3>
              <div className="bg-slate-800 rounded-lg shadow-md overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
                      <th className="px-4 py-2 text-left">Region</th>
                      <th className="px-4 py-2 text-right">Mean Delta</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.ranked_improvements.map((r, i) => (
                      <tr key={i} className="border-b border-slate-700/50">
                        <td className="px-4 py-2">{r.region_description}</td>
                        <td className="px-4 py-2 text-right font-mono text-green-500">
                          {r.mean_delta.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
