# olegovic-singbox-routing

[English](README.md) · **Русский**

Мой профиль маршрутизации: пишется один раз в `profiles/olegovic.json` и собирается для нескольких клиентов.

| Клиент | Файл | Примечание |
| --- | --- | --- |
| [Throne](https://github.com/throneproj/Throne) | `dist/throne/Olegovic_<Linux\|Windows\|macOS>_system_<proxy\|direct>` | ссылка `throne://route/…`. `dist/throne/ALL` добавляет все шесть |
| Happ | `dist/happ/Olegovic.DEEPLINK` / `.json` | мобильная сборка, без правил по процессам |
| INCY | `dist/incy/Olegovic.DEEPLINK` / `.json` | мобильная сборка, без правил по процессам |
| sing-box (Hiddify, Karing, NekoBox…) | `dist/singbox/<те же имена>.json`, `Olegovic_mobile.json` | блоки `dns` и `route`, которые нужно влить в полный конфиг |

Остальные профили в `profiles/` — копии для друзей, собираются только для их клиентов:

| Профиль | Ссылка для Throne |
| --- | --- |
| Barada (Windows, только Throne) | `dist/throne/Barada_Windows_system_<proxy\|direct>`, правила как у Olegovic |

## Что куда идёт

Правила проверяются сверху вниз, срабатывает первое подходящее. Всё, что не подошло ни под одно правило, идёт **через прокси**.

| # | Правило | Куда | Что совпадает |
| --- | --- | --- | --- |
| – | DNS, локальная сеть | перехват / напрямую | добавляются автоматически |
| 1 | IPv6 выкл. | блок | любое IPv6-соединение; приложения переключаются на IPv4 |
| 2 | Реклама | блок | `category-ads-all` |
| 3 | Торренты | напрямую | протокол BitTorrent (любой клиент), процессы qBittorrent |
| 4 | Мессенджеры | прокси | домены Telegram, Discord, WhatsApp и IP Telegram. Плюс процессы Discord/Telegram, поэтому ловится и **голос в Discord** (UDP на голые IP) |
| 5 | Игры | напрямую | домены Steam/Blizzard; процессы Steam, Battle.net, Wine/Proton, umu, Lutris и Faugus (на macOS ещё CrossOver, Whisky и Heroic); всё, что лежит в Steam, `steamapps`, `compatibilitytools.d`, `~/Games`, `~/Faugus` и папках установки Battle.net/Blizzard |
| 6 | QUIC выкл. | блок | UDP 443, который не ушёл напрямую как игровой трафик. Браузеры и YouTube переходят на TCP |
| 7 | Заблокированное или геоблок | прокси | `ru-blocked` (домены и IP), YouTube, Roblox, ИИ-сервисы, GitHub, Docker, npm, AUR, JetBrains, Notion, NVIDIA, Intel, Spotify |
| 8 | Сервисы только для России | напрямую | `ru-available-only-inside` (банки, госуслуги и другие сайты, которые не пускают с зарубежных IP) |
| 9 | **Система** | **прокси или напрямую**, в зависимости от сборки | терминалы, оболочки, консольные утилиты, пакетные менеджеры (pacman, paru, yay, Shelly, flatpak…), KDE Plasma и её службы, службы systemd, Docker. На Windows: `C:\Windows\…`, Windows Terminal, PowerShell, Git, Defender. На macOS: `/System/Library/…`, `/usr/…`, Homebrew, Terminal/iTerm2/Ghostty/Warp, обновления системы |
| 10 | Россия | напрямую | `category-ru`, `geoip:ru`, `.ru` `.su` `.рф` |

Браузеры в правило «Система» не входят. Во всех сборках они подчиняются правилам 7, 8 и 10.

### Что стоит знать

- **macOS:** приложения определяются по пути внутри бандла `.app`, поэтому вспомогательные процессы Electron вроде `Discord Helper` тоже попадают под правило. Сетевой процесс Safari живёт в `WebKit.framework`, и правило «Система» его намеренно не трогает, так что на macOS браузеры тоже ведут себя одинаково в обеих сборках.
- **Правила по процессам требуют TUN-режима Throne** для приложений, которые игнорируют системный прокси: игры, qBittorrent и большинство консольных утилит. В режиме системного прокси такие приложения до Throne просто не доходят.
- **Процесс определяется по программе, которая открывает соединение**, а не по окну, которое вы видите. Поэтому в правиле «Система» перечислены `curl`, `git`, `pacman` и т. д., а не только терминалы. Python-приложения видны как `python3`, поэтому по имени их не поймать.
- **Процессы root в Linux** (`pacman` через sudo, основной процесс Shelly `shelly`, `packagekitd`, `fwupd`) определяются, только если ядро Throne может читать чужие записи в `/proc`. Если не может, они проходят дальше до правила 10, а затем уходят в прокси.
- **Happ/INCY не сохраняют порядок правил.** Правила сливаются в группы «Блок», «Прокси» и «Напрямую», которые применяются в этом порядке.

## Импорт

**Throne:** импортируйте по raw-ссылке, например:

```
https://raw.githubusercontent.com/olegoviccc/olegovic-singbox-routing/main/dist/throne/Olegovic_Linux_system_direct
```

Или вставьте содержимое `dist/throne/ALL` — ссылку `throne://remoteroute/`, которая добавляет все шесть профилей.

**Happ / INCY:** откройте содержимое файла `.DEEPLINK` на устройстве. `onadd` добавляет профиль и сразу его включает.

**sing-box:** влейте блоки `dns` и `route` из JSON в свой конфиг. Они ожидают outbound'ы с тегами `proxy` и `direct`.

## Настройки Throne (DNS и TUN)

Throne хранит настройки в собственной базе, а не в файле, который можно импортировать, поэтому их нужно выставить вручную. Названия ниже — как в английском интерфейсе Throne. Настройки подходят для любого профиля маршрутизации: при включённом **Enable DNS Routing** Throne смотрит в активный профиль и отправляет домены из правил «напрямую» на Direct DNS, а домены из правил «прокси» — на Remote DNS.

**Routing settings → DNS** (*Use Custom DNS Object* оставьте выключенным)

| Настройка | Значение | Зачем |
| --- | --- | --- |
| Remote DNS | `https://1.1.1.1/dns-query` | DoH через прокси для проксируемых и неопознанных доменов. Провайдер не видит запросы и не может их подменить |
| Remote DNS → Disable IPv6 | ✅ | только IPv4-ответы, в пару к правилу, блокирующему IPv6 |
| Direct DNS | `https://77.88.8.8/dns-query` | DoH Яндекса для прямых доменов. Российские CDN отдают российские адреса, а запросы зашифрованы |
| Direct DNS → Disable IPv6 | ✅ | |
| Default DNS server | `remote` | домены, не подошедшие ни под одно правило, резолвятся через прокси |
| Enable DNS Routing | ✅ | |
| Enable FakeIP | ❌ | не нужно: сниффинг и так восстанавливает имена доменов, а FakeIP может ломать приложения, которые кэшируют IP |
| Default Domain Strategy | `ipv4_only` | как резолвится адрес самого прокси-сервера |
| Resolve Domain Strategy | *(пусто)* | |

**Настройки TUN**

| Настройка | Значение | Зачем |
| --- | --- | --- |
| Tun Enable IPv6 | ❌ на Linux/Windows, **✅ на macOS** | Linux/Windows: при включённом Strict Route IPv6 становится недоступным, а не идёт в обход туннеля. На macOS strict route нет, поэтому IPv6 должен заходить в туннель, где его блокирует правило 1 |
| Strict Route | ✅ | не даёт IPv6 и DNS утекать мимо туннеля. На Windows включено по умолчанию; на Linux включите вручную. На macOS ни на что не влияет |
| Auto Redirect (Linux) | ✅ (по умолчанию) | |
| Private Range Bypass | ✅ (по умолчанию) | локальная сеть, KDE Connect и принтеры остаются вне туннеля |

Если на Linux Strict Route ломает сеть Docker или виртуальных машин, выключите его и заодно отключите IPv6 в системе (например, `sysctl net.ipv6.conf.all.disable_ipv6=1`). Иначе IPv6-трафик пойдёт в обход туннеля.

Файлы sing-box в `dist/singbox/` содержат такую же настройку DNS в блоке `dns`. Профили Happ/INCY используют те же два резолвера.

## Если что-то не работает

**Throne пишет «Input is not valid JSON, base64, or a Throne route link» при загрузке ссылки.** Throne не скачивает ссылки `raw.githubusercontent.com` напрямую — он подменяет их на зеркало jsDelivr (`https://testingcf.jsdelivr.net/gh/olegoviccc/olegovic-singbox-routing@main/dist/throne/…`, в зависимости от *Routing settings → Remote Rule-set Mirror*). jsDelivr кэширует `@main` на несколько часов, в том числе ответы «файл не найден». Новый файл или файл, который запрашивали, пока репозиторий был приватным, может прийти страницей с ошибкой, и Throne не может её разобрать.

- После каждого пуша в `main` CI сбрасывает кэш jsDelivr для всех файлов в `dist/`. Чтобы сбросить вручную, запустите workflow **Build** на вкладке Actions.
- Чтобы увидеть, что получает Throne, откройте ссылку jsDelivr выше в браузере. Там должна быть одна строка `throne://route/…`.
- Обходной путь: откройте raw-ссылку GitHub в браузере, скопируйте текст `throne://route/…` и импортируйте его из буфера обмена. Автообновления тогда не будет.
- Или поставьте *Remote Rule-set Mirror* в **GitHub** — тогда Throne берёт raw-ссылки как есть. Rule-set'ы тогда тоже будут качаться с GitHub.

## Редактирование

1. Измените `profiles/olegovic.json`.
2. Запустите `python3 build.py` (Python 3, без зависимостей). С `--check` скрипт ещё и проверяет, что каждый rule-set существует в источниках.
3. Коммитьте `profiles/` и `dist/` вместе. CI падает, если `dist/` устарел, и прогоняет каждый файл sing-box через `sing-box check`.

Ключи профиля кроме `rules`: `name`, `description`, `final` (`proxy` или `direct`), `platforms` (`linux`, `windows`, `macos`), `clients` (любые из `throne`, `singbox`, `happ`, `incy`; по умолчанию все) и `in_all` (`false` не включает профиль в `dist/throne/ALL`).

Формат правила:

```jsonc
{
  "name": "Gaming",
  "outbound": "direct",            // proxy | direct | block | system
  "geosite": ["steam"],            // в Throne: geosite-steam, в Happ: geosite:steam
  "geoip": ["ru"],
  "domain": [], "domain_suffix": [], "domain_keyword": [], "domain_regex": [], "ip_cidr": [],
  "protocol": ["bittorrent"],      // протокол, определённый сниффингом
  "process_name":       { "linux": ["steam"], "windows": ["steam.exe"] },  // или простой список для всех платформ
  "process_path":       { ... },
  "process_path_regex": { "linux": ["/steamapps/"] }                       // синтаксис Go RE2
}
```

- Домены, IP и geo-списки объединяются через ИЛИ.
- `protocol` и каждый ключ `process_*` превращаются в отдельные правила с тем же outbound, потому что иначе sing-box требовал бы совпадения всех условий сразу.
- `ip_version`, `network` и `port` образуют одно общее правило и не смешиваются с другими условиями.
- `outbound: "system"` даёт по две сборки на платформу, а в мобильные сборки такое правило не попадает.

### Откуда берутся geo-списки

- **Throne:** его встроенные rule-set'ы ([список](https://github.com/throneproj/routeprofiles/blob/rule-set/srslist.h)).
- **sing-box / Happ / INCY:** [runetfreedom/russia-v2ray-rules-dat](https://github.com/runetfreedom/russia-v2ray-rules-dat) с теми же названиями категорий.

`ru-blocked` объединяет реестр Роскомнадзора (через antifilter) с re:filter и community.antifilter, где есть и часть сайтов, которые сами блокируют пользователей из России. Такие списки никогда не бывают полными, поэтому по умолчанию всё идёт через прокси.
