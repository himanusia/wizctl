# wizctl

![Python](https://img.shields.io/badge/python-3.6%2B-blue)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)
![Version](https://img.shields.io/badge/version-0.4.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Control Philips WiZ smart lights from your terminal: no cloud, no bridge, and
no third-party dependencies. The command is named `wiz`.

## What changed in 0.4.0

- A bare `wiz` refreshes discovery before showing status.
- Every discovered light gets a local numeric ID, such as `1` or `2`.
- The WiZ MAC address is retained as the stable device identity when DHCP
  changes the IP address.
- Friendly names can be assigned and used as targets.
- `wiz forget` removes a light from this CLI's registry and keeps it ignored
  until it is explicitly re-adopted.
- The original IP/name cache is migrated automatically.

```console
$ wiz
2 light(s):
  [1] -            192.0.2.50     ON   dim=80%  mac=aa:bb:cc:dd:ee:ff
  [2] desk         192.0.2.51     off  dim=100%

$ wiz rename desk @1
  [1] desk         192.0.2.50     renamed to 'desk'

$ wiz night @desk
1 light(s):
  [1] desk         192.0.2.50     -> ON   10%, 2700K
```

WiZ devices speak a local API over UDP port 38899. Discovery and control stay
on the same LAN as the lights; nothing is sent to a cloud service.

## Install

### With your AI agent (recommended)

Paste this single line into any coding assistant: Claude Code, Codex, Cursor,
Hermes, or another agent:

```text
Install and set up https://github.com/himanusia/wizctl for me by following its README, then show me my lights.
```

The README is written so an agent can follow it end to end: detect the OS,
pick an install method, learn the commands, and verify with a local `wiz` call.

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

**Windows**: install Python first if needed (`winget install Python.Python.3`),
then save `wiz.py` anywhere and run `python wiz.py <command>`. Allow the
firewall prompt on first run.

## Usage

```text
wiz                          discover, then show tracked lights
wiz list                     show cached status without discovery
wiz find                     discover all WiZ lights
wiz find --include-forgotten re-adopt forgotten lights
wiz --version               print the CLI version
wiz on | off                 turn every tracked light on / off
wiz <10-100>                brightness percent (turns lights on)
wiz night | warm | white | cool
                             temperature presets
wiz temp <2700-6500>        color temperature in Kelvin
wiz rgb RRGGBB              RGB color (color models only)
wiz scene <id>              activate a scene by numeric ID
wiz rename <name> [target]  assign a friendly name
wiz forget [target]         remove light(s) from this CLI registry
wiz add <ip>                manually register a light by IP
```

### Targeting one light

Targets can be a local numeric ID, a friendly name, or an IP address. A trailing
`@` makes the target explicit and is recommended in scripts:

```sh
wiz rename desk @1
wiz on @desk
wiz 40 @desk
wiz warm 192.0.2.50
wiz off 2
```

A name target is case-insensitive and supports a prefix. A command without a
target applies to every tracked light. Direct IP control also works before a
light has been registered.

### Forgetting and re-adopting

`forget` removes a light from the local registry. It does **not** turn off,
reset, or remove the physical bulb from the official WiZ app.

```sh
wiz forget @desk       # forget one light by name
wiz forget @1          # forget one light by numeric ID
wiz forget 192.0.2.50
wiz forget             # forget every tracked light
wiz find --include-forgotten  # discover and re-adopt forgotten lights
```

Forgotten devices are ignored by normal automatic discovery. Re-adopting one
creates a new local numeric ID; its old ID is not reused.

## State and migration

The registry is stored at `~/.config/wiz/lights.json`. Version 0.4.0 migrates
the earlier format containing only `ip` and `name` entries the first time it
writes the file. The v2 shape contains a numeric `id`, a stable WiZ `uid` when
the device reports its MAC, the current `ip`, and the local `name`.

If a different MAC appears on an IP previously used by another tracked light,
the old record is retained as offline and the new device gets a separate ID.
This prevents a reused DHCP address from inheriting the old light's name.

The numeric ID is a local handle, not a WiZ cloud/account ID. The MAC-derived
UID is what lets discovery associate the same bulb after a DHCP address change.
If a particular firmware does not report a MAC, the current IP is the fallback
identity and can change with DHCP.

## Using with AI agents

`wiz` is deliberately agent-friendly: one command surface, plain-text output,
meaningful exit codes, no interactivity, and no cloud calls. A ready-made agent
skill ships at [`skills/wiz/SKILL.md`](skills/wiz/SKILL.md).

## Supported hardware

Any WiZ-connected bulb speaking the local API works, including:

- full-color models (`rgb` supported),
- tunable-white models (typically 2700–6500 K),
- dimmable-only models (brightness).

Commands outside a bulb's capabilities may be silently ignored by the bulb;
where applicable, `wiz` reads the resulting state back after a write.

## Protocol and security

The WiZ Local API is undocumented but widely implemented: JSON datagrams over
UDP port 38899, unauthenticated, LAN-only.

- `getPilot` reads current state (power, dimming, temperature, color, scene).
- `setPilot` applies changes (`state`, `dimming`, `temp`, `r/g/b`, `sceneId`).
- Discovery broadcasts a `registration` probe; bulbs answer with their IP and,
  on supported firmware, a MAC address.

Anything on the local network may be able to control these bulbs because the
firmware protocol has no authentication. Do not expose this script as an
internet-facing service.

## Development

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile wiz.py
```

## License

MIT
