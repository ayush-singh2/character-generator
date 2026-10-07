// A single storage boundary for this explicitly local-only application.
const scoped = key => /^(bb_characters|bb_char_order|bb_ws_regen)/.test(key) ? `${key}_${window.localStorage.getItem('bb_current') || 'default'}` : key;
export const storage = {
  getItem(key) { return window.localStorage.getItem(scoped(key)); },
  setItem(key, value) { try {window.localStorage.setItem(scoped(key), value);} catch (error) {window.dispatchEvent(new CustomEvent('bb-storage-error')); throw error;} },
  removeItem(key) {window.localStorage.removeItem(scoped(key));},
};
export function read(key, fallback) {try {return JSON.parse(storage.getItem(key)) ?? fallback;} catch {return fallback;}}
export function write(key, value) {storage.setItem(key, JSON.stringify(value));}
export async function readImage(file) {
  if (!/^image\/(png|jpeg|webp|gif)$/.test(file.type)) throw new Error('Choose a PNG, JPEG, WebP or GIF image.');
  if (file.size > 3 * 1024 * 1024) throw new Error('Choose an image smaller than 3 MB for local storage.');
  return new Promise((resolve, reject) => {const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error('The image could not be read.')); reader.readAsDataURL(file);});
}
