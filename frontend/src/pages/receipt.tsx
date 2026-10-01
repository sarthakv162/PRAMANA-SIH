import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { PageHeading, Panel, Skeleton, StateMessage } from '../components/ui';

export function ReceiptPage() {
  const { t } = useTranslation(); const { id = '' } = useParams(); const [verified, setVerified] = useState(false);
  const receipt = useQuery({ queryKey: ['receipt', id], queryFn: () => api.receipt(id), enabled: Boolean(id) });
  const verify = useMutation({ mutationFn: () => api.verify(id), onSuccess: () => setVerified(true) });
  const result = verify.data;
  return <div className="page-stack"><PageHeading eyebrow="AUDIT TRAIL" title={t('receiptTitle')} description={t('receiptDescription')} action={<Link className="text-button" to="/">← {t('ask')}</Link>} />
    {receipt.isLoading && <Panel><Skeleton rows={6} /></Panel>}{receipt.error && <StateMessage error={receipt.error} onRetry={() => void receipt.refetch()} />}
    {receipt.data && <><Panel className="receipt-panel"><div className="receipt-heading"><div><span className="eyebrow">AUDIT RECEIPT</span><h2>{receipt.data.id}</h2></div><button className="button button-primary" onClick={() => verify.mutate()} disabled={verify.isPending}>{verify.isPending ? t('loading') : `◉ ${t('verify')}`}</button></div><dl className="receipt-grid"><dt>Request ID</dt><dd>{receipt.data.request_id}</dd><dt>{t('version')}</dt><dd>{receipt.data.corpus_version}</dd><dt>{t('generated')}</dt><dd>{new Date(receipt.data.created_at).toLocaleString()}</dd><dt>Query hash</dt><dd><code>{receipt.data.query_hash}</code></dd><dt>Prompt version</dt><dd>{receipt.data.prompt_version}</dd><dt>Previous hash</dt><dd><code>{receipt.data.prev_hash}</code></dd><dt>Entry hash</dt><dd><code className="hash-block">{receipt.data.entry_hash}</code></dd></dl><div className="model-chips">{Object.entries(receipt.data.model_ids).map(([key, value]) => <span key={key}>{key} · {value}</span>)}</div><h3>Chunk hashes</h3>{receipt.data.chunk_hashes.map((hash) => <code className="hash-block" key={hash}>{hash}</code>)}</Panel>
      {verify.error && <StateMessage error={verify.error} onRetry={() => verify.mutate()} />}
      {result && <Panel className={`verification-panel ${result.chain_valid ? 'verify-good' : 'verify-bad'}`}><div className="verify-summary"><span className="verify-symbol">{result.chain_valid ? '✓' : '×'}</span><div><h2>{t(result.chain_valid ? 'chainValid' : 'chainInvalid')}</h2><code>{result.corpus_root}</code></div></div><div className="table-scroll"><table><thead><tr><th>Evidence ID</th><th>SHA-256</th><th>In corpus</th><th>Merkle proof</th></tr></thead><tbody>{result.spans.map((span) => <tr key={span.evidence_id}><td><code>{span.evidence_id}</code></td><td><code>{span.sha256}</code></td><td>{span.in_corpus ? '✓ Valid' : '× Invalid'}</td><td>{span.merkle_proof_valid ? `✓ ${t('merkleValid')}` : `× ${t('merkleInvalid')}`}</td></tr>)}</tbody></table></div></Panel>}
      {import.meta.env.VITE_API_MODE !== 'live' && <Link className="test-fixture-link" to="/receipt/tampered">Open tampered mock receipt →</Link>}
    </>}{verified && <span className="sr-only" role="status">Verification complete</span>}
  </div>;
}
