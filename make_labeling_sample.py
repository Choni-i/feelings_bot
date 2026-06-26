import pandas as pd


INPUT_FILE = "tbank_reviews.csv"
OUTPUT_FILE = "sample_for_labeling.csv"

N_POSITIVE = 50
N_NEGATIVE = 50
RANDOM_STATE = 42


df = pd.read_csv(INPUT_FILE)

df = df.dropna(subset=["full_text", "sentiment_label"])
df = df[df["sentiment_label"].isin(["positive", "negative"])]

positive_df = df[df["sentiment_label"] == "positive"].sample(
    n=min(N_POSITIVE, len(df[df["sentiment_label"] == "positive"])),
    random_state=RANDOM_STATE
)

negative_df = df[df["sentiment_label"] == "negative"].sample(
    n=min(N_NEGATIVE, len(df[df["sentiment_label"] == "negative"])),
    random_state=RANDOM_STATE
)

sample = pd.concat([positive_df, negative_df], ignore_index=True)
sample = sample.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)

sample["id"] = range(1, len(sample) + 1)
sample["rating_label"] = sample["sentiment_label"]

sample_for_labeling = sample[
    [
        "id",
        "rating_total",
        "rating_label",
        "full_text"
    ]
].copy()

sample_for_labeling["llm_label"] = ""
sample_for_labeling["comment"] = ""

sample_for_labeling.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

print(f"Готово: создан файл {OUTPUT_FILE}")
print(f"Размер выборки: {len(sample_for_labeling)}")
print(sample_for_labeling["rating_label"].value_counts())