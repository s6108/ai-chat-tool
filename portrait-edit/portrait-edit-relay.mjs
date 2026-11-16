import { createServer } from 'node:http';
import { timingSafeEqual } from 'node:crypto';

const {
  PORTRAIT_EDIT_PROVIDER = 'openai',
  OPENAI_API_KEY,
  ARK_API_KEY,
  ARK_IMAGE_MODEL = 'doubao-seedream-5-5-261028',
  PORTRAIT_RELAY_TOKEN,
  PORT = '8787',
  HOST = '127.0.0.1',
} = process.env;

if (!PORTRAIT_RELAY_TOKEN || PORTRAIT_RELAY_TOKEN.length < 24) {
  throw new Error('Set PORTRAIT_RELAY_TOKEN to a random token of at least 24 characters.');
}
if (PORTRAIT_EDIT_PROVIDER === 'seedream') {
  if (!ARK_API_KEY || !ARK_IMAGE_MODEL.trim()) {
    throw new Error('Set ARK_API_KEY and an enabled Seedream model or image endpoint in ARK_IMAGE_MODEL.');
  }
} else if (PORTRAIT_EDIT_PROVIDER === 'openai') {
  if (!OPENAI_API_KEY) throw new Error('Set OPENAI_API_KEY for the OpenAI provider.');
} else {
  throw new Error('PORTRAIT_EDIT_PROVIDER must be seedream or openai.');
}

const authorized = (header) => {
  const actual = Buffer.from(header ?? '');
  const expected = Buffer.from(`Bearer ${PORTRAIT_RELAY_TOKEN}`);
  return actual.length === expected.length && timingSafeEqual(actual, expected);
};

const retouchPrompt = `
你是专业人像修图师。以输入照片为唯一依据，在原有画面上做写实后期。逐项检查，按这张照片的实际情况决定是否处理及处理幅度。优先级：肤色准确、自然质感、风格化效果。沿用原片的光线和氛围。

保留人物身份、年龄特征、脸型、五官比例、肤色基调、视线、表情、手势、姿态、身材和衣着。保留痣、雀斑、毛孔、发际线和皮肤自然明暗。保持机位、构图、取景边界、画幅比例及场景物件的位置。禁止换脸、拉伸身体、改变五官几何或重绘不可辨认的细节。

按顺序检查并修饰：
1. 基础校正。处理可见的曝光问题、白平衡偏差、色差和不自然的暗角。有明显镜头变形时，仅在能保留人物比例、场景线条和原画幅的情况下修正。
2. 清理干扰。处理明显的临时痘印、头皮屑、衣物污点和遮挡五官的散落发丝，保留原有发型和发际线。若背景抢眼，通过局部明暗和色彩减弱干扰，保留真实物件。
3. 肤质和肤色。分开处理局部色块与纹理，减轻斑驳及过亮的反光。让脸、颈、耳和可见手臂协调，保留毛孔、自然色差和立体过渡。
4. 光影与五官。在原光源方向上细调局部明暗，保留高光及阴影层次。眼神光、眉毛、唇部、眼白和牙齿仅在有需要且清晰可见时适度调整，避免漂白和边缘光晕。
5. 色调与细节。先校正肤色，再调整环境色。分区降噪和锐化，眉眼、发丝及衣物保留细节，皮肤避免强化噪点。对模糊或过曝处，只改善原片中仍可辨认的细节。
6. 输出前复核人物和构图是否忠实于输入，检查肤色过渡、发丝和衣物边缘、亮斑、牙齿和眼白。无法可靠修饰的区域保留原状。

只返回精修后的照片。尽可能保持输入画幅，禁止裁剪、填边、叠字或添加水印。
`.trim();

const seedreamPrompt = `
以原图为唯一依据做写实人像精修，保持构图、画幅、场景、身份、五官比例、眼神、表情、姿态和发型。保留痣、雀斑、毛孔、发丝和衣料细节。按图校正曝光与偏色，均衡脸、耳、颈和手臂肤色，减轻过强反光、暂时性瑕疵和噪点；顺着原光向局部调整明暗，保留高光与暗部层次。仅在需要处处理，优先肤色准确和自然质感。不要裁切、填边、改脸、改变物件、虚构细节或叠加文字。
`.trim();

function requestImageEdit(jpeg, signal) {
  if (PORTRAIT_EDIT_PROVIDER === 'seedream') {
    return fetch('https://ark.cn-beijing.volces.com/api/v3/images/generations', {
      method: 'POST',
      headers: { Authorization: `Bearer ${ARK_API_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: ARK_IMAGE_MODEL.trim(),
        image: `data:image/jpeg;base64,${jpeg.toString('base64')}`,
        prompt: seedreamPrompt,
        size: '2K',
        response_format: 'b64_json',
        output_format: 'jpeg',
        watermark: false,
      }),
      signal,
    });
  }

  const form = new FormData();
  form.set('model', 'gpt-image-2');
  form.set('image', new Blob([jpeg], { type: 'image/jpeg' }), 'portrait.jpg');
  form.set('prompt', retouchPrompt);
  form.set('size', 'auto');
  form.set('output_format', 'jpeg');
  return fetch('https://api.openai.com/v1/images/edits', {
    method: 'POST',
    headers: { Authorization: `Bearer ${OPENAI_API_KEY}` },
    body: form,
    signal,
  });
}

async function upstreamFailureStatus(result) {
  const payload = await result.json().catch(() => ({}));
  const code = payload?.error?.code;
  const safeCode = typeof code === 'string' && /^[a-z0-9_.-]{1,100}$/i.test(code) ? code : 'unspecified';
  console.error('Image edit failed:', PORTRAIT_EDIT_PROVIDER, result.status, safeCode);
  if (result.status === 429) return 429;
  if (PORTRAIT_EDIT_PROVIDER === 'seedream' &&
      ['ModelNotOpen', 'OperationDenied.ServiceNotOpen', 'InvalidEndpointOrModel.NotFound',
        'InvalidEndpointOrModel.ModelIDAccessDisabled'].includes(safeCode)) return 424;
  return 502;
}

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

    const result = await requestImageEdit(jpeg, AbortSignal.any([cancel.signal, AbortSignal.timeout(165_000)]));
    if (!result.ok) {
      res.writeHead(await upstreamFailureStatus(result)).end();
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
