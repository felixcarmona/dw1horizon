// Numeric release filtering, without a browser.
import assert from 'node:assert/strict';
import { releasedVersions, compareVersions } from '../js/changelog.js';
const versions = ['1.0.0', '0.1.0', '0.0.10', '0.0.9', '0.0.1'].map((version) => ({ version }));
assert.deepEqual(releasedVersions(versions, 'v0.0.9').map((v) => v.version), ['0.0.9', '0.0.1']);
assert.deepEqual(releasedVersions(versions, 'v0.0.10').map((v) => v.version), ['0.0.10', '0.0.9', '0.0.1']);
assert.deepEqual(releasedVersions(versions, 'v0.0.0'), []);
for (const missing of [undefined, null, '', 'invalid']) assert.deepEqual(releasedVersions(versions, missing), versions);
assert.equal(compareVersions('v1.0.0', '0.99.99'), 1);
assert.equal(compareVersions('0.1.0', 'v0.1.0'), 0);
console.log('all ok: numeric changelog release filtering');
