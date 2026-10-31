#!/usr/bin/env python3
"""Reference checker: every file or folder the documentation and the scripts name must exist.

    python3 tools/checkrefs.py            # exit 1 and a list when something is dead
    python3 tools/checkrefs.py -v         # also print what was skipped

Checked
  * Markdown links `[text](relative/path.md#anchor)` in every tracked `.md` (the file is looked up next to
    the document; local heading fragments are checked too);
  * repository paths written in backticks or code in `.md`, `.py`, `.sh` and `.dws` files when they start with
    a top-level folder of the repository (`tools/`, `docs/`, `mods/`, `story/`, `content/`) or are
    `README.md`. Globs (`*`), placeholders (`<..>`, `NAME`, `NNNN`, `{..}`) and a trailing `...` are skipped.
Not checked: paths into build/, extracted/, imported/, decomp/ (generated, ignored or submodules)."""
import os, re, subprocess, sys
from urllib.parse import unquote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP = ('tools', 'docs', 'mods', 'story', 'content')
SKIP_DIRS = ('decomp/', 'build/', 'extracted/', 'imported/', 'text/us/', 'text/jp/', 'text/jp-rev1/', 'text/es-fan/', 'mods/patches/', 'content/species/',
             'docs/data/story-analysis/', 'story/base/',
             # the private inputs (docs/building.md): ignored by git, present only where they were copied
             'mods/experimental/motion/v61-models/files', 'content/localized/signs/sized', 'content/localized/tournament/sized')
FOREIGN = ()
DESIGN_DOCS = ()
# Optional research inventories are generated or supplied separately, outside the source build.
OPTIONAL_REFERENCES = {
    # Full-resolution example art is supplied locally; see tools/maps/examples/README.md.
    'story/mods/what-the-island-forgot/art/full/engine-room-2304x1856.png',
    'story/mods/what-the-island-forgot/art/full/the-new-street-2304x1856.jpg',
    'docs/data/crossgame-models.csv', 'docs/data/crossgame-identified.csv',
    'docs/data/crossgame-sources.csv', 'content/motion-loop-contracts.json',
    # web/README.md, relative to web/: the release workflow writes it (tools/site_digimon.py) and git ignores it.
    'content/digimon.json',
}
PATH = re.compile(r'(?<![\w/.:-])((?:%s)/[\w./+-]*[\w/])' % '|'.join(TOP))
LINK = re.compile(r'\[[^\]]*\]\(([^)\s]+)\)')
PLACEHOLDER = re.compile(r'[*<>{}$]|\bNAME\b|\bRELEASE\b|\bNNN|\bXXX|\bN\b|\bID\b|\bZONE\b|\bMOD\b|\.\.\.|\bX\b|<|\bFILE\b')

# Frozen motion evidence retains the producer paths it used. Resolve the move and still require the current file.
RELOCATIONS = {
    'tools/modeldelta.py': 'tools/models/delta.py',
    'tools/v61edit.py': 'tools/models/edit.py',
    'tools/v61delta.py': 'tools/models/verify_deltas.py',
    'tools/v61imports.py': 'tools/models/audit_origins.py',
    'content/models/v61/': 'content/models/imports/',

    'mods/experimental/batch-import/': 'content/imports/',
    'mods/tools': 'mods/experimental/motion/history/recovery-2026-10-27/tools',
}


def tracked():
    out = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard'], cwd=ROOT, capture_output=True, text=True).stdout
    return [f for f in out.split('\n') if f and not f.startswith(('decomp/',)) and os.path.exists(os.path.join(ROOT, f))]


def exists(rel):
    for old, new in RELOCATIONS.items():
        if old.endswith('/') and rel == old.rstrip('/'):
            rel = new.rstrip('/')
            break
        if rel == old or (old.endswith('/') and rel.startswith(old)):
            rel = new + rel[len(old):]
            break
    return os.path.exists(os.path.join(ROOT, rel))


def headings(path):
    """GitHub-style Markdown heading IDs, including repeated headings."""
    try:
        with open(os.path.join(ROOT, path), encoding='utf-8') as source:
            text = source.read()
    except (OSError, UnicodeError):
        return set()
    ids, seen, fenced = set(), {}, False
    for line in text.splitlines():
        if line.lstrip().startswith(('```', '~~~')):
            fenced = not fenced
        if fenced or not re.match(r'^#{1,6} ', line):
            continue
        title = re.sub(r' +#+$', '', line.lstrip('#').strip())
        title = re.sub(r'<[^>]*>', '', title).lower()
        slug = re.sub(r'[^\w\- ]', '', title).replace(' ', '-')
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        ids.add(slug + (f'-{count}' if count else ''))
    ids.update(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)', text))
    return ids


def check_file(rel, verbose):
    bad, skipped = [], []
    try:
        with open(os.path.join(ROOT, rel), encoding='utf-8') as source:
            text = source.read()
    except (UnicodeDecodeError, OSError):
        return bad, skipped
    here = os.path.dirname(rel)
    for n, line in enumerate(text.split('\n'), 1):
        if rel.endswith('.md'):
            for m in LINK.finditer(line):
                target = unquote(m.group(1))
                if re.match(r'[a-z]+:', target): continue
                t, _, anchor = target.partition('#')
                p = os.path.normpath(os.path.join(here, t)) if t else rel
                if not exists(p): bad.append((rel, n, f'link {t}'))
                elif anchor and p.endswith('.md') and anchor not in headings(p):
                    bad.append((rel, n, f'fragment {target}'))
        # Index entries name tools relative to tools/; content indexes name their
        # own subdirectories. Check these concrete spans without interpreting
        # arbitrary command output or generated-file examples as source paths.
        if rel in ('tools/README.md', 'content/README.md'):
            index_text = line.split('|')[1] if rel == 'content/README.md' and line.startswith('|') else line
            for span in re.findall(r'`([^`]+)`', index_text):
                if not re.fullmatch(r'[\w./-]+', span) or '*' in span:
                    continue
                if '/' not in span and not span.endswith(('.py', '.sh')):
                    continue
                candidate = os.path.normpath(os.path.join(here, span))
                if span.startswith(TOP) or exists(span):
                    continue
                if not exists(candidate):
                    bad.append((rel, n, f'index path {span}'))
        for m in PATH.finditer(line):
            p = m.group(1).rstrip('/.')
            if rel in DESIGN_DOCS or p in FOREIGN or re.fullmatch(r'docs/\d\d', p) or exists(p + '.py') or exists(p.rsplit('.', 1)[0] + '.py'): continue
            if p in OPTIONAL_REFERENCES or any(p.startswith(d) for d in SKIP_DIRS) or PLACEHOLDER.search(line[m.start():m.end() + 3]):
                skipped.append((rel, n, p)); continue
            if p.rstrip('/') in TOP: continue
            tail = line[m.end():m.end() + 1]
            if re.match(r'[`)]?\s+there\b', line[m.end():]): continue          # a path in another project
            if tail in ('*', '<', '{'): skipped.append((rel, n, p)); continue
            if not exists(p) and not exists(os.path.join(here, p)):
                if re.search(r'\.[a-z]{1,4}$', p) or os.path.isdir(os.path.join(ROOT, os.path.dirname(p))):
                    bad.append((rel, n, p))
    return bad, skipped


def main():
    verbose = '-v' in sys.argv
    bad_all = []
    for rel in tracked():
        if rel.endswith(('.md', '.py', '.sh', '.dws', '.lua')) and rel != 'tools/checkrefs.py' and not rel.startswith(('mods/patches/', 'mods/experimental/scale/main-repo')):
            bad, skipped = check_file(rel, verbose)
            bad_all += bad
            if verbose:
                for s in skipped: print('skip', *s)
    for rel, n, what in bad_all:
        print(f'{rel}:{n}: missing {what}')
    print(f'{len(bad_all)} dead reference(s)')
    return 1 if bad_all else 0


if __name__ == '__main__':
    sys.exit(main())
