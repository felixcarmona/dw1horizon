// Keep converted OPFS Files alive for this page, across builds and remembered-disc copies.
// A session lock protects them from other tabs. Next visit removes abandoned sessions.
let session;
export function conversionSession() {
  return session ||= (async () => {
    if (!navigator.locks || !navigator.storage?.getDirectory) return null;
    const root = await (await navigator.storage.getDirectory()).getDirectoryHandle('horizon-conversions', { create: true });
    for await (const [name] of root.entries()) {
      await navigator.locks.request(`horizon-convert-${name}`, { ifAvailable: true }, async lock => {
        if (lock) await root.removeEntry(name, { recursive: true }).catch(() => {});
      });
    }
    const name = crypto.randomUUID();
    return new Promise(resolve => {
      navigator.locks.request(`horizon-convert-${name}`, async () => {
        try { resolve(await root.getDirectoryHandle(name, { create: true })); }
        catch { resolve(null); return; }
        await new Promise(() => {}); // released by the browser when the page closes
      }).catch(() => resolve(null));
    });
  })().catch(() => null);
}
