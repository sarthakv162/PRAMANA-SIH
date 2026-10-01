import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation } from '@tanstack/react-query';
import { api } from '../api/client';
import type { EvidenceSpan, Formulation, PatentRisk } from '../api/types';
import { DecisionPathView } from '../components/decision-path';
import { FormulationForm } from '../components/forms';
import { EvidenceDrawer, PageHeading, Panel, RiskBadge, Skeleton, StateMessage } from '../components/ui';
import { emptyFormulation, useAppStore } from '../state/store';

export function PatentRiskPage() {
  const { t } = useTranslation(); const { asOf, language, formulationDraft, setFormulationDraft } = useAppStore();
  const [selected, setSelected] = useState<EvidenceSpan | null>(null);
  const mutation = useMutation({ mutationFn: (formulation: Formulation) => api.patentRisk({ ...formulation, as_of: asOf, language }) });
  const result = mutation.data as PatentRisk | undefined;
  return <div className="page-stack"><PageHeading eyebrow="DETERMINISTIC RULE ENGINE" title={t('patentTitle')} description={t('patentDescription')} />
    <FormulationForm value={formulationDraft ?? emptyFormulation} onChange={setFormulationDraft} onSubmit={() => mutation.mutate(formulationDraft)} busy={mutation.isPending} submitLabel={t('analyze')} />
    {mutation.isPending && <Panel><Skeleton rows={4} /></Panel>}{mutation.error && <StateMessage error={mutation.error} onRetry={() => mutation.mutate(formulationDraft)} />}
    {result && <div className="result-stack"><Panel className="risk-result"><div className="risk-summary"><div><span className="eyebrow">{t('riskIndicator').toUpperCase()}</span><h2>{t(result.gauge)} risk</h2><p>Rule-weight score · {result.score.toFixed(2)} · Not a probability</p></div><div className={`risk-gauge gauge-${result.gauge}`} role="img" aria-label={`${t(result.gauge)} risk indicator`}><div className="gauge-inner"><b>{Math.round(result.score * 100)}</b><span>{t('riskIndicator')}</span></div></div></div><div className="risk-sections">{result.per_section.map((item) => <article className="risk-card" key={item.section}><div className="section-title"><h3>Section {item.section}</h3><RiskBadge risk={item.risk} /></div>{item.triggered_rules.length > 0 && <p className="small-muted">{item.triggered_rules.join(' · ')}</p>}{item.reasons.map((reason, index) => <p key={index}>{reason}</p>)}<div className="citation-chips">{item.evidence_ids.map((id) => <button key={id} className="citation-chip" onClick={() => setSelected(result.evidence[id] ?? null)}>[{id}]</button>)}</div></article>)}</div><div className="what-help"><h3>{t('whatWouldHelp')}</h3>{result.what_would_help.map((item, index) => <p key={index}>↗ {item.text}</p>)}</div><LinkReceipt id={result.receipt_id} /></Panel><DecisionPathView path={result.decision_path} evidence={result.evidence} /><EvidenceDrawer evidence={selected} onClose={() => setSelected(null)} /></div>}
  </div>;
}
function LinkReceipt({ id }: { id: string }) { return <a className="text-button" href={`/receipt/${id}`}>Receipt {id} ↗</a>; }
