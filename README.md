# wizctl

![Python](https://img.shields.io/badge/python-3.6%2B-blue)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

Control Philips WiZ smart lights from your terminal — no cloud, no bridge,
no account, no dependencies.

```console
$ wizctl find
found 2 light(s):
  192.168.1.50    -          on, dim=80%
  192.168.1.51    desk       off, dim=100%

$ wizctl night desk
1 light(s):
  192.168.1.51    -> ON   10%, 2700K
```

Speaks the WiZ Local API directly (JSON over UDP port 38899) — the same local
protocol the official mobile app uses on your home network. Everything runs
on your LAN; nothing ever leaves it.

## Install

**pipx / pip**

```sh
pipx install git+https://github.com/himanusia/wizctl.git
```

**curl** (macOS/Linux)

```sh
curl -fsSL https://raw.githubusercontent.com/himanusia/wizctl/main/wizctl.py -o ~/.local/bin/wizctl && chmod +x ~/.local/bin/wizctl
```

**Windows** — `winget install Python.Python.3` first if needed, then either
install command above (run `wizctl` from a terminal) or download
`wizctl.py` and use `python wizctl.py <command>`. Allow the firewall prompt
on first run.

**With your AI agent** — paste this single line into any coding assistant
(Claude Code, Codex, Cursor, Hermes, ...):

```text
Install and set up https://github.com/himanusia/wizctl for me by following its README, then show me my lights.
```

This README is written so an agent can follow it end to end: check PATH,
pick an install method for the OS, learn the commands below (or copy
[`skills/wizctl/SKILL.md`](skills/wizctl/SKILL.md) into its skills directory),
and verify with `wizctl`.

> Type `wiz` a lot? Add once to your shell profile: `alias wiz=wizctl`

## Usage

```
wizctl                          show status of every known light
wizctl find                     discover all WiZ lights on the network
wizctl on | off                 turn every light on / off
wizctl <10-100>                 brightness percent (turns lights on)
wizctl night | warm | white | cool
                                temperature presets (night = dim warm)
wizctl temp <2700-6500>         color temperature in Kelvin
wizctl rgb RRGGBB               RGB color (color models only; white-only
                                models silently ignore it)
wizctl scene <id>               activate a scene by numeric id (1-32)
wizctl rename <name> [@target]  give light(s) a friendly name
wizctl forget [target]          remove light(s) from the cache
wizctl add <ip>                 manually add a light by IP
```

### Targeting individual lights

Every command accepts an optional target: a friendly name you assigned with
`rename`, or a bare IP address.

```sh
wizctl rename desk              # renames every known light to 'desk'
wizctl rename lamp @desk        # renames only the light currently named 'desk'
wizctl on desk                  # turn on just that light
wizctl 40 @lamp                 # 40% brightness on 'lamp'
wizctl warm 192.168.1.50        # presets accept an IP too
wizctl off                      # no target = every known light
```

Without a target, commands apply to every light found so far. Lights that do
not respond are reported as unreachable instead of hanging; the exit code is
non-zero if any target failed, so it composes cleanly in scripts.

### State

Discovery results and names live in `~/.config/wizctl/lights.json`. Nothing
else is written anywhere. Delete the file to start fresh.

## Using with AI agents

`wizctl` is deliberately agent-friendly: single command surface, plain-text
output, meaningful exit codes, no interactivity, no cloud calls. A ready-made
agent skill ships at [`skills/wizctl/SKILL.md`](skills/wizctl/SKILL.md) —
point your assistant at this repo and it handles the rest (see the one-liner
in **Install**).

## Supported hardware

Any WiZ-connected bulb speaking the local API works, including:

- full-color models (`rgb` supported),
- tunable-white models (2700–6500 K),
- dimmable-only models (brightness).

The tool does not need to know which type you own: commands outside a bulb's
capability are simply ignored by the bulb itself. Most modern WiZ bulbs clamp
out-of-range color temperatures automatically.

## Protocol notes

The WiZ Local API is undocumented-but-widely-implemented: JSON datagrams over
UDP port 38899, unauthenticated, LAN-only.

- `getPilot` reads current state (power, dimming, temperature, color, scene).
- `setPilot` applies changes (`state`, `dimming`, `temp`, `r/g/b`, `sceneId`).
- Discovery broadcasts a `registration` probe to `255.255.255.255:38899`;
  every bulb answers from its own address.

There is intentionally **no** cloud support here: WiZ's cloud protocol is
proprietary, and remote access belongs to the official mobile app or
self-hosted relays. This tool deliberately covers only the "same network as
your lights" case.

## Security note

Like the WiZ protocol itself, this tool has no authentication — anything on
your LAN can control the bulbs. That is a property of the bulbs' firmware,
not of wizctl. Do not run this script as part of any internet-exposed service.

## License

MIT
