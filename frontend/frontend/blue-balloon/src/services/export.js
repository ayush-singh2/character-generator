import React from 'react';
import {createRoot} from 'react-dom/client';
import {flushSync} from 'react-dom';
import BBR from '../editor/render';
import BBTH from '../editor/book-theme';

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob), link = document.createElement('a');
  link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 5000);
}
export async function exportBook({pages, settings, dims, theme, format, quality, bleed, onProgress}) {
  if (!pages.length) throw new Error('Choose at least one page to export.');
  const {toPng, getFontEmbedCSS} = await import('html-to-image');
  const host = document.createElement('div'); host.className = 'book-export-host'; document.body.append(host);
  const root = createRoot(host), images = [];
  try {
    let fontEmbedCSS;
    for (const [index, page] of pages.entries()) {
      flushSync(() => root.render(React.createElement('div', {className:'book-export-page', style:{width:dims.w,height:dims.h,background:BBTH.pageBg(page,theme)}},page.els.map(el => React.createElement(React.Fragment,{key:el.id},BBR.renderEl(el,{theme,page,dims}))))));
      await document.fonts.ready;
      await Promise.all([...host.querySelectorAll('img')].map(img => img.decode()));
      fontEmbedCSS ??= await getFontEmbedCSS(host.firstChild);
      images.push(await toPng(host.firstChild,{pixelRatio:quality === 'Print 300dpi' ? 3.125 : quality === 'High' ? 2 : 1,fontEmbedCSS}));
      onProgress(Math.round(((index+1)/pages.length)*90));
    }
    const name = (settings.name || 'storybook').replace(/[^\p{L}\p{N} -]/gu,'').trim().replace(/\s+/g,'-').toLowerCase() || 'storybook';
    if (format === 'PNG images') {
      const {default: JSZip} = await import('jszip'); const zip = new JSZip();
      images.forEach((src,index) => zip.file(`${name}-${String(index+1).padStart(2,'0')}.png`,src.split(',')[1],{base64:true}));
      const blob = await zip.generateAsync({type:'blob'}); downloadBlob(blob,`${name}.zip`);
    } else {
      const {jsPDF} = await import('jspdf');
      const sizes = {A3:[297,420],A4:[210,297],A5:[148,210],Letter:[216,279],Square:[210,210]};
      let [w,h] = sizes[settings.size] || sizes.A4;
      if (/horizon/i.test(settings.orientation || '')) [w,h] = [h,w];
      const margin = bleed ? 6 : 0, pw = w+margin*2, ph = h+margin*2;
      const pdf = new jsPDF({orientation:pw>ph?'landscape':'portrait',unit:'mm',format:[pw,ph],compress:true});
      images.forEach((src,index) => {
        if (index) pdf.addPage([pw,ph],pw>ph?'landscape':'portrait');
        pdf.addImage(src,'PNG',margin,margin,w,h);
        if (bleed) {pdf.setDrawColor(100); pdf.setLineWidth(.15); for (const x of [margin,margin+w]) for (const y of [margin,margin+h]) {const dx=x===margin?-1:1,dy=y===margin?-1:1; pdf.line(x+dx*2,y,x+dx*5,y);pdf.line(x,y+dy*2,x,y+dy*5);}}
      });
      pdf.setProperties({title:settings.name,author:settings.author || '',creator:'Blue Balloon'});
      downloadBlob(pdf.output('blob'),`${name}.pdf`);
    }
    onProgress(100);
  } finally {root.unmount();host.remove();}
}
