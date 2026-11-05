// Files are snapshots: after a backing file changes, obtain the directory, handle and File again.
export const staleFile = (error) => /InvalidStateError|NotReadableError/.test(String(error?.name || '') + ' ' + String(error));

export async function retryFile(label, read, onRetry = () => {}) {
  for (let attempt = 0; ; attempt++) {
    try { return await read(); }
    catch (error) {
      if (!staleFile(error)) throw error;
      if (attempt) throw new DOMException(`${label}: ${error.message || error}`, 'NotReadableError');
      onRetry(`The browser lost access to ${label}; reopening it and retrying once.`);
    }
  }
}

export async function buildDirectory(path = '', create = false) {
  let dir = await (await navigator.storage.getDirectory()).getDirectoryHandle('horizon-build', { create });
  for (const part of path.split('/').filter(Boolean)) dir = await dir.getDirectoryHandle(part, { create });
  return dir;
}

export async function discFile(disc) {
  if (!disc.path) return disc; // compatibility with callers that supply a File
  const parts = disc.path.split('/');
  const dir = await buildDirectory(parts.slice(0, -1).join('/'));
  return new File([await (await dir.getFileHandle(parts.at(-1))).getFile()], disc.name);
}

// Copy in bounded chunks before long jobs start. The copies stay immutable until the disc writer finishes.
export async function snapshotDisc(file, game, { handle, check = () => {}, log } = {}) {
  return retryFile(`input disc ${game}`, async () => {
    check();
    const source = handle ? await handle.getFile() : file;
    if (source.size !== file.size) throw new DOMException('The selected disc changed. Select the disc again.', 'NotReadableError');
    const dir = await buildDirectory('inputs', true);
    const output = await (await dir.getFileHandle(game, { create: true })).createWritable();
    try {
      for (let at = 0; at < source.size; at += 8 << 20) {
        check();
        await output.write(await source.slice(at, at + (8 << 20)).arrayBuffer());
      }
      check();
      await output.close();
    } catch (error) {
      try { await output.abort(); } catch { /* already closed */ }
      throw error;
    }
    return { path: `inputs/${game}`, name: file.name };
  }, log);
}
