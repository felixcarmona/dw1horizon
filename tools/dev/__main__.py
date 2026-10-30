"""Developer commands: python3 -m tools.dev build [options]."""
import sys

if len(sys.argv) > 1 and sys.argv[1] == 'build':
    from .build import main
    main(sys.argv[2:])
else:
    raise SystemExit('usage: python3 -m tools.dev build [--lang en] [--run] [--no-cache]')
