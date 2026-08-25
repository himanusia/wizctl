#!/usr/bin/env python3
"""wizctl - control Philips WiZ lights over your LAN. No cloud, no bridge, no dependencies.

Works with any number of bulbs on the local network. Discovers them via UDP
broadcast, remembers them in a small cache file, and can address all lights
at once or individual ones by IP or a friendly name you assign.

Usage:
  wizctl                          show status of every known light
  wizctl find                     re-discover all WiZ lights on the network
  wizctl on | off                 turn every light on / off
  wizctl <10-100>                 brightness percent (turns lights on)
  wizctl night | warm | white | cool
                                  temperature presets (night = dim warm)
  wizctl temp <2700-6500>         color temperature in Kelvin
  wizctl rgb RRGGBB               set RGB color (color models only;
                                  white-only models silently ignore it)
  wizctl scene <id>               activate a scene by numeric id (1-32)
  wizctl rename <name>            give the targeted light(s) a friendly name
  wizctl forget [target]          remove light(s) from the cache
  wizctl add <ip>                 manually add a light by IP

Any command accepts an optional target suffix to address specific lights:
  wizctl on desk                  where 'desk' is a name previously set
  wizctl 40 192.168.1.50          or a bare IP
Without a target, commands apply to every light found so far.

Configuration lives in ~/.config/wizctl/lights.json

Requirements: Python 3.6+ standard library only.
Protocol: WiZ Local API - JSON over UDP port 38899 (same LAN as the bulbs).
"""
import json
import os
import socket
import sys
import time

PORT = 38899
CONF_DIR = os.path.expanduser("~/.config/wizctl")
CACHE_FILE = os.path.join(CONF_DIR, "lights.json")
DISCOVERY_WAIT = 2.0
CMD_TIMEOUT = 1.5

PRESETS = {"night": {"dimming": 10, "temp": 2700},
           "warm": {"temp": 2700},
           "white": {"temp": 4000},
           "cool": {"temp": 6500}}


# ---------- cache ----------

def load_cache():
    try:
        with open(CACHE_FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return {e["ip"]: e.get("name") for e in data.get("lights", [])}


def save_cache(lights):
    os.makedirs(CONF_DIR, exist_ok=True)
    entries = [{"ip": ip, "name": name} for ip, name in sorted(lights.items())]
    with open(CACHE_FILE, "w") as f:
        json.dump({"lights": entries}, f, indent=2)


# ---------- protocol ----------

def udp_call(ip, payload, timeout=CMD_TIMEOUT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(json.dumps(payload).encode(), (ip, PORT))
        data, _addr = sock.recvfrom(2048)
        return json.loads(data.decode())
    finally:
        sock.close()


def get_pilot(ip):
    resp = udp_call(ip, {"method": "getPilot", "params": {}})
    return resp.get("result", {})


def set_pilot(ip, params):
    resp = udp_call(ip, {"method": "setPilot", "params": params})
    ok = resp.get("result", {}).get("success", False)
    if not ok:
        raise RuntimeError("bulb rejected the command")
    time.sleep(0.35)  # let the bulb apply before anyone reads state back


def discover():
    """Broadcast on port 38899; every WiZ device on the LAN answers."""
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            my_ip = probe.getsockname()[0]
        finally:
            probe.close()
    except OSError:
        my_ip = "1.1.1.1"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(DISCOVERY_WAIT)
    reg = json.dumps({"method": "registration",
                      "params": {"phoneIp": my_ip, "register": False}})
    found = set()
    try:
        for broadcast in ("255.255.255.255", my_ip.rsplit(".", 1)[0] + ".255"):
            try:
                sock.sendto(reg.encode(), (broadcast, PORT))
            except OSError:
                pass
        while True:
            _data, addr = sock.recvfrom(2048)
            found.add(addr[0])
    except socket.timeout:
        pass
    finally:
        sock.close()
    return sorted(found)


# ---------- helpers ----------

def resolve_targets(args):
    """Split trailing '@' target (ip or name) from args; '' means 'all'."""
    lights = load_cache()
    target = ""
    if args and (args[-1].startswith("@")):
        target = args[-1][1:]
        args = args[:-1]
    elif args and len(args) >= 2 and looks_like_ip(args[-1]):
        target = args[-1]
        args = args[:-1]

    if not target:
        return args, sorted(lights)
    if looks_like_ip(target):
        return args, [target]
    matches = [ip for ip, name in lights.items()
               if name and name.lower().startswith(target.lower())]
    if not matches:
        sys.exit("wizctl: no light named '%s' (run 'wizctl' to see known lights)" % target)
    return args, matches


def looks_like_ip(text):
    parts = text.split(".")
    return (len(parts) == 4
            and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts))


def parse_temp(value):
    try:
        kelvin = int(value)
    except ValueError:
        sys.exit("wizctl: temp must be a number in Kelvin, e.g. 'wizctl temp 3500'")
    return max(2200, min(kelvin, 6500))


def build_params(cmd, args):
    """Translate a command into setPilot params, or None for read-only cmds."""
    if cmd == "on":
        return {"state": True}
    if cmd == "off":
        return {"state": False}
    if cmd.isdigit():
        return {"dimming": max(10, min(int(cmd), 100)), "state": True}
    if cmd in PRESETS:
        params = dict(PRESETS[cmd])
        params["state"] = True
        return params
    if cmd == "temp":
        if len(args) != 1:
            sys.exit("usage: wizctl temp <kelvin>")
        return {"temp": parse_temp(args[0]), "state": True}
    if cmd == "rgb":
        if len(args) != 1 or len(args[0]) != 6:
            sys.exit("usage: wizctl rgb RRGGBB")
        try:
            r, g, b = (int(args[0][i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            sys.exit("wizctl: rgb expects hex like ff8800")
        return {"r": r, "g": g, "b": b, "state": True}
    if cmd == "scene":
        if len(args) != 1 or not args[0].isdigit():
            sys.exit("usage: wizctl scene <id>")
        return {"sceneId": int(args[0]), "state": True}
    return None


def apply(ip, params):
    try:
        if params is None:
            pilot = get_pilot(ip)
            state = "ON " if pilot.get("state") else "off"
            bits = ["dim=%s%%" % pilot.get("dimming")]
            if pilot.get("sceneId"):
                bits.append("scene=%s" % pilot["sceneId"])
            if pilot.get("temp"):
                bits.append("%sK" % pilot["temp"])
            if any(k in pilot for k in ("r", "g", "b")):
                bits.append("rgb=%02x%02x%02x" % (pilot.get("r", 0),
                                                  pilot.get("g", 0),
                                                  pilot.get("b", 0)))
            print("  %-15s %s  %s" % (ip, state, "  ".join(bits)))
            return True
        else:
            set_pilot(ip, params)
            pilot = get_pilot(ip)
            state = "ON " if pilot.get("state") else "off"
            label = label_for(params)
            print("  %-15s -> %s  %s" % (ip, state, label))
            return True
    except (socket.timeout, OSError):
        print("  %-15s ✗ unreachable" % ip)
        return False
    except RuntimeError as exc:
        print("  %-15s ✗ %s" % (ip, exc))
        return False


def label_for(params):
    labels = []
    if "dimming" in params:
        labels.append("%s%%" % params["dimming"])
    if "temp" in params:
        labels.append("%sK" % params["temp"])
    if "r" in params:
        labels.append("#%02x%02x%02x" % (params["r"], params["g"], params["b"]))
    if "sceneId" in params:
        labels.append("scene %s" % params["sceneId"])
    if params.get("state") is False:
        labels.append("power off")
    return ", ".join(labels) or "power on"


# ---------- subcommands ----------

def cmd_find():
    lights = load_cache()
    found = discover()
    if not found:
        print("no WiZ lights answered the broadcast "
              "(are you on the same network?)")
        return 1
    for ip in found:
        lights.setdefault(ip, None)
    save_cache(lights)
    print("found %d light(s):" % len(found))
    for ip in found:
        name = lights.get(ip)
        try:
            pilot = get_pilot(ip)
            detail = "%s, dim=%s%%" % ("on" if pilot.get("state") else "off",
                                       pilot.get("dimming"))
        except (socket.timeout, OSError):
            detail = "unresponsive"
        print("  %-15s %-10s %s" % (ip, name or "-", detail))
    return 0


def cmd_rename(args, targets):
    if not args or len(args) != 1:
        sys.exit("usage: wizctl rename <name> [@target]")
    if not targets:
        sys.exit("wizctl: no lights known yet - run 'wizctl find' first")
    lights = load_cache()
    for ip in targets:
        lights[ip] = args[0]
        print("  %-15s renamed to '%s'" % (ip, args[0]))
    save_cache(lights)


def cmd_forget(targets):
    lights = load_cache()
    doomed = targets or sorted(lights)
    for ip in doomed:
        lights.pop(ip, None)
        print("  %-15s forgotten" % ip)
    save_cache(lights)


def cmd_add(ip):
    if not looks_like_ip(ip):
        sys.exit("wizctl: '%s' does not look like an IP address" % ip)
    lights = load_cache()
    lights.setdefault(ip, None)
    save_cache(lights)
    print("added %s" % ip)
    apply(ip, None)


def main():
    argv = sys.argv[1:]
    if argv and argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if not argv:
        argv = ["status"]

    cmd = argv[0]
    if cmd == "find":
        return cmd_find()
    if cmd == "add":
        if len(argv) != 2:
            sys.exit("usage: wizctl add <ip>")
        cmd_add(argv[1])
        return 0

    args, targets = resolve_targets(argv)
    if cmd == "rename":
        cmd_rename(args[1:], targets)
        return 0
    if cmd == "forget":
        cmd_forget(targets)
        return 0

    if not targets:
        print("no lights known yet - run 'wizctl find' first, "
              "or add one with 'wizctl add <ip>'")
        return 1

    params = build_params(cmd, args[1:])
    if params is None and cmd not in ("on", "off") and not cmd.isdigit() \
            and cmd not in PRESETS and cmd != "status":
        sys.exit("wizctl: unknown command '%s' (run 'wizctl' for help)" % cmd)

    print("%d light(s):" % len(targets))
    results = [apply(ip, params) for ip in targets]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
