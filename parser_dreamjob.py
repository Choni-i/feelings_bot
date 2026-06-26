import re
import time
import random
from typing import List, Dict, Optional

import requests
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm


BASE_URL = "https://dreamjob.ru/employers/25607"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}

def remove_company_response(text: str) -> str:
    if not text:
        return ""

    stop_markers = [
        "Ответ компании",
        "Здравствуйте",
        "Благодарим",
        "Спасибо",
        "Сожалеем",
        "Напишите",
        "Пожалуйста",
        "С уважением",
        "Мы понимаем",
        "Будем рады",
    ]

    for marker in stop_markers:
        pos = text.find(marker)
        if pos != -1:
            text = text[:pos]

    return normalize_text(text)



def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def parse_float_ru(value: str) -> Optional[float]:
    value = value.replace(",", ".")
    match = re.search(r"\d+\.\d+|\d+", value)
    return float(match.group(0)) if match else None


def sentiment_from_rating(rating: Optional[float]) -> str:
    if rating is None:
        return "unknown"
    if rating >= 4.0:
        return "positive"
    if rating <= 2.9:
        return "negative"
    return "neutral"


def extract_between(text: str, start: str, end_markers: List[str]) -> str:
    if start not in text:
        return ""

    part = text.split(start, 1)[1]

    end_positions = []
    for marker in end_markers:
        pos = part.find(marker)
        if pos != -1:
            end_positions.append(pos)

    if end_positions:
        part = part[: min(end_positions)]

    return normalize_text(part)


def parse_review_block(block_text: str, source_url: str) -> Dict:
    text = normalize_text(block_text)

    pros = extract_between(
        text,
        "Что нравится?",
        ["Что можно улучшить?", "Преимущества и льготы", "Недостатки", "Ответ компании"]
    )

    cons = extract_between(
        text,
        "Что можно улучшить?",
        ["Преимущества и льготы", "Недостатки", "Ответ компании"]
    )
    
    pros = remove_company_response(pros)
    cons = remove_company_response(cons)

    # Должность обычно стоит в начале блока
    position = ""
    first_parts = text.split("...")
    if first_parts:
        position = normalize_text(first_parts[0])

    # Ищем город и дату: "Москва, май 2026"
    city = ""
    review_date = ""
    city_date_match = re.search(
        r"([А-ЯЁA-Z][а-яёА-ЯЁa-zA-Z\-\s]+),\s*(январь|февраль|март|апрель|май|июнь|июль|август|сентябрь|октябрь|ноябрь|декабрь)\s+\d{4}",
        text
    )
    if city_date_match:
        city_date = city_date_match.group(0)
        parts = city_date.split(",", 1)
        city = normalize_text(parts[0])
        review_date = normalize_text(parts[1])

    experience_match = re.search(r"(Работаю|Работал|Работала)\s+[^,]*?(меньше года|1-2 года|3-5 лет|5-10 лет|более 10 лет)", text)
    experience = experience_match.group(0) if experience_match else ""

    # После даты часто идут рейтинги. Берем первые 7 чисел формата 4,7 / 3,0 и т.п.
    ratings = re.findall(r"\b[1-5],[0-9]\b", text)
    ratings_float = [parse_float_ru(r) for r in ratings[:7]]

    rating_total = ratings_float[0] if len(ratings_float) > 0 else None



    bad_markers = [
    "Отзывы по должностям",
    "Отзывы по городам",
    "Информация о Т-Банк",
    "О корпоративной культуре",
    "Часто задаваемые вопросы",
    "Рекомендуют ли сотрудники",
    "Какая оплата труда",
    "Как сотрудники Т-Банк оценивают",
    "Тинькофф теперь Т-Банк",
]

    for marker in bad_markers:
        if marker in pros:
            pros = pros.split(marker)[0]

        if marker in cons:
            cons = cons.split(marker)[0]

    
    if len(pros) > 1500:
        pros = ""

    if len(cons) > 1500:
        cons = ""
    
    full_text = normalize_text(f"{pros} {cons}")

    return {
        "company": "Т-Банк",
        "position": position,
        "city": city,
        "review_date": review_date,
        "experience": experience,
        "rating_total": rating_total,
        "pros_text": pros,
        "cons_text": cons,
        "full_text": full_text,
        "sentiment_label": sentiment_from_rating(rating_total),
        "source_url": source_url,
    }


def parse_page(page: int, retries: int = 3) -> List[Dict]:
    url = BASE_URL if page == 1 else f"{BASE_URL}?page={page}"

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=60)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            page_text = soup.get_text("\n")

            raw_blocks = re.split(r"\n\s*(?=[А-ЯЁA-Z][^\n]{2,80}\n\s*\.\.\.)", page_text)

            reviews = []
            for raw in raw_blocks:
                if "Что нравится?" in raw and "Что можно улучшить?" in raw:
                    item = parse_review_block(raw, url)
                    if item["full_text"]:
                        reviews.append(item)

            return reviews

        except Exception as e:
            print(f"Попытка {attempt}/{retries} для страницы {page} не удалась: {e}")
            time.sleep(random.uniform(10, 20))

    return []


def main(max_pages: int = 20):
    all_reviews = []

    for page in tqdm(range(1, max_pages + 1)):
        try:
            reviews = parse_page(page)
            print(f"page={page}: {len(reviews)} reviews")
            all_reviews.extend(reviews)

            if len(reviews) == 0 and page > 1:
                print("Страница не распарсилась, пропускаю и иду дальше.")
                continue

            time.sleep(random.uniform(1.0, 2.5))

        except Exception as e:
            print(f"Ошибка на странице {page}: {e}")
            break

    df = pd.DataFrame(all_reviews)

    print("\nГотово!")
    print(f"Сохранено отзывов: {len(df)}")

    if df.empty:
        print("Отзывы не собраны. Скорее всего сайт не ответил, заблокировал запрос или интернет/VPN мешает подключению.")
        return

    df = df.drop_duplicates(subset=["position", "city", "review_date", "full_text"])
    df.to_csv("tbank_reviews.csv", index=False, encoding="utf-8-sig")

    print(df["sentiment_label"].value_counts(dropna=False))


if __name__ == "__main__":
    main(max_pages=20)