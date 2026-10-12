#!/usr/bin/env python3
"""Generate client-specific routing profiles from profiles/*.json.

Each source profile is built for every desktop platform it lists, once with
"system" rules going through the proxy and once with them going direct, plus
one mobile build without process rules:

  dist/throne/<Name>_<Platform>_system_<proxy|direct>       throne://route link
  dist/throne/<Name>_<Platform>_system_<proxy|direct>.json  plain rules array
  dist/throne/ALL                                           remoteroute bundle
  dist/singbox/<same names>.json and <Name>_mobile.json     sing-box dns + route
  dist/happ/<Name>.json, <Name>.DEEPLINK                    Happ (mobile build)
  dist/incy/<Name>.json, <Name>.DEEPLINK                    INCY (mobile build)

Usage:
  python3 build.py           regenerate dist/
  python3 build.py --check   also verify every referenced rule-set exists
                             upstream (needs network)

Only the standard library is used.
"""
import base64
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROFILES = ROOT / "profiles"
DIST = ROOT / "dist"

REPO = "olegoviccc/olegovic-singbox-routing"
BRANCH = "main"
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/dist"

# Geo data used for sing-box (.srs) and Happ/INCY (.dat). Same category names
# in both, so geosite:X / geosite-X.srs always match.
RF = "https://raw.githubusercontent.com/runetfreedom/russia-v2ray-rules-dat/release"
SRS_URL = RF + "/sing-box/rule-set-{kind}/{kind}-{name}.srs"
GEOIP_DAT = RF + "/geoip.dat"
GEOSITE_DAT = RF + "/geosite.dat"

# Throne resolves rule-set names through its built-in list.
THRONE_SRSLIST = "https://raw.githubusercontent.com/throneproj/routeprofiles/rule-set/srslist.h"

# DoH resolvers: remote is used for proxied domains (through the proxy),
# direct for Russian/direct domains (Yandex, so Russian CDNs pick local nodes).
DNS_REMOTE = "1.1.1.1"
DNS_DIRECT = "77.88.8.8"

# Happ/INCY DNS defaults; a profile can override any key via "happ": {...}.
HAPP_DEFAULTS = {
    "RemoteDNSType": "DoH",
    "RemoteDNSDomain": f"https://{DNS_REMOTE}/dns-query",
    "RemoteDNSIP": DNS_REMOTE,
    "DomesticDNSType": "DoH",
    "DomesticDNSDomain": f"https://{DNS_DIRECT}/dns-query",
    "DomesticDNSIP": DNS_DIRECT,
    "DomainStrategy": "IPIfNonMatch",
    "FakeDNS": "false",
    "UseChunkFiles": "true",
}

OUTBOUNDS = ("proxy", "direct", "block", "system")
PLATFORMS = ("linux", "windows", "macos")
PLATFORM_NAMES = {"linux": "Linux", "windows": "Windows", "macos": "macOS"}

# sing-box ORs these together within one rule (rule_set merges into them).
ADDRESS = ("domain", "domain_suffix", "domain_keyword", "domain_regex", "ip_cidr")
# sing-box ANDs each of these with everything else, so every one becomes its
# own rule. Values are a list (all platforms) or {"linux": [...], ...}.
PROCESS = ("process_name", "process_path", "process_path_regex")
# Emitted together as a single AND rule; can't be mixed with other matchers.
CONDITION = ("ip_version", "network", "port")


def die(msg):
    sys.exit(f"error: {msg}")


def b64(data, urlsafe=False):
    raw = data.encode()
    if urlsafe:
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return base64.b64encode(raw).decode()


def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def slug(name):
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")


def load_profile(path):
    p = json.loads(path.read_text(encoding="utf-8"))
    where = path.name
    if not p.get("name"):
        die(f"{where}: missing name")
    if p.get("final", "proxy") not in ("proxy", "direct"):
        die(f"{where}: final must be proxy or direct")
    for plat in p.get("platforms", []):
        if plat not in PLATFORMS:
            die(f"{where}: unknown platform {plat!r}")
    known = set(ADDRESS + PROCESS + CONDITION) | {"geosite", "geoip", "protocol", "outbound", "name"}
    for i, rule in enumerate(p.get("rules", []), 1):
        tag = f"{where}: rule {rule.get('name') or i!r}"
        if rule.get("outbound") not in OUTBOUNDS:
            die(f"{tag}: outbound must be one of {OUTBOUNDS}")
        unknown = set(rule) - known
        if unknown:
            die(f"{tag}: unknown keys {sorted(unknown)}")
        for key in PROCESS:
            if isinstance(rule.get(key), dict) and set(rule[key]) - set(PLATFORMS):
                die(f"{tag}: {key} has unknown platforms")
        has_cond = any(k in rule for k in CONDITION)
        has_other = any(k in rule for k in known - set(CONDITION) - {"outbound", "name"})
        if has_cond and has_other:
            die(f"{tag}: {CONDITION} can't be combined with other matchers")
        if not has_cond and not has_other:
            die(f"{tag}: no matchers")
    return p


def rule_sets(rule):
    return ([f"geosite-{n}" for n in rule.get("geosite", [])]
            + [f"geoip-{n}" for n in rule.get("geoip", [])])


def for_platform(value, platform):
    if platform is None or not value:
        return []
    if isinstance(value, dict):
        return value.get(platform, [])
    return value


def action(outbound):
    if outbound == "block":
        return {"action": "reject"}
    return {"action": "route", "outbound": outbound}


def expand(rule, platform, system):
    """One source rule -> list of (label, sing-box matchers, action) parts.

    platform None means a mobile build: process rules are dropped, and so are
    "system" rules, since there is nothing to match them against."""
    outbound = rule["outbound"]
    if outbound == "system":
        if platform is None:
            return []
        outbound = system
    act = action(outbound)
    name = rule.get("name", "")
    parts = []

    cond = {k: rule[k] for k in CONDITION if k in rule}
    if cond:
        parts.append((name, cond, act))

    addr = {k: rule[k] for k in ADDRESS if rule.get(k)}
    if rule_sets(rule):
        addr["rule_set"] = rule_sets(rule)
    if addr:
        parts.append((name, addr, act))

    for proto in rule.get("protocol", []):
        parts.append((f"{name} ({proto})", {"protocol": proto}, act))

    for key in PROCESS:
        values = for_platform(rule.get(key), platform)
        if values:
            label = key.replace("process_", "").replace("_", " ")
            parts.append((f"{name} (process {label})", {key: values}, act))
    return parts


def target_parts(p, platform, system):
    parts = [
        ("DNS", {"protocol": "dns"}, {"action": "hijack-dns"}),
        ("LAN", {"ip_is_private": True}, action("direct")),
    ]
    for rule in p.get("rules", []):
        parts += expand(rule, platform, system)
    return parts


def targets(p):
    """(display name, file slug, platform, system) for every build of p."""
    out = []
    uses_system = any(r["outbound"] == "system" for r in p.get("rules", []))
    for plat in p.get("platforms", []):
        for system in (("proxy", "direct") if uses_system else ("proxy",)):
            suffix = f" {PLATFORM_NAMES[plat]}" + (f" system-{system}" if uses_system else "")
            out.append((p["name"] + suffix, slug(p["name"] + suffix), plat, system))
    return out


# --- Throne -------------------------------------------------------------------

def throne_rules(parts):
    return [{**match, **act} for _, match, act in parts]


def throne_link(name, final, parts):
    rules = [{**match, **act, "name": label or f"rule #{i}", "type": "custom"}
             for i, (label, match, act) in enumerate(parts, 1)]
    payload = {
        "default_outbound": final,
        "kind": "throne-route-profile",
        "name": name,
        "rules": rules,
        "v": 1,
    }
    return "throne://route/" + b64(compact(payload), urlsafe=True)


# --- sing-box -----------------------------------------------------------------

def singbox_route(final, parts):
    rules = [{"action": "sniff"}]
    tags = []
    for _, match, act in parts:
        rules.append({**match, **act})
        tags += [t for t in match.get("rule_set", []) if t not in tags]
    defs = []
    for tag in tags:
        kind, name = tag.split("-", 1)
        defs.append({
            "tag": tag,
            "type": "remote",
            "format": "binary",
            "url": SRS_URL.format(kind=kind, name=name),
            "download_detour": "direct",
        })
    return {
        "dns": singbox_dns(parts),
        "route": {
            "rules": rules,
            "rule_set": defs,
            "final": final,
            "auto_detect_interface": True,
            "default_domain_resolver": "dns-direct",
        },
    }


# Same idea as Throne's "DNS routing": domains of direct rules resolve via the
# direct server, domains of proxy rules via the remote one, the rest remote.
# IPv4 only, matching the IPv6 reject rule.
def singbox_dns(parts):
    servers = {"direct": "dns-direct", "proxy": "dns-remote"}
    rules = []
    for _, match, act in parts:
        server = servers.get(act.get("outbound"))
        if not server:
            continue
        cond = {k: v for k, v in match.items() if k in ADDRESS and k != "ip_cidr"}
        sites = [t for t in match.get("rule_set", []) if t.startswith("geosite-")]
        if sites:
            cond["rule_set"] = sites
        if cond:
            rules.append({**cond, "action": "route", "server": server})
    return {
        "servers": [
            {"type": "https", "tag": "dns-remote", "server": DNS_REMOTE, "detour": "proxy"},
            {"type": "https", "tag": "dns-direct", "server": DNS_DIRECT},
        ],
        "rules": rules,
        "final": "dns-remote",
        "strategy": "ipv4_only",
    }


# --- Happ / INCY --------------------------------------------------------------

def xray_domains(rule):
    out = [f"geosite:{n}" for n in rule.get("geosite", [])]
    out += [f"full:{d}" for d in rule.get("domain", [])]
    out += [f"domain:{d}" for d in rule.get("domain_suffix", [])]
    out += [f"keyword:{d}" for d in rule.get("domain_keyword", [])]
    out += [f"regexp:{d}" for d in rule.get("domain_regex", [])]
    return out


def xray_ips(rule):
    return [f"geoip:{n}" for n in rule.get("geoip", [])] + rule.get("ip_cidr", [])


def happ_profile(p, last_updated):
    buckets = {o: {"sites": [], "ip": []} for o in ("proxy", "direct", "block")}
    buckets["direct"]["sites"].append("geosite:private")
    buckets["direct"]["ip"].append("geoip:private")
    order = []
    for rule in p.get("rules", []):
        o = rule["outbound"]
        sites, ips = xray_domains(rule), xray_ips(rule)
        # Happ has no process, protocol or port matching; system rules are
        # desktop-only.
        if o == "system" or not (sites or ips):
            continue
        if o not in order:
            order.append(o)
        buckets[o]["sites"] += [x for x in sites if x not in buckets[o]["sites"]]
        buckets[o]["ip"] += [x for x in ips if x not in buckets[o]["ip"]]
    # Happ can't keep per-rule order, only the order of the three buckets.
    order += [o for o in buckets if o not in order]

    prof = {
        "Name": p["name"],
        "GlobalProxy": "true" if p.get("final", "proxy") == "proxy" else "false",
        **HAPP_DEFAULTS,
        "Geoipurl": GEOIP_DAT,
        "Geositeurl": GEOSITE_DAT,
        "LastUpdated": last_updated,
        "DnsHosts": {},
        "RouteOrder": "-".join(order),
        "DirectSites": buckets["direct"]["sites"],
        "DirectIp": buckets["direct"]["ip"],
        "ProxySites": buckets["proxy"]["sites"],
        "ProxyIp": buckets["proxy"]["ip"],
        "BlockSites": buckets["block"]["sites"],
        "BlockIp": buckets["block"]["ip"],
    }
    prof.update(p.get("happ", {}))
    return prof


# Happ only refreshes a profile when LastUpdated changes, so bump it only when
# the rest of the profile actually changed (keeps rebuilds deterministic).
def happ_last_updated(p, existing_path):
    try:
        old = json.loads(existing_path.read_text(encoding="utf-8"))
        if happ_profile(p, old["LastUpdated"]) == old:
            return old["LastUpdated"]
    except (OSError, ValueError, KeyError):
        pass
    return str(int(time.time()))


# --- output -------------------------------------------------------------------

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False)


def build(profiles):
    expected = set()

    def out(rel, text):
        expected.add(DIST / rel)
        write(DIST / rel, text)

    bundle = []
    built = []
    for p in profiles:
        final = p.get("final", "proxy")
        for display, name, plat, system in targets(p):
            parts = target_parts(p, plat, system)
            out(f"throne/{name}", throne_link(display, final, parts))
            out(f"throne/{name}.json", dump(throne_rules(parts)))
            out(f"singbox/{name}.json", dump(singbox_route(final, parts)))
            bundle.append(f"{RAW}/throne/{name}#{display}")
            built.append(name)

        name = slug(p["name"])
        out(f"singbox/{name}_mobile.json", dump(singbox_route(final, target_parts(p, None, None))))
        happ_json = DIST / f"happ/{name}.json"
        prof = happ_profile(p, happ_last_updated(p, happ_json))
        for client in ("happ", "incy"):
            out(f"{client}/{name}.json", dump(prof))
            out(f"{client}/{name}.DEEPLINK", f"{client}://routing/onadd/{b64(compact(prof))}")
        built.append(f"{name} (mobile)")

    if bundle:
        out("throne/ALL", "throne://remoteroute/" + b64("\n".join(bundle), urlsafe=True))

    for stale in DIST.rglob("*"):
        if stale.is_file() and stale not in expected:
            stale.unlink()
            print(f"removed stale {stale.relative_to(ROOT)}")
    return built


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "routing-build"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def check(profiles):
    srslist = fetch(THRONE_SRSLIST).decode()
    throne_tags = set(re.findall(r'\{"([^"]+)",\s*"', srslist))
    bad = []
    seen = set()
    for p in profiles:
        for rule in p.get("rules", []):
            for tag in rule_sets(rule):
                if tag in seen:
                    continue
                seen.add(tag)
                if tag not in throne_tags:
                    bad.append(f"{p['name']}: {tag} is not a Throne built-in rule-set")
                kind, name = tag.split("-", 1)
                url = SRS_URL.format(kind=kind, name=name)
                try:
                    req = urllib.request.Request(url, method="HEAD")
                    urllib.request.urlopen(req, timeout=30).close()
                except urllib.error.URLError:
                    bad.append(f"{p['name']}: {tag} not found in runetfreedom ({url})")
            for key in PROCESS:
                if key != "process_path_regex":
                    continue
                for plat in PLATFORMS:
                    for rx in for_platform(rule.get(key), plat):
                        try:
                            re.compile(rx)
                        except re.error as e:
                            bad.append(f"{p['name']}: bad regex {rx!r}: {e}")
    for b in bad:
        print(b, file=sys.stderr)
    if bad:
        sys.exit(1)
    print(f"all {len(seen)} rule-sets exist upstream")


def main():
    files = sorted(PROFILES.glob("*.json"))
    if not files:
        die("no profiles in profiles/")
    profiles = [load_profile(f) for f in files]
    names = [slug(p["name"]) for p in profiles]
    if len(set(names)) != len(names):
        die("two profiles share the same name")
    built = build(profiles)
    print(f"built {len(built)} target(s): {', '.join(built)}")
    if "--check" in sys.argv[1:]:
        check(profiles)


if __name__ == "__main__":
    main()
