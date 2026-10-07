import React, {useState} from 'react';
import SiteHeader from '../components/SiteHeader';
import {Icon} from '../editor/icons';
import {Button, Input, Dialog, DialogHeader, DialogTitle, DialogDescription, DialogFooter} from '../editor/ui';
import {read, write} from '../services/storage';

const DEFAULT_USER = {
  name: 'Amara Bello', username: 'amarabello', email: 'amara@blueballoon.studio',
  phone: '+1 (415) 555-0134',
  bio: 'Children’s book author & illustrator. Building gentle bedtime stories with a small, mighty team at Blue Balloon.',
};
const NAV = [
  {id: 'personal', label: 'Personal', icon: 'user'},
  {id: 'security', label: 'Security', icon: 'lock'},
  {id: 'connected', label: 'Connected', icon: 'command'},
  {id: 'data', label: 'Data', icon: 'download'},
];
const CONNECTIONS = [
  {key: 'google', name: 'Google', icon: 'mail'},
  {key: 'github', name: 'GitHub', icon: 'github'},
  {key: 'apple', name: 'Apple', icon: 'command'},
  {key: 'microsoft', name: 'Microsoft', icon: 'package'},
];

function Switch({checked, onChange, label}) {
  return <span className="switch"><input type="checkbox" role="switch" aria-label={label} checked={checked} onChange={onChange}/><span className="track" aria-hidden="true"/><span className="thumb" aria-hidden="true"/></span>;
}

function EditProfileDialog({user, onClose, onSave}) {
  const [f, setF] = useState(user);
  const up = k => e => setF(s => ({...s, [k]: e.target.value}));
  return <Dialog open onOpenChange={v => !v && onClose()} label="Edit profile">
    <DialogHeader><DialogTitle>Edit profile</DialogTitle><DialogDescription>Make changes to your profile here. Save when you’re done.</DialogDescription></DialogHeader>
    <div className="dlg-grid">
      <div className="dlg-field"><label htmlFor="ep-name">Full name</label><Input id="ep-name" value={f.name} onChange={up('name')} autoFocus/></div>
      <div className="dlg-field"><label htmlFor="ep-user">Username</label><Input id="ep-user" value={f.username} onChange={up('username')}/></div>
    </div>
    <div className="dlg-grid">
      <div className="dlg-field"><label htmlFor="ep-email">Email</label><Input id="ep-email" type="email" value={f.email} onChange={up('email')}/></div>
      <div className="dlg-field"><label htmlFor="ep-phone">Phone (optional)</label><Input id="ep-phone" value={f.phone} onChange={up('phone')}/></div>
    </div>
    <div className="dlg-field"><label htmlFor="ep-bio">Bio</label><textarea id="ep-bio" className="ui-textarea" rows={3} value={f.bio} onChange={up('bio')}/></div>
    <DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={() => onSave(f)}>Save changes</Button></DialogFooter>
  </Dialog>;
}

function DeleteAccountDialog({user, onClose, onConfirm}) {
  const [txt, setTxt] = useState('');
  const ok = txt.trim() === user.username;
  return <Dialog open onOpenChange={v => !v && onClose()} label="Delete account">
    <DialogHeader><DialogTitle>Delete account</DialogTitle><DialogDescription>This permanently deletes your account, workspaces, and all books you own. This cannot be undone.</DialogDescription></DialogHeader>
    <div className="dlg-field"><label htmlFor="del-confirm">Type <span className="code-pill">{user.username}</span> to confirm</label><Input id="del-confirm" value={txt} onChange={e => setTxt(e.target.value)} placeholder={user.username} autoFocus/></div>
    <DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button variant="destructive" disabled={!ok} onClick={onConfirm}>Delete account</Button></DialogFooter>
  </Dialog>;
}

export default function Profile() {
  const [user, setUser] = useState(() => ({...DEFAULT_USER, ...read('bb_profile', {})}));
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [twoFA, setTwoFA] = useState(() => read('bb_profile', {}).twoFA ?? true);
  const [conns, setConns] = useState(() => read('bb_connections', {google: true, github: true, apple: false, microsoft: false}));
  const [toast, setToast] = useState('');
  const flash = m => {setToast(m); setTimeout(() => setToast(''), 2000);};
  const initials = (user.name || '?').split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase();

  const saveProfile = f => {setUser(f); try {write('bb_profile', {...f, twoFA});} catch { /* surfaced globally */ } setEditing(false); flash('Profile updated');};
  const toggle2FA = e => {const v = e.target.checked; setTwoFA(v); try {write('bb_profile', {...user, twoFA: v});} catch { /* noop */ } flash(v ? 'Two-factor enabled' : 'Two-factor disabled');};
  const toggleConn = c => {setConns(s => {const next = {...s, [c.key]: !s[c.key]}; try {write('bb_connections', next);} catch { /* noop */ } flash(`${c.name} ${next[c.key] ? 'connected' : 'disconnected'}`); return next;});};
  const deleteAccount = () => {try {write('bb_profile', {}); write('bb_connections', {});} catch { /* noop */ } setDeleting(false); flash('Account scheduled for deletion'); setTimeout(() => location.assign('/login'), 900);};

  return <div className="site-page"><SiteHeader/>
    <div className="settings-shell">
      <nav className="side-nav" aria-label="Account sections">
        <h2>Account</h2><p className="navsub">Profile, security, and connections.</p>
        {NAV.map(n => <a key={n.id} className="nav-item" href={`#${n.id}`}><Icon name={n.icon}/>{n.label}</a>)}
        <div className="nav-sep"/>
        <a className="nav-item danger" href="#danger"><Icon name="circle-alert"/>Danger zone</a>
      </nav>
      <main className="settings-content">
        <div className="page-head"><h1>Account</h1><p>Manage your profile, security, and connected services.</p></div>

        <section id="personal">
          <div className="profile-hero">
            <div className="avatar" aria-hidden="true">{initials}</div>
            <div className="who"><h2>{user.name}</h2><p>{user.email}</p><span className="handle">@{user.username}</span></div>
            <div style={{marginLeft: 'auto'}}><Button variant="outline" onClick={() => setEditing(true)}>Edit profile</Button></div>
          </div>
          <p className="desc" style={{maxWidth: '60ch', color: 'var(--muted-foreground)'}}>{user.bio}</p>
        </section>

        <section id="security" className="grp">
          <p className="grp-title">Security</p>
          <div className="setting-row"><div className="row-info"><p className="lbl">Two-factor authentication</p><p className="desc">Require a second step when signing in on a new device.</p></div><div className="row-ctl"><Switch checked={twoFA} onChange={toggle2FA} label="Two-factor authentication"/></div></div>
          <div className="setting-row"><div className="row-info"><p className="lbl">Password</p><p className="desc">Not used on this local workspace.</p></div><div className="row-ctl"><Button variant="outline" onClick={() => flash('Local workspace — no password to change')}>Change</Button></div></div>
        </section>

        <section id="connected" className="grp">
          <p className="grp-title">Connected accounts</p>
          {CONNECTIONS.map(c => {const on = !!conns[c.key]; return <div className="conn-row" key={c.key}>
            <span className="ci"><Icon name={c.icon} size={18}/></span>
            <div className="cm"><div className="t">{c.name}</div><div className="d">{on ? `Connected as ${user.username}` : 'Not connected'}</div></div>
            <span className={`badge${on ? ' on' : ''}`}>{on ? 'Connected' : 'Not connected'}</span>
            <Button variant="outline" size="sm" onClick={() => toggleConn(c)}>{on ? 'Disconnect' : 'Connect'}</Button>
          </div>;})}
        </section>

        <section id="data" className="grp">
          <p className="grp-title">Data</p>
          <div className="setting-row"><div className="row-info"><p className="lbl">Export your books</p><p className="desc">Download a copy of everything stored on this device.</p></div><div className="row-ctl"><Button variant="outline" onClick={() => location.assign('/home')}>Go to library</Button></div></div>
        </section>

        <section id="danger">
          <div className="danger-card">
            <h3>Delete account</h3>
            <p>Permanently remove your profile, connections, and local data. This cannot be undone.</p>
            <Button variant="destructive" onClick={() => setDeleting(true)}>Delete account</Button>
          </div>
        </section>

        {toast && <div className="save-bar" role="status"><Icon name="circle-check" size={15}/>{toast}</div>}
      </main>
    </div>
    {editing && <EditProfileDialog user={user} onClose={() => setEditing(false)} onSave={saveProfile}/>}
    {deleting && <DeleteAccountDialog user={user} onClose={() => setDeleting(false)} onConfirm={deleteAccount}/>}
  </div>;
}
