# Error reports from the web builder: design (not implemented)

Status: proposal only. Nothing in the page sends anything anywhere today; the player can only copy the report
("Copy error report") and paste it where they want.

## What a report holds today

`copyReport` in `web/js/app.js`: the message in the player's language, the advice listed under it, the error's own
text (a browser exception or a Python traceback from inside Pyodide's virtual file system) and the build's log
(at most 1024 lines). The log's lines are: the browser line (user agent, cores, `navigator.deviceMemory`, worker
count), the room check, the engine version and download sizes, the base disc's release title and file count, one
line per job (name, seconds, heap, file sizes), and the failures.

The log holds no file names or paths of the player's discs, no checksums of their discs, and no disc data. The
error's own text can: a Python traceback from reading a disc names it as mounted in the worker
(`/disc/<the file's name>`, `/source-disc-<game>/<the file's name>`, `web/js/engine/worker.js` mountDisc), and a file
name may carry a person's name. So anything sent replaces those names with `<disc>` first, and any new log line goes
through the same review.

## Rules for any option

- Nothing is sent without a click on a button whose label says it sends, after the player has seen the exact text
  that would be sent (shown in the open Details or in a preview).
- Only what is listed above, plus the release id (`engine/current.json`: release version and engine version). No disc
  hashes, no file names, no paths outside the engine's own, no IP address kept by us, no cookies, no identifiers.
- Size cap (the last ~200 log lines); the disc file names replaced as said above, and the same replacement run again
  wherever the report is received, as a second guard.
- The privacy text on the page (`privacy.body`) is updated in all eight languages in the same change.

## Option A: a prefilled GitHub issue (no server)

A "Report on GitHub" link next to "Copy error report" opens
`https://github.com/<repo>/issues/new?template=web-builder.yml&title=...&body=...` with the error key, the release and
engine versions, the browser line, and the last ~40 log lines (URLs above ~8 KB get cut, so the body is trimmed and
the full report stays on the clipboard). The player sees the whole issue on GitHub before pressing Submit.

- Consent is GitHub's own submit button. Nothing touches our side.
- Needs a GitHub account; the issue is public (the report has nothing personal, but the player's GitHub name is on it).
- Work: an issue form `.github/ISSUE_TEMPLATE/web-builder.yml` and about 20 lines in `app.js`.

## Option B: Discord, as now, made easier (no server)

"Copy error report" plus a link to the Discord server's reports channel, with one line saying to paste it there. This
is the path players already take (the report in this branch comes from Discord); the change is only a link and the
copied text starting with a short header (release, error key, browser line) so the first screen of a long paste says
what matters.

- No account beyond Discord; no structure, the tracker is still read by hand.
- Work: a few lines in `app.js` and one string in eight languages.

## Option C: an opt-in "Send this report" button (needs a server)

The page POSTs the report (JSON: error key, versions, browser line, log tail) to an endpoint, which files it as an
issue in a private tracker or posts it to a private Discord channel through a webhook.

- The site is static (GitHub Pages): it cannot receive anything. The endpoint is a separate service, e.g. a small
  serverless function. The page must never hold a GitHub token or webhook URL; only the function holds them.
- The function: accepts only `Origin: https://dw1horizon.com`, caps the size (e.g. 64 KB), rate-limits per client
  without storing addresses (or puts a CAPTCHA-free proof of work in front), drops the request's IP before storing,
  validates the JSON shape, and replaces disc file names again. Reports are kept for a fixed time (e.g. 90 days).
- The page shows the exact JSON before sending and a "Sent" / "Could not send, copy it instead" result. A failed
  send never retries on its own.
- Work: the function, its secret configuration and monitoring, the privacy text, and the page side (about 60 lines).
  It is the only option that adds something to keep running.

## Recommendation

Do A and B together first: both are a link next to the existing button, neither needs a server or a secret, and the
player sends the report themselves on a site they already trust. Count how many reports arrive and how complete they
are for a release or two. Consider C only if reports are lost because players will not use GitHub or Discord, and
then as a serverless function, separate from any machine that hosts or builds the project.
