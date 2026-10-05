import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation } from '@tanstack/react-query';
import { api } from '../api/client';
import type { ClassifyResponse, EvidenceSpan, IpPosture } from '../api/types';
import { DecisionPathView } from '../components/decision-path';
import { EvidenceDrawer, EvidenceQuote, PageHeading, Panel, RiskBadge, Skeleton, StateMessage } from '../components/ui';
import { useAppStore } from '../state/store';

function PostureResult({ result }: { result: Extract<ClassifyResponse, { type: 'result' }> }) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<EvidenceSpan | null>(null);
  const keys: (keyof IpPosture)[] = ['patent', 'gi', 'trademark', 'design', 'copyright', 'trade_secret'];
  const label = (key: string) => t(({ patent: 'patent', gi: 'gi', trademark: 'trademark', design: 'design', copyright: 'copyright', trade_secret: 'tradeSecret' } as Record<string, string>)[key] ?? key);

  return <div className="result-stack">
    <Panel className="classification-result">
      <div className="result-banner">
        <span className="result-icon" aria-hidden="true">◈</span>
        <div><span className="eyebrow">{t('provisionalPosture')}</span><h2>{result.category_label}</h2></div>
      </div>
      <section className="classification-requirements" aria-labelledby="classification-requirements-title">
        <h3 id="classification-requirements-title">{t('requirements')}</h3>
        {result.requirements.length ? <ul className="requirements-list">{result.requirements.map((item, index) => <li key={`${item.text}-${index}`}>
          <span>{item.text}</span>
          {item.evidence_ids.map((id) => {
            const evidence = result.evidence[id];
            return evidence ? <button key={id} type="button" className="classify-citation-chip" title={evidence.citation_label} aria-label={`${t('openSource')}: ${evidence.citation_label}`} onClick={() => setSelected(evidence)}><span aria-hidden="true">↗</span>{evidence.citation_label}</button> : null;
          })}
        </li>)}</ul> : <p className="classification-no-requirements">{t('empty')}</p>}
      </section>
      <section className="classification-posture" aria-labelledby="classification-posture-title">
        <h3 id="classification-posture-title">{t('ipPosture')}</h3>
        <div className="posture-matrix">{keys.map((key) => {
          const item = result.ip_posture[key];
          return item ? <article className="posture-cell" key={key}><span>{label(key)}</span><RiskBadge risk={item.risk} /><p>{item.note}</p></article> : null;
        })}</div>
      </section>
      <section className="abs-posture" aria-labelledby="classification-abs-title"><b id="classification-abs-title">{t('abs')}</b><p>{result.abs_posture.summary}</p></section>
    </Panel>
    <DecisionPathView path={result.decision_path} evidence={result.evidence} />
    <EvidenceDrawer evidence={selected} onClose={() => setSelected(null)} />
  </div>;
}

export function ClassificationPage() {
  const { t } = useTranslation(); const { jurisdiction, asOf, language } = useAppStore();
  const [answers, setAnswers] = useState<Record<string, string | string[] | boolean>>({}); const [current, setCurrent] = useState<ClassifyResponse | null>(null);
  const mutation = useMutation({ mutationFn: (next: Record<string, string | string[] | boolean>) => api.classify({ answers: next, jurisdiction, as_of: asOf, language }) });
  useEffect(() => { mutation.mutate({}); // Initial tree question is server-driven.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { if (mutation.data) setCurrent(mutation.data); }, [mutation.data]);
  const question = current?.type === 'question' ? current : null;
  const value = question ? answers[question.question_id] : undefined;
  const setAnswer = (next: string | string[] | boolean) => { if (!question) return; setAnswers((previous) => ({ ...previous, [question.question_id]: next })); };
  const submit = () => mutation.mutate(answers);
  const back = () => { if (!question) return; const keys = Object.keys(answers); if (!keys.length) return; const updated = { ...answers }; delete updated[keys[keys.length - 1]]; setAnswers(updated); mutation.mutate(updated); };
  return <div className="page-stack"><PageHeading eyebrow="RULE ENGINE / STATELESS WIZARD" title={t('classifyTitle')} description={t('classifyDescription')} />
    {mutation.isPending && !current && <Panel><Skeleton rows={5} /></Panel>}
    {mutation.error && <StateMessage error={mutation.error} onRetry={submit} />}
    {question && <Panel className="wizard-panel">
      <div className="wizard-progress"><span>{t('requirements')}</span><span>{question.progress.answered} / {question.progress.estimated_total}</span></div>
      <div className="progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={question.progress.estimated_total} aria-valuenow={question.progress.answered}><i style={{ width: `${Math.max(8, question.progress.answered / Math.max(1, question.progress.estimated_total) * 100)}%` }} /></div>
      <span className="eyebrow">{t('questionNumber').toUpperCase()} {question.progress.answered + 1}</span>
      <h2 id="classification-question">{question.text}</h2>
      <details className="why-popover"><summary>{t('whyAsk')}</summary><p>{question.why_asked}</p>{question.evidence_ids.map((id) => question.evidence[id] && <EvidenceQuote key={id} evidence={question.evidence[id]} />)}</details>
      {!!question.input.fields?.length && <div className="wizard-fields">{question.input.fields.map((field) => <label key={field.id}>{field.label}
        {field.options.length ? <select aria-label={field.label} value={typeof answers[field.id] === 'string' ? answers[field.id] as string : ''} disabled={mutation.isPending} onChange={(event) => setAnswers((previous) => ({ ...previous, [field.id]: event.target.value }))}><option value="">Choose an answer</option>{field.options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
          : <textarea aria-label={field.label} rows={2} value={typeof answers[field.id] === 'string' ? answers[field.id] as string : ''} disabled={mutation.isPending} onChange={(event) => setAnswers((previous) => ({ ...previous, [field.id]: event.target.value }))} />}
      </label>)}</div>}
      {question.input.kind === 'single' && <fieldset className="option-list wizard-input" aria-labelledby="classification-question" disabled={mutation.isPending}>{question.input.options.map((option) => <label className="radio-option" key={option.value}><input type="radio" name={question.question_id} checked={value === option.value} onChange={() => setAnswer(option.value)} /><span>{option.label}</span></label>)}</fieldset>}
      {question.input.kind === 'multi' && <fieldset className="option-list wizard-input" aria-labelledby="classification-question" disabled={mutation.isPending}>{question.input.options.map((option) => { const selected = Array.isArray(value) && value.includes(option.value); return <label className="check-field" key={option.value}><input type="checkbox" checked={selected} onChange={() => setAnswer(selected ? (value as string[]).filter((item) => item !== option.value) : [...(Array.isArray(value) ? value : []), option.value])} /><span>{option.label}</span></label>; })}</fieldset>}
      {question.input.kind === 'boolean' && <fieldset className="option-list wizard-input" aria-labelledby="classification-question" disabled={mutation.isPending}>{[true, false].map((item) => <label className="radio-option" key={String(item)}><input type="radio" name={question.question_id} checked={value === item} onChange={() => setAnswer(item)} /><span>{item ? t('yes') : t('no')}</span></label>)}</fieldset>}
      {question.input.kind === 'text' && !question.input.fields?.length && <label className="wizard-text-label"><span>{question.text}</span><textarea rows={3} value={typeof value === 'string' ? value : ''} disabled={mutation.isPending} onChange={(event) => setAnswer(event.target.value)} /></label>}
      <div className="wizard-actions"><button className="button button-secondary" type="button" onClick={back} disabled={!Object.keys(answers).length || mutation.isPending}>← {t('back')}</button><button className="button button-primary" onClick={submit} disabled={mutation.isPending || (question.input.fields?.some((field) => field.required && !answers[field.id]) ?? false)}>{mutation.isPending ? t('loading') : t('submit')} →</button></div>
    </Panel>}
    {current?.type === 'result' && <PostureResult result={current} />}
  </div>;
}
