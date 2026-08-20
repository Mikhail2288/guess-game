from PIL import Image
import os

input_dir = "static/images"
output_dir = "static/images_webp"

# Создаём выходную папку
os.makedirs(output_dir, exist_ok=True)

converted = 0
skipped = 0

for filename in os.listdir(input_dir):
    if filename.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".tiff",".webp")):
        try:
            img = Image.open(os.path.join(input_dir, filename))

            # Уменьшаем до 800px по ширине (максимум)
            if img.width > 800:
                ratio = 800 / img.width
                new_height = int(img.height * ratio)
                img = img.resize((800, new_height), Image.LANCZOS)

            # Конвертируем в RGB если есть прозрачность
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Сохраняем как WebP
            name = os.path.splitext(filename)[0]
            output_path = os.path.join(output_dir, f"{name}.webp")
            img.save(output_path, "WEBP", quality=95)

            print(f"✅ {filename} → {name}.webp")
            converted += 1
        except Exception as e:
            print(f"❌ {filename}: {e}")
            skipped += 1
    else:
        skipped += 1

print(f"\nКонвертировано: {converted}, пропущено: {skipped}")