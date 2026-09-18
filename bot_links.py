"""
Маппинг username бота -> ссылка на целевого бота.

Добавляйте новые записи в BOT_LINKS:
  "username_этого_бота": "https://t.me/целевой_бот?start={username}",

{username} — подставится username текущего бота (без @).
"""

BOT_LINKS: dict[str, str] = {
    "zoomerskyyvpnbot": "https://t.me/zoomerskyvpn_bot?start={username}",
    "oppen21vpnbot": "https://t.me/open21vpn_bot?start={username}",
    "fastmobillevpnbot": "https://t.me/fastmobilevpnbot?start={username}",
    "fastgamerrbot": "https://t.me/fastgamerbot?start={username}",
    "gagarinskyyvpnbot": "https://t.me/Gagarinskyvpnbot?start={username}",
    "abroadplus_bot": "https://t.me/zoomerskyvpn_bot?start={username}",
    "rgqwbot": "https://t.me/open21vpn_bot?start={username}",
    "GuavaVPNchikbot": "https://t.me/zoomerskyvpn_bot?start={username}",
}


def get_target_url(bot_username: str) -> str | None:
    key = bot_username.lstrip("@").lower()
    template = BOT_LINKS.get(key)
    if template is None:
        return None
    return template.format(username=bot_username.lstrip("@"))
