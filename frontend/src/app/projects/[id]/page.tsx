"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  auth,
  projects as projectsApi,
  scenarios as scenariosApi,
  catalogues,
  jobs as jobsApi,
  members as membersApi,
  forcing as forcingApi,
  facadeGreeningAdvisory,
} from "@/lib/api";
import type { ForcingFile, FacadeGreeningAdvisory } from "@/lib/api";
import type {
  Project,
  ProjectMember,
  ProjectRole,
  ScenarioRecord,
  Scenario,
  ScenarioType,
  ForcingArchetype,
  TreePlacement,
  SurfaceChange,
  GreenRoof,
  ValidationIssue,
  SpeciesInfo,
  SurfaceInfo,
  DataQualityTier,
  BoundingBox,
} from "@/lib/types";
import MapContainer from "@/components/map/MapContainer";
import DrawTools from "@/components/map/DrawTools";

const FORCING_OPTIONS: { value: ForcingArchetype; label: string }[] = [
  { value: "typical_hot_day", label: "Typical Hot Day (synthetic)" },
  { value: "heat_wave_day", label: "Heat Wave Day (synthetic)" },
  { value: "moderate_summer_day", label: "Moderate Summer Day (synthetic)" },
  { value: "warm_night", label: "Warm Night (synthetic)" },
];

const GREEN_ROOF_VEGETATION_TYPES = [
  "sedum",
  "grass_herbs",
  "intensive_mixed",
];

function tierBadge(tier: DataQualityTier) {
  const colors: Record<DataQualityTier, string> = {
    screening: "bg-red-600",
    project: "bg-amber-600",
    research: "bg-green-600",
  };
  return (
    <span
      className={`${colors[tier]} text-white text-xs font-bold px-2 py-0.5 rounded uppercase`}
    >
      {tier}
    </span>
  );
}

function emptyScenario(type: ScenarioType): Scenario {
  return {
    name: "",
    description: "",
    scenario_type: type,
    domain: {
      bbox: { west: 0, south: 0, east: 0, north: 0 },
      resolution_m: 10,
      epsg: 25832,
      nz: 40,
      dz: 2,
    },
    simulation: {
      forcing: "typical_hot_day",
      simulation_hours: 8,
      output_interval_s: 3600,
    },
    trees: [],
    surface_changes: [],
    green_roofs: [],
  };
}

export default function ProjectWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const projectId = Number(params.id);

  const [project, setProject] = useState<Project | null>(null);
  const [scenarioList, setScenarioList] = useState<ScenarioRecord[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [scenario, setScenario] = useState<Scenario>(emptyScenario("baseline"));
  const [isNew, setIsNew] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>([]);
  const [speciesCatalogue, setSpeciesCatalogue] = useState<Record<string, SpeciesInfo>>({});
  const [surfaceCatalogue, setSurfaceCatalogue] = useState<Record<string, SurfaceInfo>>({});

  const [activeTool, setActiveTool] = useState<"none" | "bbox" | "tree" | "surface">("none");
  const [treeSpecies, setTreeSpecies] = useState("tilia_cordata");
  const [surfaceMaterial, setSurfaceMaterial] = useState("grass");
  const [submitting, setSubmitting] = useState(false);

  // Green roof form
  const [grBuildingId, setGrBuildingId] = useState("");
  const [grVegType, setGrVegType] = useState("sedum");
  const [grDepth, setGrDepth] = useState(0.1);

  // Members
  const [membersList, setMembersList] = useState<ProjectMember[]>([]);
  const [newMemberEmail, setNewMemberEmail] = useState("");
  const [newMemberRole, setNewMemberRole] = useState<'viewer' | 'editor'>("viewer");
  const [currentUserEmail, setCurrentUserEmail] = useState("");
  const isOwner = membersList.some(
    (m) => m.role === "owner" && m.email === currentUserEmail
  );

  // Forcing files
  const [forcingFiles, setForcingFiles] = useState<ForcingFile[]>([]);
  const [forcingUploading, setForcingUploading] = useState(false);
  const forcingFileRef = useRef<HTMLInputElement>(null);

  // Facade greening advisory
  const [advisoryArea, setAdvisoryArea] = useState(50);
  const [advisorySpecies, setAdvisorySpecies] = useState("hedera_helix");
  const [advisoryCoverage, setAdvisoryCoverage] = useState(1.0);
  const [advisoryResult, setAdvisoryResult] = useState<FacadeGreeningAdvisory | null>(null);
  const [advisoryLoading, setAdvisoryLoading] = useState(false);

  const validateTimeout = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Load project + scenarios + catalogues
  useEffect(() => {
    const token = localStorage.getItem("palm4u_token");
    if (!token) {
      router.push("/login");
      return;
    }
    Promise.all([
      projectsApi.get(projectId),
      scenariosApi.list(projectId),
      catalogues.species(),
      catalogues.surfaces(),
      membersApi.list(projectId),
    ]).then(([proj, scens, species, surfaces, mems]) => {
      setProject(proj);
      setScenarioList(scens);
      setSpeciesCatalogue(species);
      setSurfaceCatalogue(surfaces);
      setMembersList(mems);
      forcingApi.list(projectId).then(setForcingFiles).catch(() => {});
      if (scens.length > 0) {
        setSelectedId(scens[0].id);
        setScenario(scens[0].scenario_json);
      }
    }).catch((err) => setError(err.message));

    auth.me().then((u) => setCurrentUserEmail(u.email)).catch(() => {});
  }, [projectId, router]);

  // Debounced validation
  const triggerValidation = useCallback(
    (s: Scenario) => {
      if (validateTimeout.current) clearTimeout(validateTimeout.current);
      validateTimeout.current = setTimeout(async () => {
        if (!selectedId && !isNew) return;
        try {
          if (selectedId) {
            const issues = await scenariosApi.validate(projectId, selectedId);
            setValidationIssues(issues);
          }
        } catch {
          // Validation endpoint may not exist yet
        }
      }, 800);
    },
    [projectId, selectedId, isNew]
  );

  function updateScenario(patch: Partial<Scenario>) {
    const updated = { ...scenario, ...patch };
    setScenario(updated);
    triggerValidation(updated);
  }

  function selectScenario(rec: ScenarioRecord) {
    setSelectedId(rec.id);
    setScenario(rec.scenario_json);
    setIsNew(false);
    setValidationIssues([]);
  }

  function startNew(type: ScenarioType) {
    setSelectedId(null);
    setIsNew(true);
    setScenario(emptyScenario(type));
    setValidationIssues([]);
  }

  async function saveScenario() {
    setSaving(true);
    setError("");
    try {
      if (isNew) {
        const created = await scenariosApi.create(projectId, scenario);
        setScenarioList((prev) => [...prev, created]);
        setSelectedId(created.id);
        setIsNew(false);
      } else if (selectedId) {
        const updated = await scenariosApi.update(projectId, selectedId, scenario);
        setScenarioList((prev) =>
          prev.map((s) => (s.id === selectedId ? updated : s))
        );
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleRunSimulation() {
    if (!selectedId) return;
    setSubmitting(true);
    setError("");
    try {
      const job = await jobsApi.run(selectedId);
      router.push(`/projects/${projectId}/results/${job.job_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Submission failed");
      setSubmitting(false);
    }
  }

  async function handleCompare() {
    if (!selectedId) return;
    const baseline = scenarioList.find((s) => s.scenario_json.scenario_type === "baseline");
    if (!baseline) {
      setError("No baseline scenario found for comparison");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const job = await jobsApi.compare(
        baseline.id,
        selectedId,
        `Compare: ${baseline.name} vs ${scenario.name}`,
        ""
      );
      router.push(`/projects/${projectId}/results/${job.job_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Comparison failed");
      setSubmitting(false);
    }
  }

  // Map interaction callbacks
  const handleBboxComplete = useCallback((bbox: BoundingBox) => {
    setScenario((prev) => ({
      ...prev,
      domain: { ...prev.domain, bbox },
    }));
    setActiveTool("none");
  }, []);

  const handleTreePlace = useCallback((lng: number, lat: number) => {
    setScenario((prev) => ({
      ...prev,
      trees: [
        ...prev.trees,
        { species_id: treeSpecies, x: lng, y: lat },
      ],
    }));
  }, [treeSpecies]);

  const handleSurfaceComplete = useCallback((vertices: [number, number][]) => {
    setScenario((prev) => ({
      ...prev,
      surface_changes: [
        ...prev.surface_changes,
        { surface_type_id: surfaceMaterial, vertices },
      ],
    }));
  }, [surfaceMaterial]);

  const handlePointClick = useCallback((lng: number, lat: number) => {
    // Handled by DrawTools
  }, []);

  function removeTree(idx: number) {
    const trees = [...scenario.trees];
    trees.splice(idx, 1);
    updateScenario({ trees });
  }

  function removeSurface(idx: number) {
    const surfaces = [...scenario.surface_changes];
    surfaces.splice(idx, 1);
    updateScenario({ surface_changes: surfaces });
  }

  function addGreenRoof() {
    if (!grBuildingId.trim()) return;
    const gr: GreenRoof = {
      building_id: grBuildingId.trim(),
      vegetation_type: grVegType,
      substrate_depth_m: grDepth,
    };
    updateScenario({ green_roofs: [...scenario.green_roofs, gr] });
    setGrBuildingId("");
  }

  function removeGreenRoof(idx: number) {
    const roofs = [...scenario.green_roofs];
    roofs.splice(idx, 1);
    updateScenario({ green_roofs: roofs });
  }

  async function handleAddMember() {
    if (!newMemberEmail.trim()) return;
    try {
      const member = await membersApi.add(projectId, newMemberEmail.trim(), newMemberRole);
      setMembersList((prev) => [...prev, member]);
      setNewMemberEmail("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to add member");
    }
  }

  async function handleRemoveMember(memberId: number) {
    try {
      await membersApi.remove(projectId, memberId);
      setMembersList((prev) => prev.filter((m) => m.id !== memberId));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to remove member");
    }
  }

  // --- Forcing file handlers ---

  async function loadForcingFiles() {
    try {
      setForcingFiles(await forcingApi.list(projectId));
    } catch {
      // may not exist for this project yet
    }
  }

  async function handleForcingUpload() {
    const file = forcingFileRef.current?.files?.[0];
    if (!file) return;
    setForcingUploading(true);
    try {
      await forcingApi.upload(projectId, file);
      await loadForcingFiles();
      if (forcingFileRef.current) forcingFileRef.current.value = "";
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setForcingUploading(false);
    }
  }

  async function handleForcingDelete(id: number) {
    try {
      await forcingApi.remove(projectId, id);
      setForcingFiles((prev) => prev.filter((f) => f.id !== id));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  // --- Facade greening advisory handler ---

  async function runAdvisory() {
    setAdvisoryLoading(true);
    setAdvisoryResult(null);
    try {
      const result = await facadeGreeningAdvisory.estimate({
        facade_area_m2: advisoryArea,
        species: advisorySpecies,
        coverage_fraction: advisoryCoverage,
      });
      setAdvisoryResult(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Advisory estimate failed");
    } finally {
      setAdvisoryLoading(false);
    }
  }

  // Compute effective data quality tier
  const effectiveTier: DataQualityTier = (() => {
    const sources = scenario.data_sources;
    if (!sources) return "screening";
    const tiers: DataQualityTier[] = [
      sources.buildings?.quality_tier,
      sources.terrain?.quality_tier,
      sources.vegetation?.quality_tier,
    ].filter(Boolean) as DataQualityTier[];
    if (tiers.length === 0) return "screening";
    const order: DataQualityTier[] = ["screening", "project", "research"];
    return tiers.reduce((worst, t) =>
      order.indexOf(t) < order.indexOf(worst) ? t : worst
    );
  })();

  const hasBaseline = scenarioList.some(
    (s) => s.scenario_json.scenario_type === "baseline"
  );
  const isIntervention =
    scenario.scenario_type === "single_intervention" ||
    scenario.scenario_type === "concept_comparison";

  const bboxDefined = scenario.domain.bbox.west !== 0 || scenario.domain.bbox.east !== 0;

  if (!project) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-slate-400">{error || "Loading project..."}</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* LEFT SIDEBAR */}
      <div className="w-72 bg-slate-800 border-r border-slate-700 flex flex-col overflow-y-auto">
        <div className="p-4 border-b border-slate-700">
          <h2 className="font-bold text-lg truncate">{project.name}</h2>
          <p className="text-xs text-slate-400 truncate">{project.description}</p>
        </div>

        {/* Scenario list */}
        <div className="p-4 border-b border-slate-700">
          <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">
            Scenarios
          </h3>
          <div className="space-y-1">
            {scenarioList.map((rec) => (
              <button
                key={rec.id}
                onClick={() => selectScenario(rec)}
                className={`w-full text-left px-3 py-2 rounded text-sm transition-colors ${
                  selectedId === rec.id
                    ? "bg-blue-600 text-white"
                    : "text-slate-300 hover:bg-slate-700"
                }`}
              >
                <div className="font-medium truncate">{rec.name || "Untitled"}</div>
                <div className="text-xs opacity-70">{rec.scenario_type}</div>
              </button>
            ))}
          </div>
          <div className="flex gap-2 mt-3">
            <button
              onClick={() => startNew("baseline")}
              className="flex-1 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded px-2 py-1.5 transition-colors"
              data-testid="new-baseline"
            >
              New Baseline
            </button>
            <button
              onClick={() => startNew("single_intervention")}
              className="flex-1 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded px-2 py-1.5 transition-colors"
              data-testid="new-intervention"
            >
              New Intervention
            </button>
          </div>
        </div>

        {/* Tools panel */}
        <div className="p-4 border-b border-slate-700">
          <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">
            Tools
          </h3>
          <div className="space-y-1">
            {[
              { id: "bbox" as const, label: "Define Study Area" },
              { id: "tree" as const, label: "Place Trees" },
              { id: "surface" as const, label: "Edit Surfaces" },
            ].map((tool) => (
              <button
                key={tool.id}
                data-testid={`tool-${tool.id}`}
                onClick={() =>
                  setActiveTool(activeTool === tool.id ? "none" : tool.id)
                }
                className={`w-full text-left px-3 py-2 rounded text-sm transition-colors ${
                  activeTool === tool.id
                    ? "bg-blue-600 text-white"
                    : "text-slate-300 hover:bg-slate-700"
                }`}
              >
                {tool.label}
              </button>
            ))}
          </div>

          {/* Species selector for tree tool */}
          {activeTool === "tree" && (
            <div className="mt-3">
              <label className="block text-xs text-slate-400 mb-1">Tree Species</label>
              <select
                value={treeSpecies}
                onChange={(e) => setTreeSpecies(e.target.value)}
                data-testid="tree-species-select"
                className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white"
              >
                {Object.entries(speciesCatalogue).map(([id, info]) => (
                  <option key={id} value={id}>{info.common_name}</option>
                ))}
              </select>
            </div>
          )}

          {/* Material selector for surface tool */}
          {activeTool === "surface" && (
            <div className="mt-3">
              <label className="block text-xs text-slate-400 mb-1">Surface Material</label>
              <select
                value={surfaceMaterial}
                onChange={(e) => setSurfaceMaterial(e.target.value)}
                data-testid="surface-material-select"
                className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white"
              >
                {Object.entries(surfaceCatalogue).map(([id, info]) => (
                  <option key={id} value={id}>{info.name}</option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Green Roofs section with toggle/add form */}
        <div className="p-4">
          <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">
            Green Roofs
          </h3>
          <div className="bg-red-900/20 border border-red-700 rounded p-2 mb-2">
            <p className="text-red-500 font-bold text-xs" data-testid="green-roof-warning">
              NOT YET SIMULATED — ignored in PALM input
            </p>
          </div>
          {scenario.green_roofs.map((gr, idx) => (
            <div
              key={idx}
              className="bg-slate-700 rounded p-2 text-xs mb-1 flex items-center justify-between"
            >
              <div>
                <span className="font-medium">{gr.building_id}</span>
                <span className="text-slate-400 ml-1">
                  {gr.vegetation_type} &middot; {gr.substrate_depth_m}m
                </span>
              </div>
              <button
                onClick={() => removeGreenRoof(idx)}
                className="text-red-400 hover:text-red-300 ml-2"
              >
                &times;
              </button>
            </div>
          ))}
          <div className="mt-2 space-y-1">
            <input
              type="text"
              value={grBuildingId}
              onChange={(e) => setGrBuildingId(e.target.value)}
              placeholder="Building ID"
              data-testid="green-roof-building-id"
              className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white"
            />
            <div className="flex gap-1">
              <select
                value={grVegType}
                onChange={(e) => setGrVegType(e.target.value)}
                data-testid="green-roof-veg-type"
                className="flex-1 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white"
              >
                {GREEN_ROOF_VEGETATION_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <input
                type="number"
                value={grDepth}
                onChange={(e) => setGrDepth(Number(e.target.value))}
                step={0.05}
                min={0.05}
                max={1.0}
                data-testid="green-roof-depth"
                className="w-16 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white"
              />
            </div>
            <button
              onClick={addGreenRoof}
              data-testid="add-green-roof"
              className="w-full text-xs bg-slate-600 hover:bg-slate-500 text-white rounded px-2 py-1 transition-colors"
            >
              Add Green Roof
            </button>
          </div>
        </div>

        {/* Forcing Files */}
        <div className="p-4 border-t border-slate-700">
          <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">
            Forcing Files
          </h3>
          {forcingFiles.length === 0 ? (
            <p className="text-xs text-slate-500">No custom forcing files uploaded.</p>
          ) : (
            <div className="space-y-1 mb-2" data-testid="forcing-file-list">
              {forcingFiles.map((f) => (
                <div
                  key={f.id}
                  className="flex items-center justify-between bg-slate-700 rounded px-2 py-1 text-xs"
                >
                  <div className="truncate flex-1">
                    <span className="font-medium">{f.filename}</span>
                    <span className="text-slate-400 ml-1">
                      ({(f.file_size / 1024).toFixed(0)} KB)
                    </span>
                    {f.validated && (
                      <span className="ml-1 text-green-400 text-[10px]">validated</span>
                    )}
                  </div>
                  <button
                    onClick={() => handleForcingDelete(f.id)}
                    className="text-red-400 hover:text-red-300 ml-2"
                  >
                    &times;
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="mt-2 flex gap-1">
            <input
              ref={forcingFileRef}
              type="file"
              accept=".nc,.NC,.nc4"
              data-testid="forcing-file-input"
              className="flex-1 text-xs text-slate-400 file:mr-2 file:py-1 file:px-2 file:rounded file:border-0 file:text-xs file:bg-slate-600 file:text-white cursor-pointer"
            />
            <button
              onClick={handleForcingUpload}
              disabled={forcingUploading}
              data-testid="forcing-upload-btn"
              className="bg-slate-600 hover:bg-slate-500 text-white rounded px-3 py-1 text-xs transition-colors disabled:opacity-50"
            >
              {forcingUploading ? "..." : "Upload"}
            </button>
          </div>
        </div>

        {/* Facade Greening Advisory */}
        <div className="p-4 border-t border-slate-700">
          <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">
            Facade Greening Advisory
          </h3>
          <div className="bg-amber-900/30 border border-amber-700 rounded p-2 mb-2">
            <p className="text-amber-400 font-bold text-[10px]" data-testid="advisory-banner">
              ADVISORY ESTIMATE — not based on PALM simulation
            </p>
          </div>
          <div className="space-y-1">
            <div>
              <label className="block text-[10px] text-slate-400">Facade area (m&sup2;)</label>
              <input
                type="number"
                value={advisoryArea}
                onChange={(e) => setAdvisoryArea(Number(e.target.value))}
                min={1}
                max={5000}
                data-testid="advisory-area"
                className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white"
              />
            </div>
            <div>
              <label className="block text-[10px] text-slate-400">Species</label>
              <select
                value={advisorySpecies}
                onChange={(e) => setAdvisorySpecies(e.target.value)}
                data-testid="advisory-species"
                className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white"
              >
                <option value="hedera_helix">Hedera helix</option>
                <option value="parthenocissus_tricuspidata">Parthenocissus tricuspidata</option>
                <option value="wisteria_sinensis">Wisteria sinensis</option>
                <option value="fallopia_baldschuanica">Fallopia baldschuanica</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] text-slate-400">Coverage fraction</label>
              <input
                type="number"
                value={advisoryCoverage}
                onChange={(e) => setAdvisoryCoverage(Number(e.target.value))}
                step={0.1}
                min={0.1}
                max={1.0}
                data-testid="advisory-coverage"
                className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white"
              />
            </div>
            <button
              onClick={runAdvisory}
              disabled={advisoryLoading}
              data-testid="advisory-run-btn"
              className="w-full text-xs bg-amber-700 hover:bg-amber-600 text-white rounded px-2 py-1 transition-colors disabled:opacity-50"
            >
              {advisoryLoading ? "Estimating..." : "Run Advisory Estimate"}
            </button>
          </div>
          {advisoryResult && (
            <div className="mt-2 bg-amber-900/20 border border-amber-800 rounded p-2 text-xs space-y-1" data-testid="advisory-results">
              <p className="text-amber-400 font-bold text-[10px]">
                {advisoryResult.result_kind} | coupled_with_palm: {String(advisoryResult.coupled_with_palm)}
              </p>
              <div>
                <span className="text-slate-400">Cooling:</span>{" "}
                {advisoryResult.cooling_effect.delta_t_celsius.low.toFixed(1)} to{" "}
                {advisoryResult.cooling_effect.delta_t_celsius.high.toFixed(1)} &deg;C
              </div>
              <div>
                <span className="text-slate-400">Energy saving:</span>{" "}
                {(advisoryResult.energy_savings.summer_cooling_load_reduction_fraction.low * 100).toFixed(0)}%
                &ndash;{" "}
                {(advisoryResult.energy_savings.summer_cooling_load_reduction_fraction.high * 100).toFixed(0)}%
              </div>
              {advisoryResult.pollutant_uptake.pollutants && (
                <div>
                  <span className="text-slate-400">Pollutant uptake:</span>
                  {Object.entries(advisoryResult.pollutant_uptake.pollutants).map(
                    ([pol, vals]) => (
                      <span key={pol} className="ml-1">
                        {pol}: {vals.central_kg_per_year.toFixed(3)} kg/yr
                      </span>
                    )
                  )}
                </div>
              )}
              <p className="text-[9px] text-slate-500 mt-1">{advisoryResult.disclaimer}</p>
            </div>
          )}
        </div>

        {/* Team Members */}
        <div className="p-4 border-t border-slate-700">
          <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">
            Team Members
          </h3>
          <div className="space-y-1 mb-2" data-testid="members-list">
            {membersList.map((m) => (
              <div
                key={m.id}
                className="flex items-center justify-between bg-slate-700 rounded px-2 py-1 text-xs"
                data-testid={`member-${m.user_id}`}
              >
                <span className="truncate flex-1" title={m.email}>
                  {m.email}
                </span>
                <span
                  className={`ml-1 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                    m.role === "owner"
                      ? "bg-amber-600 text-white"
                      : m.role === "editor"
                      ? "bg-blue-600 text-white"
                      : "bg-slate-500 text-white"
                  }`}
                >
                  {m.role}
                </span>
                {m.role !== "owner" && isOwner && (
                  <button
                    onClick={() => handleRemoveMember(m.id)}
                    className="text-red-400 hover:text-red-300 ml-1"
                    title="Remove member"
                  >
                    &times;
                  </button>
                )}
              </div>
            ))}
          </div>
          {isOwner && (
            <div className="space-y-1" data-testid="add-member-form">
              <input
                type="email"
                placeholder="user@example.com"
                value={newMemberEmail}
                onChange={(e) => setNewMemberEmail(e.target.value)}
                data-testid="member-email-input"
                className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white placeholder-slate-500"
              />
              <div className="flex gap-1">
                <select
                  value={newMemberRole}
                  onChange={(e) => setNewMemberRole(e.target.value as 'viewer' | 'editor')}
                  data-testid="member-role-select"
                  className="flex-1 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white"
                >
                  <option value="viewer">Viewer</option>
                  <option value="editor">Editor</option>
                </select>
                <button
                  onClick={handleAddMember}
                  data-testid="add-member-btn"
                  className="bg-blue-600 hover:bg-blue-700 text-white rounded px-3 py-1 text-xs transition-colors"
                >
                  Add
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* CENTER: MAP */}
      <div className="flex-1 flex flex-col">
        {error && (
          <div className="bg-red-900/30 border-b border-red-700 px-4 py-2">
            <p className="text-red-500 text-sm">{error}</p>
          </div>
        )}
        <div className="flex-1 relative" style={{ minHeight: 400 }} data-testid="map-container">
          <MapContainer
            bbox={bboxDefined ? scenario.domain.bbox : undefined}
            onPointClick={handlePointClick}
          >
            <DrawTools
              mode={activeTool}
              onBboxComplete={handleBboxComplete}
              onTreePlace={handleTreePlace}
              onSurfaceComplete={handleSurfaceComplete}
            />
          </MapContainer>
          {/* Bbox info overlay */}
          {bboxDefined && (
            <div className="absolute top-2 left-2 z-10 bg-slate-800/90 rounded px-3 py-1.5 text-xs text-slate-300" data-testid="bbox-info">
              Study Area: {scenario.domain.bbox.west.toFixed(4)}, {scenario.domain.bbox.south.toFixed(4)} &mdash; {scenario.domain.bbox.east.toFixed(4)}, {scenario.domain.bbox.north.toFixed(4)}
            </div>
          )}
        </div>
      </div>

      {/* RIGHT SIDEBAR */}
      <div className="w-96 bg-slate-800 border-l border-slate-700 overflow-y-auto">
        <div className="p-4 space-y-6">
          {/* Scenario details */}
          <section>
            <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">
              Scenario Details
            </h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Name</label>
                <input
                  type="text"
                  value={scenario.name}
                  onChange={(e) => updateScenario({ name: e.target.value })}
                  data-testid="scenario-name"
                  className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">
                  Description
                </label>
                <textarea
                  value={scenario.description || ""}
                  onChange={(e) => updateScenario({ description: e.target.value })}
                  rows={2}
                  className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </section>

          {/* Domain (manual input for bbox when not using map) */}
          <section>
            <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">
              Domain
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {(["west", "south", "east", "north"] as const).map((dir) => (
                <div key={dir}>
                  <label className="block text-xs text-slate-400 mb-1 capitalize">{dir}</label>
                  <input
                    type="number"
                    value={scenario.domain.bbox[dir]}
                    onChange={(e) =>
                      updateScenario({
                        domain: {
                          ...scenario.domain,
                          bbox: { ...scenario.domain.bbox, [dir]: Number(e.target.value) },
                        },
                      })
                    }
                    data-testid={`domain-${dir}`}
                    className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-2 mt-2">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Resolution (m)</label>
                <input
                  type="number"
                  value={scenario.domain.resolution_m}
                  onChange={(e) =>
                    updateScenario({
                      domain: { ...scenario.domain, resolution_m: Number(e.target.value) },
                    })
                  }
                  data-testid="domain-resolution"
                  className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">EPSG</label>
                <input
                  type="number"
                  value={scenario.domain.epsg}
                  onChange={(e) =>
                    updateScenario({
                      domain: { ...scenario.domain, epsg: Number(e.target.value) },
                    })
                  }
                  className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white"
                />
              </div>
            </div>
          </section>

          {/* Simulation settings */}
          <section>
            <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">
              Simulation Settings
            </h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">
                  Forcing Archetype (synthetic profile)
                </label>
                <select
                  value={scenario.simulation.forcing}
                  onChange={(e) =>
                    updateScenario({
                      simulation: {
                        ...scenario.simulation,
                        forcing: e.target.value as ForcingArchetype,
                      },
                    })
                  }
                  data-testid="forcing-select"
                  className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {FORCING_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-amber-500 mt-1">
                  Uses synthetic forcing profiles, not DWD TRY data
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">
                    Duration (hours)
                  </label>
                  <input
                    type="number"
                    value={scenario.simulation.simulation_hours}
                    onChange={(e) =>
                      updateScenario({
                        simulation: {
                          ...scenario.simulation,
                          simulation_hours: Number(e.target.value),
                        },
                      })
                    }
                    min={1}
                    max={24}
                    data-testid="sim-hours"
                    className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">
                    Output Interval (s)
                  </label>
                  <input
                    type="number"
                    value={scenario.simulation.output_interval_s}
                    onChange={(e) =>
                      updateScenario({
                        simulation: {
                          ...scenario.simulation,
                          output_interval_s: Number(e.target.value),
                        },
                      })
                    }
                    step={300}
                    min={300}
                    data-testid="sim-interval"
                    className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
            </div>
          </section>

          {/* Data Quality */}
          <section>
            <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">
              Data Quality
            </h3>
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-300">Effective Tier:</span>
              {tierBadge(effectiveTier)}
            </div>
            {effectiveTier === "screening" && (
              <p className="text-xs text-amber-500 mt-1">
                Screening-level data: results are indicative only. Not suitable
                for regulatory or design decisions.
              </p>
            )}
          </section>

          {/* Trees */}
          <section>
            <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">
              Trees ({scenario.trees.length})
            </h3>
            {scenario.trees.length === 0 ? (
              <p className="text-xs text-slate-500">
                No trees placed. Use the &quot;Place Trees&quot; tool on the map.
              </p>
            ) : (
              <div className="space-y-1 max-h-40 overflow-y-auto" data-testid="tree-list">
                {scenario.trees.map((tree, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between bg-slate-700 rounded px-2 py-1 text-xs"
                  >
                    <span>
                      {speciesCatalogue[tree.species_id]?.common_name ||
                        tree.species_id}{" "}
                      ({tree.x.toFixed(4)}, {tree.y.toFixed(4)})
                    </span>
                    <button
                      onClick={() => removeTree(idx)}
                      className="text-red-400 hover:text-red-300 ml-2"
                    >
                      &times;
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Surfaces */}
          <section>
            <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">
              Surfaces ({scenario.surface_changes.length})
            </h3>
            {scenario.surface_changes.length === 0 ? (
              <p className="text-xs text-slate-500">
                No surface changes. Use the &quot;Edit Surfaces&quot; tool.
              </p>
            ) : (
              <div className="space-y-1 max-h-40 overflow-y-auto" data-testid="surface-list">
                {scenario.surface_changes.map((sc, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between bg-slate-700 rounded px-2 py-1 text-xs"
                  >
                    <span>
                      {surfaceCatalogue[sc.surface_type_id]?.name ||
                        sc.surface_type_id}{" "}
                      &middot; {sc.vertices.length} vertices
                    </span>
                    <button
                      onClick={() => removeSurface(idx)}
                      className="text-red-400 hover:text-red-300 ml-2"
                    >
                      &times;
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Green Roofs (right sidebar) */}
          {scenario.green_roofs.length > 0 && (
            <section>
              <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">
                Green Roofs ({scenario.green_roofs.length})
              </h3>
              {scenario.green_roofs.map((gr, idx) => (
                <div key={idx} className="bg-slate-700 rounded p-2 text-xs mb-1">
                  <span>{gr.building_id}</span>
                  <span className="ml-2 text-red-500 font-bold">
                    (NOT YET SIMULATED — ignored in PALM input)
                  </span>
                </div>
              ))}
            </section>
          )}

          {/* Validation */}
          <section>
            <h3 className="text-xs uppercase text-slate-500 font-semibold mb-2">
              Validation
            </h3>
            {validationIssues.length === 0 ? (
              <p className="text-xs text-green-500" data-testid="validation-ok">No issues detected</p>
            ) : (
              <div className="space-y-1 max-h-32 overflow-y-auto" data-testid="validation-issues">
                {validationIssues.map((issue, idx) => (
                  <div
                    key={idx}
                    className={`text-xs px-2 py-1 rounded ${
                      issue.severity === "error"
                        ? "bg-red-900/30 text-red-500"
                        : issue.severity === "warning"
                        ? "bg-amber-900/30 text-amber-500"
                        : "bg-blue-900/30 text-blue-400"
                    }`}
                  >
                    [{issue.code}] {issue.message}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Actions */}
          <section className="space-y-2">
            <button
              onClick={saveScenario}
              disabled={saving}
              data-testid="save-scenario"
              className="w-full bg-slate-600 hover:bg-slate-500 text-white rounded px-4 py-2 text-sm disabled:opacity-50 transition-colors"
            >
              {saving ? "Saving..." : isNew ? "Create Scenario" : "Save Changes"}
            </button>
            <button
              onClick={handleRunSimulation}
              disabled={submitting || !selectedId}
              data-testid="run-simulation"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 text-sm font-medium disabled:opacity-50 transition-colors"
            >
              {submitting ? "Submitting..." : "Run Simulation"}
            </button>
            {isIntervention && hasBaseline && (
              <button
                onClick={handleCompare}
                disabled={submitting || !selectedId}
                data-testid="compare-baseline"
                className="w-full bg-green-700 hover:bg-green-600 text-white rounded px-4 py-2 text-sm disabled:opacity-50 transition-colors"
              >
                Compare with Baseline
              </button>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
