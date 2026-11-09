import { createServer } from 'node:http';
import { timingSafeEqual } from 'node:crypto';

const { OPENAI_API_KEY, PORTRAIT_RELAY_TOKEN, PORT = '8787', HOST = '127.0.0.1' } = process.env;
if (!OPENAI_API_KEY || !PORTRAIT_RELAY_TOKEN || PORTRAIT_RELAY_TOKEN.length < 24) {
  throw new Error('Set OPENAI_API_KEY and a random PORTRAIT_RELAY_TOKEN of at least 24 characters.');
}

const authorized = (header) => {
  const actual = Buffer.from(header ?? '');
  const expected = Buffer.from(`Bearer ${PORTRAIT_RELAY_TOKEN}`);
  return actual.length === expected.length && timingSafeEqual(actual, expected);
};

const maxInput = 8 * 1024 * 1024;
let busy = false;
createServer(async (req, res) => {
  if (req.method !== 'POST' || req.url !== '/portrait-edit') {
    res.writeHead(404).end();
    return;
  }
  if (!authorized(req.headers.authorization)) {
    res.writeHead(401).end();
    return;
  }
  if (req.headers['content-type'] !== 'image/jpeg') {
    res.writeHead(415).end();
    return;
  }
  const length = Number(req.headers['content-length']);
  if (!Number.isSafeInteger(length) || length < 3 || length > maxInput) {
    res.writeHead(413).end();
    return;
  }
  if (busy) {
    res.writeHead(429).end();
    return;
  }

  busy = true;
  const cancel = new AbortController();
  res.on('close', () => cancel.abort());
  try {
    const chunks = [];
    let received = 0;
    for await (const chunk of req) {
      received += chunk.length;
      if (received > length) {
        res.writeHead(413).end();
        return;
      }
      chunks.push(chunk);
    }
    const jpeg = Buffer.concat(chunks);
    if (received !== length || jpeg[0] !== 255 || jpeg[1] !== 216 || jpeg[2] !== 255) {
      res.writeHead(400).end();
      return;
    }

    const form = new FormData();
    form.set('model', 'gpt-image-2');
    form.set('image', new Blob([jpeg], { type: 'image/jpeg' }), 'portrait.jpg');
    form.set('prompt', '美化这张照片，交付清晰、鲜明、有层次的写实人像。根据照片自主决定后期。保留人物身份、五官形态、视线、表情、手势、姿势、衣着及场景内容。不要添加文字。');
    form.set('size', 'auto');
    form.set('output_format', 'jpeg');
    const result = await fetch('https://api.openai.com/v1/images/edits', {
      method: 'POST',
      headers: { Authorization: `Bearer ${OPENAI_API_KEY}` },
      body: form,
      signal: AbortSignal.any([cancel.signal, AbortSignal.timeout(165_000)]),
    });
    if (!result.ok) {
      console.error('Image edit upstream status:', result.status);
      res.writeHead(result.status === 429 ? 429 : 502).end();
      return;
    }
    const encoded = (await result.json()).data?.[0]?.b64_json;
    if (typeof encoded !== 'string' || encoded.length > 32 * 1024 * 1024) {
      res.writeHead(502).end();
      return;
    }
    const edited = Buffer.from(encoded, 'base64');
    if (edited[0] !== 255 || edited[1] !== 216 || edited[2] !== 255) {
      res.writeHead(502).end();
      return;
    }
    res.writeHead(200, {
      'Content-Type': 'image/jpeg',
      'Content-Length': edited.length,
      'Cache-Control': 'no-store',
    }).end(edited);
  } catch (error) {
    console.error('Image edit relay error:', error.name);
    if (!res.destroyed) res.writeHead(error.name === 'TimeoutError' ? 504 : 502).end();
  } finally {
    busy = false;
  }
}).listen(Number(PORT), HOST);
