import React from 'react';
import {Icon} from '../editor/icons';
export default function SiteHeader() {return <header className="bb-topbar"><a className="bb-brand" href="/home"><span className="bb-mark" aria-hidden="true"/>Blue Balloon</a><span className="local-badge">Local workspace</span><nav className="bb-topnav" aria-label="Account"><a className="bb-topnav-link" href="/settings" aria-label="Settings"><Icon name="settings" size={18}/></a><a className="bb-topnav-link" href="/profile" aria-label="Account"><Icon name="circle-user" size={18}/></a></nav></header>;}
