"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { jobs as jobsApi, exports_ } from "@/lib/api";
import type {
  ComfortStatistics,
  PETClassification,
  DeltaStatistics,
  ThresholdImpact,
  DataQualityTier,
} from "@/lib/types";

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

interface SingleResults {
  comfort_statistics: ComfortStatistics[];
  pet_classification: PETClassification;
  data_quality_tier?: DataQualityTier;
  confidence?: {
    headline: string;
    detail: string;
    caveats: string[];
    suitable_for: string[];
    not_suitable_for: string[];
  };
}

interface ComparisonData {
  delta_statistics: DeltaStatistics[];
  threshold_impacts: ThresholdImpact[];
  ranked_improvements?: { region: string; improvement: number }[];
}

function ResultSummary({
  label,
  results,
}: {
  label: string;
  results: SingleResults | null;
}) {
  if (!results) {
    return (
      <div className="bg-slate-800 rounded-lg shadow-md p-4">
        <h3 className="font-bold mb-2">{label}</h3>
        <p className="text-slate-400 text-sm">Loading...</p>
      </div>
    );
  }

  return (
    <div className="bg-slate-800 rounded-lg shadow-md p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-bold">{label}</h3>
        {results.data_quality_tier && tierBadge(results.data_quality_tier)}
      </div>
      {results.comfort_statistics.map((stat) => (
        <div key={stat.variable} className="mb-2">
          <span className="text-xs uppercase text-slate-500">
            {stat.variable}
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-xl font-bold">{stat.mean.toFixed(1)}</span>
            <span className="text-xs text-slate-400">
              mean (P05: {stat.p05.toFixed(1)}, P95: {stat.p95.toFixed(1)})
            </span>
          </div>
        </div>
      ))}
      {results.pet_classification && (
        <div className="mt-2 pt-2 border-t border-slate-700 text-xs text-slate-400">
          Dominant: {results.pet_classification.dominant_class.replace(/_/g, " ")}{" "}
          &middot; Stress: {results.pet_classification.stress_level}
        </div>
      )}
    </div>
  );
}

export default function ComparePage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = Number(params.id);
  const baselineJobId = Number(searchParams.get("baseline"));
  const interventionJobId = Number(searchParams.get("intervention"));

  const [baselineResults, setBaselineResults] = useState<SingleResults | null>(null);
  const [interventionResults, setInterventionResults] = useState<SingleResults | null>(null);
  const [comparison, setComparison] = useState<ComparisonData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!baselineJobId || !interventionJobId) {
      setError("Missing baseline or intervention job ID in URL parameters");
      return;
    }
    loadAll();
  }, [baselineJobId, interventionJobId]);

  async function loadAll() {
    try {
      const [br, ir] = await Promise.all([
        jobsApi.getResults(baselineJobId) as Promise<unknown>,
        jobsApi.getResults(interventionJobId) as Promise<unknown>,
      ]);
      setBaselineResults(br as SingleResults);
      setInterventionResults(ir as SingleResults);

      // The comparison endpoint is on the intervention job
      const comp = (await jobsApi.getComparison(interventionJobId)) as unknown as ComparisonData;
      setComparison(comp);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load comparison data");
    }
  }

  // Weakest tier of both
  const weakestTier: DataQualityTier = (() => {
    const order: DataQualityTier[] = ["screening", "project", "research"];
    const a = baselineResults?.data_quality_tier || "screening";
    const b = interventionResults?.data_quality_tier || "screening";
    return order.indexOf(a) <= order.indexOf(b) ? a : b;
  })();

  return (
    <div className="flex-1 overflow-y-auto p-6 max-w-6xl mx-auto w-full">
      {/* SCREENING watermark */}
      {weakestTier === "screening" && (
        <div className="fixed inset-0 pointer-events-none flex items-center justify-center z-50">
          <span className="text-red-500/10 text-[8rem] font-black rotate-[-30deg] select-none">
            SCREENING
          </span>
        </div>
      )}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Scenario Comparison</h1>
          <p className="text-sm text-slate-400">
            Baseline Job #{baselineJobId} vs Intervention Job #
            {interventionJobId}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">Weakest tier:</span>
          {tierBadge(weakestTier)}
        </div>
      </div>

      {error && <p className="text-red-500 mb-4">{error}</p>}

      {/* Side by side */}
      <div className="grid md:grid-cols-2 gap-4 mb-8">
        <ResultSummary label="Baseline" results={baselineResults} />
        <ResultSummary label="Intervention" results={interventionResults} />
      </div>

      {/* Confidence panel (weakest) */}
      {(baselineResults?.confidence || interventionResults?.confidence) && (
        <div className="bg-slate-800 rounded-lg shadow-md p-6 mb-6 border-l-4 border-amber-500">
          <h2 className="text-lg font-bold mb-2 text-amber-400">
            Confidence Assessment (weakest of both scenarios)
          </h2>
          {(() => {
            const conf =
              baselineResults?.confidence || interventionResults?.confidence;
            if (!conf) return null;
            return (
              <>
                <p className="font-semibold text-white mb-1">{conf.headline}</p>
                <p className="text-sm text-slate-300 mb-3">{conf.detail}</p>
                {conf.caveats.length > 0 && (
                  <ul className="list-disc list-inside text-sm text-amber-500 mb-3 space-y-0.5">
                    {conf.caveats.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                )}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <h4 className="text-xs uppercase text-green-500 font-semibold mb-1">
                      Suitable For
                    </h4>
                    <ul className="text-sm text-slate-300 space-y-0.5">
                      {conf.suitable_for.map((s, i) => (
                        <li key={i}>+ {s}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h4 className="text-xs uppercase text-red-500 font-semibold mb-1">
                      Not Suitable For
                    </h4>
                    <ul className="text-sm text-slate-300 space-y-0.5">
                      {conf.not_suitable_for.map((s, i) => (
                        <li key={i}>- {s}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </>
            );
          })()}
        </div>
      )}

      {/* Comparison tables */}
      {comparison && (
        <>
          {/* Delta statistics */}
          <section className="mb-6">
            <h2 className="text-lg font-bold mb-3">Delta Statistics</h2>
            <div className="bg-slate-800 rounded-lg shadow-md overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
                    <th className="px-4 py-2 text-left">Variable</th>
                    <th className="px-4 py-2 text-right">Mean Delta</th>
                    <th className="px-4 py-2 text-right">Median Delta</th>
                    <th className="px-4 py-2 text-right">Max Improvement</th>
                    <th className="px-4 py-2 text-right">Max Worsening</th>
                    <th className="px-4 py-2 text-right">% Improved</th>
                    <th className="px-4 py-2 text-right">% Worsened</th>
                    <th className="px-4 py-2 text-right">% Unchanged</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.delta_statistics.map((d) => (
                    <tr key={d.variable} className="border-b border-slate-700/50">
                      <td className="px-4 py-2 font-medium">{d.variable}</td>
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
                      <td
                        className={`px-4 py-2 text-right font-mono ${
                          d.median_delta < 0
                            ? "text-green-500"
                            : d.median_delta > 0
                            ? "text-red-500"
                            : "text-slate-300"
                        }`}
                      >
                        {d.median_delta > 0 ? "+" : ""}
                        {d.median_delta.toFixed(2)}
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
                      <td className="px-4 py-2 text-right font-mono text-slate-400">
                        {d.pct_unchanged.toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Threshold impacts */}
          <section className="mb-6">
            <h2 className="text-lg font-bold mb-3">Threshold Impacts</h2>
            <div className="bg-slate-800 rounded-lg shadow-md overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
                    <th className="px-4 py-2 text-left">Threshold</th>
                    <th className="px-4 py-2 text-right">Value</th>
                    <th className="px-4 py-2 text-right">
                      Cells Above (Baseline)
                    </th>
                    <th className="px-4 py-2 text-right">
                      Cells Above (Intervention)
                    </th>
                    <th className="px-4 py-2 text-right">Cells Improved</th>
                    <th className="px-4 py-2 text-right">Cells Worsened</th>
                    <th className="px-4 py-2 text-right">% Improved</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.threshold_impacts.map((t, i) => (
                    <tr key={i} className="border-b border-slate-700/50">
                      <td className="px-4 py-2 font-medium">
                        {t.threshold_name}
                      </td>
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
                        {t.cells_improved}
                      </td>
                      <td className="px-4 py-2 text-right font-mono text-red-500">
                        {t.cells_worsened}
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

          {/* Ranked improvements */}
          {comparison.ranked_improvements && comparison.ranked_improvements.length > 0 && (
            <section className="mb-6">
              <h2 className="text-lg font-bold mb-3">Ranked Improvement Regions</h2>
              <div className="bg-slate-800 rounded-lg shadow-md overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
                      <th className="px-4 py-2 text-left">#</th>
                      <th className="px-4 py-2 text-left">Region</th>
                      <th className="px-4 py-2 text-right">Improvement</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.ranked_improvements.map((r, i) => (
                      <tr key={i} className="border-b border-slate-700/50">
                        <td className="px-4 py-2 text-slate-500">{i + 1}</td>
                        <td className="px-4 py-2">{r.region}</td>
                        <td className="px-4 py-2 text-right font-mono text-green-500">
                          {r.improvement.toFixed(2)}
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

      {/* Difference map */}
      <section className="mb-6">
        <h2 className="text-lg font-bold mb-3">Difference Map</h2>
        <div
          id="compare-map"
          className="bg-slate-900 rounded-lg border border-slate-700 flex items-center justify-center"
          style={{ minHeight: 400 }}
        >
          <p className="text-slate-600 text-sm">
            Difference map overlay container (MapLibre)
          </p>
        </div>
      </section>

      {/* Download */}
      <section className="mb-6">
        <a
          href={exports_.pdfUrl(interventionJobId)}
          target="_blank"
          rel="noopener noreferrer"
          className="bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 text-sm inline-block transition-colors"
        >
          Download Comparison PDF
        </a>
      </section>
    </div>
  );
}
