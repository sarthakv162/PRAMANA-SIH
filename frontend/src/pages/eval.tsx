import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api/client';
import type { EvalResults } from '../api/types';
import { PageHeading, Panel, Skeleton, StateMessage, EmptyState } from '../components/ui';
import { useAppStore } from '../state/store';

export function EvalPage() {
  const { t } = useTranslation();
  const theme = useAppStore((state) => state.theme);
  const query = useQuery({ queryKey: ['eval-latest'], queryFn: api.evalLatest });
  const result = query.data;
  const chartColors = theme === 'dark'
    ? { grid: 'rgba(205, 218, 206, .18)', text: '#b7c4ba', line: '#a8c8ae', tooltip: '#202a22', border: 'rgba(205, 218, 206, .2)' }
    : { grid: '#e2e9e3', text: '#68776d', line: '#548469', tooltip: '#fff', border: '#dce5dc' };
  return <div className="page-stack"><PageHeading eyebrow="MEASURED SYSTEM QUALITY" title={t('evalTitle')} description={t('evalDescription')} />
    {query.isLoading && <Panel><Skeleton rows={4} /></Panel>}{query.error && <StateMessage error={query.error} onRetry={() => void query.refetch()} />}
    {result && <>
      <Panel className="eval-meta">
        <div className="eval-run-heading"><span className="eyebrow">{t('latestRun').toUpperCase()}</span><h2>{result.run_id}</h2></div>
        <div className="eval-metadata"><span><b>{t('questions')}</b>{result.n_questions}</span><span><b>{t('conditions')}</b>{result.conditions.length}</span><span><b>{t('version')}</b>{result.corpus_version}</span><span><b>{t('generated')}</b>{new Date(result.generated_at).toLocaleString()}</span></div>
      </Panel>
      {result.conditions.length > 0 ? <Panel className="eval-table-panel">
        <div className="section-title"><div><span className="eyebrow">{result.conditions.length} {t('conditions').toLowerCase()}</span><h2>{t('conditions')}</h2></div><span className="small-muted">{t('questions')}: {result.n_questions}</span></div>
        <div className="table-scroll"><table><thead><tr><th scope="col">{t('conditions')}</th><th scope="col">{t('citationPrecision')}</th><th scope="col">{t('citationRecall')}</th><th scope="col">{t('faithfulness')}</th><th scope="col">{t('abstentionAccuracy')}</th><th scope="col">{t('leaks')}</th></tr></thead><tbody>{result.conditions.map((row) => <tr key={row.name}><th scope="row">{row.name}</th><td>{formatRate(row.citation_precision)}</td><td>{formatRate(row.citation_recall)}</td><td>{formatRate(row.faithfulness)}</td><td>{formatRate(row.abstention_accuracy)}</td><td>{row.jurisdiction_leaks}</td></tr>)}</tbody></table></div>
      </Panel> : <Panel className="eval-empty-panel"><EmptyState title={t('noEval')} detail={t('evalNoMeasurements')} /></Panel>}
      {result.risk_coverage.length > 0 && <Panel className="eval-chart-panel">
        <div className="section-title"><div><span className="eyebrow">{t('evalRiskCoverage')}</span><h2>{t('evalRiskCoverage')}</h2></div></div>
        <div className="chart-wrap eval-chart" role="img" aria-label={t('evalRiskCoverage')}><ResponsiveContainer width="100%" height="100%"><LineChart data={result.risk_coverage} margin={{ top: 12, right: 20, bottom: 20, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
          <XAxis dataKey="coverage" type="number" domain={[0, 1]} tickFormatter={formatRate} tick={{ fill: chartColors.text, fontSize: 12 }} axisLine={{ stroke: chartColors.grid }} tickLine={{ stroke: chartColors.grid }} label={{ value: t('evalCoverage'), position: 'insideBottom', offset: -10, fill: chartColors.text }} />
          <YAxis dataKey="risk" type="number" domain={[0, 1]} tickFormatter={formatRate} tick={{ fill: chartColors.text, fontSize: 12 }} axisLine={{ stroke: chartColors.grid }} tickLine={{ stroke: chartColors.grid }} />
          <Tooltip content={({ active, payload }) => {
            const point = payload?.[0]?.payload as EvalResults['risk_coverage'][number] | undefined;
            return active && point ? <div className="eval-chart-tooltip" style={{ background: chartColors.tooltip, borderColor: chartColors.border, color: chartColors.text }}><b>{t('evalRiskCoverage')}</b><span>{t('evalCoverage')} <strong>{formatRate(point.coverage)}</strong></span><span>{t('evalRisk')} <strong>{formatRate(point.risk)}</strong></span><span>{t('evalThreshold')} <strong>{formatRate(point.threshold)}</strong></span></div> : null;
          }} />
          <Line dataKey="risk" type="monotone" name={t('evalRisk')} stroke={chartColors.line} strokeWidth={3} dot={{ r: 4, fill: chartColors.line, strokeWidth: 0 }} activeDot={{ r: 6 }} />
        </LineChart></ResponsiveContainer></div>
      </Panel>}
    </>}
  </div>;
}
function formatRate(value: number) { return `${(value * 100).toFixed(1)}%`; }
