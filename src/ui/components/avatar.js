// Retrato ilustrado y ficticio del paciente.
import { esc } from '../../utils/text.js';

export function avatar(p, large = false) {
  const female = p.sex === 'Mujer';
  return '<span class="avatar ' + p.color + (large ? ' avatar-large' : '') + '">' +
    '<svg viewBox="0 0 80 90" role="img" aria-label="Retrato ficticio de ' + esc(p.firstName) + '"><path d="M8 90c2-24 15-31 32-31s30 7 32 31" fill="' + (female ? '#648f88' : '#7c8e9b') + '"/>' +
    '<path d="M33 53v14l7 7 7-7V53" fill="#d5a88b"/>' +
    (female ? '<path d="M18 51c-8-42 12-45 22-45s31 3 22 52l-7 10H24Z" fill="#64615c"/>' : '<path d="M21 36C17 8 58 6 60 33l-5 23H26Z" fill="#64615c"/>') +
    '<ellipse cx="40" cy="36" rx="18" ry="24" fill="#e6bd9e"/><path d="M22 30C20 9 57 7 59 30c-12-1-18-7-23-12-1 7-6 10-14 12" fill="#68645e"/><path d="M31 37h4m11 0h4m-16 13q6 5 12 0" stroke="#665348" stroke-width="1.7" fill="none" stroke-linecap="round"/>' +
    (female ? '<path d="m27 65 13 9-8 16H20m33-25-13 9 8 16h12" fill="#f0f4f0"/>' : '<path d="m29 65 11 9 11-9-4 25H34" fill="#eaf0f3"/>') + '</svg></span>';
}
