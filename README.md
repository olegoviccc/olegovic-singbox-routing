# olegovic-singbox-routing

My routing profile, written once in `profiles/olegovic.json` and generated for several clients.

| Client | File | Notes |
| --- | --- | --- |
| [Throne](https://github.com/throneproj/Throne) | `dist/throne/Olegovic_<Linux\|Windows>_system_<proxy\|direct>` | `throne://route/…` link. `dist/throne/ALL` adds all four |
| Happ | `dist/happ/Olegovic.DEEPLINK` / `.json` | mobile build, no process rules |
| INCY | `dist/incy/Olegovic.DEEPLINK` / `.json` | mobile build, no process rules |
| sing-box (Hiddify, Karing, NekoBox…) | `dist/singbox/<same names>.json`, `Olegovic_mobile.json` | `route` block to merge into a full config |

## What goes where

Rules are checked top to bottom and the first match wins. Anything that matches nothing goes through the **proxy**.

| # | Rule | Goes | Matches |
| --- | --- | --- | --- |
| – | DNS, LAN | hijack / direct | added automatically |
| 1 | IPv6 off | reject | every IPv6 connection; apps fall back to IPv4 |
| 2 | Ads | reject | `category-ads-all` |
| 3 | Torrents | direct | the BitTorrent protocol (any client), qBittorrent processes |
| 4 | Messengers | proxy | Telegram, Discord, WhatsApp domains and Telegram IPs. Discord/Telegram processes too, so **Discord voice** (UDP to bare IPs) is caught |
| 5 | Gaming | direct | Steam/Blizzard domains; Steam, Battle.net, Wine/Proton, umu, Lutris and Faugus processes; anything under Steam, `steamapps`, `compatibilitytools.d`, `~/Games`, `~/Faugus` and the Battle.net/Blizzard install folders |
| 6 | QUIC off | reject | UDP 443 that wasn't already sent direct for gaming. Browsers and YouTube fall back to TCP |
| 7 | Blocked or geoblocked | proxy | `ru-blocked` (domains and IPs), YouTube, Roblox, AI services, GitHub, Docker, npm, AUR, JetBrains, Notion, NVIDIA, Intel, Spotify |
| 8 | Russia-only services | direct | `ru-available-only-inside` (banks, government services and other sites that reject foreign IPs) |
| 9 | **System** | **proxy or direct**, per build | terminals, shells, CLI tools, package managers (pacman, paru, yay, Shelly, flatpak…), KDE Plasma and its helpers, systemd services, Docker. On Windows: `C:\Windows\…`, Windows Terminal, PowerShell, Git, Defender |
| 10 | Russia | direct | `category-ru`, `geoip:ru`, `.ru` `.su` `.рф` |

Browsers aren't in the System rule. They follow rules 7, 8 and 10 in every build.

### Things to know

- **Process rules need Throne's TUN mode** for apps that ignore the system proxy, such as games, qBittorrent and most CLI tools. In system-proxy mode those apps never reach Throne.
- **A process is matched by the program that opens the connection**, not the window you see. That's why the System rule lists `curl`, `git`, `pacman` and so on, not just the terminals. Python apps show up as `python3`, so they aren't matched by name.
- **Linux root processes** (`pacman` under sudo, Shelly's main `shelly` process, `packagekitd`, `fwupd`) can only be identified if Throne's core can read other users' `/proc` entries. If it can't, they fall through to rule 10 and then to the proxy.
- **Happ/INCY can't keep rule order.** Rules are merged into Block, Proxy and Direct buckets, applied in that order.

## Importing

**Throne:** import from a raw link (it works once this is on `main`), e.g.

```
https://raw.githubusercontent.com/olegoviccc/olegovic-singbox-routing/main/dist/throne/Olegovic_Linux_system_direct
```

Or paste the contents of `dist/throne/ALL`, a `throne://remoteroute/` link that adds all four.

**Happ / INCY:** open the `.DEEPLINK` contents on the device. `onadd` adds the profile and activates it.

**sing-box:** merge `dns` and `route` from the JSON into your config. They expect outbounds tagged `proxy` and `direct`.

## Throne settings (DNS and TUN)

Throne keeps its settings in its own database, not in a file you can import, so set these by hand. They work with all four route profiles: with **Enable DNS Routing** on, Throne reads the active profile and sends the domains of direct rules to the Direct DNS server and the domains of proxy rules to the Remote DNS server.

**Routing settings → DNS** (leave *Use Custom DNS Object* off)

| Setting | Value | Why |
| --- | --- | --- |
| Remote DNS | `https://1.1.1.1/dns-query` | DoH through the proxy for proxied and unmatched domains. Your ISP can't see or tamper with the lookups |
| Remote DNS → Disable IPv6 | ✅ | IPv4 answers only, matching the IPv6 reject rule |
| Direct DNS | `https://77.88.8.8/dns-query` | Yandex DoH for direct domains. Russian CDNs get a Russian answer, and the queries are encrypted |
| Direct DNS → Disable IPv6 | ✅ | |
| Default DNS server | `remote` | domains that match no rule are resolved through the proxy |
| Enable DNS Routing | ✅ | |
| Enable FakeIP | ❌ | not needed: sniffing already restores domain names, and FakeIP can break apps that cache IPs |
| Default Domain Strategy | `ipv4_only` | how the proxy server's own hostname is resolved |
| Resolve Domain Strategy | *(empty)* | |

**TUN settings**

| Setting | Value | Why |
| --- | --- | --- |
| Tun Enable IPv6 | ❌ | with Strict Route on, IPv6 becomes unreachable instead of bypassing the tunnel |
| Strict Route | ✅ | stops IPv6 and DNS from leaking around the tunnel. Already on by default on Windows; turn it on for Linux |
| Auto Redirect (Linux) | ✅ (default) | |
| Private Range Bypass | ✅ (default) | LAN, KDE Connect and printers stay outside the tunnel |

If Strict Route breaks Docker or VM networking on Linux, turn it off and also turn off IPv6 on the system (e.g. `sysctl net.ipv6.conf.all.disable_ipv6=1`). Otherwise IPv6 traffic goes around the tunnel.

The sing-box files in `dist/singbox/` include the same DNS setup as a `dns` block. Happ/INCY profiles use the same two resolvers.

## Editing

1. Edit `profiles/olegovic.json`.
2. Run `python3 build.py` (Python 3, no dependencies). `--check` also verifies that every rule-set exists upstream.
3. Commit `profiles/` and `dist/` together. CI fails if `dist/` is stale, and it runs every sing-box output through `sing-box check`.

Rule format:

```jsonc
{
  "name": "Gaming",
  "outbound": "direct",            // proxy | direct | block | system
  "geosite": ["steam"],            // Throne: geosite-steam, Happ: geosite:steam
  "geoip": ["ru"],
  "domain": [], "domain_suffix": [], "domain_keyword": [], "domain_regex": [], "ip_cidr": [],
  "protocol": ["bittorrent"],      // sniffed protocol
  "process_name":       { "linux": ["steam"], "windows": ["steam.exe"] },  // or a plain list for all platforms
  "process_path":       { ... },
  "process_path_regex": { "linux": ["/steamapps/"] }                       // Go RE2 syntax
}
```

- Domain, IP and geo matchers are combined with OR.
- `protocol` and each `process_*` key become separate rules with the same outbound, because sing-box would otherwise require all of them to match at once.
- `ip_version`, `network` and `port` form one combined rule and can't be mixed with other matchers.
- `outbound: "system"` produces the two builds per platform, and the rule is left out of mobile builds.

### Where the geo lists come from

- **Throne:** its built-in rule-sets ([list](https://github.com/throneproj/routeprofiles/blob/rule-set/srslist.h)).
- **sing-box / Happ / INCY:** [runetfreedom/russia-v2ray-rules-dat](https://github.com/runetfreedom/russia-v2ray-rules-dat), which uses the same category names.

`ru-blocked` combines the Roskomnadzor registry (via antifilter) with re:filter and community.antifilter, which also list some sites that block Russian users. Those lists are never complete, which is why everything defaults to the proxy.
