# wizctl

Control Philips WiZ smart lights from your terminal — no cloud, no bridge, no account, no dependencies.

`wizctl` speaks the WiZ Local API directly (JSON over UDP port 38899), the same
protocol the official mobile app uses when your phone is on the same network.
Everything runs locally: discovery, status, and control. It works with any
number of bulbs and never leaves your LAN.

```console
$ wizctl find
found 2 light(s):
  192.168.1.50    -          on, dim=80%
  192.168.1.51    desk       off, dim=100%

$ wizctl night desk
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
- **Single file, stdlib only.** Copy `wizctl.py` anywhere a Python 3.6+
  interpreter exists.

## Requirements

Any system with **Python 3.6+** (already preinstalled on macOS and most Linux
distros). On Windows, run commands as `python wizctl.py <command>`. There are
no third-party packages.

## Install

**With pipx (recommended):**

```sh
pipx install git+https://github.com/himanusia/wizctl.git
```

**Or plain curl** (macOS/Linux):

```sh
mkdir -p ~/.local/bin
curl -fsSL https://raw.githubusercontent.com/himanusia/wizctl/main/wizctl.py \
  -o ~/.local/bin/wizctl
chmod +x ~/.local/bin/wizctl
```

Make sure `~/.local/bin` is on your `PATH`, then try:

```sh
wizctl find
```

**Manual:** just download `wizctl.py` and run it directly — `python3 wizctl.py
find`. Installing is optional; the script has zero dependencies.

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
not respond (powered off at the wall switch, different network) are reported
as unreachable instead of hanging; the exit code is non-zero if any target
failed, so it composes cleanly in scripts.

### How state is stored

Discovery results and names live in `~/.config/wizctl/lights.json`. Nothing
else is written anywhere. Delete the file to start fresh.

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
of wizctl. Do not run this script as part of any internet-exposed service.

## License

MIT
