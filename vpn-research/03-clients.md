# Клиенты

Общее требование: клиент должен уметь брать **подписку** (несколько серверов и протоколов одной ссылкой), автоматически **выбирать рабочий вход** и маршрутизировать трафик (российское напрямую, остальное через VPN). Маршрутизация уже есть в этом репозитории (`dist/`).

| Платформа | Клиент | Протоколы | Маршрутизация из этого репо |
| --- | --- | --- | --- |
| Linux (CachyOS), Windows, macOS | **Throne** | VLESS (XHTTP/gRPC/Reality), Hysteria2, Shadowsocks…, через ядро sing-box | ✅ профили `dist/throne/*` |
| Linux / Windows / macOS | Amnezia VPN | AmneziaWG, своё | ❌ только своя маршрутизация по сайтам |
| Android | **Happ**, v2rayNG, Hiddify, Karing | VLESS, Hysteria2 (Happ, Hiddify, Karing) | ✅ Happ/INCY: `dist/happ`, `dist/incy`; sing-box-клиенты: `dist/singbox/*_mobile.json` |
| iOS / iPadOS | **Happ**, INCY, Streisand, Karing | VLESS, Hysteria2 | ✅ Happ/INCY |
| Android/iOS | AmneziaWG / Amnezia VPN | AmneziaWG | ❌ (split tunneling по приложениям) |
| Роутер (OpenWrt 24.10+) | **Podkop** (sing-box) | VLESS, Shadowsocks, Trojan, Hysteria2, SOCKS, AmneziaWG через интерфейс | Свои списки (itdoginfo), точечно по доменам |

## Заметки

- **Throne:** уже настроен под профили из этого репо. После появления сервера останется добавить подписку и включить TUN.
- **Happ** берёт маршрутизацию из `dist/happ/Olegovic.DEEPLINK`. Порядок правил там упрощённый (block → proxy → direct), подробнее в основном README.
- **Hysteria2 и AmneziaWG на телефоне:** Happ и Hiddify поддерживают Hysteria2. AmneziaWG требует отдельного приложения Amnezia, а в нём своя маршрутизация.
- **Роутер с Podkop** ([itdoginfo/podkop](https://github.com/itdoginfo/podkop), [гайд](https://www.securitylab.ru/blog/personal/Bitshield/362152.php)) удобен для дома и дачи: все устройства в сети получают обход без настройки. Нужна OpenWrt 24.10, для новых версий Podkop требуется sing-box ≥ 1.12. По порядку цифр: MT7621 даёт около 100 Мбит/с, Filogic 820 — 600–800 Мбит/с.
- **Резервные клиенты:** на телефоне держать два клиента с разными протоколами (Happ с VLESS/Hy2 и Amnezia с AWG). Если один протокол режут, можно переключиться руками.

## Что добавить в этот репозиторий, когда будет сервер

- В профилях маршрутизации появится правило «российские сервисы → выход через дачу», если дача будет работать как RU-выход (см. [04-dacha.md](04-dacha.md)).
- Нужен шаблон подписки с несколькими входами и `urltest`, но без самих ключей: секреты в публичный репозиторий не кладём.
