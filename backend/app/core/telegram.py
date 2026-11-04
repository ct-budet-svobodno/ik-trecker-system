"""Проверка initData из Telegram Mini App.

Telegram подписывает данные запуска мини-аппа ключом, производным от токена бота:
secret = HMAC_SHA256(key="WebAppData", msg=bot_token),
hash   = HMAC_SHA256(key=secret, msg=data_check_string).
data_check_string — все поля, кроме hash, в виде key=value, отсортированные и
склеенные через перевод строки. См. core.telegram.org/bots/webapps.
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class InvalidInitDataError(Exception):
    pass


def validate_init_data(init_data: str, bot_token: str, max_age: int) -> dict:
    """Возвращает объект user из initData или кидает InvalidInitDataError."""
    if not bot_token:
        raise InvalidInitDataError("Telegram не настроен на сервере")
    try:
        fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError as exc:
        raise InvalidInitDataError("Повреждённые данные Telegram") from exc

    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise InvalidInitDataError("Нет подписи Telegram")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise InvalidInitDataError("Подпись Telegram не сходится")

    try:
        auth_date = int(fields.get("auth_date", "0"))
    except ValueError as exc:
        raise InvalidInitDataError("Повреждённые данные Telegram") from exc
    if time.time() - auth_date > max_age:
        raise InvalidInitDataError("Данные Telegram устарели, откройте мини-апп заново")

    try:
        user = json.loads(fields.get("user", ""))
    except ValueError as exc:
        raise InvalidInitDataError("Нет пользователя Telegram") from exc
    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        raise InvalidInitDataError("Нет пользователя Telegram")
    return user
