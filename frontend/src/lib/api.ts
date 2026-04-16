import type {
  BoundingBox,
  ComfortStatistics,
  DeltaStatistics,
  Job,
  PETClassification,
  Project,
  ProjectMember,
  ProjectRole,
  ResolvedBuildingsResponse,
  Scenario,
  ScenarioRecord,
  SpeciesInfo,
  SurfaceInfo,
  ThresholdImpact,
  ValidationIssue,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('palm4u_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

interface AuthTokenResponse {
  access_token: string;
  token_type: string;
}

interface UserResponse {
  id: number;
  email: string;
}

export const auth = {
  register(email: string, password: string) {
    return apiFetch<AuthTokenResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  async login(email: string, password: string) {
    const headers: Record<string, string> = {
      'Content-Type': 'application/x-www-form-urlencoded',
    };
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('palm4u_token');
      if (token) headers['Authorization'] = `Bearer ${token}`;
    }
    const body = new URLSearchParams({ username: email, password });
    const res = await fetch(`${API_BASE}/auth/login`, { method: 'POST', headers, body });
    if (!res.ok) {
      const text = await res.text();
      throw new ApiError(res.status, text);
    }
    return res.json() as Promise<AuthTokenResponse>;
  },

  me() {
    return apiFetch<UserResponse>('/auth/me');
  },
};

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

export const projects = {
  list() {
    return apiFetch<Project[]>('/projects');
  },

  create(name: string, description: string) {
    return apiFetch<Project>('/projects', {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    });
  },

  get(id: number) {
    return apiFetch<Project>(`/projects/${id}`);
  },

  delete(id: number) {
    return apiFetch<void>(`/projects/${id}`, { method: 'DELETE' });
  },
};

// ---------------------------------------------------------------------------
// Project Members
// ---------------------------------------------------------------------------

export const members = {
  list(projectId: number) {
    return apiFetch<ProjectMember[]>(`/projects/${projectId}/members`);
  },

  add(projectId: number, email: string, role: ProjectRole = 'viewer') {
    return apiFetch<ProjectMember>(`/projects/${projectId}/members`, {
      method: 'POST',
      body: JSON.stringify({ email, role }),
    });
  },

  update(projectId: number, memberId: number, role: ProjectRole) {
    return apiFetch<ProjectMember>(`/projects/${projectId}/members/${memberId}`, {
      method: 'PUT',
      body: JSON.stringify({ role }),
    });
  },

  remove(projectId: number, memberId: number) {
    return apiFetch<void>(`/projects/${projectId}/members/${memberId}`, {
      method: 'DELETE',
    });
  },
};

// ---------------------------------------------------------------------------
// Scenarios
// ---------------------------------------------------------------------------

export const scenarios = {
  list(projectId: number) {
    return apiFetch<ScenarioRecord[]>(`/projects/${projectId}/scenarios`);
  },

  create(projectId: number, scenario: Scenario) {
    return apiFetch<ScenarioRecord>(`/projects/${projectId}/scenarios`, {
      method: 'POST',
      body: JSON.stringify({ scenario_json: scenario }),
    });
  },

  get(projectId: number, id: number) {
    return apiFetch<ScenarioRecord>(`/projects/${projectId}/scenarios/${id}`);
  },

  update(projectId: number, id: number, scenario: Scenario) {
    return apiFetch<ScenarioRecord>(`/projects/${projectId}/scenarios/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ scenario_json: scenario }),
    });
  },

  async validate(projectId: number, id: number) {
    const resp = await apiFetch<{ valid: boolean; issues: ValidationIssue[] }>(
      `/projects/${projectId}/scenarios/${id}/validate`,
      { method: 'POST' },
    );
    return resp.issues;
  },
};

// ---------------------------------------------------------------------------
// Jobs
// ---------------------------------------------------------------------------

interface ComparisonResults {
  delta_statistics: DeltaStatistics[];
  threshold_impacts: ThresholdImpact[];
}

interface SingleResults {
  comfort_statistics: ComfortStatistics[];
  pet_classification: PETClassification;
}

export const jobs = {
  run(scenarioId: number) {
    return apiFetch<Job>('/jobs/run', {
      method: 'POST',
      body: JSON.stringify({ scenario_id: scenarioId }),
    });
  },

  compare(baselineId: number, interventionId: number, name: string, description: string) {
    return apiFetch<Job>('/jobs/compare', {
      method: 'POST',
      body: JSON.stringify({
        baseline_id: baselineId,
        intervention_id: interventionId,
        name,
        description,
      }),
    });
  },

  list() {
    return apiFetch<Job[]>('/jobs');
  },

  get(id: number) {
    return apiFetch<Job>(`/jobs/${id}`);
  },

  getResults(id: number) {
    return apiFetch<SingleResults>(`/jobs/${id}/results`);
  },

  getComparison(id: number) {
    return apiFetch<ComparisonResults>(`/jobs/${id}/comparison`);
  },

  getFieldUrl(id: number, variable: string, timestep: number): string {
    return `${API_BASE}/jobs/${id}/fields/${variable}/${timestep}`;
  },

  retry(id: number) {
    return apiFetch<Job>(`/jobs/${id}/retry`, { method: 'POST' });
  },

  cancel(id: number) {
    return apiFetch<Job>(`/jobs/${id}/cancel`, { method: 'POST' });
  },
};

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

export const exports_ = {
  pdfUrl(jobId: number): string {
    return `${API_BASE}/exports/jobs/${jobId}/pdf`;
  },

  geotiffUrl(jobId: number, variable: string): string {
    return `${API_BASE}/exports/jobs/${jobId}/geotiff/${variable}`;
  },
};

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

export const data = {
  fetchBuildings(bbox: BoundingBox, epsg: number) {
    return apiFetch<unknown>('/data/buildings', {
      method: 'POST',
      body: JSON.stringify({ bbox, epsg }),
    });
  },

  fetchDem(bbox: BoundingBox, epsg: number) {
    return apiFetch<unknown>('/data/dem', {
      method: 'POST',
      body: JSON.stringify({ bbox, epsg }),
    });
  },
};

// ---------------------------------------------------------------------------
// Building geometry edits (ADR-004)
// ---------------------------------------------------------------------------

export const buildingEdits = {
  getResolved(projectId: number, scenarioId: number) {
    return apiFetch<ResolvedBuildingsResponse>(
      `/projects/${projectId}/scenarios/${scenarioId}/buildings`
    );
  },

  appendEdit(
    projectId: number,
    scenarioId: number,
    edit: {
      op: string;
      id?: string;
      geometry?: unknown;
      height_m?: number;
      roof_type?: string;
      wall_material_id?: string;
      target_building_id?: string;
      set?: Record<string, unknown>;
    }
  ) {
    return apiFetch<{
      edit_id: string;
      warnings: { edit_id: string; code: string; message: string }[];
      resolved: ResolvedBuildingsResponse;
    }>(`/projects/${projectId}/scenarios/${scenarioId}/buildings/edits`, {
      method: 'POST',
      body: JSON.stringify(edit),
    });
  },

  deleteEdit(projectId: number, scenarioId: number, editId: string) {
    return apiFetch<{ deleted: string; resolved: ResolvedBuildingsResponse }>(
      `/projects/${projectId}/scenarios/${scenarioId}/buildings/edits/${editId}`,
      { method: 'DELETE' }
    );
  },

  reorder(projectId: number, scenarioId: number, orderedIds: string[]) {
    return apiFetch<{ resolved: ResolvedBuildingsResponse }>(
      `/projects/${projectId}/scenarios/${scenarioId}/buildings/edits:reorder`,
      { method: 'POST', body: JSON.stringify({ ordered_ids: orderedIds }) }
    );
  },
};

// ---------------------------------------------------------------------------
// Catalogues
// ---------------------------------------------------------------------------

export const catalogues = {
  species() {
    return apiFetch<Record<string, SpeciesInfo>>('/catalogues/species');
  },

  surfaces() {
    return apiFetch<Record<string, SurfaceInfo>>('/catalogues/surfaces');
  },

  comfortThresholds() {
    return apiFetch<unknown>('/catalogues/comfort-thresholds');
  },
};

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

interface QueueStats {
  jobs: Record<string, number>;
  stale_workers: number;
  active_workers: number;
}

interface AuditLogEntry {
  id: number;
  user_id: number | null;
  action: string;
  resource_type: string;
  resource_id: number | null;
  detail: string | null;
  ip_address: string | null;
  request_id: string | null;
  created_at: string | null;
}

interface HealthResponse {
  status: string;
  timestamp: string;
  components: Record<string, { status: string; [key: string]: unknown }>;
}

interface AdminUser {
  id: number;
  email: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string | null;
}

interface AdminJob {
  job_id: number;
  user_id: number;
  project_id: number;
  job_type: string;
  status: string;
  worker_id: string | null;
  priority: number;
  retry_count: number;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export const admin = {
  queueStats() {
    return apiFetch<QueueStats>('/admin/queue-stats');
  },

  auditLog(limit = 50, offset = 0, action?: string) {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (action) params.set('action', action);
    return apiFetch<AuditLogEntry[]>(`/admin/audit-log?${params}`);
  },

  health() {
    return apiFetch<HealthResponse>('/health');
  },

  listUsers(limit = 50, offset = 0) {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    return apiFetch<AdminUser[]>(`/admin/users?${params}`);
  },

  patchUser(id: number, patch: { is_admin?: boolean; is_active?: boolean }) {
    return apiFetch<AdminUser>(`/admin/users/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    });
  },

  listJobs(limit = 50, offset = 0, statusFilter?: string) {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (statusFilter) params.set('status_filter', statusFilter);
    return apiFetch<AdminJob[]>(`/admin/jobs?${params}`);
  },

  getPalmRunner() {
    return apiFetch<PalmRunnerConfig>('/admin/palm-runner');
  },

  savePalmRunner(body: {
    mode: string | null;
    remote_url: string | null;
    remote_token: string | null;
  }) {
    return apiFetch<PalmRunnerConfig>('/admin/palm-runner', {
      method: 'PUT',
      body: JSON.stringify(body),
    });
  },

  testPalmRunner(body?: { remote_url?: string; remote_token?: string }) {
    return apiFetch<PalmRunnerTestResult>('/admin/palm-runner/test', {
      method: 'POST',
      body: JSON.stringify(body ?? {}),
    });
  },
};

// Shape of GET /admin/palm-runner (no raw token ever returned).
export interface PalmRunnerConfig {
  mode: string;
  mode_source: 'db' | 'env' | 'default';
  remote_url: string | null;
  remote_url_source: 'db' | 'env' | 'unset';
  token_configured: boolean;
  remote_token_source: 'db' | 'env' | 'unset';
}

export interface PalmRunnerTestResult {
  ok: boolean;
  http_status: number | null;
  url?: string;
  error?: string;
  worker?: Record<string, unknown>;
}

// Lightweight, non-admin routing hint for the scenario editor's Run button.
export interface RunnerInfo {
  mode: string;
  label: string;
  remote_url: string | null;
  token_configured: boolean;
  ready: boolean;
}

export function getRunnerInfo() {
  return apiFetch<RunnerInfo>('/runner-info');
}

// ---------------------------------------------------------------------------
// Forcing files
// ---------------------------------------------------------------------------

export interface ForcingFile {
  id: number;
  filename: string;
  file_size: number;
  validated: boolean;
  validation_errors: string[] | string | null;
  description?: string;
  created_at?: string | null;
}

export const forcing = {
  list(projectId: number) {
    return apiFetch<ForcingFile[]>(`/projects/${projectId}/forcing`);
  },

  async upload(projectId: number, file: File, description = '') {
    const form = new FormData();
    form.append('file', file);
    if (description) form.append('description', description);
    const headers: Record<string, string> = {};
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('palm4u_token');
      if (token) headers['Authorization'] = `Bearer ${token}`;
    }
    const res = await fetch(`${API_BASE}/projects/${projectId}/forcing`, {
      method: 'POST',
      headers,
      body: form,
    });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return res.json() as Promise<ForcingFile>;
  },

  remove(projectId: number, forcingId: number) {
    return apiFetch<void>(`/projects/${projectId}/forcing/${forcingId}`, {
      method: 'DELETE',
    });
  },
};

// ---------------------------------------------------------------------------
// Facade greening ADVISORY (NON-PALM, NON-COUPLED)
//
// IMPORTANT: every response from this namespace carries
//   result_kind: "advisory_non_palm"
//   coupled_with_palm: false
// The UI MUST display these flags prominently and MUST NOT merge or
// co-display these results with PALM-coupled outputs.
// ---------------------------------------------------------------------------

export interface AdvisoryProvenance {
  result_kind: 'advisory_non_palm';
  coupled_with_palm: false;
  method: string;
  uncertainty: string;
  warning: string;
}

export interface FacadeGreeningAdvisory extends AdvisoryProvenance {
  pollutant_uptake: AdvisoryProvenance & {
    inputs: Record<string, unknown>;
    leaf_area_m2: { low: number; central: number; high: number };
    pollutants: Record<
      string,
      { low_kg_per_year: number; central_kg_per_year: number; high_kg_per_year: number }
    >;
  };
  cooling_effect: AdvisoryProvenance & {
    delta_t_celsius: { low: number; high: number };
    scope: string;
  };
  energy_savings: AdvisoryProvenance & {
    summer_cooling_load_reduction_fraction: { low: number; high: number };
  };
  disclaimer: string;
}

export const facadeGreeningAdvisory = {
  estimate(input: {
    facade_area_m2: number;
    species: string;
    coverage_fraction?: number;
    climate_zone?: string;
  }) {
    return apiFetch<FacadeGreeningAdvisory>('/advisory/facade-greening', {
      method: 'POST',
      body: JSON.stringify({ coverage_fraction: 1.0, climate_zone: 'temperate', ...input }),
    });
  },

  species() {
    return apiFetch<{
      result_kind: 'advisory_non_palm';
      coupled_with_palm: false;
      species: { id: string; lai_low: number; lai_central: number; lai_high: number }[];
    }>('/advisory/facade-greening/species');
  },
};
