/**
 * 零依赖静态服务器 + /api 反向代理。
 *
 * 运行：
 *   node server.mjs
 * 可选环境变量：
 *   PORT=5173                 前端端口
 *   BACKEND_URL=http://localhost:8080   后端地址
 *
 * 浏览器访问 http://localhost:5173 ，页面内的 /api/v1/* 会被代理到后端，
 * 因此前后端同源，无需在后端增加 CORS 配置。
 */
import http from 'node:http';
import { createReadStream, promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT) || 5173;
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8080';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.woff2': 'font/woff2',
};

function proxy(req, res, url) {
  const target = new URL(url.pathname + url.search, BACKEND_URL);
  const proxyReq = http.request(
    target,
    {
      method: req.method,
      headers: { ...req.headers, host: target.host },
    },
    proxyRes => {
      res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
      proxyRes.pipe(res);
    },
  );
  proxyReq.on('error', error => {
    const body = JSON.stringify({
      code: 'BACKEND_UNAVAILABLE',
      message: `无法连接后端服务（${BACKEND_URL}）：${error.code || error.message || '连接被拒绝'}`,
    });
    res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(body);
  });
  req.pipe(proxyReq);
}

async function serveStatic(req, res, url) {
  const requested = decodeURIComponent(url.pathname);
  const relative = requested === '/' ? '/index.html' : requested;
  const filePath = path.resolve(ROOT, `.${relative}`);

  if (!filePath.startsWith(ROOT + path.sep) && filePath !== ROOT) {
    res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Forbidden');
    return;
  }

  try {
    const stat = await fs.stat(filePath);
    if (stat.isDirectory()) {
      return serveStatic(req, res, new URL(`${url.pathname.replace(/\/?$/, '/')}index.html`, 'http://localhost'));
    }
    const type = MIME[path.extname(filePath).toLowerCase()] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': type, 'Cache-Control': 'no-store' });
    if (req.method === 'HEAD') {
      res.end();
      return;
    }
    createReadStream(filePath).pipe(res);
  } catch {
    // 单页应用回退
    const fallback = path.join(ROOT, 'index.html');
    res.writeHead(200, { 'Content-Type': MIME['.html'], 'Cache-Control': 'no-store' });
    createReadStream(fallback).pipe(res);
  }
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || `localhost:${PORT}`}`);
  if (url.pathname.startsWith('/api/')) {
    proxy(req, res, url);
    return;
  }
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.writeHead(405, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Method Not Allowed');
    return;
  }
  serveStatic(req, res, url);
});

server.listen(PORT, () => {
  console.log(`管理看板已启动：http://localhost:${PORT}`);
  console.log(`接口代理：/api/v1/* -> ${BACKEND_URL}/api/v1/*`);
  console.log('请先启动后端：cd src/backend && .\\mvnw.cmd spring-boot:run');
});

server.on('error', error => {
  if (error.code === 'EADDRINUSE') {
    console.error(`端口 ${PORT} 已被占用，可通过 PORT=其他端口 node server.mjs 启动。`);
  } else {
    console.error('服务器启动失败：', error);
  }
  process.exit(1);
});
