// web/test (not deployed): the time-left estimate of js/engine/engine.js (jobsEstimate), in Node, no browser.
//   node web/test/estimate.mjs
// It plays the plan's schedule forward: a chain of jobs is as long as its jobs added up whatever the workers, the
// bound "longest path or work over the workers" was shorter than what the build then took.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const web = path.join(path.dirname(new URL(import.meta.url).pathname), '..');
const src = fs.readFileSync(path.join(web, 'js/engine/engine.js'), 'utf8');
const m = src.match(/  jobsEstimate\(jobs, n, ran = new Map\(\)\) \{[\s\S]*?\n  \}\n/);
assert.ok(m, 'jobsEstimate not found');
const { jobsEstimate } = new Function(`return {${m[0]}}`)();

const rest = (jobs) => {                      // prio: the longest path to the end, as build_engine.py makes it
  const users = new Map(jobs.map((j) => [j.id, []]));
  for (const j of jobs) for (const d of j.deps) users.get(d).push(j.id);
  const by = new Map(jobs.map((j) => [j.id, j]));
  for (const j of [...jobs].reverse()) j.prio = j.est + Math.max(0, ...users.get(j.id).map((u) => by.get(u).prio));
  return jobs;
};
const job = (id, est, deps = [], part = 'unit') => ({ id, est, deps, part, prio: 0 });

// independent jobs: the work over the workers
let jobs = rest([0, 1, 2, 3, 4, 5].map((i) => job(i, 10)));
assert.equal(jobsEstimate(jobs, 3), 20);
assert.equal(jobsEstimate(jobs, 6), 10);
assert.equal(jobsEstimate(jobs, 1), 60);

// a chain stays a chain however many workers there are, and the others fill in beside it
jobs = rest([job(0, 10), job(1, 10, [0]), job(2, 10, [1]), job(3, 5), job(4, 5), job(5, 5)]);
assert.equal(jobsEstimate(jobs, 4), 30);
// a job that waits for a long one: the old bound said 20 (work 40 / 2 workers, path 20), the schedule takes 30
jobs = rest([job(0, 20), job(1, 5), job(2, 5, [1]), job(3, 5, [0]), job(4, 5, [2])]);
assert.equal(jobsEstimate(jobs, 2), 25);
// the finishes run one at a time
jobs = rest([job(0, 1), job(1, 10, [0], 'finish'), job(2, 10, [0], 'finish')]);
assert.equal(jobsEstimate(jobs, 4), 21);
// jobs already running keep their workers and count what they have run
jobs = rest([job(0, 10), job(1, 10), job(2, 10)]);
assert.equal(jobsEstimate(jobs, 2, new Map([[2, 4]])), 16);
assert.equal(jobsEstimate([], 2), 0);

// the release's own plan, if a built one is at hand: never less than the old bound, the same work with one worker
const plan = process.argv[2];
if (plan) {
  const p = JSON.parse(fs.readFileSync(plan, 'utf8'));
  const work = p.jobs.reduce((a, j) => a + j.est, 0);
  assert.ok(Math.abs(jobsEstimate(p.jobs, 1) - work) < 1e-6);
  for (const n of [2, 4, 6]) {
    const t = jobsEstimate(p.jobs, n);
    assert.ok(t >= Math.max(Math.max(...p.jobs.map((j) => j.prio)), work / n) - 1e-6);
    console.log(`${n} workers: ${(t / 60).toFixed(1)} min`);
  }
}
console.log('estimate ok');
