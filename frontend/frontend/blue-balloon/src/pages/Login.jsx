import React, {useState} from 'react';
import {Button, Input} from '../editor/ui';
import {read, write} from '../services/storage';
import {request} from '../services/api';
import {backendEnabled} from '../services/projects';

// Sign-in. With the backend enabled (VITE_API_URL set) this POSTs the shared
// password to /api/login, which sets an httponly session cookie — nothing is
// stored client-side. Without a backend it falls back to the original
// local-first behaviour: capture a name/email into the local profile.
export default function Login() {
  const existing = read('bb_profile', {});
  const [email, setEmail] = useState(existing.email || '');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async e => {
    e.preventDefault();
    if (backendEnabled) {
      if (!password) {setError('Enter the password to continue.'); return;}
      setBusy(true); setError('');
      try {
        await request('/login', {method: 'POST', body: {password}});
        // Remember the email for display only; the session lives in the cookie.
        if (email.trim()) write('bb_profile', {...existing, email: email.trim()});
        location.assign('/home');
      } catch {
        setError('That password was not accepted. Please try again.');
        setBusy(false);
      }
      return;
    }
    // Local-first fallback (no backend configured).
    if (!email.trim()) {setError('Enter your email to continue.'); return;}
    setBusy(true); setError('');
    try {
      const name = existing.name || email.split('@')[0].replace(/[._-]+/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      write('bb_profile', {...existing, email: email.trim(), name});
      location.assign('/home');
    } catch {
      setError('Could not sign in on this device. Free up browser storage and try again.');
      setBusy(false);
    }
  };

  return <div className="auth-page"><form className="auth-card" onSubmit={submit}>
    <span className="auth-brand"><span className="bb-mark" aria-hidden="true"/>Blue Balloon</span>
    <h1>Log in</h1>
    <p className="auth-sub">Enter your email and password to continue.</p>
    <div className="auth-field">
      <label htmlFor="login-email">Email</label>
      <Input id="login-email" type="email" autoFocus placeholder="m@example.com" value={email} onChange={e => setEmail(e.target.value)}/>
    </div>
    <div className="auth-field">
      <div className="auth-field-row">
        <label htmlFor="login-password">Password</label>
        <button type="button" className="auth-link" onClick={() => setError(backendEnabled ? 'Ask your workspace admin for the shared password.' : 'Passwords aren’t used on this local workspace — just continue.')}>Forgot password?</button>
      </div>
      <Input id="login-password" type="password" value={password} onChange={e => setPassword(e.target.value)}/>
    </div>
    {error && <p className="auth-error" role="alert">{error}</p>}
    <Button type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Log in'}</Button>
    <p className="auth-alt">{backendEnabled ? 'Your session is kept for this browser.' : 'This workspace is saved on this device.'}</p>
  </form></div>;
}
