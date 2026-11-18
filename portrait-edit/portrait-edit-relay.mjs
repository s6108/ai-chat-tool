import { handleComposition } from './photographer-vision.mjs';
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
你是专业人像后期修图师。以原图为底片，交付可以直接入作品册的人像精修。观察照片，挑出最影响人像观感的两三项问题，做成在正常尺寸下看得出来的局部改善。优先处理脸部光线、肤色和质感。

按需执行：
• 有额头、鼻梁或脸颊的油光时，局部压下刺眼反光，保留皮肤细节和正常高光。顶光或逆光造成眼窝、脸颊阴影时，用柔和的局部补光打开阴影，保留原光源方向和脸部立体感。光线已平衡时保留原亮度。
• 校正肤色受灯光产生的偏橙、偏红、偏绿或偏冷，局部均匀不自然的色斑，让脸、耳、颈与手协调。只减少影响观感的临时瑕疵和过重的纹理反差，保留毛孔、稳定的痣和雀斑、年龄特征及自然皱纹。
• 让眉眼、发丝和衣物的原有细节更清楚。背景亮处太抢眼时，适当降低局部亮度或对比度，使视线先落在人物上。
• 完成后以正常观看大小复核：主要问题应有肉眼可见的改善，不能靠只加全局亮度、锐化或饱和度交付。回退任何造成塑料皮、光晕或肤色失真的调整。

保留身份、五官比例、脸型、真实肤色基调、表情、视线、姿态、服饰、物件与构图。不换脸、不液化、不重建五官、不添加虚构细节、不裁切或填边。只输出精修照片。
`.trim();

const landscapePrompt = `
你是专业风光摄影后期修图师。以原片为依据，按实际画面调整曝光、白平衡、高光、阴影、色彩关系和空间层次，使照片清晰、有层次且符合原有光线氛围。按需压低刺眼亮部，打开仍有细节的阴影，适度局部对比、去雾、降噪和分区锐化，保留云、水、雾、植被和山石的真实质感。避免过度 HDR、边缘光晕、过饱和和暗部噪点。保留机位、地平线、构图、景物位置、季节、天气与光源方向。不得换天、添太阳、移山、添加或删除建筑人物、虚构细节，不裁剪、不填边、不叠字。只输出调整后的照片。
`.trim();

function requestImageEdit(jpeg, signal, genre) {
  const landscape = genre === 'landscape';
  if (PORTRAIT_EDIT_PROVIDER === 'seedream') {
    return fetch('https://ark.cn-beijing.volces.com/api/v3/images/generations', {
      method: 'POST',
      headers: { Authorization: `Bearer ${ARK_API_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: ARK_IMAGE_MODEL.trim(),
        image: `data:image/jpeg;base64,${jpeg.toString('base64')}`,
        prompt: landscape ? landscapePrompt : seedreamPrompt,
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
  form.set('prompt', landscape ? landscapePrompt : retouchPrompt);
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
  if (req.method === 'POST' && req.url === '/photographer-plan') {
    if (!authorized(req.headers.authorization)) { res.writeHead(401).end(); return; }
    await handleComposition(req, res, { apiKey: OPENAI_API_KEY, model: process.env.PHOTOGRAPHER_VISION_MODEL || 'gpt-6.2-astra' });
    return;
  }
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

    const result = await requestImageEdit(jpeg, AbortSignal.any([cancel.signal, AbortSignal.timeout(165_000)]),
                                          req.headers['x-photo-genre']);
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
