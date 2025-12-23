import requests
import time
import re

from loguru import logger

from models import Item
from datetime import datetime


class SendAdToVk:
    """
    Отправка объявлений во ВК через messages.send.

    Ожидается, что:
    - bot_token — это access_token сообщества/бота
    - peer_ids — список получателей (peer_id / user_id / chat_id)
    """

    def __init__(self, bot_token: str, peer_ids: list[int | str], api_version: str = "5.199",
                 max_retries: int = 5, retry_delay: int = 5):
        self.bot_token = bot_token
        self.peer_ids = peer_ids
        self.api_url = "https://api.vk.com/method/messages.send"
        self.api_version = api_version
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def __send_to_vk(self, peer_id: int | str, ad: Item = None, msg: str = None):
        """
        Отправка одного сообщения во ВК (только текст).
        """
        try:
            if msg:
                message = msg
            else:
                message = self.format_ad(ad)

            for attempt in range(1, self.max_retries + 1):
                try:
                    payload = {
                        "access_token": self.bot_token,
                        "v": self.api_version,
                        "peer_id": str(peer_id),
                        "random_id": int(time.time() * 1000),
                        "message": message,
                    }

                    logger.debug(f"Отправка в VK (попытка {attempt}): peer_id={peer_id}")

                    response = requests.post(self.api_url, data=payload, timeout=15)

                    if response.status_code != 200:
                        logger.warning(f"VK API HTTP {response.status_code}: {response.text}")
                        if response.status_code >= 500:
                            raise requests.RequestException(f"Серверная ошибка VK: {response.status_code}")
                        break

                    data = response.json()
                    if "error" in data:
                        error = data["error"]
                        logger.warning(f"Ошибка VK API: {error.get('error_code')} - {error.get('error_msg')}")
                        break

                    logger.debug(f"Сообщение во ВК успешно отправлено (попытка {attempt})")
                    break

                except requests.RequestException as e:
                    logger.error(f"Ошибка при отправке в VK (попытка {attempt}): {e}")
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay)
                    else:
                        logger.error(f"Не удалось отправить VK-сообщение после всех попыток. peer_id: {peer_id}")

        except Exception as e:
            logger.error(f"Критическая ошибка в __send_to_vk: {e}")
            logger.exception(e)

    def send_to_vk(self, ad: Item = None, msg: str = None):
        """
        Отправка сообщения всем настроенным получателям.
        """
        for peer_id in self.peer_ids:
            self.__send_to_vk(peer_id=peer_id, ad=ad, msg=msg)

    @staticmethod
    def format_ad(ad: Item) -> str:
        """
        Форматирование объявления в текст для ВК.
        Основано на логике Telegram, но без HTML-разметки.
        """
        parts = []

        # Заголовок (как в ТГ, но без HTML/BB-кода — VK для ботов не поддерживает разметку)
        if title := getattr(ad, "title", ""):
            parts.append(title)

        # Цена (как в ТГ, но без HTML/BB-кода)
        if price := getattr(ad, "price", "") or getattr(ad, "priceDetailed", ""):
            if hasattr(price, 'value'):
                price = str(price.value)
            elif hasattr(price, '__str__'):
                price = str(price)

            if price and price != "0":
                try:
                    formatted_price = '{:,d}'.format(int(float(price))).replace(',', ' ')
                    price_part = f"💰 {formatted_price} ₽"
                    if getattr(ad, "isPromotion", False):
                        price_part += " 🢁"
                    parts.append(price_part)
                except Exception:
                    price_part = f"💰 {price} ₽"
                    if getattr(ad, "isPromotion", False):
                        price_part += " 🢁"
                    parts.append(price_part)

        # Адрес
        address = getattr(ad, "addressDetailed", "")
        if address:
            try:
                address_text = re.search(
                    r"locationName\s*=\s*['\"]([^'\"]+)['\"]",
                    str(address),
                    re.IGNORECASE
                ).group(1).strip()
                parts.append(f"🏠 {address_text}")
            except Exception as e:
                logger.warning(f"Ошибка при обработке адреса для VK: {e}")

        # Ссылка (аналогично ТГ)
        if item_id := getattr(ad, "id", ""):
            parts.append(f"🔍 https://avito.ru/{item_id}\n")

         # Описание с обработкой тегов для поиска
        if description := getattr(ad, "description", ""):
            # Список паттернов для "тегов для поиска"
            tag_patterns = [
                "Теги для поиска:",
                "Теги для поиска :",
                "ТЕГИ ДЛЯ ПОИСКА:",
                "ТЕГИ ДЛЯ ПОИСКА :",
                "Теги для поиска",
                "ТЕГИ ДЛЯ ПОИСКА",
                "Теги поиска:",
                "Теги поиска :",
                "ТЕГИ ПОИСКА:",
                "ТЕГИ ПОИСКА :",
                "Поисковые теги:",
                "Поисковые теги :",
                "ПОИСКОВЫЕ ТЕГИ:",
                "ПОИСКОВЫЕ ТЕГИ :",
                "Ключевые слова:",
                "Ключевые слова :",
                "КЛЮЧЕВЫЕ СЛОВА:",
                "КЛЮЧЕВЫЕ СЛОВА :",
                "Tags for search:",
                "TAGS FOR SEARCH:",
                "Search tags:",
                "SEARCH TAGS:",
                "Keywords:",
                "KEYWORDS:",
                "Теги:",
                "ТЕГИ:",
                "Tags:",
                "TAGS:",
                # С дополнительными разделителями
                "Теги для поиска -",
                "Теги для поиска - ",
                "Теги для поиска—",
                "Теги для поиска —",
                "ТЕГИ ДЛЯ ПОИСКА -",
                "ТЕГИ ДЛЯ ПОИСКА —",
                # На английском с русскими буквами (опечатки)
                "Tеги для поиска:",
                "Тags для поиска:",
                "Теgи для поиска:",
                # Разные регистры и пробелы
                "теги для поиска:",
                "теги для поиска :",
                " теги для поиска:",
                " теги для поиска :",
                # С точкой в конце
                "Теги для поиска.",
                "ТЕГИ ДЛЯ ПОИСКА.",
                # С многоточием
                "Теги для поиска...",
                "ТЕГИ ДЛЯ ПОИСКА...",
                "Для поиска: "
            ]
            
            # Находим начало тегов для поиска
            tag_start = -1
            tag_pattern_used = ""
            
            for pattern in tag_patterns:
                idx = description.find(pattern)
                if idx != -1:
                    # Ищем с начала паттерна
                    tag_start = idx
                    tag_pattern_used = pattern
                    break

            # Если нашли теги, обрезаем описание
            if tag_start != -1:
                # Добавляем "..." к паттерну, чтобы показать, что текст обрезан
                description = description[:tag_start] + tag_pattern_used + " ..."
            
            current_length = len("\n".join(parts))
            available_length = 700 - current_length - 50
            
            if available_length > 50 and len(description) > available_length:
                truncated = description[:available_length]
                last_space = truncated.rfind(' ')
                if last_space > 0:
                    truncated = truncated[:last_space]
                description = truncated + "..."
            
            # В VK для ботов нет blockquote, оставляем просто текст отдельным абзацем
            parts.append(description)

        # Время публикации
        if timestamp := getattr(ad, "sortTimeStamp", ""):
            try:
                ts = float(timestamp)
                if ts > 1_000_000_000_000:  # миллисекунды
                    ts /= 1000
                dt = datetime.fromtimestamp(ts)
                parts.append(f"\n📅 {dt.strftime('%d.%m.%Y %H:%M:%S')}")
            except Exception:
                parts.append(f"\n📅 {timestamp}")

        message = "\n".join(parts)
        return message
