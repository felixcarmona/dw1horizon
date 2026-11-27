#!/usr/bin/env python3
"""The Windows setup template (docs/player.md, "A setup wizard"): an NSIS wizard with Horizon Play inside and no game.

    python3 tools/player/installer.py --player "Horizon Play" --out Horizon-Setup.exe

--player is a Windows Horizon Play folder (tools/player/build.py on Windows, or `_internal/player` of the desktop
patcher's zip). CI publishes the result as Horizon-Setup.exe and the desktop patcher carries it: on the player's own
computer tools/patcher/setup_exe.py appends the disc it built (the game is never in a release). When run, the wizard
installs for the current user only (no administrator), into %LOCALAPPDATA%\\Programs\\<name>, with Start menu and desktop
shortcuts and an entry in Windows' installed apps, and has `horizon-play.exe --unpack` write the appended disc into the
install folder. The uninstaller leaves the saves (Horizon Play keeps them in %APPDATA%\\Horizon\\Horizon). A template with
no disc appended says so at the start and quits. It is made with NSIS: makensis from the PATH or its usual Windows
folder, else in a Docker ubuntu:24.04 container.
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
# The patcher appends the disc after the installer's own data (tools/patcher/setup_exe.py). NSIS reads only the length
# its first header records, but its CRC check covers the whole file, so it is switched off (not tested with it on).
CRCCheck off
Name "{name}"
OutFile "Horizon-Setup.exe"
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

LangString NoGame ${{LANG_ENGLISH}} "This setup has no game inside.$\nMake it with the Horizon Patcher, from your own discs, and run the setup it writes."
LangString NoGame ${{LANG_SPANISH}} "Este instalador no lleva el juego dentro.$\nCrealo con el Horizon Patcher, a partir de tus discos, y ejecuta el instalador que genera."
LangString Unpacking ${{LANG_ENGLISH}} "Unpacking the game..."
LangString Unpacking ${{LANG_SPANISH}} "Desempaquetando el juego..."
LangString UnpackFailed ${{LANG_ENGLISH}} "The game could not be unpacked (is there room on the disk?). Nothing was installed."
LangString UnpackFailed ${{LANG_SPANISH}} "No se pudo desempaquetar el juego (hay espacio en el disco?). No se instalo nada."

Function .onInit
  ; a setup made by the patcher ends with the magic "HZSETUP1"; the bare template does not
  FileOpen $0 "$EXEPATH" r
  FileSeek $0 -8 END
  FileRead $0 $1 8
  FileClose $0
  StrCmp $1 "HZSETUP1" +3
  MessageBox MB_OK|MB_ICONSTOP "$(NoGame)" /SD IDOK
  Quit
FunctionEnd

Function Play
  SetOutPath "$INSTDIR"
  Exec '"$INSTDIR\horizon-play.exe" "$INSTDIR\{disc}.cue"'
FunctionEnd

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "app\*.*"
  File "icon.ico"
  DetailPrint "$(Unpacking)"
  nsExec::ExecToLog '"$INSTDIR\horizon-play.exe" --unpack "$EXEPATH" "$INSTDIR"'
  Pop $0
  StrCmp $0 "0" +2
  Abort "$(UnpackFailed)"
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


def makensis():
    """The makensis to run: on the PATH, else where the Windows installer and choco put it, else None (Docker)."""
    found = shutil.which('makensis')
    if found:
        return found
    for base in (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'), r'C:\Program Files (x86)'):
        path = base and os.path.join(base, 'NSIS', 'makensis.exe')
        if path and os.path.isfile(path):
            return path
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--player', required=True, help='a Windows Horizon Play folder (with horizon-play.exe)')
    ap.add_argument('--out', required=True, help='the setup template to write (Horizon-Setup.exe)')
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

    with tempfile.TemporaryDirectory(prefix='hpsetup-') as work:
        app = os.path.join(work, 'app')
        shutil.copytree(a.player, app)
        with open(os.path.join(work, 'icon.ico'), 'wb') as f:
            f.write(make_icons.ico())
        # the player and the disc (about 700 MB, not in the template) the patcher appends
        kb = sum(os.path.getsize(os.path.join(r, n)) for r, _, ns in os.walk(app) for n in ns) // 1024 + 700 * 1024
        with open(os.path.join(work, 'setup.nsi'), 'w', encoding='utf-8-sig') as f:
            f.write(NSI.format(name=a.name, key=key, disc=a.name, version=version, vi=vi, kb=kb,
                               unkey=rf'Software\Microsoft\Windows\CurrentVersion\Uninstall\{key}'))
        exe = makensis()
        if exe:
            subprocess.run([exe, '-V2', 'setup.nsi'], cwd=work, check=True)
        else:
            subprocess.run(['docker', 'run', '--rm', '-v', f'{work}:/w', '-w', '/w', 'ubuntu:24.04', 'sh', '-c',
                            'apt-get update -qq >/dev/null && apt-get install -y -qq nsis >/dev/null 2>&1 && '
                            f'makensis -V2 setup.nsi && chown {os.getuid()}:{os.getgid()} Horizon-Setup.exe'], check=True)
        shutil.move(os.path.join(work, 'Horizon-Setup.exe'), a.out)
    print(f'{a.out}: {os.path.getsize(a.out) // (1024 * 1024)} MB, {a.name} {version}, no game inside')


if __name__ == '__main__':
    main()
