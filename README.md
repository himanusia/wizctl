# wiz

Control Philips WiZ smart lights from your terminal — no cloud, no bridge, no account, no dependencies.

`wiz` speaks the WiZ Local API directly (JSON over UDP port 38899), the same
protocol the official mobile app uses when your phone is on the same network.
Everything runs locally: discovery, status, and control. It works with any
number of bulbs and never leaves your LAN.

```console
$ wiz find
found 2 light(s):
  192.168.1.50    -          on, dim=80%
  192.168.1.51    desk       off, dim=100%

$ wiz night desk
1 light(s):
  192.168.1.51    -> ON   10%, 2700K
```

## Why

- **No cloud.** Commands are UDP packets on your LAN. If the internet is down,
  your lights still work.
- **No setup.** No pairing, no accounts, no API keys. Bulbs answer any client
  on the same network.
- **Multi-light by design.** Discovery finds every bulb on the network; give
  them names, then target all of them or one at a time.
- **Single file, stdlib only.** Copy `wiz.py` anywhere a Python 3.6+
  interpreter exists.

## Requirements

Any system with **Python 3.6+**:

- **macOS / Linux** — Python is preinstalled (macOS may prompt to allow
  "Local Network" access the first time; approve it).
- **Windows** — works too. Install Python from [python.org](https://www.python.org/downloads/)
  (or `winget install Python.Python.3`), then run commands as
  `python wiz.py <command>`. Windows Firewall may ask for network access the
  first time; allow it. Everything else behaves identically.

There are no third-party packages on any platform.

## Install

**With pipx (recommended):**

```sh
pipx install git+https://github.com/himanusia/wizctl.git
```

**Or plain curl** (macOS/Linux):

```sh
mkdir -p ~/.local/bin
curl -fsSL https://raw.githubusercontent.com/himanusia/wizctl/main/wiz.py \
  -o ~/.local/bin/wiz
chmod +x ~/.local/bin/wiz
```

Make sure `~/.local/bin` is on your `PATH`, then try:

```sh
wiz find
```

**Manual:** just download `wiz.py` and run it directly — `python3 wiz.py
find`. Installing is optional; the script has zero dependencies.

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
not respond (powered off at the wall switch, different network) are reported
as unreachable instead of hanging; the exit code is non-zero if any target
failed, so it composes cleanly in scripts.

### How state is stored

Discovery results and names live in `~/.config/wiz/lights.json`. Nothing
else is written anywhere. Delete the file to start fresh.

## Using with AI agents

`wiz` is deliberately agent-friendly: single command surface, plain-text
output, meaningful exit codes, no interactivity, no cloud calls. Point your
agent at the script and it can control your lights from natural language
("turn the desk lamp to night mode").

A ready-made agent skill ships in this repo at
[`skills/wiz/SKILL.md`](skills/wiz/SKILL.md) — copy it into your assistant's
skills directory (Hermes Agent, Claude, etc.) and it knows when and how to
call `wiz`. The command table above is all an agent really needs if you
prefer writing your own.

### Or let your agent do the installing

Paste this into your AI agent as-is; it installs the tool, learns the command
surface, and verifies everything by itself:

```text
Install and set up the "wiz" CLI from https://github.com/himanusia/wizctl
so we can control my Philips WiZ lights together:

1. Check whether `wiz` is already on PATH (`command -v wiz`). If yes, go to
   step 3.
2. Install it from the repo above:
   - preferred: pipx install git+https://github.com/himanusia/wizctl.git
   - fallback (no pipx): download
     https://raw.githubusercontent.com/himanusia/wizctl/main/wiz.py to
     ~/.local/bin/wiz, make it executable, and ensure ~/.local/bin is on PATH.
     (Windows: save wiz.py anywhere and run it as `python wiz.py <command>`.)
3. Learn the command surface before using it: read the Usage section of
   https://github.com/himanusia/wizctl#usage and
   https://raw.githubusercontent.com/himanusia/wizctl/main/skills/wiz/SKILL.md
   (subcommands, @name/IP targeting suffix, exit codes). If your runtime has
   a skills directory, save that SKILL.md there so future sessions remember.
4. Run bare `wiz` to list known lights and show me the output. This only
   works while this machine is on the same network as the bulbs — if every
   light reports unreachable, tell me that instead of retrying.
```

## Supported hardware

Any WiZ-connected bulb speaking the local API works, including:

- full-color models (`rgb` supported),
- tunable-white models (2700–6500 K; `temp`, `night`, `warm`, `white`, `cool`),
- dimmable-only models (brightness).

The tool does not need to know which type you own: commands outside a bulb's
capability are simply ignored by the bulb itself. Color temperature ranges can
differ slightly per model — most modern WiZ clamps values automatically.

## Protocol notes

The WiZ Local API is undocumented-but-widely-implemented: JSON datagrams over
UDP port 38899, unauthenticated, LAN-only.

- `getPilot` reads current state (power, dimming, temperature, color, scene).
- `setPilot` applies changes (`state`, `dimming`, `temp`, `r/g/b`, `sceneId`).
- Discovery broadcasts a `registration` probe to `255.255.255.255:38899`;
  every bulb answers from its own address.

There is intentionally **no** cloud support here: WiZ's cloud protocol is
proprietary, and remote access belongs to the official app or self-hosted
relays. This tool deliberately covers only the "same network as your lights"
case.

## Security note

Like the WiZ protocol itself, this tool has no authentication — anything on
your LAN can control the bulbs. That is a property of the bulbs' firmware, not
of wiz. Do not run this script as part of any internet-exposed service.

## License

MIT
