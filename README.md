# olegovic-singbox-routing

My routing profiles, written once and generated for several clients:

| Client | What to use |
| --- | --- |
| [Throne](https://github.com/throneproj/Throne) | `dist/throne/<Name>` (a `throne://route/…` link) or `dist/throne/ALL` (all profiles at once) |
| Happ | `dist/happ/<Name>.DEEPLINK` (`happ://routing/onadd/…`) or `dist/happ/<Name>.json` |
| INCY | `dist/incy/<Name>.DEEPLINK` (`incy://routing/onadd/…`) or `dist/incy/<Name>.json` |
| Any sing-box client (sing-box, Hiddify, Karing, NekoBox…) | `dist/singbox/<Name>.json`, a `route` block to paste into a full config |

## Profiles

| Profile | Default | Direct | Proxy | Blocked |
| --- | --- | --- | --- | --- |
| **Bypass Russia** | proxy | private IPs, `category-ru`, `ru-available-only-inside`, `geoip:ru`, `.ru` `.su` `.рф` | everything else | ads |

## Importing

**Throne:** import a single profile from its raw link, e.g.

```
https://raw.githubusercontent.com/olegoviccc/olegovic-singbox-routing/main/dist/throne/Bypass_Russia
```

Or open the contents of `dist/throne/ALL`, a `throne://remoteroute/` link that adds every profile from this repo.

**Happ / INCY:** open the `.DEEPLINK` file's contents on the device, or paste the link into the app. `onadd` adds the profile and activates it right away.

**sing-box:** merge `route` from `dist/singbox/<Name>.json` into your config. It expects outbounds tagged `proxy` and `direct`. Rule-sets download through `direct`.

## Editing

1. Edit or add a file in `profiles/` (format below).
2. Run `python3 build.py` (Python 3, no dependencies). `--check` also verifies that every rule-set exists upstream.
3. Commit `profiles/` and `dist/` together. CI fails if `dist/` is out of date.

```jsonc
{
  "name": "My Profile",          // shown in the client; file names come from it
  "final": "proxy",              // where unmatched traffic goes: proxy | direct
  "rules": [                     // first match wins (see the Happ note)
    {
      "outbound": "direct",      // proxy | direct | block
      "geosite": ["category-ru"],      // geosite-<name> / geosite:<name>
      "geoip": ["ru"],                 // geoip-<name>   / geoip:<name>
      "domain": ["exact.example.com"],
      "domain_suffix": ["example.com"],
      "domain_keyword": ["example"],
      "domain_regex": ["^ex.*\\.com$"],
      "ip_cidr": ["1.2.3.0/24"]
    }
  ],
  "happ": { "RemoteDNSIP": "8.8.8.8" }  // optional overrides for Happ/INCY fields
}
```

Every profile automatically starts with DNS hijack and sends private/LAN IPs direct.

### Where the geo lists come from

- **Throne:** its built-in rule-set names ([list](https://github.com/throneproj/routeprofiles/blob/rule-set/srslist.h)).
- **sing-box, Happ, INCY:** [runetfreedom/russia-v2ray-rules-dat](https://github.com/runetfreedom/russia-v2ray-rules-dat) (`.srs` for sing-box, `geosite.dat`/`geoip.dat` for Happ/INCY), which uses the same category names.

`build.py --check` fails if a name you use is missing from either source.

### Client differences

- **Happ/INCY** can't keep rule order. Rules are merged into Direct, Proxy and Block buckets, and `RouteOrder` follows the order in which each outbound first appears in `rules`.
- Happ only re-applies a profile when `LastUpdated` changes. The build bumps it only when a profile's content actually changes.
