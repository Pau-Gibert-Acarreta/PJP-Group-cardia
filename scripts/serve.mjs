import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL('../', import.meta.url));
const port = Number(process.env.PORT || 5173);
// Core Backend API (backend/). Las peticiones a /api/* se reenvían allí, así el navegador
// habla con un solo origen y no hace falta CORS.
const api = new URL(process.env.CARDIA_API_URL || 'http://127.0.0.1:8000');
const types = { '.json': 'application/json; charset=utf-8', '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg' };

function proxy(req, res) {
  const upstream = http.request({ hostname: api.hostname, port: api.port || 80, path: req.url, method: req.method, headers: { ...req.headers, host: api.host } }, response => {
    res.writeHead(response.statusCode, response.headers);
    response.pipe(res);
  });
  upstream.on('error', () => {
    if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ detail: 'No se puede conectar con el backend en ' + api.origin }));
  });
  req.pipe(upstream);
}

http.createServer(async (req, res) => {
  if (req.url.startsWith('/api/')) return proxy(req, res);
  try {
    const relative = decodeURIComponent(new URL(req.url, 'http://localhost').pathname).replace(/^\/+/, '') || 'index.html';
    const target = path.resolve(root, relative);
    const inside = path.relative(root, target);
    if (inside.startsWith('..') || path.isAbsolute(inside) || inside.split(path.sep).some(p => p.startsWith('.')) || !['index.html', 'src', 'assets'].includes(inside.split(path.sep)[0])) {
      res.writeHead(403); res.end('Acceso no permitido'); return;
    }
    const content = await readFile(target);
    res.writeHead(200, { 'Content-Type': types[path.extname(target)] || 'application/octet-stream', 'Cache-Control': 'no-cache' });
    res.end(content);
  } catch { res.writeHead(404); res.end('Archivo no encontrado'); }
}).listen(port, process.env.HOST || '127.0.0.1', () => console.log('Cardia disponible en http://localhost:' + port + ' (API: ' + api.origin + ')'));
