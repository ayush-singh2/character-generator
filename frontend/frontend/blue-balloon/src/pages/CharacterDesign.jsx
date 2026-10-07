import React, {useState} from 'react';
import SiteHeader from '../components/SiteHeader';
import {Button, Field, Input} from '../editor/ui';
import {Icon} from '../editor/icons';
import {read, write, readImage, storage} from '../services/storage';
import {projectHref, backendEnabled} from '../services/projects';
import {designCharacter, approveCharacter} from '../services/book';

export default function CharacterDesign() {
  const params = new URLSearchParams(location.search), id = params.get('char') || 'ram', variant = params.get('variant');
  const data = read('bb_characters', {}), character = data[id] || {};
  const [description, setDescription] = useState('');
  const [name, setName] = useState(character.name || id);
  const [image, setImage] = useState(character.design?.preview || '');
  const [photoFile, setPhotoFile] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [filename, setFilename] = useState('Character reference');
  const slug = storage.getItem('bb_current') || 'default';
  const back = `${projectHref(slug)}&mode=characters`;

  const upload = async e => {
    const file = e.target.files[0];
    if (!file) return;
    setBusy(true); setError('');
    try {setImage(await readImage(file)); setPhotoFile(file); setFilename(file.name);}
    catch (err) {setError(err.message);}
    finally {setBusy(false);}
  };

  const saveLocal = () => {
    try {
      const source = {type: 'upload', preview: image, name: filename, description};
      const next = {...character, name: name.trim(), mode: character.mode || 'constant'};
      if (variant) next.variants = (next.variants || []).map(v => v.id === variant ? {...v, source} : v);
      else next.design = source;
      write('bb_characters', {...data, [id]: next});
      storage.setItem('bb_ws_regen', '1');
      location.assign(back);
    } catch {
      setError('Could not save this reference. Browser storage may be full.');
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true); setError('');
    if (backendEnabled) {
      try {
        // Send the description as the design instruction plus an optional photo;
        // the backend redesigns the character on-model, then we lock it in.
        await designCharacter(slug, name.trim(), description.trim() || 'Keep this character on-model and consistent.', photoFile);
        await approveCharacter(slug, name.trim());
        storage.setItem('bb_ws_regen', '1');
        location.assign(back);
      } catch (err) {
        setError(err?.message || 'The server could not design this character. Try again.');
        setBusy(false);
      }
      return;
    }
    saveLocal();
  };

  const canSave = !!name.trim() && !busy && (backendEnabled ? (!!description.trim() || !!image) : !!image);

  return <div className="site-page"><SiteHeader/><main className="setup-page"><a href={back}>Back to your storybook</a><p className="eyebrow">Meet your characters</p><h1>Give your character a face.</h1><p>Keep a visual reference alongside their story.</p><div className="character-design-grid"><section className="setup-card"><Field label="Character name"><Input value={name} onChange={e => setName(e.target.value)} maxLength={80}/></Field><Field label="Character description"><textarea className="ui-textarea" rows={5} value={description} onChange={e => setDescription(e.target.value)} placeholder="Their appearance, personality, and little details…"/></Field><div className="demo-note"><Icon name="circle-alert"/><p>{backendEnabled ? 'Describe the character and optionally add a reference photo — the studio will design them on-model and keep them consistent across the book.' : 'AI image generation needs a connected backend. Upload a reference image to use in your book today.'}</p></div><label className="upload-button ui-btn ui-btn--outline"><Icon name="upload"/>{backendEnabled ? 'Add reference photo (optional)' : 'Upload reference'}<input type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={upload} disabled={busy}/></label><p className="muted">PNG, JPEG, WebP or GIF · up to 3 MB</p>{error && <p role="alert" className="form-error">{error}</p>}<Button disabled={!canSave} onClick={save}>{busy ? (backendEnabled ? 'Designing…' : 'Saving…') : 'Use this character'}</Button></section><div className="character-preview">{image ? <img src={image} alt={`Reference for ${name}`}/> : <div className="empty-state"><Icon name="users" size={48}/><p>Your character reference will appear here.</p></div>}</div></div></main></div>;
}
