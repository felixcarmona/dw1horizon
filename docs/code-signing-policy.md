# Code signing policy (draft)

This policy covers the signed programs of Digimon World: Horizon: the desktop patcher, Horizon Patcher, for Windows
(and its macOS build, signed with the project's Apple Developer ID). It is a draft for the project's application to
SignPath Foundation's code signing for open-source projects; it applies once the project is accepted.

## What is signed

Only programs built by GitHub Actions from this repository's source, from a release tag, by
`.github/workflows/desktop.yml` (`tools/patcher/gui.py` frozen with PyInstaller by `tools/patcher/app/build.py`).
Nothing built elsewhere, no third-party program and no game data is signed. The release package itself (patch files
and build tools, applied to the player's own discs) is not an executable and is checked by SHA-256 instead
(`horizon-checksums.json`).

## Team and roles

| Role | Who |
|---|---|
| Author (writes and commits code) | the repository owner (the GitHub account that owns this repository) |
| Reviewer (reviews every change before it reaches `main`; `main` takes pull requests only) | the repository owner (the GitHub account that owns this repository) |
| Approver (approves each signing request of a release) | the repository owner (the GitHub account that owns this repository) |

Every team member uses multi-factor authentication on GitHub and on SignPath.

## Privacy

Horizon Patcher sends nothing about the player or their computer anywhere. It goes on the network only when the
player presses Download, "Check for a new release" or Build, and then only to ask GitHub for the project's latest
release and download its package and checksums. The player's discs, their files and the built disc stay on the
player's computer; nothing is uploaded. The app keeps its settings (the paths of the discs, the chosen language and
folder) and the downloaded package in the user's own application folders.
