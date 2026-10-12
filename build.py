#!/usr/bin/env python3
"""Generate client-specific routing profiles from profiles/*.json.

One source profile -> four outputs:

  dist/throne/<Name>        throne://route/<base64> link (import in Throne)
  dist/throne/<Name>.json   plain rules array (for reading / copy-paste)
  dist/singbox/<Name>.json  sing-box "route" block with remote rule_set defs
  dist/happ/<Name>.json     Happ routing profile (Xray geosite/geoip)
  dist/happ/<Name>.DEEPLINK happ://routing/onadd/<base64>
  dist/incy/...             same as happ, with incy:// links

plus dist/throne/ALL (throne://remoteroute bundle of every profile).

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

# Happ/INCY DNS defaults; a profile can override any key via "happ": {...}.
HAPP_DEFAULTS = {
    "RemoteDNSType": "DoH",
    "RemoteDNSDomain": "https://1.1.1.1/dns-query",
    "RemoteDNSIP": "1.1.1.1",
    "DomesticDNSType": "DoH",
    "DomesticDNSDomain": "https://77.88.8.8/dns-query",
    "DomesticDNSIP": "77.88.8.8",
    "DomainStrategy": "IPIfNonMatch",
    "FakeDNS": "false",
    "UseChunkFiles": "true",
}

OUTBOUNDS = ("proxy", "direct", "block")
MATCHERS = ("geosite", "geoip", "domain", "domain_suffix", "domain_keyword",
            "domain_regex", "ip_cidr")


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
    for i, rule in enumerate(p.get("rules", []), 1):
        if rule.get("outbound") not in OUTBOUNDS:
            die(f"{where}: rule #{i}: outbound must be one of {OUTBOUNDS}")
        unknown = set(rule) - set(MATCHERS) - {"outbound", "name"}
        if unknown:
            die(f"{where}: rule #{i}: unknown keys {sorted(unknown)}")
        if not any(rule.get(m) for m in MATCHERS):
            die(f"{where}: rule #{i}: no matchers")
    return p


def rule_sets(rule):
    return ([f"geosite-{n}" for n in rule.get("geosite", [])]
            + [f"geoip-{n}" for n in rule.get("geoip", [])])


def action(rule):
    if rule["outbound"] == "block":
        return {"action": "reject"}
    return {"action": "route", "outbound": rule["outbound"]}


# sing-box splits domain and IP matchers of one rule with OR, which is what we
# want, so a rule maps 1:1. Throne uses the same field names.
def singbox_matchers(rule):
    out = {}
    for key in ("domain", "domain_suffix", "domain_keyword", "domain_regex", "ip_cidr"):
        if rule.get(key):
            out[key] = rule[key]
    if rule_sets(rule):
        out["rule_set"] = rule_sets(rule)
    return out


# --- Throne -------------------------------------------------------------------

def throne_rules(p):
    rules = [
        {"action": "hijack-dns", "protocol": "dns"},
        {"action": "route", "ip_is_private": True, "outbound": "direct"},
    ]
    for rule in p.get("rules", []):
        rules.append({**action(rule), **singbox_matchers(rule)})
    return rules


def throne_link(p):
    rules = []
    for i, r in enumerate(throne_rules(p), 1):
        rules.append({**r, "name": f"rule #{i}", "type": "custom"})
    payload = {
        "default_outbound": p.get("final", "proxy"),
        "kind": "throne-route-profile",
        "name": p["name"],
        "rules": rules,
        "v": 1,
    }
    return "throne://route/" + b64(compact(payload), urlsafe=True)


# --- sing-box -----------------------------------------------------------------

def singbox_route(p):
    rules = [
        {"action": "sniff"},
        {"protocol": "dns", "action": "hijack-dns"},
        {"ip_is_private": True, "action": "route", "outbound": "direct"},
    ]
    tags = []
    for rule in p.get("rules", []):
        rules.append({**singbox_matchers(rule), **action(rule)})
        tags += [t for t in rule_sets(rule) if t not in tags]
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
    return {"route": {
        "rules": rules,
        "rule_set": defs,
        "final": p.get("final", "proxy"),
        "auto_detect_interface": True,
    }}


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
    buckets = {o: {"sites": [], "ip": []} for o in OUTBOUNDS}
    buckets["direct"]["sites"].append("geosite:private")
    buckets["direct"]["ip"].append("geoip:private")
    order = []
    for rule in p.get("rules", []):
        o = rule["outbound"]
        if o not in order:
            order.append(o)
        buckets[o]["sites"] += [x for x in xray_domains(rule) if x not in buckets[o]["sites"]]
        buckets[o]["ip"] += [x for x in xray_ips(rule) if x not in buckets[o]["ip"]]
    # Happ can't keep per-rule order, only the order of the three buckets.
    order += [o for o in OUTBOUNDS if o not in order]

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


def build(profiles):
    expected = set()

    def out(rel, text):
        expected.add(DIST / rel)
        write(DIST / rel, text)

    bundle = []
    for p in profiles:
        name = slug(p["name"])
        out(f"throne/{name}", throne_link(p))
        out(f"throne/{name}.json", json.dumps(throne_rules(p), indent=2, ensure_ascii=False))
        out(f"singbox/{name}.json", json.dumps(singbox_route(p), indent=2, ensure_ascii=False))
        bundle.append(f"{RAW}/throne/{name}#{p['name']}")

        happ_json = DIST / f"happ/{name}.json"
        prof = happ_profile(p, happ_last_updated(p, happ_json))
        text = json.dumps(prof, indent=2, ensure_ascii=False)
        for client in ("happ", "incy"):
            out(f"{client}/{name}.json", text)
            out(f"{client}/{name}.DEEPLINK", f"{client}://routing/onadd/{b64(compact(prof))}")

    out("throne/ALL", "throne://remoteroute/" + b64("\n".join(bundle), urlsafe=True))

    for stale in DIST.rglob("*"):
        if stale.is_file() and stale not in expected:
            stale.unlink()
            print(f"removed stale {stale.relative_to(ROOT)}")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "routing-build"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def check(profiles):
    srslist = fetch(THRONE_SRSLIST).decode()
    throne_tags = set(re.findall(r'\{"([^"]+)",\s*"', srslist))
    bad = []
    for p in profiles:
        for rule in p.get("rules", []):
            for tag in rule_sets(rule):
                if tag not in throne_tags:
                    bad.append(f"{p['name']}: {tag} is not a Throne built-in rule-set")
                kind, name = tag.split("-", 1)
                url = SRS_URL.format(kind=kind, name=name)
                try:
                    req = urllib.request.Request(url, method="HEAD")
                    urllib.request.urlopen(req, timeout=30).close()
                except urllib.error.URLError:
                    bad.append(f"{p['name']}: {tag} not found in runetfreedom ({url})")
    for b in bad:
        print(b, file=sys.stderr)
    if bad:
        sys.exit(1)
    print("all rule-sets exist upstream")


def main():
    files = sorted(PROFILES.glob("*.json"))
    if not files:
        die("no profiles in profiles/")
    profiles = [load_profile(f) for f in files]
    names = [slug(p["name"]) for p in profiles]
    if len(set(names)) != len(names):
        die("two profiles share the same name")
    build(profiles)
    print(f"built {len(profiles)} profile(s): {', '.join(names)}")
    if "--check" in sys.argv[1:]:
        check(profiles)


if __name__ == "__main__":
    main()
