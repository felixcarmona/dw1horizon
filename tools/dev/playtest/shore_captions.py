#!/usr/bin/env python3
"""Capture the real Whamon ferry caption in every selected language.

The private card and quest flags choose the repeat ferry offer. Native city
section 55 (a regular interaction, not an event that suppresses captions) walks
to Whamon, asks the question and warps to screen 309. Only the choice is seeded;
normal script, file paging, caption cache and rendering execute real game code.
"""

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.load_camera import card_fixture
from tools.dev.playtest.training_evolution import call
from tools.langpatch import elf_symbols
from tools.localize.captions import names, encode
from tools.languages import CODES


def run(args):
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    wide = args.ram8
    e = ProofEmu(args.disc, args.exe, args.port, str(out / "emu"))
    e.env["EMU_ARGS"] = "-interpreter -debugger" + (" -8mb" if wide else "")
    if wide:
        e.ram = lambda: e.api("/api/v1/cpu/ram/raw")[:0x200000]
    for n, (a, _, _) in elf_symbols(args.exe + ".elf").items():
        e.table.setdefault(n, a)
    languages = (
        args.languages.split(",") if args.languages else CODES[: 9 if wide else 8]
    )
    rows = []
    try:
        e.start(str(card_fixture(out, 112, [650, 0, 750], 3, False, 1, 0)))
        if args.state:
            e.run("load", str(args.state.resolve()))
            e.run("resume")
            assert e.in_control()
        else:
            assert e.continue_game() == 0
        e.run("save", str(out / "boot.state"))
        for language in languages:
            lang = CODES.index(language)
            assert lang != 8 or wide, "Chinese requires --ram8"
            e.run("load", str(out / "boot.state"))
            e.run("resume")
            call(e, "modSetLanguage", lang)
            ptr = call(e, "getScreenCaption", 309) & 0x1FFFFF
            actual = e.ram()[ptr : ptr + 36].split(b"\0")[0]
            expected = encode(
                names(CODES[lang])["screen.caption.drowned_shore"], CODES[lang]
            )
            for flag in [224, 751, 736, 735]:
                e.gs("trigger", str(flag), "1")
            e.run("resume")
            assert e.warp(168)
            e.run("pause")
            e.run(
                "lua",
                f"""CAP={{n=0,done=false,arrival=false}}
     CAP.sel=PCSX.addBreakpoint({e.A('tickSelectionDialogue')},'Exec',4,'ferry-yes',function()
       local m=PCSX.getMemPtr();m[{(e.A('DIALOGUE_SELECTION')+10)&0x1fffff}]=0
     end)
     CAP.render=PCSX.addBreakpoint({e.A('renderMapName')},'Exec',4,'ferry-caption',function()
       if PCSX.getRegisters().GPR.n.a0==309 then
         CAP.arrival=true;CAP.n=CAP.n+1
         if CAP.n==6 then CAP.done=true;PCSX.pauseEmulator() end
       end
     end)""",
            )
            call(e, "callScriptSection", e.peek("CURRENT_SCRIPT_ID", "H"), 55, 0)
            e.run("resume")
            deadline = time.monotonic() + 100
            while time.monotonic() < deadline:
                if e.run("lua", "return CAP.done").strip() == "true":
                    break
                e.run("press", "CIRCLE", "8")
                e.wait(0.2)
            else:
                raise AssertionError(f"ferry caption absent: {CODES[lang]}")
            e.run("shot", str(out / f"ferry-{CODES[lang]}-caption.png"))
            e.run("lua", "CAP.sel:remove();CAP.render:remove();PCSX.resumeEmulator()")
            assert e.in_control()
            row = dict(
                language=CODES[lang],
                actual=actual.hex(),
                expected=expected.hex(),
                translated=actual == expected,
                screen=e.peek("CURRENT_SCREEN", "h"),
                ram8=wide,
            )
            rows.append(row)
            print(json.dumps(row), flush=True)
            assert row["screen"] == 309, row
            if args.before:
                assert actual == b"Drowned Shore", row
            else:
                assert row["translated"], row
            (out / "captions.json").write_text(json.dumps(rows, indent=2) + "\n")
    finally:
        e.stop()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("disc")
    p.add_argument("--exe", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--port", type=int, default=42423)
    p.add_argument("--ram8", action="store_true")
    p.add_argument("--state", type=Path, help="field checkpoint from this exact disc")
    p.add_argument(
        "--languages",
        help="comma-separated language codes; defaults to all supported by this RAM size",
    )
    p.add_argument(
        "--before",
        action="store_true",
        help="expect the old English caption in every language",
    )
    run(p.parse_args())


if __name__ == "__main__":
    main()
