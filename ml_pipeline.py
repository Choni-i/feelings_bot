import re
import joblib
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score
from sklearn.decomposition import LatentDirichletAllocation


# =========================
# СТОП-СЛОВА И МУСОР С САЙТА
# =========================

RUS_STOPWORDS = {
    "что", "это", "как", "для", "или", "при", "так", "то", "по", "на", "в", "с", "и", "а",
    "мы", "вы", "вас", "нас", "они", "она", "оно", "он", "я", "ты",
    "отзыв", "отзывы", "полезный", "ответ", "ссылка", "ответить",
    "компания", "компании", "работа", "работе", "работу", "работаю", "работал", "работала",
    "банк", "банка", "банке", "т", "тинькофф",
    "который", "которая", "которые", "которых", "которым",
    "есть", "был", "была", "были", "будет", "будут",
    "очень", "просто", "свою", "свои", "свой",
    "меня", "тебя", "себя", "мне", "тебе",
    "весь", "всех", "все", "всё",
    "также", "потому", "поэтому",
    "здравствуйте", "благодарим", "спасибо", "рады", "сожалеем",
    "мнение", "обратную", "связь", "ваше", "ваш", "наш", "наша",
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "специалист", "менеджер", "отдела", "ведущий", "старший",
    "руководитель", "оператор", "поддержки", "главный", "клиентами",
    "работы", "сотрудников", "понимаем", "действительно", "вам",
    "важно", "фио", "дата", "нам", "ru",
    "москва", "пожалуйста",
    "замечания", "делиться",
    "стесняйтесь", "дополнительные",
    "мысли", "возможность",
    "представителей", "предложения", "предложение", "условия", "декабрь"
}


# =========================
# ФУНКЦИИ
# =========================

def clean_text(text):
    text = str(text).lower()

    # удаляем типичные ответы компании
    patterns_to_remove = [
        r"здравствуйте.*",
        r"спасибо.*",
        r"благодарим.*",
        r"пожалуйста.*",
        r"напишите.*",
        r"сожалеем.*",
        r"мы понимаем.*",
        r"будем рады.*",
        r"с уважением.*",
    ]

    for pattern in patterns_to_remove:
        text = re.sub(pattern, " ", text)

    # удаляем ссылки
    text = re.sub(r"http\S+", " ", text)

    # оставляем только буквы
    text = re.sub(r"[^а-яёa-z\s]", " ", text)

    # убираем лишние пробелы
    text = re.sub(r"\s+", " ", text).strip()

    return text


def make_binary_label(label):
    if label == "positive":
        return "positive"
    if label == "negative":
        return "negative"
    return None


def print_topic_words(model, feature_names, n_top_words=10):
    topic_rows = []

    for topic_idx, topic in enumerate(model.components_):
        top_indices = topic.argsort()[:-n_top_words - 1:-1]
        top_words = [feature_names[i] for i in top_indices]
        top_weights = [topic[i] for i in top_indices]

        print(f"\nТема {topic_idx + 1}:")
        print(", ".join(top_words))

        for word, weight in zip(top_words, top_weights):
            topic_rows.append({
                "topic": f"Тема {topic_idx + 1}",
                "word": word,
                "weight": weight
            })

    return pd.DataFrame(topic_rows)


# =========================
# ЗАГРУЗКА ДАННЫХ
# =========================

df = pd.read_csv("tbank_reviews.csv")

print(f"Всего отзывов в CSV: {len(df)}")

df = df.dropna(subset=["full_text", "sentiment_label"])

df["sentiment_binary"] = df["sentiment_label"].apply(make_binary_label)

# Убираем neutral, потому что для weak supervision он шумный
df = df.dropna(subset=["sentiment_binary"])

df["clean_text"] = df["full_text"].apply(clean_text)

print("\nРаспределение классов после удаления neutral:")
print(df["sentiment_binary"].value_counts())


# =========================
# ОБУЧЕНИЕ МОДЕЛИ ТОНАЛЬНОСТИ
# =========================

X = df["clean_text"]
y = df["sentiment_binary"]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

pipeline = Pipeline([
    (
        "tfidf",
        TfidfVectorizer(
            max_features=7000,
            ngram_range=(1, 2),
            min_df=2,
            stop_words=list(RUS_STOPWORDS)
        )
    ),
    (
        "clf",
        LogisticRegression(
            max_iter=1000,
            class_weight="balanced"
        )
    )
])

pipeline.fit(X_train, y_train)

preds = pipeline.predict(X_test)

print("\nAccuracy:")
print(round(accuracy_score(y_test, preds), 3))

print("\nClassification report:")
print(classification_report(y_test, preds))

joblib.dump(pipeline, "sentiment_model.pkl")
print("\nМодель сохранена: sentiment_model.pkl")


# =========================
# ПРЕДСКАЗАНИЯ ДЛЯ ВСЕГО ДАТАСЕТА
# =========================

proba = pipeline.predict_proba(df["clean_text"])
classes = pipeline.classes_

predicted = []

for probs in proba:
    max_prob = probs.max()
    label = classes[probs.argmax()]

    if max_prob < 0.65:
        predicted.append("neutral")
    else:
        predicted.append(label)

df["predicted_sentiment"] = predicted

df.to_csv("tbank_reviews_with_predictions.csv", index=False, encoding="utf-8-sig")
print("Файл с предсказаниями сохранен: tbank_reviews_with_predictions.csv")


# =========================
# TOPIC MODELING ДЛЯ НЕГАТИВНЫХ ТЕКСТОВ
# =========================

negative_texts = (
    df[df["predicted_sentiment"] == "negative"]["cons_text"]
    .dropna()
    .apply(clean_text)
)

print(f"\nКоличество негативных текстов для тем: {len(negative_texts)}")

vectorizer = CountVectorizer(
    max_df=0.85,
    min_df=3,
    stop_words=list(RUS_STOPWORDS)
)

X_topics = vectorizer.fit_transform(negative_texts)

lda = LatentDirichletAllocation(
    n_components=4,
    random_state=42,
    learning_method="batch"
)

lda.fit(X_topics)

feature_names = vectorizer.get_feature_names_out()

print("\n=== НЕГАТИВНЫЕ ТЕМЫ ===")
topics_df = print_topic_words(lda, feature_names, n_top_words=10)

topics_df.to_csv("negative_topics_words.csv", index=False, encoding="utf-8-sig")
print("\nТаблица топ-слов сохранена: negative_topics_words.csv")


# =========================
# BARPLOT ТОП-СЛОВ ПО НЕГАТИВНЫМ ТЕКСТАМ
# =========================

word_counts = X_topics.sum(axis=0).A1
words = vectorizer.get_feature_names_out()

top_words_df = pd.DataFrame({
    "word": words,
    "count": word_counts
}).sort_values("count", ascending=False).head(20)

top_words_df.to_csv("negative_top_words.csv", index=False, encoding="utf-8-sig")
print("Топ негативных слов сохранен: negative_top_words.csv")

plt.figure(figsize=(12, 7))
plt.barh(top_words_df["word"][::-1], top_words_df["count"][::-1])
plt.title("Топ-20 слов в негативных отзывах")
plt.xlabel("Количество упоминаний")
plt.ylabel("Слова")
plt.tight_layout()
plt.savefig("negative_top_words_barplot.png", dpi=200)

print("Barplot сохранен: negative_top_words_barplot.png")