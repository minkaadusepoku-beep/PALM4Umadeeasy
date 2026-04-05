// Match backend/src/models/scenario.py exactly

export type DataQualityTier = 'screening' | 'project' | 'research';
export type ForcingArchetype = 'typical_hot_day' | 'heat_wave_day' | 'moderate_summer_day' | 'warm_night';
export type ScenarioType = 'baseline' | 'single_intervention' | 'concept_comparison';
export type JobStatus = 'pending' | 'running' | 'completed' | 'failed';
export type JobType = 'single' | 'comparison';

export interface BoundingBox { west: number; south: number; east: number; north: number; }

export interface DomainConfig {
  bbox: BoundingBox;
  resolution_m: number;
  epsg: number;
  nz: number;
  dz: number;
}

export interface DataSource {
  source_type: string;
  quality_tier: DataQualityTier;
  description: string;
}

export interface DomainData {
  buildings: DataSource;
  terrain: DataSource;
  vegetation: DataSource;
}

export interface TreePlacement {
  species_id: string;
  x: number;
  y: number;
  height_m?: number;
  crown_diameter_m?: number;
}

export interface SurfaceChange {
  surface_type_id: string;
  vertices: [number, number][];
}

export interface GreenRoof {
  building_id: string;
  substrate_depth_m: number;
  vegetation_type: string;
}

export interface SimulationSettings {
  forcing: ForcingArchetype;
  simulation_hours: number;
  output_interval_s: number;
}

export interface Scenario {
  schema_version?: string;
  name: string;
  description?: string;
  scenario_type: ScenarioType;
  domain: DomainConfig;
  data_sources?: DomainData;
  simulation: SimulationSettings;
  trees: TreePlacement[];
  surface_changes: SurfaceChange[];
  green_roofs: GreenRoof[];
}

export interface ValidationIssue {
  code: string;
  severity: 'error' | 'warning' | 'info';
  message: string;
  context?: Record<string, unknown>;
}

export interface ComfortStatistics {
  variable: string;
  mean: number;
  median: number;
  std: number;
  p05: number;
  p95: number;
  min_val: number;
  max_val: number;
  n_valid: number;
}

export interface PETClassification {
  class_fractions: Record<string, number>;
  dominant_class: string;
  stress_level: string;
}

export interface DeltaStatistics {
  variable: string;
  mean_delta: number;
  median_delta: number;
  max_improvement: number;
  max_worsening: number;
  pct_improved: number;
  pct_worsened: number;
  pct_unchanged: number;
  n_valid: number;
}

export interface ThresholdImpact {
  variable: string;
  threshold_name: string;
  threshold_value: number;
  cells_above_baseline: number;
  cells_above_intervention: number;
  cells_improved: number;
  cells_worsened: number;
  pct_improved: number;
}

export interface Project {
  id: number;
  name: string;
  description: string;
  scenario_count?: number;
  created_at: string;
}

export interface ScenarioRecord {
  id: number;
  project_id: number;
  name: string;
  scenario_type: string;
  scenario_json: Scenario;
  created_at: string;
}

export interface Job {
  id: number;
  job_id: number;
  job_type: JobType;
  status: JobStatus;
  baseline_scenario_id: number;
  intervention_scenario_id?: number;
  output_dir?: string;
  result_summary?: Record<string, unknown>;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface SpeciesInfo {
  common_name: string;
  common_name_de: string;
  height_m: { min: number; max: number; default: number };
  crown_diameter_m: { min: number; max: number; default: number };
  trunk_height_m: { min: number; max: number; default: number };
  lad_max_m2m3: number;
  palm_tree_type: number;
  source: string;
}

export interface SurfaceInfo {
  name: string;
  palm_category: string;
  palm_type_id: number;
  albedo: number;
  emissivity: number;
}
