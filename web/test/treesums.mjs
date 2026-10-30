// web/test (the engine's tests, not deployed); puppeteer-core from build/stage9/node/node_modules (npm i puppeteer-core there).
// node treesums.mjs PROFILE OUT.json: the SHA-1 of every file of the last build's OPFS tree (page left by ?keep), by path
import puppeteer from './browser.mjs';
import fs from 'node:fs';
const [profile, out] = process.argv.slice(2);
const b = await puppeteer.launch({ executablePath: process.env.CHROMIUM || '/snap/bin/chromium', headless: 'new', userDataDir: profile, args: ['--no-sandbox'], protocolTimeout: 0 });
const p = await b.newPage();
await p.goto(process.env.URL || 'http://127.0.0.1:8799/favicon.svg');
const r = await p.evaluate(async () => {
  const out = {};
  const walk = async (d, pre) => {
    for await (const [n, h] of d.entries()) {
      if (h.kind === 'directory') await walk(h, `${pre}${n}/`);
      else {
        const buf = await (await h.getFile()).arrayBuffer();
        const dg = new Uint8Array(await crypto.subtle.digest('SHA-1', buf));
        out[pre + n] = [...dg].map((x) => x.toString(16).padStart(2, '0')).join('');
      }
    }
  };
  const root = await (await navigator.storage.getDirectory()).getDirectoryHandle('horizon-build');
  await walk(await root.getDirectoryHandle('tree'), '');
  // (a job's outputs are under @<token>/: the registry the page left says which version of each path is the last)
  if (!out['registry.json']) return out;
  const tree = await root.getDirectoryHandle('tree');
  const reg = JSON.parse(await (await (await tree.getFileHandle('registry.json')).getFile()).text());
  return Object.fromEntries(Object.entries(reg).map(([p, loc]) => [p, out[loc]]));
});
fs.writeFileSync(out, JSON.stringify(r));
console.log(Object.keys(r).length, 'files');
await b.close();
