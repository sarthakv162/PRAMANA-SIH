import { useEffect, useRef, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { useAppStore } from '../state/store';
import { localISODate } from '../lib/date';
import type { Language, Persona, UiLanguage } from '../api/types';

const navGroups = [
  { label: 'navGroupSahayak', links: [['/', 'navAsk', '⌕'], ['/classify', 'navClassify', '◈']] },
  { label: 'navGroupProtection', links: [['/patent-risk', 'navIp', '◇'], ['/abs', 'navAbs', '▤'], ['/tk', 'navTkdl', '◉']] },
  { label: 'navGroupEvidence', links: [['/case', 'navCases', '▱'], ['/corpus', 'navEvidence', '▥'], ['/eval', 'navEvaluation', '▧']] },
] as const;
const languages: { key: UiLanguage; label: string }[] = [{ key: 'en', label: 'English' }, { key: 'hi', label: 'हिन्दी' }, { key: 'ta', label: 'தமிழ்' }, { key: 'bn', label: 'বাংলা' }, { key: 'mr', label: 'मराठी' }];
const themeLabels: Record<UiLanguage, { group: string; light: string; dark: string }> = {
  en: { group: 'Color theme', light: 'Light mode', dark: 'Dark mode' }, hi: { group: 'रंग थीम', light: 'लाइट मोड', dark: 'डार्क मोड' },
  ta: { group: 'வண்ணத் தோற்றம்', light: 'ஒளி பயன்முறை', dark: 'இருள் பயன்முறை' }, bn: { group: 'রঙের থিম', light: 'লাইট মোড', dark: 'ডার্ক মোড' }, mr: { group: 'रंग थीम', light: 'लाईट मोड', dark: 'डार्क मोड' },
};
const personas: { key: Persona; label: string }[] = [{ key: 'vaidya', label: 'vaidya' }, { key: 'startup', label: 'startup' }, { key: 'attorney', label: 'attorney' }, { key: 'licensing_officer', label: 'licensingOfficer' }, { key: 'researcher', label: 'researcher' }];

function GlobalControls() {
  const { t, i18n } = useTranslation();
  const { jurisdiction, setJurisdiction, asOf, setAsOf, language, setLanguage, uiLanguage, setUiLanguage, persona, setPersona } = useAppStore();
  const [showVersions, setShowVersions] = useState(false);
  const versions = useQuery({ queryKey: ['versions'], queryFn: api.versions });
  const selected = languages.find((item) => item.key === uiLanguage)?.key ?? 'en';
  const updateLanguage = (value: UiLanguage) => { setUiLanguage(value); void i18n.changeLanguage(value); document.documentElement.lang = value; };
  return <div className="global-controls">
    <div className="scope-control"><span className="scope-label">{t('scopeLabel')}</span><div className="control-group jurisdiction-control" aria-label={t('jurisdiction')}>
      {(['IN', 'INTL', 'BOTH'] as const).map((value) => <button key={value} className={jurisdiction === value ? 'selected' : ''} onClick={() => setJurisdiction(value)} aria-pressed={jurisdiction === value}>{value === 'IN' ? t('india') : value === 'INTL' ? t('international') : t('sideBySide')}</button>)}
    </div></div>
    <label className="compact-control date-control"><span>{t('asOf')}</span><input aria-label={t('asOf')} type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} /></label>
    <label className="compact-control"><span>{t('language')}</span><select aria-label={t('language')} value={language} onChange={(event) => setLanguage(event.target.value as Language)}><option value="auto">Auto</option>{['en', 'hi', 'ta', 'bn', 'mr', 'te', 'gu', 'kn', 'ml', 'pa', 'or'].map((code) => <option key={code} value={code}>{code.toUpperCase()}</option>)}</select></label>
    <label className="compact-control persona-control"><span>{t('persona')}</span><select aria-label={t('persona')} value={persona} onChange={(event) => setPersona(event.target.value as Persona)}>{personas.map((item) => <option key={item.key} value={item.key}>{t(item.label)}</option>)}</select></label>
    <label className="compact-control ui-language-control"><span>{t('uiLanguage')}</span><select aria-label={t('uiLanguage')} value={selected} onChange={(event) => updateLanguage(event.target.value as UiLanguage)}>{languages.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
    <div className="version-control"><button className="version-chip" onClick={() => setShowVersions((value) => !value)} aria-expanded={showVersions}>● {versions.data?.find((item) => item.status === 'live')?.label ?? 'Corpus …'}⌄</button>{showVersions && <div className="version-popover"><b>{t('versions')}</b>{versions.isLoading ? <small>{t('loading')}</small> : versions.data?.length ? versions.data.map((item) => <div className="version-line" key={item.label}><span>{item.label}</span><small>{item.status}</small></div>) : <small>{versions.error instanceof Error ? versions.error.message : t('empty')}</small>}</div>}</div>
  </div>;
}

export function AppShell() {
  const { t } = useTranslation();
  const { asOf, refreshAsOf, theme, setTheme, uiLanguage } = useAppStore();
  const today = localISODate();
  const health = useQuery({ queryKey: ['health'], queryFn: api.health });
  const isMock = health.data?.mock_mode ?? true;
  const [online, setOnline] = useState(() => navigator.onLine);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [sidebarHidden, setSidebarHidden] = useState(false);
  const [isMobile, setIsMobile] = useState(() => typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 640px)').matches);
  const topbarRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    // A cached browser page can reopen without reloading or rehydrating the store.
    const onPageShow = (event: PageTransitionEvent) => refreshAsOf(event.persisted);
    const onFocus = () => refreshAsOf();
    const onVisibility = () => { if (document.visibilityState === 'visible') refreshAsOf(); };
    window.addEventListener('pageshow', onPageShow);
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onVisibility);
    const interval = window.setInterval(onFocus, 60_000);
    return () => {
      window.removeEventListener('pageshow', onPageShow);
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onVisibility);
      window.clearInterval(interval);
    };
  }, [refreshAsOf]);
  useEffect(() => { const onOnline = () => setOnline(true); const onOffline = () => setOnline(false); window.addEventListener('online', onOnline); window.addEventListener('offline', onOffline); return () => { window.removeEventListener('online', onOnline); window.removeEventListener('offline', onOffline); }; }, []);
  useEffect(() => {
    const media = window.matchMedia('(max-width: 640px)');
    const onChange = () => { setIsMobile(media.matches); setMobileOpen(false); };
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, []);
  useEffect(() => {
    const header = topbarRef.current;
    if (!header) return;
    const updateHeaderHeight = () => document.documentElement.style.setProperty('--app-topbar-height', `${header.getBoundingClientRect().height}px`);
    updateHeaderHeight();
    const observer = new ResizeObserver(updateHeaderHeight);
    observer.observe(header);
    return () => { observer.disconnect(); document.documentElement.style.removeProperty('--app-topbar-height'); };
  }, []);
  useEffect(() => {
    if (!mobileOpen) return;
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') setMobileOpen(false); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [mobileOpen]);
  useEffect(() => { document.documentElement.dataset.theme = theme; document.documentElement.style.colorScheme = theme; }, [theme]);
  const labels = themeLabels[uiLanguage];
  return <div className="app-shell">
    <div className="corner-ambients" aria-hidden="true"><div className="corner-orb corner-orb-upper"><span /><i /></div><div className="corner-orb corner-orb-lower"><span /><i /></div></div>
    <header className="topbar" ref={topbarRef}>
      <NavLink to="/" className="brand" aria-label="IP-SAKTI Sahayak home"><span className="brand-mark">P</span><span><strong>IP-SAKTI</strong><small>{t('brandTagline')}</small></span></NavLink>
      <button className="sidebar-toggle" type="button" aria-label={sidebarHidden ? t('showSidebar') : t('hideSidebar')} title={sidebarHidden ? t('showSidebar') : t('hideSidebar')} aria-controls="primary-sidebar" aria-expanded={!sidebarHidden} onClick={() => setSidebarHidden((hidden) => !hidden)}><span aria-hidden="true">{sidebarHidden ? '☰' : '‹'}</span></button>
      <GlobalControls />
      <div className="theme-control" role="group" aria-label={labels.group}><button type="button" className={theme === 'light' ? 'selected' : ''} aria-label={labels.light} aria-pressed={theme === 'light'} title={labels.light} onClick={() => setTheme('light')}><span aria-hidden="true">☼</span></button><button type="button" className={theme === 'dark' ? 'selected' : ''} aria-label={labels.dark} aria-pressed={theme === 'dark'} title={labels.dark} onClick={() => setTheme('dark')}><span aria-hidden="true">◐</span></button></div>
      <span className={`mode-chip ${isMock ? 'mode-mock' : 'mode-live'}`}>{isMock ? t('mock') : t('live')}</span>
      <button className="mobile-menu" type="button" aria-label={mobileOpen ? t('hideSidebar') : t('showSidebar')} title={mobileOpen ? t('hideSidebar') : t('showSidebar')} aria-controls="primary-sidebar" aria-expanded={mobileOpen} onClick={() => setMobileOpen((value) => !value)}><span aria-hidden="true">{mobileOpen ? '×' : '☰'}</span></button>
    </header>
    {isMobile && mobileOpen && <button className="nav-scrim" aria-label={t('hideSidebar')} onClick={() => setMobileOpen(false)} />}
    <div className="below-topbar">{asOf !== today && <div className="asof-banner">◷ {t('lawAsOf')} {new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(`${asOf}T00:00:00`))}</div>}{!online && <div className="offline-banner">◌ {t('offline')}</div>}</div>
    <div className="app-body"><aside id="primary-sidebar" className={`sidebar ${!isMobile && sidebarHidden ? 'sidebar-collapsed' : ''} ${isMobile && mobileOpen ? 'mobile-visible' : ''}`} aria-label="Primary navigation" aria-hidden={isMobile ? !mobileOpen : sidebarHidden} inert={isMobile ? !mobileOpen : sidebarHidden}>{navGroups.map((group) => <section className="nav-section" key={group.label}><div className="nav-label">{t(group.label)}</div>{group.links.map(([to, key, icon]) => <NavLink key={to} to={to} end={to === '/'} onClick={() => setMobileOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><span aria-hidden="true">{icon}</span>{t(key)}</NavLink>)}</section>)}</aside><main className="main-content"><Outlet /></main></div>
  </div>;
}
