import pandas as pd


INPUT_FILE = "sample_for_labeling_labeled.csv"
OUTPUT_FILE = "labeling_comparison_report.csv"


df = pd.read_csv(INPUT_FILE)

df = df.dropna(subset=["rating_label", "llm_label"])
df["llm_label"] = df["llm_label"].astype(str).str.strip().str.lower()
df["rating_label"] = df["rating_label"].astype(str).str.strip().str.lower()

valid_labels = ["positive", "negative", "mixed", "neutral"]
df = df[df["llm_label"].isin(valid_labels)]

# Для сравнения считаем совпадением только точное совпадение positive/negative.
# mixed и neutral считаем сигналом, что рейтинг-разметка была шумной.
df["exact_match"] = df["rating_label"] == df["llm_label"]
df["is_noisy_case"] = df["llm_label"].isin(["mixed", "neutral"]) | (~df["exact_match"])

total = len(df)
matches = df["exact_match"].sum()
noisy = df["is_noisy_case"].sum()

match_rate = matches / total if total else 0
noise_rate = noisy / total if total else 0

print("\n=== Проверка качества автоматической разметки ===")
print(f"Всего размечено: {total}")
print(f"Совпадений rating_label и llm_label: {matches}")
print(f"Доля совпадений: {match_rate:.2%}")
print(f"Потенциально шумных случаев: {noisy}")
print(f"Доля потенциально шумных случаев: {noise_rate:.2%}")

print("\nРаспределение LLM-разметки:")
print(df["llm_label"].value_counts())

print("\nМатрица сравнения:")
print(pd.crosstab(df["rating_label"], df["llm_label"]))

df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

print(f"\nОтчёт сохранён: {OUTPUT_FILE}")