import React, {Suspense, lazy, useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ErrorBoundary} from './components/ErrorBoundary';
import {storage} from './services/storage';
import './styles/reference.css';
import './styles/app.css';
import './styles/pages.css';
import './styles/landing.css';
const Landing = lazy(() => import('./pages/Landing'));
const Workspace = lazy(() => import('./editor/workspace'));
const Home = lazy(() => import('./pages/Home'));
const NewProject = lazy(() => import('./pages/NewProject'));
const CharacterDesign = lazy(() => import('./pages/CharacterDesign'));
const Login = lazy(() => import('./pages/Login'));
const Settings = lazy(() => import('./pages/Settings'));
const Profile = lazy(() => import('./pages/Profile'));
const params = new URLSearchParams(location.search);
try {if (params.get('project')) storage.setItem('bb_current', params.get('project'));} catch { /* The app displays storage failures below. */ }
function App() {
  const [notice, setNotice] = useState('');
  useEffect(() => {const storageError = () => setNotice('Your changes could not be saved on this device. Free up browser storage and try again.'); window.addEventListener('bb-storage-error', storageError); return () => window.removeEventListener('bb-storage-error', storageError);}, []);
  // When any authenticated request 401s (api.js dispatches this), the session
  // has expired — bounce to /login unless we're already there.
  useEffect(() => {const expired = () => {if (!/\/login$/i.test(location.pathname)) location.assign('/login');}; window.addEventListener('bb-session-expired', expired); return () => window.removeEventListener('bb-session-expired', expired);}, []);
  const path = decodeURIComponent(location.pathname);
  return <ErrorBoundary>{notice && <div className="global-notice" role="alert">{notice}<button onClick={() => setNotice('')} aria-label="Dismiss storage notice">Dismiss</button></div>}<Suspense fallback={<main className="status-page" aria-busy="true"><div className="loading-mark"/><p>Opening your storybook…</p></main>}>{path === '/' || path === '/home' || path === '/Home.html' ? <Home/> : path === '/welcome' || path === '/Landing.html' ? <Landing/> : path === '/new' || path === '/New Project.html' ? <NewProject/> : path === '/character-design' || path === '/Characters.html' || path === '/Design with AI.html' ? <CharacterDesign/> : path === '/login' || path === '/Login.html' ? <Login/> : path === '/settings' || path === '/Settings.html' ? <Settings/> : path === '/profile' || path === '/Profile.html' ? <Profile/> : path === '/workspace' || path === '/Workspace.html' ? <Workspace/> : <main className="status-page"><h1>This page isn’t in your book</h1><a href="/home">Back to your books</a></main>}</Suspense></ErrorBoundary>;
}
createRoot(document.getElementById('root')).render(<App/>);
