import pandas as pd
import streamlit as st
import plotly.express as px
import joblib


st.set_page_config(
    page_title="HR Emotional Analytics",
    layout="wide"
)

st.title("HR Emotional Analytics Dashboard")


# =========================
# LOAD DATA
# =========================

df = pd.read_csv("tbank_reviews_with_predictions.csv")
model = joblib.load("sentiment_model.pkl")


# =========================
# SIDEBAR
# =========================

st.sidebar.header("Фильтры")

sentiment_filter = st.sidebar.multiselect(
    "Тональность",
    options=df["predicted_sentiment"].unique(),
    default=df["predicted_sentiment"].unique()
)

df_filtered = df[
    df["predicted_sentiment"].isin(sentiment_filter)
]


# =========================
# METRICS
# =========================

total_reviews = len(df_filtered)

positive_count = len(
    df_filtered[df_filtered["predicted_sentiment"] == "positive"]
)

negative_count = len(
    df_filtered[df_filtered["predicted_sentiment"] == "negative"]
)

neutral_count = len(
    df_filtered[df_filtered["predicted_sentiment"] == "neutral"]
)

emotional_index = round(
    (positive_count - negative_count) / total_reviews,
    2
) if total_reviews > 0 else 0


col1, col2, col3, col4 = st.columns(4)

col1.metric("Всего сообщений", total_reviews)
col2.metric("Позитивных", positive_count)
col3.metric("Негативных", negative_count)
col4.metric("Нейтральных", neutral_count)

st.metric("Employee Sentiment Index", emotional_index)

if emotional_index < 0:
    st.warning("Обнаружен негативный эмоциональный фон.")
elif emotional_index < 0.3:
    st.info("Эмоциональный фон смешанный, требуется наблюдение.")
else:
    st.success("Эмоциональный фон преимущественно положительный.")


# =========================
# SENTIMENT PIE
# =========================

sentiment_counts = (
    df_filtered["predicted_sentiment"]
    .value_counts()
    .reset_index()
)

sentiment_counts.columns = ["sentiment", "count"]

fig_pie = px.pie(
    sentiment_counts,
    values="count",
    names="sentiment",
    title="Распределение эмоционального фона"
)

st.plotly_chart(fig_pie, width="stretch")


# =========================
# HR THEMES
# =========================

NEGATIVE_HR_THEMES = {
    "Зарплата и компенсации": [
        "зарплата", "доход", "премия",
        "бонус", "оплата", "заработную", "плату"
    ],
    "Нагрузка и график": [
        "график", "нагрузка", "время",
        "смена", "переработки", "заданий", "день"
    ],
    "Руководство и коммуникация": [
        "руководитель", "отношение",
        "общение", "менеджер", "сотрудникам"
    ],
    "Штрафы и контроль": [
        "штраф", "штрафы", "ошибка",
        "контроль", "проверка", "нарушения"
    ],
    "Карьера и развитие": [
        "рост", "развитие", "обучение", "карьера"
    ],
    "Полевые сотрудники": [
        "представитель", "представителя", "представители"
    ],
}

POSITIVE_HR_THEMES = {
    "Коллектив и поддержка": [
        "коллектив", "команда", "поддержка",
        "помогают", "общение"
    ],
    "График и гибкость": [
        "график", "удаленка", "удаленная",
        "гибкий", "свобода"
    ],
    "Зарплата и бонусы": [
        "зарплата", "доход", "премия",
        "бонус", "оплата"
    ],
    "Обучение и развитие": [
        "обучение", "развитие",
        "рост", "карьера", "наставник"
    ],
    "Условия труда": [
        "условия", "офис", "дмс",
        "комфорт", "льготы"
    ],
}


def calculate_theme_scores(data, sentiment, themes):
    text = " ".join(
        data[data["predicted_sentiment"] == sentiment]["clean_text"].astype(str)
    )

    scores = {}

    for theme, keywords in themes.items():
        score = 0
        for word in keywords:
            score += text.count(word)
        scores[theme] = score

    return pd.DataFrame({
        "theme": list(scores.keys()),
        "score": list(scores.values())
    })


st.subheader("HR-темы в отзывах")

col_neg, col_pos = st.columns(2)

negative_themes_df = calculate_theme_scores(
    df_filtered,
    "negative",
    NEGATIVE_HR_THEMES
)

positive_themes_df = calculate_theme_scores(
    df_filtered,
    "positive",
    POSITIVE_HR_THEMES
)

with col_neg:
    fig_neg = px.bar(
        negative_themes_df.sort_values("score"),
        x="score",
        y="theme",
        orientation="h",
        title="Негативные темы"
    )
    st.plotly_chart(fig_neg, width="stretch")

with col_pos:
    fig_pos = px.bar(
        positive_themes_df.sort_values("score"),
        x="score",
        y="theme",
        orientation="h",
        title="Позитивные темы"
    )
    st.plotly_chart(fig_pos, width="stretch")


# =========================
# REVIEWS
# =========================

st.subheader("Примеры отзывов")

reviews_for_display = df_filtered[
    df_filtered["full_text"].astype(str).str.len() <= 1200
]

sample_reviews = reviews_for_display[
    ["predicted_sentiment", "full_text"]
].sample(
    min(10, len(reviews_for_display)),
    random_state=42
)

for _, row in sample_reviews.iterrows():
    text = str(row["full_text"])

    short_text = (
        text[:700] + "..."
        if len(text) > 700
        else text
    )

    if row["predicted_sentiment"] == "negative":
        st.error(short_text)
    elif row["predicted_sentiment"] == "neutral":
        st.warning(short_text)
    else:
        st.success(short_text)


# =========================
# SURVEY ANALYSIS
# =========================

st.subheader("Анализ ежемесячных опросов сотрудников")

try:
    survey_df = pd.read_csv("survey_responses.csv")

    NEGATIVE_SURVEY_MARKERS = [
    "много задач",
    "мало времени",
    "не хватает",
    "не всегда",
    "срочные задачи",
    "без контекста",
    "вызывает стресс",
    "вызывает усталость",
    "напряжение",
    "меньше срочных",
    "мало перерывов",
    "хотелось бы",
    "можно улучшить",
    ]

    POSITIVE_SURVEY_MARKERS = [
        "нравится",
        "помогает",
        "поддержка",
        "открытая команда",
        "понятные цели",
        "команда помогает",
        "возможность предлагать идеи",
    ]


    def predict_survey_sentiment(text):
        text_lower = str(text).lower()

        for marker in NEGATIVE_SURVEY_MARKERS:
            if marker in text_lower:
                return "negative"

        for marker in POSITIVE_SURVEY_MARKERS:
            if marker in text_lower:
                return "positive"

        # если правилом не поймали — используем модель
        proba = model.predict_proba([text_lower])[0]
        classes = model.classes_

        max_prob = proba.max()
        label = classes[proba.argmax()]

        if max_prob < 0.65:
            return "neutral"

        return label


    survey_df["predicted_sentiment"] = survey_df["response"].apply(
        predict_survey_sentiment
    )

    survey_counts = (
        survey_df["predicted_sentiment"]
        .value_counts()
        .reset_index()
    )

    survey_counts.columns = ["sentiment", "count"]

    col_survey_chart, col_survey_table = st.columns(2)

    with col_survey_chart:
        fig_survey = px.pie(
            survey_counts,
            values="count",
            names="sentiment",
            title="Тональность ответов в опросе"
        )

        st.plotly_chart(fig_survey, width="stretch")

    with col_survey_table:
        st.dataframe(
            survey_df[
                [
                    "date",
                    "department",
                    "question",
                    "response",
                    "predicted_sentiment"
                ]
            ],
            width="stretch"
        )

except FileNotFoundError:
    st.info("Файл survey_responses.csv пока не найден.")


# =========================
# HR SUMMARY
# =========================

st.subheader("AI HR Summary")

top_negative_theme = negative_themes_df.sort_values(
    "score",
    ascending=False
).iloc[0]["theme"]

top_positive_theme = positive_themes_df.sort_values(
    "score",
    ascending=False
).iloc[0]["theme"]

negative_share = round(
    negative_count / total_reviews * 100,
    1
) if total_reviews > 0 else 0

positive_share = round(
    positive_count / total_reviews * 100,
    1
) if total_reviews > 0 else 0

neutral_share = round(
    neutral_count / total_reviews * 100,
    1
) if total_reviews > 0 else 0


summary_text = f"""
### Краткая сводка эмоционального фона сотрудников

- Доля позитивных сообщений: **{positive_share}%**
- Доля негативных сообщений: **{negative_share}%**
- Доля нейтральных сообщений: **{neutral_share}%**
- Employee Sentiment Index: **{emotional_index}**

### Основные позитивные темы
Наиболее часто сотрудники положительно упоминают: **{top_positive_theme}**

### Основные негативные темы
Наиболее часто встречающаяся проблемная зона: **{top_negative_theme}**

### Потенциальные рекомендации HR
"""

recommendations = []

if top_negative_theme == "Нагрузка и график":
    recommendations.append("- проверить уровень нагрузки, график и возможные переработки;")

if top_negative_theme == "Зарплата и компенсации":
    recommendations.append("- оценить прозрачность компенсационной политики и систему премирования;")

if top_negative_theme == "Руководство и коммуникация":
    recommendations.append("- провести анализ качества коммуникации между руководителями и командами;")

if top_negative_theme == "Штрафы и контроль":
    recommendations.append("- пересмотреть практики контроля, штрафов и обратной связи;")

if top_negative_theme == "Карьера и развитие":
    recommendations.append("- усилить карьерные треки, обучение и коммуникацию возможностей роста;")

if top_negative_theme == "Полевые сотрудники":
    recommendations.append("- отдельно проанализировать условия работы сотрудников на выездных/полевых ролях;")

if len(recommendations) == 0:
    recommendations.append("- продолжить регулярный мониторинг эмоционального фона сотрудников.")

summary_text += "\n".join(recommendations)

st.markdown(summary_text)