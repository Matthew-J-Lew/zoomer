import json
from googletrans import Translator

INPUT_FILE = "transcript.final.jsonl" # change this to a varible that is recieved from the front end 
OUTPUT_FILE = "translated.json"
TARGET_LANG = "fr" # have multiple lang that the user selects 
BATCH_SIZE = 5

translator = Translator()

objects = []
texts = []
text_positions = []

# 1. Read JSONL safely
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        if not line.strip():
            continue

        obj = json.loads(line)
        objects.append(obj)

        text = obj.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text)
            text_positions.append(len(objects) - 1)

# 2. Translate in batches
translated_texts = []

for i in range(0, len(texts), BATCH_SIZE):
    batch = texts[i:i + BATCH_SIZE]

    try:
        translations = translator.translate(batch, src="en", dest=TARGET_LANG)
        translated_texts.extend([t.text for t in translations])
    except Exception:
        # fallback to single translation
        for text in batch:
            try:
                translated_texts.append(
                    translator.translate(text, src="en", dest=TARGET_LANG).text
                )
            except:
                translated_texts.append(text)

# 3. Map translations back
for pos, translated in zip(text_positions, translated_texts):
    objects[pos]["text"] = translated

# 4. Write output
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(objects, f, ensure_ascii=False, indent=2)

print("✅ Translation completed successfully")



# text = """
# Hello everyone! How are you guys doing?
# """
# def translate_text(text, target_language):
#     translator = Translator()
#     result = translator.translate(text, dest=target_language)
#     return result.text

# if __name__ == "__main__":
#     #english_text = input("Enter English text: ")
#     english_text = text
#     target_lang = input("Enter target language code (e.g., fr, es, ko): ")

#     translated = translate_text(english_text, target_lang)
#     print("Translated text:", translated)