import { useState } from 'react';
import { Icon } from './components';

export interface Profile { name: string; email: string }
const storageKey = 'cloudpilot.demo-profile';

export function readProfile(): Profile | null {
  try {
    const value = JSON.parse(localStorage.getItem(storageKey) ?? 'null') as Profile | null;
    return value && typeof value.name === 'string' && typeof value.email === 'string' ? value : null;
  } catch { return null; }
}

export function saveProfile(profile: Profile | null) {
  try {
    if (profile) localStorage.setItem(storageKey, JSON.stringify(profile));
    else localStorage.removeItem(storageKey);
  } catch { /* The current profile still works when browser storage is unavailable. */ }
}

export function Login({ onLogin }: { onLogin: (profile: Profile) => void }) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  return <div className="login-page"><div className="login-brand"><span className="brand-mark"><Icon name="cloud" size={25}/></span>CloudPilot</div><section className="login-card"><div className="login-icon"><Icon name="user" size={26}/></div><h1>Welcome to CloudPilot</h1><p>Your cloud expenses, resources and recommendations in one place.</p><form onSubmit={event => { event.preventDefault(); if (name.trim()) onLogin({ name: name.trim(), email: email.trim() }); }}><label>Your name<input required autoComplete="name" maxLength={80} placeholder="Alex Morgan" value={name} onChange={event => setName(event.target.value)}/></label><label>Email<input required type="email" autoComplete="email" maxLength={200} placeholder="alex@company.com" value={email} onChange={event => setEmail(event.target.value)}/></label><label>Organization<select aria-label="Choose organization"><option>CloudPilot demo</option></select></label><button className="primary-button" type="submit">Continue to workspace<Icon name="arrow" size={17}/></button></form><div className="login-or"><span/>or<span/></div><button className="secondary-button" onClick={() => onLogin({ name: 'Demo user', email: 'demo@cloudpilot.local' })}>Use demo profile</button><p className="login-note"><Icon name="info" size={15}/>Local demo profile. Details stay in this browser; no password or account is created.</p></section><p className="login-footer">Cloud cost visibility · Built for informed decisions</p></div>;
}
