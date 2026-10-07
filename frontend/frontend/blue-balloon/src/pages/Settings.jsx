import React, {useState} from 'react';
import SiteHeader from '../components/SiteHeader';
import {Icon} from '../editor/icons';
import {Button, Select} from '../editor/ui';
import {read, write} from '../services/storage';

const DEFAULTS = {
  language: 'English (US)', timezone: '(GMT-08:00) Pacific Time', dateFormat: 'MMM D, YYYY',
  autoSave: true, startupPage: 'Home Dashboard', defaultView: 'Grid',
  sortOrder: 'Recently Edited', projectStatus: 'Draft', bookSize: 'Square (8×8 in)',
  canvasSize: '1080 × 1080 px', versionHistory: true,
  sharingPerm: 'Can View', allowInvites: true, commentPerm: 'Everyone',
};
const CATS = [
  {id: 'general', label: 'General', icon: 'settings'},
  {id: 'projects', label: 'Projects', icon: 'folder'},
  {id: 'collaboration', label: 'Collaboration', icon: 'users'},
  {id: 'about', label: 'About', icon: 'file-text'},
];

function Switch({checked, onChange, label}) {
  return <span className="switch"><input type="checkbox" role="switch" aria-label={label} checked={checked} onChange={onChange}/><span className="track" aria-hidden="true"/><span className="thumb" aria-hidden="true"/></span>;
}
function Row({label, desc, children}) {
  return <div className="setting-row"><div className="row-info"><p className="lbl">{label}</p>{desc && <p className="desc">{desc}</p>}</div><div className="row-ctl">{children}</div></div>;
}
function Group({title, children}) {
  return <div className="grp">{title && <p className="grp-title">{title}</p>}{children}</div>;
}

export default function Settings() {
  const [s, setS] = useState(() => ({...DEFAULTS, ...read('bb_settings_v1', {})}));
  const [saved, setSaved] = useState('');
  const [cat, setCat] = useState(() => {
    const h = decodeURIComponent(location.hash.slice(1));
    return CATS.some(c => c.id === h) ? h : 'general';
  });
  const set = (k, v) => setS(prev => {
    const next = {...prev, [k]: v};
    try {write('bb_settings_v1', next); setSaved('Saved'); setTimeout(() => setSaved(''), 1600);} catch { setSaved('Not saved'); }
    return next;
  });
  const go = id => {setCat(id); history.replaceState(null, '', `#${id}`); window.scrollTo(0, 0);};
  const reset = () => {setS({...DEFAULTS}); try {write('bb_settings_v1', {...DEFAULTS});} catch { /* surfaced globally */ } setSaved('Reset to defaults'); setTimeout(() => setSaved(''), 1600);};

  const sel = (k, options) => <Select value={s[k]} onChange={e => set(k, e.target.value)} options={options}/>;
  const sw = (k, label) => <Switch checked={s[k]} onChange={e => set(k, e.target.checked)} label={label}/>;

  return <div className="site-page"><SiteHeader/>
    <div className="settings-shell">
      <nav className="side-nav" aria-label="Settings sections">
        <h2>Settings</h2><p className="navsub">Manage how BB artists works for you.</p>
        {CATS.map(c => <button key={c.id} className={`nav-item${cat === c.id ? ' active' : ''}`} onClick={() => go(c.id)}><Icon name={c.icon}/>{c.label}</button>)}
        <div className="nav-sep"/>
        <button className="nav-item danger" onClick={reset}><Icon name="loader"/>Reset defaults</button>
      </nav>
      <main className="settings-content">
        <div className="page-head"><h1>{CATS.find(c => c.id === cat).label}</h1><p>Preferences are saved on this device.</p></div>

        {cat === 'general' && <>
          <Group title="Localization">
            <Row label="Language" desc="The language used across menus, buttons, and dialogs.">{sel('language', ['English (US)', 'English (UK)', 'Español', 'Français', 'Deutsch', '日本語', 'Português (BR)'])}</Row>
            <Row label="Time Zone" desc="Timestamps on projects and activity use this zone.">{sel('timezone', ['(GMT-08:00) Pacific Time', '(GMT-05:00) Eastern Time', '(GMT+00:00) London', '(GMT+01:00) Berlin', '(GMT+05:30) India', '(GMT+09:00) Tokyo'])}</Row>
            <Row label="Date Format" desc="How dates appear throughout the app.">{sel('dateFormat', ['MMM D, YYYY', 'MM/DD/YYYY', 'DD/MM/YYYY', 'YYYY-MM-DD'])}</Row>
          </Group>
          <Group title="Behavior">
            <Row label="Auto Save" desc="Automatically save changes to your storybooks as you work.">{sw('autoSave', 'Auto save')}</Row>
            <Row label="Startup Page" desc="The screen shown when you open BB artists.">{sel('startupPage', ['Home Dashboard', 'Last Opened Project', 'New Project', 'Templates'])}</Row>
            <Row label="Default Project View" desc="How projects are laid out on the home dashboard.">{sel('defaultView', ['Grid', 'List', 'Compact'])}</Row>
          </Group>
        </>}

        {cat === 'projects' && <>
          <Group title="Defaults">
            <Row label="Default Sort Order" desc="How projects are ordered on the dashboard.">{sel('sortOrder', ['Recently Edited', 'Newest Created', 'Alphabetical (A–Z)', 'Most Pages', 'Status'])}</Row>
            <Row label="Default Project Status" desc="Status assigned to newly created storybooks.">{sel('projectStatus', ['Draft', 'In Progress', 'Complete'])}</Row>
            <Row label="Default Book Size" desc="Trim size applied to new storybooks.">{sel('bookSize', ['Square (8×8 in)', 'Portrait (8×10 in)', 'Landscape (10×8 in)', 'A4 Portrait', 'Custom'])}</Row>
            <Row label="Default Canvas Size" desc="Pixel dimensions for new page canvases.">{sel('canvasSize', ['1080 × 1080 px', '1200 × 1500 px', '1500 × 1200 px', '2048 × 2048 px'])}</Row>
          </Group>
          <Group title="Lifecycle">
            <Row label="Version History" desc="Keep a timeline of saved versions for every project.">{sw('versionHistory', 'Version history')}</Row>
          </Group>
        </>}

        {cat === 'collaboration' && <Group title="Sharing">
          <Row label="Default Sharing Permission" desc="Access level granted when you share a new project.">{sel('sharingPerm', ['Can View', 'Can Comment', 'Can Edit'])}</Row>
          <Row label="Allow Team Invitations" desc="Let collaborators invite additional people to your projects.">{sw('allowInvites', 'Allow invitations')}</Row>
          <Row label="Comment Permissions" desc="Who is allowed to leave comments on your projects.">{sel('commentPerm', ['Everyone', 'Collaborators only', 'No one'])}</Row>
        </Group>}

        {cat === 'about' && <Group title="Application">
          <Row label="App Version" desc="You are running the latest version."><span>v3.8.2 (build 2481)</span></Row>
          <Row label="Release Notes" desc="See what's new in this release."><a href="#about">View notes</a></Row>
          <Row label="Privacy Policy" desc="How we handle your data."><a href="#about">Read policy</a></Row>
          <Row label="Terms of Service" desc="The terms you agree to by using BB artists."><a href="#about">Read terms</a></Row>
        </Group>}

        <div className="save-bar">{saved ? <><Icon name="circle-check" size={15}/>{saved}</> : <span>Changes save automatically.</span>}</div>
      </main>
    </div>
  </div>;
}
