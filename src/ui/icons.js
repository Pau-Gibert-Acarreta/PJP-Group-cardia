// Iconos SVG en línea (trazo de 24 × 24). Uso: icon('heart'). Un nombre desconocido muestra "activity".

const icons = {
activity:'<path d="M3 12h4l3-8 4 16 3-8h4"/>',
users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/><circle cx="9" cy="7" r="4"/>',
heart:'<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>',
search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
filter:'<path d="M4 7h16M7 12h10M10 17h4"/><circle cx="8" cy="7" r="2" fill="currentColor"/><circle cx="16" cy="12" r="2" fill="currentColor"/>',
sort:'<path d="M8 4v16m-4-4 4 4 4-4m2-12h6m-6 5h4m-4 5h2"/>',
chevron:'<path d="m9 5 7 7-7 7"/>',down:'<path d="m6 9 6 6 6-6"/>',
arrow:'<path d="M19 12H5m7-7-7 7 7 7"/>',arrowUp:'<path d="m7 17 10-10M7 7h10v10"/>',arrowDown:'<path d="m7 7 10 10M7 17h10V7"/>',arrowUpright:'<path d="M12 19V5m-6 6 6-6 6 6"/>',arrowDownright:'<path d="M12 5v14m-6-6 6 6 6-6"/>',
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
alert:'<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
question:'<path d="M8.5 8.5a3.5 3.5 0 1 1 5.1 3.1c-1 .5-1.6 1.3-1.6 2.4v.5"/><path d="M12 18.5h.01"/>',
reset:'<path d="M3 10a9 9 0 1 1 1 7M3 4v6h6"/>',
edit:'<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16Z"/><path d="m13.5 6.5 4 4"/>'
};
export const icon = (name, cls = '') => '<svg class="icon ' + cls + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (icons[name] || icons.activity) + '</svg>';
