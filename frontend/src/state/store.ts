import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Formulation, Jurisdiction, Language, Persona, UiLanguage } from '../api/types';
import { localISODate } from '../lib/date';

interface CaseItem { request_id: string; summary: string; receipt_id?: string }
export type ThemeMode = 'light' | 'dark';
interface AppState {
  jurisdiction: Jurisdiction; asOf: string; language: Language; uiLanguage: UiLanguage; persona: Persona; theme: ThemeMode;
  caseFile: CaseItem[]; formulationDraft: Formulation;
  setJurisdiction: (value: Jurisdiction) => void; setAsOf: (value: string) => void;
  setLanguage: (value: Language) => void; setUiLanguage: (value: UiLanguage) => void;
  setPersona: (value: Persona) => void; setTheme: (value: ThemeMode) => void; addCaseItem: (value: CaseItem) => void;
  removeCaseItem: (id: string) => void; moveCaseItem: (index: number, direction: -1 | 1) => void;
  setFormulationDraft: (value: Formulation) => void;
}

export const emptyFormulation: Formulation = {
  name: '', intended_use: '', product_form: '', ingredients: [{ name: '', part: '', role: 'active', amount: '' }],
  process_summary: '', classical_sources_cited: [], claims_novel_effect: false, novel_effect_evidence: '',
  has_clinical_data: false, is_derivative_of_known_substance: false,
  resource_origin: { state: '', wild_or_cultivated: null, codified_tk: false }, applicant_type: null, planned_actions: [],
};
const today = localISODate;

export const useAppStore = create<AppState>()(persist((set) => ({
  jurisdiction: 'BOTH', asOf: today(), language: 'auto', uiLanguage: 'en', persona: 'vaidya', theme: 'light',
  caseFile: [], formulationDraft: emptyFormulation,
  setJurisdiction: (jurisdiction) => set({ jurisdiction }), setAsOf: (asOf) => set({ asOf }),
  setLanguage: (language) => set({ language }), setUiLanguage: (uiLanguage) => set({ uiLanguage }),
  setPersona: (persona) => set({ persona }), setTheme: (theme) => set({ theme }),
  addCaseItem: (item) => set((state) => state.caseFile.some((entry) => entry.request_id === item.request_id) ? state : { caseFile: [...state.caseFile, item] }),
  removeCaseItem: (id) => set((state) => ({ caseFile: state.caseFile.filter((entry) => entry.request_id !== id) })),
  moveCaseItem: (index, direction) => set((state) => { const target = index + direction; if (target < 0 || target >= state.caseFile.length) return state; const caseFile = [...state.caseFile]; [caseFile[index], caseFile[target]] = [caseFile[target], caseFile[index]]; return { caseFile }; }),
  setFormulationDraft: (formulationDraft) => set({ formulationDraft }),
}), { name: 'pramana-ui-state', partialize: (state) => ({ jurisdiction: state.jurisdiction, asOf: state.asOf, language: state.language, uiLanguage: state.uiLanguage, persona: state.persona, theme: state.theme, caseFile: state.caseFile, formulationDraft: state.formulationDraft }) }));
