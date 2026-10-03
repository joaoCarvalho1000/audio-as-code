// Large generated downloads use R2. All ordinary site assets bypass this handler.
// A release manifest selects immutable object keys; no arbitrary bucket access.
export function byteRange(value, size) {
  if (!value || value.includes(',')) return null;
  const match = /^bytes=(\d*)-(\d*)$/.exec(value.trim());
  if (!match || (!match[1] && !match[2])) return null;
  if (!match[1]) {
    const suffix = Number(match[2]);
    if (!Number.isSafeInteger(suffix)) return null;
    if (!suffix) return false;
    const length = Math.min(size, suffix);
    return { offset: size - length, length };
  }
  const start = Number(match[1]);
  const end = match[2] ? Number(match[2]) : size - 1;
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end)) return null;
  if (start >= size || end < start) return false;
  return { offset: start, length: Math.min(size - 1, end) - start + 1 };
}

export async function serveMedia(request, bucket, entry) {
  if (!['GET', 'HEAD'].includes(request.method)) {
    return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD' } });
  }
  const etag = `"sha256-${entry.sha256}"`;
  const headers = new Headers({
    'Content-Type': entry.content_type,
    'Content-Length': String(entry.bytes),
    'Accept-Ranges': 'bytes',
    'Cache-Control': 'public, max-age=0, must-revalidate',
    'X-Content-Type-Options': 'nosniff',
    ETag: etag,
  });
  const ifRange = request.headers.get('If-Range');
  const range = request.method === 'GET' && (!ifRange || ifRange === etag)
    ? byteRange(request.headers.get('Range'), entry.bytes) : null;
  const matches = request.headers.get('If-None-Match')?.split(',').some(
    value => value.trim() === '*' || value.trim().replace(/^W\//, '') === etag,
  );
  const metadataOnly = request.method === 'HEAD' || matches || range === false;
  const object = metadataOnly
    ? await bucket.head(entry.key)
    : await bucket.get(entry.key, range ? { range } : undefined);
  if (!object) return new Response('Not found', { status: 404 });
  if (object.size !== entry.bytes) {
    console.error(JSON.stringify({ error: 'media_size_mismatch', key: entry.key }));
    return new Response('Download unavailable', { status: 503 });
  }
  if (matches) {
    headers.delete('Content-Length');
    return new Response(null, { status: 304, headers });
  }
  if (range === false) {
    headers.set('Content-Range', `bytes */${entry.bytes}`);
    headers.delete('Content-Length');
    return new Response(null, { status: 416, headers });
  }
  if (request.method === 'HEAD') return new Response(null, { headers });
  if (range) {
    headers.set('Content-Length', String(range.length));
    headers.set('Content-Range', `bytes ${range.offset}-${range.offset + range.length - 1}/${entry.bytes}`);
  }
  return new Response(object.body, { status: range ? 206 : 200, headers });
}
