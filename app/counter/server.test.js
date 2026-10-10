// Black-box tests: the server runs as a real child process on an ephemeral
// port and is exercised over HTTP, so this works from any cwd via
// `node --test app/counter`.

const test = require('node:test');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const net = require('node:net');
const path = require('node:path');

function getFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.on('error', reject);
    srv.listen(0, '127.0.0.1', () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

async function waitUntilHealthy(base) {
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${base}/health`);
      if (res.ok) return;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error('counter server did not become healthy within 10s');
}

async function postCount(base, body) {
  return fetch(`${base}/count`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

test('counter service (spawned, black-box)', async (t) => {
  const port = await getFreePort();
  const base = `http://127.0.0.1:${port}`;
  const child = spawn(process.execPath, [path.join(__dirname, 'server.js')], {
    env: { ...process.env, PORT: String(port) },
    stdio: 'ignore',
  });
  const exited = once(child, 'exit');
  t.after(async () => {
    if (child.exitCode === null) {
      child.kill('SIGTERM');
      await exited;
    }
  });

  await waitUntilHealthy(base);

  await t.test('GET /health reports ok', async () => {
    const res = await fetch(`${base}/health`);
    assert.equal(res.status, 200);
    assert.deepEqual(await res.json(), { status: 'ok' });
  });

  await t.test('POST /count counts words, characters, unique words', async () => {
    const res = await postCount(base, { text: 'the cat sat on the mat' });
    assert.equal(res.status, 200);
    assert.deepEqual(await res.json(), { words: 6, characters: 22, uniqueWords: 5 });
  });

  await t.test('counting is case-insensitive and strips edge punctuation', async () => {
    const res = await postCount(base, { text: 'Hello, hello! (World).' });
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.words, 3);
    assert.equal(body.uniqueWords, 2); // "Hello,"/"hello!" collapse to one
  });

  await t.test('repeated and edge whitespace does not create empty words', async () => {
    const res = await postCount(base, { text: '  a  b ' });
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.words, 2);
    assert.equal(body.characters, 7); // whitespace still counts as characters
    assert.equal(body.uniqueWords, 2);
  });

  await t.test('missing text is rejected with 400', async () => {
    const res = await postCount(base, {});
    assert.equal(res.status, 400);
    assert.deepEqual(await res.json(), { error: 'text is required' });
  });

  await t.test('non-string text is rejected with 400', async () => {
    const res = await postCount(base, { text: 123 });
    assert.equal(res.status, 400);
    assert.deepEqual(await res.json(), { error: 'text is required' });
  });
});
