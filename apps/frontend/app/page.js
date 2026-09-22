'use client';
import { useState } from 'react';
export default function Home() {
  const [status, setStatus] = useState('Not checked');
  const [busy, setBusy] = useState(false);
  async function check() {
    setBusy(true);
    try {
      const response = await fetch('/api/ready', {cache:'no-store', signal:AbortSignal.timeout(10000)});
      const data = await response.json();
      setStatus(response.ok ? `API ready · PostgreSQL ${data.database}` : 'Database unavailable — check backend logs');
    } catch { setStatus('API unreachable — check routing and service health'); }
    finally { setBusy(false); }
  }
  return <main style={{maxWidth:720,margin:'12vh auto',padding:32}}>
    <p style={{color:'#57dac5',letterSpacing:3}}>CODITUDE / DEVOPS ASSESSMENT</p>
    <h1 style={{fontSize:44}}>Deployment check</h1>
    <p style={{lineHeight:1.8,color:'#b9c7d9'}}>Next.js frontend → Python API → PostgreSQL. Use the check below to verify end-to-end connectivity.</p>
    <button disabled={busy} onClick={check} style={{padding:'14px 24px',border:0,borderRadius:8,fontSize:16,background:'#57dac5',cursor:'pointer'}}>{busy?'Checking…':'Check API and database'}</button>
    <p role="status" aria-live="polite" style={{padding:24,background:'#18283e',borderRadius:8}}>{status}</p>
    <p style={{fontSize:13,color:'#96a6ba'}}>Demonstration application. No business or personal data is collected.</p>
  </main>;
}
