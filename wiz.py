#!/usr/bin/env python3
"""wiz - control Philips WiZ lights over your LAN.

No cloud, no bridge, no dependencies. A bare ``wiz`` refreshes discovery and
shows the current status. Every discovered device gets a local numeric ID,
while its WiZ MAC address is retained as the stable identity when the DHCP IP
changes. Friendly names are local aliases for those IDs.

Usage:
  wiz                          discover, then show status of tracked lights
  wiz list                     show status from the local registry only
  wiz find                     re-discover all WiZ lights on the network
  wiz find --include-forgotten re-adopt lights previously forgotten
  wiz --version               print the CLI version
  wiz on | off                 turn every tracked light on / off
  wiz <10-100>                set brightness percent (turns lights on)
  wiz night | warm | white | cool
                               temperature presets (night = dim warm)
  wiz temp <2700-6500>        color temperature in Kelvin
  wiz rgb RRGGBB              set RGB color (color models only;
                               white-only models silently ignore it)
  wiz scene <id>              activate a scene by numeric id (1-32)
  wiz rename <name> [target]  give the targeted light(s) a friendly name
  wiz forget [target]         remove light(s) from this CLI's registry
  wiz add <ip>                manually add a light by IP

Targets can be a numeric ID, a friendly name, or an IP address. Prefixing a
target with ``@`` makes the intent explicit, for example ``wiz off @desk``.
Without a target, control commands apply to every tracked light.

Configuration lives in ~/.config/wiz/lights.json. The file is a local registry;
forgetting a light never resets the physical bulb or removes it from WiZ's app.

Protocol: WiZ Local API - JSON over UDP port 38899 (same LAN as the bulbs).
"""
import json
import os
import socket
import string
import sys
import time

VERSION = "0.4.0"
STATE_VERSION = 2
PORT = 38899
CONF_DIR = os.path.expanduser("~/.config/wiz")
CACHE_FILE = os.path.join(CONF_DIR, "lights.json")
DISCOVERY_WAIT = 2.0
CMD_TIMEOUT = 1.5

PRESETS = {"night": {"dimming": 10, "temp": 2700},
           "warm": {"temp": 2700},
           "white": {"temp": 4000},
           "cool": {"temp": 6500}}

# Number of positional arguments before an optional trailing target.
COMMAND_ARGUMENTS = {
    "on": 0,
    "off": 0,
    "status": 0,
    "list": 0,
    "night": 0,
    "warm": 0,
    "white": 0,
    "cool": 0,
    "temp": 1,
    "rgb": 1,
    "scene": 1,
    "rename": 1,
    "forget": 0,
}


# ---------- registry ----------

def empty_state():
    return {"version": STATE_VERSION, "next_id": 1, "ignored": [], "lights": []}


def canonical_uid(value):
    """Return a normalized WiZ MAC UID, or None for an unknown identifier."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if text.startswith("mac:"):
        text = text[4:]
    text = text.replace(":", "").replace("-", "").replace(".", "")
    if len(text) != 12 or any(char not in string.hexdigits for char in text):
        return None
    return "mac:" + text


def display_uid(uid):
    uid = canonical_uid(uid)
    if not uid:
        return "-"
    raw = uid[4:]
    return ":".join(raw[index:index + 2] for index in range(0, 12, 2))


def _numeric_id(value):
    try:
        number = int(str(value))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _allocate_id(state):
    used = {str(light.get("id")) for light in state.get("lights", [])}
    candidate = max(_numeric_id(state.get("next_id")) or 1, 1)
    while str(candidate) in used:
        candidate += 1
    state["next_id"] = candidate + 1
    return str(candidate)


def _new_record(state, ip, uid=None, name=None):
    return {
        "id": _allocate_id(state),
        "uid": canonical_uid(uid),
        "ip": str(ip),
        "name": name or None,
    }


def _sort_lights(lights):
    return sorted(lights, key=lambda light: (
        _numeric_id(light.get("id")) or 0,
        str(light.get("ip", "")),
    ))


def _clean_ignored(values):
    cleaned = []
    for value in values if isinstance(values, list) else []:
        value = str(value)
        if value.startswith("mac:"):
            value = canonical_uid(value)
        if value and value not in cleaned:
            cleaned.append(value)
    return cleaned


def load_state():
    """Load the v2 registry and migrate the original IP/name cache in memory."""
    try:
        with open(CACHE_FILE) as handle:
            data = json.load(handle)
    except (OSError, ValueError, TypeError):
        return empty_state()

    if not isinstance(data, dict):
        return empty_state()

    state = empty_state()
    requested_next_id = _numeric_id(data.get("next_id"))
    if requested_next_id:
        state["next_id"] = requested_next_id
    state["ignored"] = _clean_ignored(data.get("ignored", []))

    raw_lights = data.get("lights", [])
    if not isinstance(raw_lights, list):
        raw_lights = []

    # v1 stored only {ip, name}; sorting makes their first IDs deterministic.
    if data.get("version") != STATE_VERSION:
        raw_lights = sorted(
            (entry for entry in raw_lights if isinstance(entry, dict)),
            key=lambda entry: str(entry.get("ip", "")),
        )

    used_ids = set()
    for entry in raw_lights:
        if not isinstance(entry, dict) or not entry.get("ip"):
            continue
        record_id = str(entry.get("id", ""))
        if not _numeric_id(record_id) or record_id in used_ids:
            record_id = _allocate_id(state)
        else:
            used_ids.add(record_id)
            state["next_id"] = max(state["next_id"], int(record_id) + 1)
        state["lights"].append({
            "id": record_id,
            "uid": canonical_uid(entry.get("uid") or entry.get("mac")),
            "ip": str(entry["ip"]),
            "name": entry.get("name") or None,
        })

    state["lights"] = _sort_lights(state["lights"])
    return state


def save_state(state):
    os.makedirs(CONF_DIR, exist_ok=True)
    payload = {
        "version": STATE_VERSION,
        "next_id": max(_numeric_id(state.get("next_id")) or 1, 1),
        "ignored": _clean_ignored(state.get("ignored", [])),
        "lights": [],
    }
    for light in _sort_lights(state.get("lights", [])):
        payload["lights"].append({
            "id": str(light["id"]),
            "uid": canonical_uid(light.get("uid")),
            "ip": str(light["ip"]),
            "name": light.get("name") or None,
        })
    temporary = CACHE_FILE + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")
    os.replace(temporary, CACHE_FILE)


def _record_by_uid(lights, uid):
    if not uid:
        return None
    for light in lights:
        if canonical_uid(light.get("uid")) == uid:
            return light
    return None


def _record_by_ip(lights, ip):
    for light in lights:
        if light.get("ip") == ip:
            return light
    return None


def _ignored_keys(ip, uid):
    keys = ["ip:" + str(ip)] if ip else []
    if uid:
        keys.insert(0, uid)
    return keys


def _remove_ignored_keys(state, keys):
    state["ignored"] = [key for key in state.get("ignored", []) if key not in keys]


def merge_discovered(state, discovered, include_ignored=False):
    """Merge discovery results and return the tracked records that were seen."""
    tracked = []
    for item in discovered:
        if isinstance(item, str):
            item = {"ip": item}
        if not isinstance(item, dict) or not item.get("ip"):
            continue
        ip = str(item["ip"])
        uid = canonical_uid(item.get("uid") or item.get("mac"))
        keys = _ignored_keys(ip, uid)
        if not include_ignored and any(key in state["ignored"] for key in keys):
            continue
        if include_ignored:
            _remove_ignored_keys(state, keys)

        record = _record_by_uid(state["lights"], uid) or _record_by_ip(state["lights"], ip)
        by_ip = _record_by_ip(state["lights"], ip)
        if record and by_ip and record is not by_ip:
            # A DHCP change can make a UID match an old record while the new IP
            # is still present as a second stale record. Keep the named record.
            if not record.get("name"):
                record["name"] = by_ip.get("name")
            state["lights"].remove(by_ip)
        if record is None:
            record = _new_record(state, ip, uid)
            state["lights"].append(record)
        else:
            record["ip"] = ip
            if uid:
                record["uid"] = uid
        tracked.append(record)
    state["lights"] = _sort_lights(state["lights"])
    return tracked


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


def parse_discovery_packet(packet):
    """Extract the stable MAC UID from a WiZ registration response."""
    try:
        if isinstance(packet, bytes):
            packet = packet.decode("utf-8")
        data = json.loads(packet)
    except (UnicodeDecodeError, ValueError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    result = data.get("result")
    if not isinstance(result, dict):
        result = {}
    uid = canonical_uid(result.get("mac") or result.get("deviceMac") or data.get("mac"))
    return {"uid": uid} if uid else {}


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
    registration = json.dumps({
        "method": "registration",
        "params": {"phoneIp": my_ip, "phoneMac": "", "register": False},
    })
    found = {}
    try:
        for broadcast in ("255.255.255.255", my_ip.rsplit(".", 1)[0] + ".255"):
            try:
                sock.sendto(registration.encode(), (broadcast, PORT))
            except OSError:
                pass
        while True:
            packet, addr = sock.recvfrom(2048)
            record = {"ip": addr[0]}
            record.update(parse_discovery_packet(packet))
            previous = found.get(addr[0])
            if previous and not record.get("uid"):
                record["uid"] = previous.get("uid")
            found[addr[0]] = record
    except socket.timeout:
        pass
    finally:
        sock.close()
    return [found[ip] for ip in sorted(found)]


# ---------- command helpers ----------

def split_target(cmd, args):
    """Split the optional trailing target from command arguments."""
    args = list(args)
    if args and args[-1].startswith("@"):
        return args[:-1], args[-1][1:]
    expected = COMMAND_ARGUMENTS.get(cmd)
    if expected is None and cmd.isdigit():
        expected = 0
    if expected is not None and len(args) > expected:
        return args[:-1], args[-1]
    return args, None


def resolve_targets(state, target=None):
    lights = _sort_lights(state.get("lights", []))
    if not target:
        return lights
    target = str(target).strip()
    if looks_like_ip(target):
        matches = [light for light in lights if light.get("ip") == target]
        if matches:
            return matches
        # Direct IP control remains useful before a device is registered.
        return [{"id": "-", "uid": None, "ip": target, "name": None, "_synthetic": True}]

    exact_id = [light for light in lights if str(light.get("id")) == target]
    if exact_id:
        return exact_id

    uid = canonical_uid(target)
    if uid:
        uid_matches = [light for light in lights if canonical_uid(light.get("uid")) == uid]
        if uid_matches:
            return uid_matches

    lowered = target.lower()
    name_matches = [
        light for light in lights
        if light.get("name") and light["name"].lower().startswith(lowered)
    ]
    if name_matches:
        return name_matches
    sys.exit("wiz: no light, ID, or name matching '%s'" % target)


def looks_like_ip(text):
    parts = str(text).split(".")
    return (len(parts) == 4
            and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts))


def parse_temp(value):
    try:
        kelvin = int(value)
    except ValueError:
        sys.exit("wiz: temp must be a number in Kelvin, e.g. 'wiz temp 3500'")
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
        return {"temp": parse_temp(args[0]), "state": True}
    if cmd == "rgb":
        try:
            r, g, b = (int(args[0][index:index + 2], 16) for index in (0, 2, 4))
        except (IndexError, ValueError):
            sys.exit("wiz: rgb expects hex like ff8800")
        if len(args[0]) != 6:
            sys.exit("wiz: rgb expects hex like ff8800")
        return {"r": r, "g": g, "b": b, "state": True}
    if cmd == "scene":
        if not args[0].isdigit():
            sys.exit("usage: wiz scene <id>")
        return {"sceneId": int(args[0]), "state": True}
    return None


def _record_name(record):
    return record.get("name") or "-"


def _record_prefix(record):
    return "[%s] %-12s %-15s" % (
        record.get("id", "-"),
        _record_name(record),
        record.get("ip", "-"),
    )


def apply(record, params):
    ip = record["ip"]
    try:
        if params is None:
            pilot = get_pilot(ip)
            state = "ON " if pilot.get("state") else "off"
            bits = ["dim=%s%%" % pilot.get("dimming")]
            if pilot.get("sceneId"):
                bits.append("scene=%s" % pilot["sceneId"])
            if pilot.get("temp"):
                bits.append("%sK" % pilot["temp"])
            if any(key in pilot for key in ("r", "g", "b")):
                bits.append("rgb=%02x%02x%02x" % (
                    pilot.get("r", 0), pilot.get("g", 0), pilot.get("b", 0)))
            if record.get("uid"):
                bits.append("mac=%s" % display_uid(record["uid"]))
            print("  %s  %s  %s" % (_record_prefix(record), state, "  ".join(bits)))
            return True

        set_pilot(ip, params)
        pilot = get_pilot(ip)
        state = "ON " if pilot.get("state") else "off"
        print("  %s  -> %s  %s" % (_record_prefix(record), state, label_for(params)))
        return True
    except (socket.timeout, OSError, ValueError):
        print("  %s  ✗ unreachable" % _record_prefix(record))
        return False
    except RuntimeError as exc:
        print("  %s  ✗ %s" % (_record_prefix(record), exc))
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


def _validate_args(cmd, args):
    expected = COMMAND_ARGUMENTS.get(cmd)
    if expected is not None and len(args) != expected:
        if cmd == "rename":
            sys.exit("usage: wiz rename <name> [@target]")
        if cmd == "temp":
            sys.exit("usage: wiz temp <kelvin> [@target]")
        if cmd == "rgb":
            sys.exit("usage: wiz rgb RRGGBB [@target]")
        if cmd == "scene":
            sys.exit("usage: wiz scene <id> [@target]")
        sys.exit("usage: wiz %s [@target]" % cmd)


# ---------- subcommands ----------

def cmd_status(state, target=None, auto_discover=False):
    if auto_discover:
        found = discover()
        if found:
            merge_discovered(state, found)
            save_state(state)
        elif not state["lights"]:
            print("no WiZ lights answered the broadcast (are you on the same network?)")
            return 1

    targets = resolve_targets(state, target)
    if not targets:
        print("no tracked lights; run 'wiz' or 'wiz find' to discover one")
        return 1
    print("%d light(s):" % len(targets))
    results = [apply(light, None) for light in targets]
    return 0 if all(results) else 1


def cmd_find(state, include_forgotten=False):
    found = discover()
    if not found:
        print("no WiZ lights answered the broadcast (are you on the same network?)")
        return 1
    tracked = merge_discovered(state, found, include_ignored=include_forgotten)
    save_state(state)
    print("found %d light(s), tracking %d:" % (len(found), len(tracked)))
    results = [apply(light, None) for light in tracked]
    if not tracked:
        print("  all discovered lights are forgotten; use --include-forgotten to re-adopt")
        return 0
    return 0 if all(results) else 1


def cmd_rename(state, args, targets):
    _validate_args("rename", args)
    if not targets:
        sys.exit("wiz: no lights known yet - run 'wiz' first")
    name = args[0]
    for target in targets:
        if target.get("_synthetic"):
            target = _new_record(state, target["ip"])
            state["lights"].append(target)
        target["name"] = name
        print("  %s  renamed to '%s'" % (_record_prefix(target), name))
    save_state(state)


def _remember_ignored(state, key):
    if key and key not in state["ignored"]:
        state["ignored"].append(key)


def cmd_forget(state, targets):
    doomed = targets or list(state["lights"])
    seen = set()
    for target in doomed:
        identity = (str(target.get("id")), target.get("ip"))
        if identity in seen:
            continue
        seen.add(identity)
        actual = next(
            (light for light in state["lights"]
             if light.get("id") == target.get("id") and light.get("ip") == target.get("ip")),
            None,
        )
        if actual:
            key = actual.get("uid") or "ip:" + actual["ip"]
            _remember_ignored(state, key)
            state["lights"].remove(actual)
            print("  %s  forgotten" % _record_prefix(actual))
        elif target.get("ip"):
            _remember_ignored(state, "ip:" + target["ip"])
            print("  %s  forgotten" % target["ip"])
    save_state(state)


def cmd_add(state, ip):
    if not looks_like_ip(ip):
        sys.exit("wiz: '%s' does not look like an IP address" % ip)
    record = _record_by_ip(state["lights"], ip)
    if record is None:
        record = _new_record(state, ip)
        state["lights"].append(record)
    _remove_ignored_keys(state, ["ip:" + ip])
    save_state(state)
    print("added %s" % _record_prefix(record))
    return 0 if apply(record, None) else 1


def cmd_control(state, cmd, args, target):
    _validate_args(cmd, args)
    targets = resolve_targets(state, target)
    if not targets:
        print("no tracked lights; run 'wiz' or 'wiz find' to discover one")
        return 1
    params = build_params(cmd, args)
    print("%d light(s):" % len(targets))
    results = [apply(light, params) for light in targets]
    return 0 if all(results) else 1


def main():
    argv = sys.argv[1:]
    if argv and argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if argv and argv[0] in ("-V", "--version", "version"):
        print("wiz %s" % VERSION)
        return 0

    state = load_state()
    if not argv:
        return cmd_status(state, auto_discover=True)

    cmd = argv[0]
    if cmd == "find":
        if len(argv) == 1:
            return cmd_find(state)
        if len(argv) == 2 and argv[1] == "--include-forgotten":
            return cmd_find(state, include_forgotten=True)
        sys.exit("usage: wiz find [--include-forgotten]")

    if cmd == "add":
        if len(argv) != 2:
            sys.exit("usage: wiz add <ip>")
        return cmd_add(state, argv[1])

    if cmd == "list":
        if len(argv) != 1:
            sys.exit("usage: wiz list")
        return cmd_status(state)

    args, target = split_target(cmd, argv[1:])
    if cmd == "status":
        _validate_args(cmd, args)
        return cmd_status(state, target, auto_discover=target is None)
    if cmd == "rename":
        return cmd_rename(state, args, resolve_targets(state, target))
    if cmd == "forget":
        _validate_args(cmd, args)
        cmd_forget(state, resolve_targets(state, target) if target else [])
        return 0

    if cmd.isdigit() or cmd in ("on", "off") or cmd in PRESETS \
            or cmd in ("temp", "rgb", "scene"):
        return cmd_control(state, cmd, args, target)
    sys.exit("wiz: unknown command '%s' (run 'wiz --help' for help)" % cmd)


if __name__ == "__main__":
    sys.exit(main())
