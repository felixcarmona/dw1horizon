#!/usr/bin/env python3
"""Play Bonus Try after normal and x5 training at every gym on a built disc.

Care, starting stats and the screen are fixtures. Native dialogue selections,
exercise setup, reels, awards, tally, script completion and field return execute
real game code. The first exercise animation is skipped through pad input.
"""

import argparse
import json
import os
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.load_camera import card_fixture
from tools.dev.playtest.training_evolution import call
from tools.dev.playtest.training_care_hud import care
from tools.dev.playtest.training_gains import stats, six
from tools.langpatch import elf_symbols

CASES = (
    [(112, "TRN", g) for g in ("Hp", "Mp", "Offense", "Defense", "Speed", "Brains")]
    + [(78, "TRN", g) for g in ("Offense", "Speed")]
    + [(119, "TRN", "Brains")]
    + [(107, "TRN2", g) for g in ("Hp", "Offense")]
    + [(108, "TRN2", g) for g in ("Defense", "Speed")]
    + [(99, "TRN2", g) for g in ("Hp", "Defense")]
    + [(165, "TRN2", "Mp")]
)


def prepare(e, screen, prefix, gym, mode):
    e.gs(
        "set",
        "gametime_running=0",
        "hour=10",
        "minute=0",
        "partner.para.condition=0",
        "partner.para.tiredness=0",
        "partner.para.foodLevel=2000",
        "partner.para.poopLevel=500",
        "partner.para.energyLevel=500",
        "partner.para.evoTimer=0",
        "partner.para.age=1",
        "partner.para.remainingLifetime=1000",
        "partner.para.sleepyHour=23",
        "partner.para.sleepyMinute=0",
        "partner.para.virusBar=0",
        "partner.stats.hp=1000",
        "partner.stats.mp=1000",
        "partner.stats.currentHP=1000",
        "partner.stats.currentMP=1000",
        "partner.stats.off=100",
        "partner.stats.def=100",
        "partner.stats.speed=100",
        "partner.stats.brain=100",
    )
    e.poke("CURRENT_FRAME", struct.pack("<H", 12000))
    e.poke("LAST_HANDLED_FRAME", struct.pack("<H", 12000))
    section = (
        5
        if screen == 119
        else (
            82
            if screen == 165
            else 81
            + {"Hp": 0, "Mp": 1, "Offense": 2, "Defense": 3, "Speed": 4, "Brains": 5}[
                gym
            ]
        )
    )
    row = {0: 0, 2: 1, 1: 2}[mode]
    e.run(
        "lua",
        f"""GY={{awards=0,slots=0,done=false,started=false,menus=0}}
 GY.b=PCSX.addBreakpoint({e.A(prefix+'_modBlockNext')},'Exec',4,'gym-award',function() GY.awards=GY.awards+1 end)
 GY.s=PCSX.addBreakpoint({e.A(prefix+'_startSlotSession')},'Exec',4,'gym-slot',function() GY.slots=GY.slots+1 end)
 GY.t=PCSX.addBreakpoint({e.A(prefix+'_modOpenStatsBox')},'Exec',4,'gym-tally',function() GY.done=true end)
 GY.start=PCSX.addBreakpoint({e.A(prefix+'_setup'+gym+'Training')},'Exec',4,'gym-setup',function() GY.started=true end)
 GY.sel=PCSX.addBreakpoint({e.A('tickSelectionDialogue')},'Exec',4,'gym-choice',function()
  local m=PCSX.getMemPtr();local b={e.A('DIALOGUE_SELECTION')&0x1fffff}
  local count=tonumber(m[b+8]);local a={e.A('SCRIPT_POINTER') & 0x1fffff}
  local key=tonumber(m[a])+256*tonumber(m[a+1])+65536*tonumber(m[a+2])+16777216*tonumber(m[a+3])
  if GY.lastChoice~=key then GY.menus=GY.menus+1;GY.lastChoice=key end
  local selection=count==4 and {row} or 0
  if {screen}==119 and GY.menus==1 then selection=1 end
  m[b+10]=selection;m[b+11]=0
 end)""",
    )
    e.poke("TALKED_TO_ENTITY", bytes([2]))
    call(e, "callScriptSection", e.peek("CURRENT_SCRIPT_ID", "H"), section, 1)
    e.run("resume")


def finish(e, out, label, prefix, bonus, expected):
    slot = prefix + "_SLOT_MACHINE"
    deadline = time.monotonic() + 110
    seen = []
    payout = None
    cancel = "CROSS" if e.peek("MOD_OPT_BUTTONS", "i") else "TRIANGLE"
    cancel_held = False
    while time.monotonic() < deadline:
        done = e.run("lua", "return GY.done").strip() == "true"
        started = e.run("lua", "return GY.started").strip() == "true"
        if not started:
            e.press("CONFIRM", 12)
            continue
        if bonus:
            ram = e.ram()
            st = e.peek(slot + "+6", "h", ram)
            if st not in seen:
                seen.append(st)
            if st >= 5:
                payout = e.peek(slot + "+2", "h", ram)
            if st in (1, 2, 3):
                e.press("CONFIRM", 12)
            else:
                e.wait(0.15)
        else:
            # A held Cancel skips the first exercise once it reaches its input
            # state. Release after its award; avoid creating a Vsync listener
            # for every poll during the approach walk.
            awarded = int(e.run("lua", "return GY.awards").strip()) > 0
            if not awarded and not cancel_held:
                e.api("/api/v1/lua/press?button=" + cancel)
                cancel_held = True
            elif awarded and cancel_held:
                e.api("/api/v1/lua/release?button=" + cancel)
                cancel_held = False
            e.wait(0.15)
        if done:
            break
    else:
        raise AssertionError((label, "no tally", seen))
    if cancel_held:
        e.api("/api/v1/lua/release?button=" + cancel)
    for _ in range(160):
        if e.peek("UI_BOX_DATA+54", "h") == 1:
            break
        e.wait(0.1)
    e.run("pause")
    pending = six(e, "STATS_GAINS")
    initial = six(e, "INITIAL_COMBAT_STATS")
    count = int(e.run("lua", "return GY.awards").strip())
    slots = int(e.run("lua", "return GY.slots").strip())
    e.run("shot", str(out / (label + "-tally.png")))
    e.run(
        "lua",
        "GY.b:remove();GY.s:remove();GY.t:remove();GY.start:remove();GY.sel:remove();PCSX.resumeEmulator()",
    )
    e.press("CONFIRM", 12)
    for _ in range(300):
        r = e.ram()
        if (
            e.peek("TAMER_STATE", "b", r) == 0
            and e.peek("IS_SCRIPT_PAUSED", "i", r) == 1
            and e.peek("ACTIVE_INSTRUCTION", "B", r) == 0
            and e.peek("TRAINING_COMPLETE", "i", r) == 0
        ):
            break
        e.wait(0.1)
    else:
        raise AssertionError(label + " field return")
    e.wait(0.25)
    e.run("pause")
    after = stats(e)
    row = dict(
        label=label,
        awards=count,
        slots=slots,
        reel_states=seen,
        payout=payout,
        pending=pending,
        initial=initial,
        after=after,
        care=care(e),
    )
    print(json.dumps(row), flush=True)
    assert count == expected, row
    assert slots == (1 if bonus else 0), row
    assert row["care"]["evoTimer"] == expected, row
    assert after == [a + b for a, b in zip(initial, pending)], row
    if bonus:
        assert payout in (5, 20, 40, 100), row
    return row


def run(args):
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    e = ProofEmu(args.disc, args.exe, args.port, str(out / "emu"))
    e.env["EMU_ARGS"] = "-interpreter -debugger"
    for name, (address, _, _) in elf_symbols(args.exe + ".elf").items():
        e.table.setdefault(name, address)
    results = []
    try:
        card = card_fixture(out, 112, [650, 0, 750], 3, False, 1, 0)
        e.start(str(card))
        if args.state:
            e.run("load", str(args.state.resolve()))
            e.run("resume")
            assert e.in_control()
        else:
            assert e.continue_game() == 0
        e.run("save", str(out / "boot.state"))
        for screen, prefix, gym in [c for c in CASES if c[0] in args.screens]:
            for mode in (0, 2):
                e.run("load", str(out / "boot.state"))
                e.run("resume")
                if screen == 119:
                    # Teacher placement after the introduction; the optional
                    # legend conversation must not replace the gym menu.
                    for flag, value in ((147, 1), (148, 1), (732, 1), (756, 0)):
                        e.gs("trigger", str(flag), str(value))
                assert e.warp(screen)
                e.run("pause")
                name = f"{screen}-{gym}-after-" + ("normal" if mode == 0 else "x5")
                prepare(e, screen, prefix, gym, mode)
                results.append(
                    finish(
                        e, out, name + "-prior", prefix, False, 1 if mode == 0 else 5
                    )
                )
                prepare(e, screen, prefix, gym, 1)
                results.append(finish(e, out, name + "-bonus", prefix, True, 1))
                (out / "gym.json").write_text(json.dumps(results, indent=2) + "\n")
    except BaseException:
        e.run("shot", str(out / "gym-failure.png"), check=False)
        e.run("save", str(out / "gym-failure.state"), check=False)
        raise
    finally:
        e.stop()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("disc")
    p.add_argument("--exe", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--port", type=int, default=42421)
    p.add_argument("--state", type=Path, help="field checkpoint from this exact disc")
    p.add_argument(
        "--screens",
        type=lambda s: set(map(int, s.split(","))),
        default={112, 78, 119, 107, 108, 99, 165},
    )
    run(p.parse_args())


if __name__ == "__main__":
    main()
