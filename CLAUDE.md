# olegovic-singbox-routing

My routing profile (`profiles/olegovic.json`, plus friends' copies like `profiles/barada.json` limited via `clients`/`platforms`/`in_all`) generated into configs for Throne, Happ, INCY and sing-box clients (`dist/`). README.md (EN) and README.ru.md (RU) explain the rules.

## Rules

- Edit `profiles/olegovic.json` or `build.py`, **never** `dist/` by hand.
- After any change run `python3 build.py --check`, then `python3 build.py`, and commit `dist/` together with the source. CI fails if `dist/` is stale and validates the output with `sing-box check`.
- Rule order matters (first match wins). When you add or move a rule, update the "What goes where" tables in **both** READMEs.
- No server addresses, UUIDs or keys in this repo. It's public and holds routing only.
