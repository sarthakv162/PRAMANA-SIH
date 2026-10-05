import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useAppStore } from '../state/store';
import { WorkspaceAccess } from '../components/workspace-access';
import { api } from '../api/client';
import { PageHeading, Panel, EmptyState } from '../components/ui';
import type { DossierFormat } from '../api/types';

export function CasePage() {
  const { t } = useTranslation(); const { caseFile, caseError, refreshCase, removeCaseItem, moveCaseItem } = useAppStore();
  useEffect(() => { void refreshCase(); }, [refreshCase]);
  const health = useQuery({ queryKey: ['health'], queryFn: api.health });
  const [format, setFormat] = useState<DossierFormat>('pdf'); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const build = async () => { setBusy(true); setError(''); try { const blob = await api.dossier(caseFile.map((item) => item.request_id), format, 'auto'); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = `pramana-dossier.${format}`; document.body.appendChild(anchor); anchor.click(); anchor.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to build dossier.'); } finally { setBusy(false); } };
  return <div className="page-stack"><PageHeading eyebrow="SHARED DEMO WORKSPACE" title={t('caseTitle')} description={t('caseDescription')} action={<span className="count-chip">{caseFile.length} items</span>} />
    <WorkspaceAccess onConnect={() => void refreshCase()} />
    {caseError && <p className="field-error" role="alert">{caseError}</p>}
    <Panel className="case-panel"><div className="section-title"><div><span className="eyebrow">SAVED ON THE SERVER · 30-DAY RETENTION</span><h2>{t('caseItems')}</h2></div></div>{caseFile.length ? <ol className="case-list">{caseFile.map((item, index) => <li className="case-item" key={item.request_id}><span className="case-index">{String(index + 1).padStart(2, '0')}</span><div className="case-summary"><b>{item.summary}</b><span>{item.request_id}{item.receipt_id && <> · <a href={`/receipt/${item.receipt_id}`}>{item.receipt_id}</a></>}</span></div><div className="case-controls"><button className="icon-button" disabled={!index} aria-label={`${t('reorder')} up`} onClick={() => moveCaseItem(index, -1)}>↑</button><button className="icon-button" disabled={index === caseFile.length - 1} aria-label={`${t('reorder')} down`} onClick={() => moveCaseItem(index, 1)}>↓</button><button className="icon-button danger-icon" aria-label={t('remove')} onClick={() => removeCaseItem(item.request_id)}>×</button></div></li>)}</ol> : <EmptyState title={t('noCaseItems')} detail="Add a saved result from an answer to build your shared case file." />}</Panel>
    <Panel className="dossier-panel"><span className="eyebrow">GENERATE FROM STORED RESULTS</span><h2>{t('dossier')}</h2>{health.data?.mock_mode !== false && <div className="note warning-note">{t('mockDossier')}</div>}<div className="dossier-controls"><label>{t('format')}<select value={format} onChange={(event) => setFormat(event.target.value as DossierFormat)}><option value="pdf">PDF</option><option value="docx">DOCX</option><option value="md">Markdown</option></select></label><p className="small-muted">Exports preserve saved results and original source text. Use DOCX or Markdown for multilingual text.</p><button className="button button-primary" disabled={!caseFile.length || busy} onClick={() => void build()}>{busy ? t('loading') : `${t('download')} ${format.toUpperCase()}`} ↓</button></div>{error && <p className="field-error" role="alert">{error}</p>}</Panel>
  </div>;
}
