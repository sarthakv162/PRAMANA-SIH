import { useState } from 'react';
import { isPublicDemo, setWorkspaceKey, workspaceKey } from '../api/client';

export function WorkspaceAccess({ onConnect }: { onConnect?: () => void }) {
  const [key, setKey] = useState(workspaceKey);
  if (isPublicDemo()) return <p className="small-muted">Public demo: everyone shares saved history and case files. Content expires after 30 days.</p>;
  return <form className="workspace-access" onSubmit={(event) => { event.preventDefault(); setWorkspaceKey(key.trim()); onConnect?.(); }}>
    <label>Demo workspace key<input type="password" value={key} onChange={(event) => setKey(event.target.value)} autoComplete="off" placeholder="Enter the shared demo key" /></label>
    <button className="button button-secondary" type="submit">Connect history</button>
    <small>All users with this key share saved history. Content expires after 30 days.</small>
  </form>;
}
