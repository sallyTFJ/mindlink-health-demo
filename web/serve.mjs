import { createServer } from 'node:http';
import { createReadStream, existsSync, statSync } from 'node:fs';
import { extname, join, normalize } from 'node:path';

const root = join(import.meta.dirname, 'dist');
const port = Number(process.env.PORT || 4173);
const mime = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8','.webmanifest':'application/manifest+json','.svg':'image/svg+xml','.csv':'text/csv; charset=utf-8'};

createServer((request, response) => {
  const pathname = decodeURIComponent(new URL(request.url, `http://${request.headers.host}`).pathname);
  const requested = pathname === '/' ? '/index.html' : pathname;
  const candidate = normalize(join(root, requested));
  if (!candidate.startsWith(root) || !existsSync(candidate) || !statSync(candidate).isFile()) {
    response.writeHead(404, {'content-type':'text/plain; charset=utf-8'});
    response.end('Not found');
    return;
  }
  response.writeHead(200, {'content-type': mime[extname(candidate)] || 'application/octet-stream', 'cache-control':'no-store'});
  createReadStream(candidate).pipe(response);
}).listen(port, '127.0.0.1', () => console.log(`MindLink preview: http://127.0.0.1:${port}`));
