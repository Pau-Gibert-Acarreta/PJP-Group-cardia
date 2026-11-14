export const esc = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const icons = {
activity:'<path d="M3 12h4l3-8 4 16 3-8h4"/>',
users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/><circle cx="9" cy="7" r="4"/>',
heart:'<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>',
search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
filter:'<path d="M4 7h16M7 12h10M10 17h4"/><circle cx="8" cy="7" r="2" fill="currentColor"/><circle cx="16" cy="12" r="2" fill="currentColor"/>',
sort:'<path d="M8 4v16m-4-4 4 4 4-4m2-12h6m-6 5h4m-4 5h2"/>',
chevron:'<path d="m9 5 7 7-7 7"/>',down:'<path d="m6 9 6 6 6-6"/>',
arrow:'<path d="M19 12H5m7-7-7 7 7 7"/>',arrowUp:'<path d="m7 17 10-10M7 7h10v10"/>',arrowDown:'<path d="m7 7 10 10M7 17h10V7"/>',
check:'<path d="m5 12 4 4L19 6"/>',clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/>',
bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-11 12a2 2 0 0 0 4 0"/>',
info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
plus:'<path d="M12 5v14M5 12h14"/>',close:'<path d="m6 6 12 12M6 18 18 6"/>',
bookmark:'<path d="M6 3h12v18l-6-4-6 4Z"/>',download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
building:'<path d="M4 21V5h16v16M2 21h20M9 21v-5h6v5M8 9h1m6 0h1M8 12h1m6 0h1"/>',
mail:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/>',
phone:'<path d="M21 16.5V20a1 1 0 0 1-1.1 1C10 20 4 14 3 4.1A1 1 0 0 1 4 3h3.5l2 5-3 2a16 16 0 0 0 7.5 7.5l2-3Z"/>',
flask:'<path d="M9 3h6m-5 0v7L4 20a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1l-6-10V3M7 15h10"/>',
pill:'<path d="M10 4 4 10a6 6 0 0 0 8 8l6-6a6 6 0 0 0-8-8Zm-3 3 10 10"/>',
clipboard:'<rect x="5" y="4" width="14" height="17" rx="2"/><rect x="9" y="2" width="6" height="4" rx="1"/><path d="M9 11h6m-6 4h4"/>',
expand:'<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
note:'<path d="M14 3H5v18h14V8Zm0 0v5h5M8 12h8m-8 4h5"/>',
shield:'<path d="M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7Z"/><path d="m8 12 3 3 5-6"/>',
reset:'<path d="M3 10a9 9 0 1 1 1 7M3 4v6h6"/>'
};
export const icon = (name, cls = '') => '<svg class="icon ' + cls + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (icons[name] || icons.activity) + '</svg>';
export function avatar(p, large = false) {
  const female = p.sex === 'Mujer';
  return '<span class="avatar ' + p.color + (large ? ' avatar-large' : '') + '">' +
    '<svg viewBox="0 0 80 90" role="img" aria-label="Retrato ficticio de ' + esc(p.firstName) + '"><path d="M8 90c2-24 15-31 32-31s30 7 32 31" fill="' + (female ? '#648f88' : '#7c8e9b') + '"/>' +
    '<path d="M33 53v14l7 7 7-7V53" fill="#d5a88b"/>' +
    (female ? '<path d="M18 51c-8-42 12-45 22-45s31 3 22 52l-7 10H24Z" fill="#64615c"/>' : '<path d="M21 36C17 8 58 6 60 33l-5 23H26Z" fill="#64615c"/>') +
    '<ellipse cx="40" cy="36" rx="18" ry="24" fill="#e6bd9e"/><path d="M22 30C20 9 57 7 59 30c-12-1-18-7-23-12-1 7-6 10-14 12" fill="#68645e"/><path d="M31 37h4m11 0h4m-16 13q6 5 12 0" stroke="#665348" stroke-width="1.7" fill="none" stroke-linecap="round"/>' +
    (female ? '<path d="m27 65 13 9-8 16H20m33-25-13 9 8 16h12" fill="#f0f4f0"/>' : '<path d="m29 65 11 9 11-9-4 25H34" fill="#eaf0f3"/>') + '</svg></span>';
}
export function sparkline(p) {
  const values = p.history.risk, min = Math.min(...values) - 1, max = Math.max(...values) + 1;
  const points = values.map((v, i) => (i * 12 + 2) + ',' + (27 - (v - min) / (max - min) * 23)).join(' ');
  return '<svg viewBox="0 0 66 32" class="sparkline" aria-label="Evolución simulada del riesgo"><polyline points="' + points + '" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
}

