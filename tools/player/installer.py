#!/usr/bin/env python3
"""A Windows setup wizard with Horizon Play and a built disc inside (docs/player.md, "A setup wizard").

    python3 tools/player/installer.py --player "Horizon Play" --disc DISC.cue --out Setup.exe

--player is a Windows Horizon Play folder (tools/player/build.py on Windows, or `_internal/player` of the desktop
patcher's zip). The wizard installs for the current user only (no administrator), into
%LOCALAPPDATA%\\Programs\\<name>, with Start menu and desktop shortcuts and an entry in Windows' installed apps; the
uninstaller leaves the saves (Horizon Play keeps them in %APPDATA%\\Horizon\\Horizon). It is made with NSIS: makensis
from the PATH, else in a Docker ubuntu:24.04 container.

The disc is the player's own game: the result is for the people who own it, never for a release or a public page.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'patcher', 'app'))
import make_icons  # noqa: E402

NSI = r'''Unicode true
SetCompressor /SOLID lzma
Name "{name}"
OutFile "Setup.exe"
RequestExecutionLevel user
InstallDir "$LOCALAPPDATA\Programs\{name}"
InstallDirRegKey HKCU "Software\{key}" "InstallDir"
VIProductVersion "{vi}"
VIAddVersionKey "ProductName" "{name}"
VIAddVersionKey "ProductVersion" "{version}"
VIAddVersionKey "FileDescription" "{name} setup"
VIAddVersionKey "FileVersion" "{version}"

!include "MUI2.nsh"
!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION Play
!define MUI_FINISHPAGE_RUN_TEXT "Play now"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Spanish"

Function Play
  SetOutPath "$INSTDIR"
  Exec '"$INSTDIR\horizon-play.exe" "$INSTDIR\{disc}.cue"'
FunctionEnd

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "app\*.*"
  File "icon.ico"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\{name}.lnk" "$INSTDIR\horizon-play.exe" '"$INSTDIR\{disc}.cue"' "$INSTDIR\icon.ico"
  CreateShortcut "$SMPROGRAMS\{name}.lnk" "$INSTDIR\horizon-play.exe" '"$INSTDIR\{disc}.cue"' "$INSTDIR\icon.ico"
  WriteRegStr HKCU "Software\{key}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "{unkey}" "DisplayName" "{name}"
  WriteRegStr HKCU "{unkey}" "DisplayVersion" "{version}"
  WriteRegStr HKCU "{unkey}" "DisplayIcon" "$INSTDIR\icon.ico"
  WriteRegStr HKCU "{unkey}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "{unkey}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "{unkey}" "NoModify" 1
  WriteRegDWORD HKCU "{unkey}" "NoRepair" 1
  WriteRegDWORD HKCU "{unkey}" "EstimatedSize" {kb}
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\{name}.lnk"
  Delete "$SMPROGRAMS\{name}.lnk"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "{unkey}"
  DeleteRegKey HKCU "Software\{key}"
SectionEnd
'''


def cue_bins(cue):
    """The files a cue names, in its folder."""
    out = []
    for line in open(cue, encoding='utf-8', errors='replace'):
        s = line.strip()
        if s.upper().startswith('FILE '):
            name = s[5:].rsplit(' ', 1)[0].strip().strip('"')
            out.append(os.path.join(os.path.dirname(os.path.abspath(cue)), name))
    if not out:
        sys.exit(f'{cue}: no FILE line')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--player', required=True, help='a Windows Horizon Play folder (with horizon-play.exe)')
    ap.add_argument('--disc', required=True, help='the built disc: its .cue (the files it names go in too)')
    ap.add_argument('--out', required=True, help='the setup program to write')
    ap.add_argument('--name', default='Digimon World Horizon', help='the name shown and installed under')
    ap.add_argument('--version', help='shown in the wizard and installed apps (default: tools/version.py)')
    a = ap.parse_args()

    if not os.path.isfile(os.path.join(a.player, 'horizon-play.exe')):
        sys.exit(f'{a.player}: no horizon-play.exe (a Windows Horizon Play folder is needed)')
    version = a.version or subprocess.run([sys.executable, os.path.join(HERE, '..', 'version.py'), 'version'],
                                          capture_output=True, text=True, check=True).stdout.strip()
    nums = [int(x) for x in version.lstrip('v').split('-')[0].split('.')[:3] if x.isdigit()]
    vi = '.'.join(str(x) for x in (nums + [0, 0, 0, 0])[:4])
    key = a.name.replace(' ', '')
    bins = cue_bins(a.disc)

    with tempfile.TemporaryDirectory(prefix='hpsetup-') as work:
        app = os.path.join(work, 'app')
        shutil.copytree(a.player, app)
        # The disc goes in under the wizard's name; the cue is rewritten to name its files the same way.
        disc = a.name
        cue = open(a.disc, encoding='utf-8', errors='replace').read()
        for i, b in enumerate(bins):
            new = f'{disc}.bin' if len(bins) == 1 else f'{disc} (Track {i + 1}).bin'
            cue = cue.replace(os.path.basename(b), new)
            os.link(b, os.path.join(app, new)) if os.stat(b).st_dev == os.stat(work).st_dev \
                else shutil.copy2(b, os.path.join(app, new))
        with open(os.path.join(app, f'{disc}.cue'), 'w', encoding='utf-8', newline='\r\n') as f:
            f.write(cue)
        with open(os.path.join(work, 'icon.ico'), 'wb') as f:
            f.write(make_icons.ico())
        kb = sum(os.path.getsize(os.path.join(r, n)) for r, _, ns in os.walk(app) for n in ns) // 1024
        with open(os.path.join(work, 'setup.nsi'), 'w', encoding='utf-8') as f:
            f.write(NSI.format(name=a.name, key=key, disc=disc, version=version, vi=vi, kb=kb,
                               unkey=rf'Software\Microsoft\Windows\CurrentVersion\Uninstall\{key}'))
        if shutil.which('makensis'):
            subprocess.run(['makensis', '-V2', 'setup.nsi'], cwd=work, check=True)
        else:
            subprocess.run(['docker', 'run', '--rm', '-v', f'{work}:/w', '-w', '/w', 'ubuntu:24.04', 'sh', '-c',
                            'apt-get update -qq >/dev/null && apt-get install -y -qq nsis >/dev/null 2>&1 && '
                            f'makensis -V2 setup.nsi && chown {os.getuid()}:{os.getgid()} Setup.exe'], check=True)
        shutil.move(os.path.join(work, 'Setup.exe'), a.out)
    print(f'{a.out}: {os.path.getsize(a.out) // (1024 * 1024)} MB, {a.name} {version}')


if __name__ == '__main__':
    main()
