"""python3 -m tools.models.babies check | encode ID MMD TIM (see the package docstring)."""
import sys

from tools.models.babies import main

sys.exit(main(sys.argv[1:]))
