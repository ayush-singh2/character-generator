import React, { useEffect, useRef, useId } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from './icons';

export function Button({variant = 'default', size = 'default', className = '', children, ...props}) {
  return <button type="button" className={`ui-btn ui-btn--${variant} ui-btn--${size} ${className}`} {...props}>{children}</button>;
}
export function Input({className = '', ...props}) { return <input className={`ui-input ${className}`} {...props}/>; }
export function Checkbox(props) {return <input type="checkbox" className="ui-checkbox" {...props}/>;}
export function Select({options = [], className = '', ...props}) {
  return <select className={`ui-select ${className}`} {...props}>{options.map(o => <option key={typeof o === 'string' ? o : o.value} value={typeof o === 'string' ? o : o.value}>{typeof o === 'string' ? o : o.label}</option>)}</select>;
}
export function Dialog({open, onOpenChange, children, label = 'Dialog'}) {
  const ref = useRef(null);
  const close = useRef(onOpenChange); close.current = onOpenChange;
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement;
    const node = ref.current;
    const nodes = () => [...node.querySelectorAll('button, input, select, textarea, a[href], [tabindex="0"]')].filter(n => !n.disabled && n.getClientRects().length);
    (node.querySelector('[autofocus]') || nodes()[0] || node).focus();
    const onKey = e => {
      if (e.key === 'Escape') {e.preventDefault(); e.stopPropagation(); close.current?.(false);}
      if (e.key === 'Tab') {const list = nodes(); const first = list[0], last = list.at(-1); if (!first) {e.preventDefault(); return;} if (e.shiftKey && document.activeElement === first) {e.preventDefault(); last.focus();} else if (!e.shiftKey && document.activeElement === last) {e.preventDefault(); first.focus();}}
    };
    node.addEventListener('keydown', onKey);
    return () => {node.removeEventListener('keydown', onKey); previous?.focus?.();};
  }, [open]);
  if (!open) return null;
  return createPortal(<div className="ui-dialog__overlay" onMouseDown={e => e.target === e.currentTarget && onOpenChange?.(false)}><div ref={ref} className="ui-dialog__content" role="dialog" aria-modal="true" aria-label={label} tabIndex={-1}><button type="button" className="ui-dialog__close" aria-label="Close dialog" onClick={() => onOpenChange?.(false)}><Icon name="x"/></button>{children}</div></div>, document.body);
}
export function DialogHeader({children}) {return <div className="ui-dialog__header">{children}</div>;}
export function DialogTitle({children}) {return <h2 className="ui-dialog__title">{children}</h2>;}
export function DialogDescription({children}) {return <p className="ui-dialog__desc">{children}</p>;}
export function DialogFooter({children}) {return <div className="ui-dialog__footer">{children}</div>;}
export function AlertDialog({open, onOpenChange, title, description, actionText = 'Continue', cancelText = 'Cancel', onAction, destructive}) {
  return <Dialog open={open} onOpenChange={onOpenChange} label={title}><DialogHeader><DialogTitle>{title}</DialogTitle><DialogDescription>{description}</DialogDescription></DialogHeader><DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>{cancelText}</Button><Button variant={destructive ? 'destructive' : 'default'} onClick={() => {onAction(); onOpenChange(false);}}>{actionText}</Button></DialogFooter></Dialog>;
}
export function Field({label, children, error}) {const id = useId(); return <label className="form-field" htmlFor={id}><span>{label}</span>{React.cloneElement(children, {id, 'aria-invalid': !!error, 'aria-describedby': error ? `${id}-error` : undefined})}{error && <span id={`${id}-error`} className="form-error" role="alert">{error}</span>}</label>;}
export default {Button, Input, Checkbox, Select, Dialog, DialogHeader, DialogTitle, DialogDescription, DialogFooter, AlertDialog};
