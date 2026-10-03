import test from 'node:test';
import assert from 'node:assert/strict';
import { byteRange, serveMedia } from './media-handler.js';

const bytes = new TextEncoder().encode('RIFFabcdefgh');
const entry = { key: 'sha/test.wav', sha256: 'abc', bytes: bytes.length, content_type: 'audio/wav' };
const etag = '"sha256-abc"';
function storage() {
  const calls = [];
  return {
    calls,
    async head(key) { calls.push(['head', key]); return { size: bytes.length }; },
    async get(key, options) {
      calls.push(['get', key, options]);
      const { offset = 0, length = bytes.length } = options?.range || {};
      return { size: bytes.length, body: new Response(bytes.slice(offset, offset + length)).body };
    },
  };
}
function request(headers = {}, method = 'GET') {
  return new Request('https://example.test/music/test.wav', { headers, method });
}
test('full media streams byte-identical content with validators', async () => {
  const result = await serveMedia(request(), storage(), entry);
  assert.equal(result.status, 200);
  assert.equal(result.headers.get('ETag'), etag);
  assert.equal(result.headers.get('Content-Type'), 'audio/wav');
  assert.deepEqual(new Uint8Array(await result.arrayBuffer()), bytes);
});
for (const [header, expected, contentRange] of [
  ['bytes=0-3', 'RIFF', 'bytes 0-3/12'],
  ['bytes=4-', 'abcdefgh', 'bytes 4-11/12'],
  ['bytes=-3', 'fgh', 'bytes 9-11/12'],
  ['bytes=9-9999', 'fgh', 'bytes 9-11/12'],
]) {
  test(`ranged delivery ${header}`, async () => {
    const result = await serveMedia(request({ Range: header }), storage(), entry);
    assert.equal(result.status, 206);
    assert.equal(result.headers.get('Content-Range'), contentRange);
    assert.equal(await result.text(), expected);
  });
}
test('unsatisfiable ranges check metadata without downloading bytes', async () => {
  const bucket = storage();
  const result = await serveMedia(request({ Range: 'bytes=12-' }), bucket, entry);
  assert.equal(result.status, 416);
  assert.equal(result.headers.get('Content-Range'), 'bytes */12');
  assert.deepEqual(bucket.calls, [['head', entry.key]]);
});
test('unsupported ranges are ignored; malformed numeric values cannot overflow', () => {
  for (const value of ['items=0-1', 'bytes=1-2,4-5', 'bytes=-', 'bytes=999999999999999999999-']) {
    assert.equal(byteRange(value, bytes.length), null);
  }
  assert.equal(byteRange('bytes=-0', bytes.length), false);
});
test('HEAD ignores Range, checks existence and returns no body', async () => {
  const bucket = storage();
  const result = await serveMedia(request({ Range: 'bytes=0-3' }, 'HEAD'), bucket, entry);
  assert.equal(result.status, 200);
  assert.equal(result.headers.get('Content-Length'), '12');
  assert.equal(await result.text(), '');
  assert.deepEqual(bucket.calls, [['head', entry.key]]);
});
test('If-None-Match checks existence without downloading the object', async () => {
  const bucket = storage();
  const result = await serveMedia(request({ 'If-None-Match': `W/${etag}` }), bucket, entry);
  assert.equal(result.status, 304);
  assert.equal(result.headers.get('Content-Length'), null);
  assert.deepEqual(bucket.calls, [['head', entry.key]]);
});
test('conditional validators take precedence over Range', async () => {
  const result = await serveMedia(request({ 'If-None-Match': etag, Range: 'bytes=999-' }), storage(), entry);
  assert.equal(result.status, 304);
});
test('If-Range accepts strong matching validators and otherwise sends full content', async () => {
  for (const [validator, status] of [[etag, 206], ['"old"', 200], [`W/${etag}`, 200]]) {
    const result = await serveMedia(request({ Range: 'bytes=0-3', 'If-Range': validator }), storage(), entry);
    assert.equal(result.status, status);
    await result.body.cancel();
  }
});
test('unknown or incomplete objects fail without exposing other bucket objects', async () => {
  assert.equal((await serveMedia(request(), { get: async () => null }, entry)).status, 404);
  assert.equal((await serveMedia(request({}, 'POST'), storage(), entry)).status, 405);
});
