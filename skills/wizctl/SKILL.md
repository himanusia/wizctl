---
name: wizctl
description: "Control Philips WiZ smart lights on the local network via the wizctl CLI. Use when the user asks about their lights - status, on/off, brightness, night/warm/cool presets, scenes - or mentions WiZ."
version: 1.0.0
category: smart-home
---

# WiZ Light Control

Agent skill for the `wizctl` CLI (single-file Python tool that speaks the WiZ
Local API: JSON over UDP port 38899, LAN-only, no cloud, no dependencies).

## Prerequisite check

```bash
command -v wizctl && wizctl || echo "wizctl not installed"
```

If missing, install per the repo README (`pipx install
git+https://github.com/himanusia/wizctl.git`, or run `python3 wizctl.py <cmd>`
directly from a clone). If the machine is not on the same network as the
bulbs, every command reports them as unreachable — say so instead of retrying.

## Commands

```bash
wizctl                  # status of all known lights (also lists saved names)
wizctl find             # re-discover bulbs on the network
wizctl on | off         # all lights
wizctl <10-100>         # brightness % (implies on)
wizctl night            # preset: 10% @ 2700K
wizctl warm             # 2700K        wizctl white   # 4000K
wizctl cool             # 6500K
wizctl temp <2700-6500> # color temperature in Kelvin
wizctl rgb RRGGBB       # color models only (silently ignored by white-only bulbs)
wizctl scene <id>       # numeric scene id (1-32)
wizctl rename <name> [@target]   # name light(s): all, or @name / @ip for one
wizctl forget [target]  # remove light(s) from cache
wizctl add <ip>         # manually add a bulb by IP
```

Targeting: a bare command applies to ALL known lights; append a name
(`wizctl on desk`) or IP (`wizctl 40 192.168.1.50`) to address one. Exit code is
non-zero if any target was unreachable.

## Behavior rules

- Known lights and names live in `~/.config/wizctl/lights.json`. Run bare `wizctl`
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
