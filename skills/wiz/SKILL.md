---
name: wiz
description: "Control Philips WiZ smart lights on the local network via the wiz CLI. Use when the user asks about WiZ lights, status, on/off, brightness, presets, scenes, names, IDs, or forgetting a device."
version: 1.2.0
category: smart-home
---

# WiZ Light Control

Agent skill for `wiz` 0.4.0, a single-file Python CLI speaking the WiZ Local
API: JSON over UDP port 38899, LAN-only, no cloud, no dependencies.

## Prerequisite check

```bash
command -v wiz && wiz --version && wiz || echo "wiz not installed"
```

If missing, install per https://github.com/himanusia/wizctl. Preferred:
`pipx install git+https://github.com/himanusia/wizctl.git`; fallback: download
raw `wiz.py` to `~/.local/bin/wiz`. If the machine is not on the same network
as the bulbs, discovery reports no responses; say so instead of retrying.

## Discovery and registry

```bash
wiz                         # discover, then show tracked light status
wiz list                    # show cached registry without discovery
wiz find                    # refresh discovery
wiz find --include-forgotten # re-adopt devices explicitly forgotten
```

A discovered device receives a local numeric ID. Its WiZ MAC address is stored
as the stable UID when firmware reports it, so a DHCP IP change does not create
a duplicate. The registry and local names live in
`~/.config/wiz/lights.json`. The original IP/name-only cache is migrated when
it is next written.

A bare `wiz` is read-only apart from refreshing this local registry. Control
commands still target only tracked lights unless given a direct IP.

## Commands

```bash
wiz on | off                    # all tracked lights
wiz <10-100>                    # brightness % (implies on)
wiz night                      # preset: 10% @ 2700K
wiz warm                       # 2700K
wiz white                      # 4000K
wiz cool                       # 6500K
wiz temp <2700-6500>            # color temperature in Kelvin
wiz rgb RRGGBB                 # color models only
wiz scene <id>                 # numeric scene ID
wiz rename <name> [target]     # assign a local friendly name
wiz forget [target]            # remove from this CLI's registry
wiz add <ip>                   # manually register a bulb by IP
```

## Targeting and lifecycle

Targets can be a numeric ID, a friendly name, or an IP. Prefixing with `@` is
recommended for unambiguous scripts. Names are case-insensitive and support a
prefix match.

```bash
wiz rename desk @1
wiz on @desk
wiz 40 @desk
wiz warm 192.0.2.50
wiz off 2
wiz forget @desk
wiz forget @1
wiz forget                    # forget every tracked light
wiz find --include-forgotten  # re-adopt forgotten devices
```

`forget` only removes a device from this CLI and adds it to the ignored list. It
does not reset the physical bulb or remove it from the official WiZ app. A
re-adopted device receives a new local numeric ID; old IDs are never reused.

## Behavior rules

- A bare command applies to all tracked lights; append a target for one.
- Direct IP control works before a device is registered.
- After a set command, the CLI reads and prints the resulting state.
- Unreachable lights are reported once; the process does not retry-loop on UDP
  timeouts, and its exit code is non-zero if any target failed.
- A discovered MAC is authoritative. If a different MAC appears at an old IP,
  the old record is retained as offline and the new device gets a new ID; never
  inherit a name from an IP collision.
- The protocol is LAN-only by design. Do not claim remote/cloud control.
- White-spectrum models may clamp out-of-range temperatures automatically.
- Testing etiquette: note the current state first and restore it afterwards.
