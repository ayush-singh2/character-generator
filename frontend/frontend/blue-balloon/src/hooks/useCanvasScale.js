import {useLayoutEffect, useState} from 'react';
export function useCanvasScale(dims) {
  const [scale, setScale] = useState(1);
  useLayoutEffect(() => {
    const stage = document.querySelector('.stage');
    if (!stage) return;
    const update = () => {const css = getComputedStyle(stage); const width = stage.clientWidth - parseFloat(css.paddingLeft) - parseFloat(css.paddingRight); const height = stage.clientHeight - parseFloat(css.paddingTop) - parseFloat(css.paddingBottom); setScale(Math.max(.15, Math.min(1,width/dims.w,height/dims.h)));};
    update(); const observer = new ResizeObserver(update); observer.observe(stage); return () => observer.disconnect();
  });
  return scale;
}
