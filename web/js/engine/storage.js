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

// External handles can lose permission independently of persistent browser storage.
// Call this from the picker/permission click when possible; a later prompt may be refused.
export async function selectedFile(handle) {
  for (let attempt = 0; ; attempt++) {
    if (typeof handle.queryPermission === 'function') {
      let permission = await handle.queryPermission({ mode: 'read' });
      if (permission !== 'granted' && typeof handle.requestPermission === 'function') {
        permission = await handle.requestPermission({ mode: 'read' });
      }
      if (permission !== 'granted') throw new DOMException('Disc read permission was refused.', 'NotAllowedError');
    }
    try { return await handle.getFile(); } catch (error) {
      if (attempt || !discReadFailure(error)) throw error;
    }
  }
}

const discReadFailure = (error) => staleFile(error)
  || ['NotAllowedError', 'SecurityError', 'NotFoundError'].includes(error?.name);

export class InputDiscError extends Error {
  constructor(game, cause) { super(`input disc ${game}: ${cause}`); this.name = 'InputDiscError'; this.cause = cause; }
}

// Copy the selected File first: handles are for remembering discs and recovering stale Files.
// Copy in bounded chunks before long jobs start. The copies stay immutable until the disc writer finishes.
export async function snapshotDisc(file, game, { handle, check = () => {}, log = () => {} } = {}) {
  let source = file;
  for (let attempt = 0; ; attempt++) {
    check();
    const dir = await buildDirectory('inputs', true);
    const output = await (await dir.getFileHandle(game, { create: true })).createWritable();
    try {
      for (let at = 0; at < source.size; at += 8 << 20) {
        check();
        let bytes;
        try { bytes = await source.slice(at, at + (8 << 20)).arrayBuffer(); }
        catch (error) {
          if (!discReadFailure(error)) throw error;
          throw new InputDiscError(game, error);
        }
        await output.write(bytes);
      }
      check();
      await output.close();
    } catch (error) {
      try { await output.abort(); } catch { /* already closed */ }
      // Output permission/quota errors and cancellation belong to the storage/build path.
      if (!(error instanceof InputDiscError) || attempt) throw error;
      log(`The browser lost access to input disc ${game}; retrying once with the selected file or a permitted handle.`);
      if (handle) {
        try {
          const fresh = await selectedFile(handle);
          if (fresh.size !== file.size || fresh.lastModified !== file.lastModified) {
            throw new InputDiscError(game, 'The selected disc changed. Select the disc again.');
          }
          source = fresh;
        } catch (reopenError) {
          if (reopenError instanceof InputDiscError) throw reopenError;
          // Android/providers may refuse handles while the original File remains readable.
          source = file;
        }
      }
      continue;
    }
    return { path: `inputs/${game}`, name: file.name };
  }
}
