import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation } from '@tanstack/react-query';
import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip } from 'recharts';
import { api } from '../api/client';
import type { Formulation, TkRadar } from '../api/types';
import { FormulationForm } from '../components/forms';
import { PageHeading, Panel, Skeleton, StateMessage } from '../components/ui';
import { emptyFormulation, useAppStore } from '../state/store';

export function TkPage() {
  const { t } = useTranslation(); const { formulationDraft, setFormulationDraft } = useAppStore();
  const mutation = useMutation({ mutationFn: (form: Formulation) => api.tkRadar(form) }); const result = mutation.data as TkRadar | undefined;
  const analyze = mutation.mutate;
  const [copied, setCopied] = useState(false);
  const hasInput = formulationDraft.ingredients.some((item) => item.name.trim().length > 0);
  useEffect(() => { if (!hasInput) return; const timeout = window.setTimeout(() => analyze(formulationDraft), 600); return () => window.clearTimeout(timeout); }, [formulationDraft, hasInput, analyze]);
  const copy = async () => { await navigator.clipboard?.writeText(result?.tkdl_query.text ?? ''); setCopied(true); window.setTimeout(() => setCopied(false), 1400); };
  return <div className="page-stack"><PageHeading eyebrow="TRADITIONAL KNOWLEDGE RADAR" title={t('tkTitle')} description={t('tkDescription')} />
    <FormulationForm value={formulationDraft ?? emptyFormulation} onChange={setFormulationDraft} onSubmit={() => mutation.mutate(formulationDraft)} busy={mutation.isPending} submitLabel={t('analyze')} />
    {mutation.isPending && !result && <Panel><Skeleton rows={4} /></Panel>}{mutation.error && <StateMessage error={mutation.error} onRetry={() => mutation.mutate(formulationDraft)} />}
    {result && <div className="tk-grid"><Panel className="radar-panel"><div className="section-title"><div><span className="eyebrow">ILLUSTRATIVE SEED DATASET</span><h2>{t('matches')}</h2></div></div><div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><RadarChart data={result.radar.axes} outerRadius="72%"><PolarGrid stroke="#e1e7df" /><PolarAngleAxis dataKey="label" tick={{ fill: '#5a6c61', fontSize: 11 }} /><Radar dataKey="value" stroke="#558368" fill="#77a983" fillOpacity={0.36} /><Tooltip formatter={(value) => `${Math.round(Number(value) * 100)}%`} /></RadarChart></ResponsiveContainer></div><div className="match-list">{result.matches.map((match) => <article className="match-card" key={match.formulation_id}><div className="section-title"><div><h3>{match.name}</h3><span className="small-muted">{match.source_text}</span></div><b className="match-score">{Math.round(match.similarity * 100)}%</b></div><div className="chip-row"><span>{t('overlap')}</span>{match.overlap.map((item) => <span className="ingredient-chip chip-good" key={item}>{item}</span>)}{match.missing_in_input.map((item) => <span className="ingredient-chip chip-missing" key={item}>{t('missing')}: {item}</span>)}{match.extra_in_input.map((item) => <span className="ingredient-chip chip-extra" key={item}>{t('extra')}: {item}</span>)}</div></article>)}</div></Panel>
      <div className="tk-side"><Panel><span className="eyebrow">ONTOLOGY NORMALIZATION</span><h2>{t('normalizedNames')}</h2>{result.normalized_ingredients.map((item) => <div className="normalized-item" key={item.input}><div className="normalized-input">{item.input}<span>{Math.round(item.confidence * 100)}%</span></div><b>{item.canonical_latin}</b><span>Sanskrit: {item.sanskrit}</span><div className="chip-row">{item.regional.map((name) => <span key={name.lang} className="ingredient-chip">{name.lang}: {name.name}</span>)}</div></div>)}</Panel>
        <Panel className="query-pack"><div className="section-title"><div><span className="eyebrow">COPYABLE SEARCH TERMS</span><h2>{t('tkdlPack')}</h2></div><button className="button button-secondary button-small" onClick={() => void copy()}>{copied ? 'Copied' : t('copyPack')}</button></div><pre>{result.tkdl_query.text}</pre><div className="chip-row">{result.tkdl_query.terms.map((item) => <span className="ingredient-chip" key={item}>{item}</span>)}{result.tkdl_query.ipc.map((item) => <span className="ingredient-chip" key={item}>{item}</span>)}</div><p className="small-muted">{result.tkdl_query.note}</p><div className="note warning-note">ⓘ {t('tkdlNotice')}</div></Panel>
        <Panel><span className="eyebrow">SEEDED WATCHLIST</span><h2>{t('watchlist')}</h2>{result.watchlist_hits.map((hit) => <article className="watchlist-item" key={hit.case}><h3>{hit.case}</h3><span className="small-muted">{hit.jurisdiction} · {hit.outcome}</span><p>{hit.summary}</p><a href={hit.source_url} target="_blank" rel="noreferrer">Open source ↗</a></article>)}</Panel></div></div>}
  </div>;
}
