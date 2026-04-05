import type {
  BoundingBox,
  ComfortStatistics,
  DeltaStatistics,
  Job,
  PETClassification,
  Project,
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
