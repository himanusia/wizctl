# wizctl

![Python](https://img.shields.io/badge/python-3.6%2B-blue)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

Control Philips WiZ smart lights from your terminal — no cloud, no bridge,
no account, no dependencies.

```console
$ wiz find
found 2 light(s):
  192.168.1.50    -          on, dim=80%
  192.168.1.51    desk       off, dim=100%

$ wiz night desk
1 light(s):
  192.168.1.51    -> ON   10%, 2700K
```

Speaks the WiZ Local API directly (JSON over UDP port 38899) — the same local
protocol the official mobile app uses on your home network. Everything runs
on your LAN; nothing ever leaves it.

## Install

### With your AI agent (recommended)

Paste this single line into any coding assistant — Claude Code, Codex,
Cursor, Hermes, anything:

```text
Install and set up https://github.com/himanusia/wizctl for me by following its README, then show me my lights.
```

This README is written so an agent can follow it end to end: detect the OS,
pick an install method below, learn the commands (or copy
[`skills/wiz/SKILL.md`](skills/wiz/SKILL.md) into its skills directory), and
verify with a live `wiz` call.

### Manual

**pipx / pip**

```sh
pipx install git+https://github.com/himanusia/wizctl.git
```

**curl** (macOS/Linux)

```sh
curl -fsSL https://raw.githubusercontent.com/himanusia/wizctl/main/wiz.py -o ~/.local/bin/wiz && chmod +x ~/.local/bin/wiz
```

Make sure `~/.local/bin` is on your `PATH`.

**Windows** — install Python first if needed (`winget install Python.Python.3`),
then save `wiz.py` anywhere and run `python wiz.py <command>`; allow the
firewall prompt on first run. Or just use the agent line above.

## Usage

```
wiz                          show status of every known light
wiz find                     discover all WiZ lights on the network
wiz on | off                 turn every light on / off
wiz <10-100>                 brightness percent (turns lights on)
wiz night | warm | white | cool
                             temperature presets (night = dim warm)
wiz temp <2700-6500>         color temperature in Kelvin
wiz rgb RRGGBB               RGB color (color models only; white-only
                             models silently ignore it)
wiz scene <id>               activate a scene by numeric id (1-32)
wiz rename <name> [@target]  give light(s) a friendly name
wiz forget [target]          remove light(s) from the cache
wiz add <ip>                 manually add a light by IP
```

### Targeting individual lights

Every command accepts an optional target: a friendly name you assigned with
`rename`, or a bare IP address.

```sh
wiz rename desk              # renames every known light to 'desk'
wiz rename lamp @desk        # renames only the light currently named 'desk'
wiz on desk                  # turn on just that light
wiz 40 @lamp                 # 40% brightness on 'lamp'
wiz warm 192.168.1.50        # presets accept an IP too
wiz off                      # no target = every known light
```

Without a target, commands apply to every light found so far. Lights that do
not respond are reported as unreachable instead of hanging; the exit code is
non-zero if any target failed, so it composes cleanly in scripts.

### State

Discovery results and names live in `~/.config/wiz/lights.json`. Nothing
else is written anywhere. Delete the file to start fresh.

## Using with AI agents

`wiz` is deliberately agent-friendly: single command surface, plain-text
output, meaningful exit codes, no interactivity, no cloud calls. A ready-made
agent skill ships at [`skills/wiz/SKILL.md`](skills/wiz/SKILL.md); see the
one-liner in **Install**.

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
