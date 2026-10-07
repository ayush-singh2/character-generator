import React from 'react';
import {Icon} from '../editor/icons';

const COVERS = {
  lantern: {title: 'The Lantern Boy', by: 'MIRA', cls: 'cover--lantern'},
  ocean: {title: 'Ocean Dreams', by: 'THEO', cls: 'cover--ocean'},
  forest: {title: 'Forest Friends', by: 'PRIYA', cls: 'cover--forest'},
};
function Cover({v, className = ''}) {
  const c = COVERS[v];
  return <div className={`land-cover ${c.cls} ${className}`}>
    <span className="land-cover__sun" aria-hidden="true"/>
    <div className="land-cover__meta"><strong>{c.title}</strong><em>BY {c.by}</em></div>
  </div>;
}

const STYLES = ['Watercolor', 'Flat', 'Line art', 'Painting', 'Vector', '3D render'];

function Feature({n, kicker, title, children, media, flip}) {
  return <section className={`land-feature${flip ? ' land-feature--flip' : ''}`}>
    <div className="land-feature__media">{media}</div>
    <div className="land-feature__text">
      <p className="land-kicker">{n} · {kicker}</p>
      <h2>{title}</h2>
      <p>{children}</p>
    </div>
  </section>;
}

export default function Landing() {
  return <div className="land">
    <header className="land-top">
      <a className="land-brand" href="/"><span className="bb-mark" aria-hidden="true"/>Blue Balloon</a>
      <nav className="land-nav" aria-label="Landing">
        <a href="#how">How it works</a>
        <a href="#styles">Illustration styles</a>
        <a href="/home">Your projects</a>
      </nav>
      <a className="land-open" href="/home">Open studio <Icon name="arrow-right" size={16}/></a>
    </header>

    <section className="land-hero">
      <div className="land-hero__text">
        <p className="land-kicker">Storybooks, made together</p>
        <h1>Turn your manuscript into a <em>beautifully illustrated</em> storybook</h1>
        <p className="land-lead">Blue Balloon reads your story, helps you shape its characters and illustration style, and lays out every page. You and your team refine each spread until it is ready to share or print.</p>
        <div className="land-cta-row">
          <a className="ui-btn ui-btn--default land-btn" href="/new">Start creating <Icon name="arrow-right" size={16}/></a>
          <span className="land-muted">No design skills needed</span>
        </div>
      </div>
      <div className="land-hero__art" aria-hidden="true">
        <Cover v="lantern" className="c1"/>
        <Cover v="ocean" className="c2"/>
        <Cover v="forest" className="c3"/>
      </div>
    </section>

    <div id="how"/>
    <Feature n="01" kicker="WRITE" title="Start with your story"
      media={<div className="land-mock land-mock--doc" aria-hidden="true"/>}>
      Upload a manuscript or begin from a blank page. Blue Balloon reads every chapter and pulls out the scenes, mood and characters it finds.
    </Feature>
    <Feature n="02" kicker="CHARACTERS" title="Bring your characters to life" flip
      media={<div className="land-mock land-avatars" aria-hidden="true"><span className="av av1"/><span className="av av2"/><span className="av av3"/></div>}>
      Describe each character once. They stay consistent from the first page to the last, in every scene they appear in.
    </Feature>

    <div id="styles"/>
    <Feature n="03" kicker="STYLE" title="Choose how it looks"
      media={<div className="land-mock" aria-hidden="true"><div className="land-styles">{STYLES.map((s, i) => <span key={s} className={`sw sw${i + 1}`}><b>{s}</b></span>)}</div></div>}>
      Pick from watercolor, flat, line art, digital painting, vector or 3D. Preview each before you commit, and set your own palette.
    </Feature>
    <Feature n="04" kicker="PAGES" title="Watch the pages come together" flip
      media={<div className="land-mock" aria-hidden="true"><Cover v="forest"/></div>}>
      Every spread is laid out with your text and artwork in place. Sizes, orientation and book length are set once and applied throughout.
    </Feature>
    <Feature n="05" kicker="REFINE" title="Edit until it feels right"
      media={<div className="land-mock land-editor" aria-hidden="true"><Cover v="lantern" className="in-editor"/></div>}>
      Rewrite a line, swap an illustration, adjust a palette. Teammates can comment and edit alongside you in the same workspace.
    </Feature>
    <Feature n="06" kicker="SHARE" title="Share your finished book" flip
      media={<div className="land-mock land-share" aria-hidden="true"><Cover v="ocean"/><div className="land-share__btns"><span className="pill">Read online</span><span className="pill">Download PDF</span><span className="pill">Order a printed copy</span></div></div>}>
      Publish a read-only link, export a print-ready PDF or order printed copies.
    </Feature>

    <section className="land-cta">
      <div><h2>Ready to make your first book?</h2><p>Open the studio and start a new storybook in minutes.</p></div>
      <a className="land-cta__btn" href="/new">Start creating <Icon name="arrow-right" size={16}/></a>
    </section>

    <footer className="land-foot"><span>Blue Balloon</span><span>Storybook creation studio</span></footer>
  </div>;
}
