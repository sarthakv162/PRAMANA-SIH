import { useTranslation } from 'react-i18next';
import type { ApplicantType, Formulation } from '../api/types';
import { Panel } from './ui';

const APPLICANT_TYPES: ApplicantType[] = ['indian_citizen', 'indian_company', 'foreign_entity', 'nri'];
const emptyOrigin = { state: null, wild_or_cultivated: null, codified_tk: null } as const;

export function FormulationForm({ value, onChange, onSubmit, busy, submitLabel }: { value: Formulation; onChange: (value: Formulation) => void; onSubmit: () => void; busy?: boolean; submitLabel?: string }) {
  const { t } = useTranslation();
  const field = <K extends keyof Formulation>(key: K, next: Formulation[K]) => onChange({ ...value, [key]: next });
  const setIngredient = (index: number, key: keyof Formulation['ingredients'][number], next: string) => field('ingredients', value.ingredients.map((item, i) => i === index ? { ...item, [key]: next } : item));
  const origin = value.resource_origin ?? emptyOrigin;
  const setOrigin = (next: Partial<NonNullable<Formulation['resource_origin']>>) => field('resource_origin', { ...origin, ...next });
  return <Panel className="form-panel"><div className="form-section-heading"><span className="section-number">01</span><div><h2>{t('formulation')}</h2><p>Provide the formulation inputs supported by the request schema.</p></div></div>
    <div className="form-grid"><label>{t('name')}<input value={value.name} onChange={(event) => field('name', event.target.value)} /></label><label>{t('intendedUse')}<input value={value.intended_use} onChange={(event) => field('intended_use', event.target.value)} /></label><label>{t('productForm')}<input value={value.product_form} onChange={(event) => field('product_form', event.target.value)} /></label><label>{t('classicalSources')}<input value={value.classical_sources_cited.join(', ')} onChange={(event) => field('classical_sources_cited', event.target.value.split(',').map((item) => item.trim()).filter(Boolean))} /></label>
      <label className="wide-field">{t('process')}<textarea rows={2} value={value.process_summary ?? ''} onChange={(event) => field('process_summary', event.target.value)} /></label>
    </div>
    <div className="repeater-heading"><h3>{t('ingredients')}</h3><button type="button" className="button button-secondary button-small" onClick={() => field('ingredients', [...value.ingredients, { name: '', part: '', role: 'active', amount: '' }])}>＋ {t('addIngredient')}</button></div>
    {value.ingredients.map((ingredient, index) => <div className="ingredient-row" key={index}><label>{t('ingredient')}<input list="ingredient-hints" value={ingredient.name} onChange={(event) => setIngredient(index, 'name', event.target.value)} /></label><label>{t('part')}<input value={ingredient.part ?? ''} onChange={(event) => setIngredient(index, 'part', event.target.value)} /></label><label>{t('role')}<select value={ingredient.role ?? 'active'} onChange={(event) => setIngredient(index, 'role', event.target.value)}><option value="active">active</option><option value="excipient">excipient</option></select></label><label>{t('amount')}<input value={ingredient.amount ?? ''} onChange={(event) => setIngredient(index, 'amount', event.target.value)} /></label>{value.ingredients.length > 1 && <button type="button" className="icon-button remove-ingredient" aria-label={`${t('remove')} ${ingredient.name || t('ingredient')}`} onClick={() => field('ingredients', value.ingredients.filter((_, i) => i !== index))}>×</button>}</div>)}
    <datalist id="ingredient-hints"><option value="haridra" /><option value="Azadirachta indica" /></datalist>
    <div className="form-grid form-grid-secondary">
      <label>{t('novelEffect')}<select value={String(value.claims_novel_effect)} onChange={(event) => field('claims_novel_effect', event.target.value === 'true')}><option value="false">{t('no')}</option><option value="true">{t('yes')}</option></select></label>
      <label>{t('clinicalData')}<select value={String(value.has_clinical_data)} onChange={(event) => field('has_clinical_data', event.target.value === 'true')}><option value="false">{t('no')}</option><option value="true">{t('yes')}</option></select></label>
      <label>Derivative of known substance<select value={String(value.is_derivative_of_known_substance)} onChange={(event) => field('is_derivative_of_known_substance', event.target.value === 'true')}><option value="false">{t('no')}</option><option value="true">{t('yes')}</option></select></label>
      <label>{t('novelEffect')} evidence<input value={value.novel_effect_evidence ?? ''} onChange={(event) => field('novel_effect_evidence', event.target.value)} /></label>
      <label>{t('applicantType')}<select value={value.applicant_type ?? ''} onChange={(event) => field('applicant_type', (event.target.value || null) as Formulation['applicant_type'])}><option value="">{t('empty')}</option>{APPLICANT_TYPES.map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}</select></label>
      <label>{t('state')}<input value={origin.state ?? ''} onChange={(event) => setOrigin({ state: event.target.value })} /></label>
      <label>{t('wildCultivated')}<select value={origin.wild_or_cultivated ?? ''} onChange={(event) => setOrigin({ wild_or_cultivated: (event.target.value || null) as 'wild' | 'cultivated' | null })}><option value="">{t('empty')}</option><option value="wild">wild</option><option value="cultivated">cultivated</option></select></label>
      <label>{t('codifiedTk')}<select value={String(origin.codified_tk)} onChange={(event) => setOrigin({ codified_tk: event.target.value === 'true' })}><option value="false">{t('no')}</option><option value="true">{t('yes')}</option></select></label>
      <label>{t('plannedActions')}<input value={value.planned_actions.join(', ')} onChange={(event) => field('planned_actions', event.target.value.split(',').map((item) => item.trim()).filter(Boolean))} placeholder="patent_filing, commercial_sale" /></label>
    </div>
    <div className="form-actions"><button className="button button-primary" type="button" onClick={onSubmit} disabled={busy}>{busy ? t('loading') : submitLabel ?? t('analyze')} <span>→</span></button></div>
  </Panel>;
}

export function CheckField({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) { return <label className="check-field"><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><span>{label}</span></label>; }
