import { create } from 'zustand';
import type {
  Job,
  Project,
  Scenario,
  ScenarioRecord,
  SpeciesInfo,
  SurfaceInfo,
  ValidationIssue,
} from './types';

interface AppStore {
  token: string | null;
  setToken: (t: string | null) => void;

  currentProject: Project | null;
  setCurrentProject: (p: Project | null) => void;

  scenarios: ScenarioRecord[];
  setScenarios: (s: ScenarioRecord[]) => void;

  // Active scenario being edited
  activeScenario: Scenario | null;
  setActiveScenario: (s: Scenario | null) => void;
  updateActiveScenario: (patch: Partial<Scenario>) => void;

  // Map state
  drawMode: 'none' | 'bbox' | 'tree' | 'surface';
  setDrawMode: (m: 'none' | 'bbox' | 'tree' | 'surface') => void;

  // Validation
  validationIssues: ValidationIssue[];
  setValidationIssues: (v: ValidationIssue[]) => void;

  // Results
  activeJob: Job | null;
  setActiveJob: (j: Job | null) => void;

  // Species/surfaces catalogues (loaded once)
  speciesCatalogue: Record<string, SpeciesInfo> | null;
  surfacesCatalogue: Record<string, SurfaceInfo> | null;
  setSpeciesCatalogue: (c: Record<string, SpeciesInfo>) => void;
  setSurfacesCatalogue: (c: Record<string, SurfaceInfo>) => void;
}

export const useAppStore = create<AppStore>((set) => ({
  token: null,
  setToken: (t) => set({ token: t }),

  currentProject: null,
  setCurrentProject: (p) => set({ currentProject: p }),

  scenarios: [],
  setScenarios: (s) => set({ scenarios: s }),

  activeScenario: null,
  setActiveScenario: (s) => set({ activeScenario: s }),
  updateActiveScenario: (patch) =>
    set((state) => ({
      activeScenario: state.activeScenario
        ? { ...state.activeScenario, ...patch }
        : null,
    })),

  drawMode: 'none',
  setDrawMode: (m) => set({ drawMode: m }),

  validationIssues: [],
  setValidationIssues: (v) => set({ validationIssues: v }),

  activeJob: null,
  setActiveJob: (j) => set({ activeJob: j }),

  speciesCatalogue: null,
  surfacesCatalogue: null,
  setSpeciesCatalogue: (c) => set({ speciesCatalogue: c }),
  setSurfacesCatalogue: (c) => set({ surfacesCatalogue: c }),
}));
