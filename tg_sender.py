import requests
import time
import re

from loguru import logger

from models import Item
from datetime import datetime


class SendAdToTg:
    def __init__(self, bot_token: str, chat_id: list, max_retries: int = 5, retry_delay: int = 5):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def __send_to_tg(self, chat_id: str | int, ad: Item = None, msg: str = None):
        try:
            if msg:
                payload = {
                    "chat_id": chat_id,
                    "text": msg,
                    "parse_mode": "HTML",
                }
                response = requests.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage", 
                                        json=payload, timeout=10)
                return response
            else:
                message = self.format_ad(ad)
                _image_url = self.get_first_image(ad=ad)

            for attempt in range(1, self.max_retries + 1):
                try:
                    payload = {
                        "chat_id": str(chat_id),  # Убедимся, что chat_id - строка
                        "caption": message,
                        "photo": _image_url if _image_url else None,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    }
                    
                    logger.debug(f"Отправка в Telegram (попытка {attempt}): chat_id={chat_id}")
                    
                    # Если нет изображения, отправляем просто текстовое сообщение
                    if not _image_url:
                        payload = {
                            "chat_id": str(chat_id),
                            "text": message,
                            "parse_mode": "HTML",
                            "disable_web_page_preview": True,
                        }
                        response = requests.post(
                            f"https://api.telegram.org/bot{self.bot_token}/sendMessage", 
                            json=payload, 
                            timeout=10
                        )
                    else:
                        response = requests.post(self.api_url, json=payload, timeout=10)
                    
                    if response.status_code == 400:
                        error_msg = response.json().get('description', 'Неизвестная ошибка')
                        logger.warning(f"Ошибка 400: {error_msg}")
                        logger.debug(f"Запрос: {payload}")
                        break

                    response.raise_for_status()
                    logger.debug(f"Сообщение успешно отправлено (попытка {attempt})")
                    break
                    
                except requests.RequestException as e:
                    logger.error(f"Ошибка при отправке (попытка {attempt}): {e}")
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay)
                    else:
                        logger.error(f"Не удалось отправить сообщение после всех попыток. Chat_id: {chat_id}")
                        
        except Exception as e:
            logger.error(f"Критическая ошибка в __send_to_tg: {e}")
            logger.exception(e)

    def send_to_tg(self, ad: Item = None, msg: str = None):
        for chat_id in self.chat_id:
            self.__send_to_tg(chat_id=chat_id, ad=ad, msg=msg)

    @staticmethod
    def get_first_image(ad: Item):
        def get_largest_image_url(img):
            best_key = max(
                img.root.keys(),
                key=lambda k: int(k.split("x")[0]) * int(k.split("x")[1])
            )
            return str(img.root[best_key])

        images_urls = [get_largest_image_url(img) for img in ad.images]
        if images_urls:
            return images_urls[0]


    @staticmethod
    def format_ad(ad: Item) -> str:
        parts = []
        
        # Заголовок
        if title := getattr(ad, "title", ""):
            parts.append(f"<b>{title}</b>")
        
        # Цена
        if price := getattr(ad, "price", "") or getattr(ad, "priceDetailed", ""):
            if hasattr(price, 'value'):
                price = str(price.value)
            elif hasattr(price, '__str__'):
                price = str(price)
            
            if price and price != "0":
                try:
                    formatted_price = '{:,d}'.format(int(float(price))).replace(',', '.')
                    price_part = f"💰<b>{formatted_price} ₽</b>"
                    if getattr(ad, "isPromotion", False):
                        price_part += " 🢁"
                    parts.append(price_part)
                except:
                    price_part = f"💰<b>{price} ₽</b>"
                    if getattr(ad, "isPromotion", False):
                        price_part += " 🢁"
                    parts.append(price_part)

        # Адрес
        address = getattr(ad, "addressDetailed", "")
        if address:
            try:
                # Преобразуем объект в строку
                address_text = re.search(r"locationName\s*=\s*['\"]([^'\"]+)['\"]", str(address), re.IGNORECASE).group(1).strip()
                parts.append(f"🏠 {address_text}")
            except Exception as e:
                import logging
                logging.warning(f"Ошибка при обработке адреса: {e}")
        
        # Ссылка
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
            
            parts.append(f"<blockquote>{description}</blockquote>")
        
        
        # Время публикации
        if timestamp := getattr(ad, "sortTimeStamp", ""):
            try:
                ts = float(timestamp)
                if ts > 1_000_000_000_000:  # миллисекунды
                    ts /= 1000
                dt = datetime.fromtimestamp(ts)
                parts.append(f"\n📅 {dt.strftime('%d.%m.%Y %H:%M:%S')}")
            except:
                parts.append(f"\n📅 {timestamp}")
        
        message = "\n".join(parts)
        return message