---
name: wiz
description: "Control Philips WiZ smart lights on the local network via the wiz CLI. Use when the user asks about their lights - status, on/off, brightness, night/warm/cool presets, scenes - or mentions WiZ."
version: 1.0.0
category: smart-home
---

# WiZ Light Control

Agent skill for the `wiz` CLI (single-file Python tool that speaks the WiZ
Local API: JSON over UDP port 38899, LAN-only, no cloud, no dependencies).

## Prerequisite check

```bash
command -v wiz && wiz || echo "wiz not installed"
```

If missing, install per the repo README (`pipx install
git+https://github.com/himanusia/wizctl.git`, or run `python3 wiz.py <cmd>`
directly from a clone). If the machine is not on the same network as the
bulbs, every command reports them as unreachable — say so instead of retrying.

## Commands

```bash
wiz                  # status of all known lights (also lists saved names)
wiz find             # re-discover bulbs on the network
wiz on | off         # all lights
wiz <10-100>         # brightness % (implies on)
wiz night            # preset: 10% @ 2700K
wiz warm             # 2700K        wiz white   # 4000K
wiz cool             # 6500K
wiz temp <2700-6500> # color temperature in Kelvin
wiz rgb RRGGBB       # color models only (silently ignored by white-only bulbs)
wiz scene <id>       # numeric scene id (1-32)
wiz rename <name> [@target]   # name light(s): all, or @name / @ip for one
wiz forget [target]  # remove light(s) from cache
wiz add <ip>         # manually add a bulb by IP
```

Targeting: a bare command applies to ALL known lights; append a name
(`wiz on desk`) or IP (`wiz 40 192.168.1.50`) to address one. Exit code is
non-zero if any target was unreachable.

## Behavior rules

- Known lights and names live in `~/.config/wiz/lights.json`. Run bare `wiz`
  first to see the setup before asking the user anything.
- After any set command the CLI prints the resulting state — trust that line;
  do not issue an extra status query.
- Unreachable light: likely powered off at the wall switch or off the network.
  Report it once; never retry-loop against a UDP timeout.
- Testing etiquette: note the current state first, restore it afterwards.
- The protocol is LAN-only by design; this tool has no remote/cloud path.
  Do not claim remote control capability or suggest cloud integrations as
  part of this tool.
- White-spectrum models clamp out-of-range temperatures automatically
  (common range 2700–6500 K); that is expected behavior, not an error.
