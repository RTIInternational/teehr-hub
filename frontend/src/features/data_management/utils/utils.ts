export const fmt = (val: string | number) => {
  if (val == null) return '—';
  return String(val)
    .replace('T', ' ')
    .replace(/\.\d+Z?$/, '');
};
