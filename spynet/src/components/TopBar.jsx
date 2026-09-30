import React from 'react';

export default function TopBar({ scanner, settings, connected, now, actions, onOpenSettings }) {
  const state = scanner ? scanner.state : 'stopped';
  const hasNetwork = settings && settings.network;
  return (
    <header className="topbar">
      <div className="brand">
        <SweepRing scanner={scanner} now={now} />
        <div className="brand-text">
          <h1>Spynet</h1>
          <StatusLine scanner={scanner} connected={connected} />
        </div>
      </div>

      <div className="controls">
        {state === 'stopped' && (
          <button className="btn primary" onClick={() => actions.start()} disabled={!hasNetwork} title={hasNetwork ? '' : 'Choose a network first'}>
            <span className="full">Start watching</span><span className="short">Start</span>
          </button>
        )}
        {state === 'running' && <button className="btn" onClick={actions.pause}>Pause</button>}
        {state === 'paused' && <button className="btn primary" onClick={actions.resume}>Resume</button>}
        {state !== 'stopped' && <button className="btn quiet" onClick={actions.stop}>Stop</button>}
        <button className="btn" onClick={actions.sweep} disabled={!hasNetwork || (scanner && scanner.sweeping)}>
          <span className="full">Sweep now</span><span className="short">Sweep</span>
        </button>
        <button className="btn icon" onClick={onOpenSettings} aria-label="Settings" title="Settings">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
          </svg>
        </button>
      </div>
    </header>
  );
}

function StatusLine({ scanner, connected }) {
  if (!connected) return <p className="status warn">Reconnecting to the server…</p>;
  if (!scanner) return <p className="status">Loading…</p>;
  if (scanner.last_error) return <p className="status error">{scanner.last_error}</p>;
  const warned = Object.keys(scanner.network_warnings || {});
  const nets = scanner.networks && scanner.networks.length ? scanner.networks : [scanner.network].filter(Boolean);
  const netLabel = nets.length <= 2 ? nets.join(', ') : `${nets[0]} +${nets.length - 1}`;
  if (scanner.state === 'stopped') {
    return <p className="status">{nets.length ? `Not watching ${netLabel}` : 'No network chosen yet'}</p>;
  }
  const found = scanner.sweep_count ? `${scanner.last_sweep_found} answered last sweep` : 'first sweep pending';
  return (
    <p className="status">
      {scanner.state === 'paused' ? 'Paused on ' : 'Watching '}
      <span className="mono">{netLabel}</span>
      {' · '}{found}
      {warned.length > 0 && <span className="warn"> · no interface on {warned.join(', ')}</span>}
      {scanner.port_queue > 0 && ` · ${scanner.port_queue} port scan${scanner.port_queue === 1 ? '' : 's'} queued`}
    </p>
  );
}

/* The sweep ring: fills up between sweeps, spins while a sweep is running. */
function SweepRing({ scanner, now }) {
  const r = 17;
  const c = 2 * Math.PI * r;
  let progress = 0;
  let label = '—';
  let cls = 'ring';
  if (scanner) {
    if (scanner.sweeping) { cls += ' sweeping'; label = '···'; progress = 1; }
    else if (scanner.state === 'running' && scanner.next_sweep_in != null) {
      const lastAt = scanner.last_sweep_at ? Date.parse(scanner.last_sweep_at) : now;
      const elapsed = Math.max(0, (now - lastAt) / 1000);
      const total = scanner.sweep_interval || 30;
      const remaining = Math.max(0, Math.round(total - elapsed));
      progress = Math.min(1, elapsed / total);
      label = `${remaining}`;
      cls += ' running';
    } else if (scanner.state === 'paused') { label = '❚❚'; cls += ' paused'; }
    else { label = '○'; }
  }
  return (
    <div className={cls} title="Seconds until the next sweep">
      <svg viewBox="0 0 40 40" width="44" height="44" aria-hidden>
        <circle cx="20" cy="20" r={r} className="ring-track" />
        <circle cx="20" cy="20" r={r} className="ring-fill" strokeDasharray={c} strokeDashoffset={c * (1 - progress)} />
      </svg>
      <span className="ring-label">{label}</span>
    </div>
  );
}
