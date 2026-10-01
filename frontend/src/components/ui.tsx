import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { EvidenceSpan } from '../api/types';
import { api } from '../api/client';

export function PageHeading({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: React.ReactNode }) {
  return <div className="page-heading"><div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1>{description && <p>{description}</p>}</div>{action}</div>;
}
export function Panel({ children, className = '' }: { children: React.ReactNode; className?: string }) { return <section className={`panel ${className}`}>{children}</section>; }
export function StateMessage({ error, onRetry, empty }: { error?: unknown; onRetry?: () => void; empty?: string }) {
  const { t } = useTranslation();
  if (error) return <div className="state-message error-state" role="alert"><b>{error instanceof Error ? error.message : 'Something went wrong.'}</b>{onRetry && <button className="button button-secondary" onClick={onRetry}>{t('retry')}</button>}</div>;
  return <div className="state-message">{empty ?? t('empty')}</div>;
}
export function Skeleton({ rows = 3 }: { rows?: number }) { return <div className="skeleton-stack" aria-label="Loading"><span className="sr-only">Loading</span>{Array.from({ length: rows }, (_, i) => <i key={i} />)}</div>; }
export function StatusBadge({ status }: { status: string }) {
  const { t } = useTranslation();
  const key = status === 'verified' ? 'verified' : status === 'partial' ? 'partial' : 'notIndexed';
  const mark = status === 'verified' ? '✓' : status === 'partial' ? '◐' : '×';
  return <span className={`badge status-${status}`}><span aria-hidden="true">{mark}</span> {t(key)}</span>;
}
export function RiskBadge({ risk }: { risk: string }) { const { t } = useTranslation(); return <span className={`badge risk-${risk}`}>{t(risk)}</span>; }
export function EmptyState({ title, detail }: { title: string; detail?: string }) { return <div className="empty-state"><div className="empty-icon" aria-hidden="true">◌</div><h3>{title}</h3>{detail && <p>{detail}</p>}</div>; }

export function EvidenceQuote({ evidence, onOpen }: { evidence: EvidenceSpan; onOpen?: () => void }) {
  const { t } = useTranslation();
  return <blockquote className="evidence-quote"><header><strong>{evidence.citation_label}</strong><span>{t('page')} {evidence.page}{evidence.page_end !== evidence.page ? `–${evidence.page_end}` : ''}</span></header><pre>{evidence.text}</pre><footer><button className="text-button" onClick={onOpen}>{t('openSource')} ↗</button><span>{evidence.jurisdiction}</span></footer></blockquote>;
}

function PdfPane({ evidence }: { evidence: EvidenceSpan }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [message, setMessage] = useState('');
  useEffect(() => {
    let cancelled = false;
    let task: { destroy: () => void } | undefined;
    const draw = async () => {
      if (!evidence.highlights.length) { setMessage('No PDF highlight coordinates are available for this span.'); return; }
      try {
        const pdfjs = await import('pdfjs-dist');
        const workerUrl = (await import('pdfjs-dist/build/pdf.worker.min.mjs?url')).default;
        pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
        task = pdfjs.getDocument({ url: api.pdfUrl(evidence.doc_id), httpHeaders: api.pdfHeaders(), rangeChunkSize: 65536 });
        const pdf = await (task as unknown as { promise: Promise<import('pdfjs-dist/types/src/display/api').PDFDocumentProxy> }).promise;
        if (cancelled) return;
        const page = await pdf.getPage(evidence.page);
        const scale = Math.min(1.2, Math.max(0.8, 720 / evidence.highlights[0].page_width));
        const viewport = page.getViewport({ scale });
        const canvas = canvasRef.current;
        if (!canvas) return;
        canvas.width = viewport.width; canvas.height = viewport.height;
        const context = canvas.getContext('2d');
        if (!context) return;
        await page.render({ canvasContext: context, viewport, canvas }).promise;
        for (const highlight of evidence.highlights.filter((item) => item.page === evidence.page)) {
          context.fillStyle = 'rgba(233, 185, 73, .32)';
          for (const rect of highlight.rects) context.fillRect(rect[0] * scale, rect[1] * scale, (rect[2] - rect[0]) * scale, (rect[3] - rect[1]) * scale);
        }
      } catch (error) { if (!cancelled) setMessage(error instanceof Error ? error.message : 'Unable to load this source PDF.'); }
    };
    void draw();
    return () => { cancelled = true; task?.destroy(); };
  }, [evidence]);
  return <div className="pdf-viewer"><canvas ref={canvasRef} aria-label={`Source document page ${evidence.page}`} />{message && <p>{message}</p>}</div>;
}

export function EvidenceDrawer({ evidence, onClose, onNavigate }: { evidence: EvidenceSpan | null; onClose: () => void; onNavigate?: (direction: number) => void }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  useEffect(() => { if (!evidence) return; const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); }; window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey); }, [evidence, onClose]);
  if (!evidence) return null;
  const copy = async () => { await navigator.clipboard?.writeText(evidence.sha256); setCopied(true); window.setTimeout(() => setCopied(false), 1600); };
  return <div className="drawer-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <aside className="source-drawer" role="dialog" aria-modal="true" aria-labelledby="source-title">
      <header className="drawer-header"><div><span className="eyebrow">{t('evidence')}</span><h2 id="source-title">{evidence.doc_title}</h2></div><button className="icon-button" aria-label={t('close')} onClick={onClose}>×</button></header>
      <div className="drawer-meta"><b>{evidence.citation_label}</b><span>{evidence.jurisdiction} · {t('page')} {evidence.page}</span><span>{t('effective')}: {evidence.effective_from}{evidence.effective_to ? ` — ${evidence.effective_to}` : ''}</span><span>{t('version')}: {evidence.corpus_version}</span><span>{t('hash')}: <code>{evidence.sha256}</code> <button className="text-button" onClick={() => void copy()}>{copied ? 'Copied' : t('copyHash')}</button></span></div>
      {evidence.highlights.length > 0 && <PdfPane evidence={evidence} />}
      <EvidenceQuote evidence={evidence} />
      <footer className="drawer-footer">{onNavigate && <div className="row"><button className="button button-secondary" onClick={() => onNavigate(-1)}>← Previous</button><button className="button button-secondary" onClick={() => onNavigate(1)}>Next →</button></div>}<a className="button button-primary" href={evidence.source_url} target="_blank" rel="noreferrer">{t('openSource')} ↗</a></footer>
    </aside>
  </div>;
}

export function LoadingBlock({ label }: { label?: string }) { const { t } = useTranslation(); return <div className="loading-block" role="status"><span className="spinner" />{label ?? t('loading')}</div>; }
