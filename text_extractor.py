import struct
from pathlib import Path
import json
import os
import argparse

def extract_texts(string_path):
    if not string_path.exists():
        print(f"Не найден путь к строкам: {string_path}")
        return

    # Словарь для хранения всех извлеченных текстов
    all_texts = {}
    
    # Информация о структуре файлов
    FILES = {
        0: {"entry_size": 0x0C, "text_offset": 0x0, "text_offset_2": 0x04, "Unknown": 0x08},
        #17: {"entry_size": 0x14, "text_offset": 0x0, "speaker_offset": 0xC},
        #30: {"entry_size": 0x8, "text_offset": 0x0},
        #31: {"entry_size": 0x4, "text_offset": 0x0},
        #32: {"entry_size": 0x4, "text_offset": 0x0},
    }

    # Обработка каждого файла
    for file_idx in FILES.keys():
        file_texts = []
        file_path = string_path / str(file_idx)
        print(file_idx)
        
        if not file_path.exists():
            continue

        with open(file_path, "rb") as f:
            fd = f.read()

        num_strings = struct.unpack_from("<I", fd, 0)[0]
        
        for string_idx in range(num_strings):
            entry_pos = 0x10 + string_idx * FILES[file_idx]["entry_size"]
            string_offset_pos = entry_pos + FILES[file_idx]["text_offset"]
            string_offset = struct.unpack_from("<I", fd, string_offset_pos)[0]

            if file_idx == 17:
                speaker_id = struct.unpack_from("<I", fd, entry_pos + FILES[file_idx]["speaker_offset"])[0]
                text = {
                    "speaker_id": speaker_id,
                    "text": fd[string_offset_pos + string_offset : fd.find(b"\x00", string_offset_pos + string_offset)].decode("utf8")
                }
            elif file_idx == 0:
                string_offset_2_pos = entry_pos + FILES[file_idx]["text_offset_2"]
                string_offset_2 = struct.unpack_from("<I", fd, string_offset_2_pos)[0]
                Unknown_id = struct.unpack_from("<I", fd, entry_pos + FILES[file_idx]["Unknown"])

                text = {
                    "Unknown": Unknown_id,
                    "text": fd[string_offset_pos + string_offset : fd.find(b"\x00", string_offset_pos + string_offset)].decode("utf8"),
                    "text_2": fd[string_offset_2_pos + string_offset_2 : fd.find(b"\x00", string_offset_2_pos + string_offset_2)].decode("utf8")
                }
            else:
                text = {
                    "text": fd[string_offset_pos + string_offset : fd.find(b"\x00", string_offset_pos + string_offset)].decode("utf8")
                }
            
            file_texts.append(text)
        
        all_texts[str(file_idx)] = file_texts

    # Сохранение в JSON файл
    with open("extracted_texts.json", "w", encoding="utf8") as f:
        json.dump(all_texts, f, ensure_ascii=False, indent=2)

    print("Тексты успешно извлечены в файл extracted_texts.json")

def pack_texts(string_path, json_file="extracted_texts.json"):
    if not os.path.exists(json_file):
        print(f"Файл {json_file} не найден")
        return

    if not string_path.exists():
        print(f"Не найден путь к строкам: {string_path}")
        return

    # Загрузка текстов из JSON
    with open(json_file, "r", encoding="utf8") as f:
        texts = json.load(f)

    # Информация о структуре файлов
    FILES = {
        0: {"entry_size": 0x0C, "text_offset": 0x0, "text_offset_2": 0x4, "Unknown": 0x8},
        #17: {"entry_size": 0x14, "text_offset": 0x0, "speaker_offset": 0xC},
        #30: {"entry_size": 0x8, "text_offset": 0x0},
        #31: {"entry_size": 0x4, "text_offset": 0x0},
        #32: {"entry_size": 0x4, "text_offset": 0x0},
    }

    # Создание бэкапов и обработка каждого файла
    for file_idx_str, file_texts in texts.items():
        file_idx = int(file_idx_str)
        if file_idx not in FILES:
            print(f"Пропуск файла {file_idx} - неизвестный формат")
            continue

        orig_file = string_path / file_idx_str
        if not orig_file.exists():
            print(f"Пропуск файла {file_idx} - оригинал не найден")
            continue

        # Создание бэкапа
        backup_file = string_path / f"{file_idx_str}.backup"
        if not backup_file.exists():
            with open(orig_file, "rb") as src, open(backup_file, "wb") as dst:
                dst.write(src.read())

        # Подготовка нового файла
        num_strings = len(file_texts)
        
        # Расчет размера заголовка и секции записей
        header_size = 0x10  # Размер заголовка
        entries_section_size = num_strings * FILES[file_idx]["entry_size"]
        
        # Создаем новый буфер с заголовком
        new_data = bytearray()
        new_data.extend(struct.pack("<I", num_strings))  # Количество строк

        # Читаем бэкап файл для получения второго значения из заголовка
        with open(backup_file, "rb") as f:
            backup_data = f.read()
            second_header_value = struct.unpack_from("<I", backup_data, 4)[0]
            new_data.extend(struct.pack("<I", second_header_value))  # Второе значение из заголовка
            new_data.extend(b"\x00" * (header_size - 8))    # Остаток заголовка

        new_data.extend(b"\x00" * entries_section_size)  # Секция записей

        # Добавляем строки и обновляем записи
        current_pos = len(new_data)  # Текущая позиция для строк

        for i, text_entry in enumerate(file_texts):
            entry_pos = header_size + i * FILES[file_idx]["entry_size"]
            
            if file_idx == 0:
                # Обработка первой строки
                string_offset_pos = entry_pos + FILES[file_idx]["text_offset"]
                text = text_entry["text"]
                text_bytes = text.encode("utf8") + b"\x00"
                relative_offset = current_pos - string_offset_pos
                struct.pack_into("<I", new_data, string_offset_pos, relative_offset)
                new_data.extend(text_bytes)
                current_pos += len(text_bytes)

                # Обработка второй строки
                string_offset_2_pos = entry_pos + FILES[file_idx]["text_offset_2"]
                text_2 = text_entry["text_2"]
                text_2_bytes = text_2.encode("utf8") + b"\x00"
                relative_offset_2 = current_pos - string_offset_2_pos
                struct.pack_into("<I", new_data, string_offset_2_pos, relative_offset_2)
                new_data.extend(text_2_bytes)
                current_pos += len(text_2_bytes)

                # Записываем Unknown значение
                unknown_pos = entry_pos + FILES[file_idx]["Unknown"]
                struct.pack_into("<I", new_data, unknown_pos, text_entry["Unknown"][0])

            elif file_idx == 17 and "speaker_id" in text_entry:
                string_offset_pos = entry_pos + FILES[file_idx]["text_offset"]
                text = text_entry["text"]
                text_bytes = text.encode("utf8") + b"\x00"
                relative_offset = current_pos - string_offset_pos
                struct.pack_into("<I", new_data, string_offset_pos, relative_offset)
                speaker_offset_pos = entry_pos + FILES[file_idx]["speaker_offset"]
                struct.pack_into("<I", new_data, speaker_offset_pos, text_entry["speaker_id"])
                new_data.extend(text_bytes)
                current_pos += len(text_bytes)

            else:
                string_offset_pos = entry_pos + FILES[file_idx]["text_offset"]
                text = text_entry["text"]
                text_bytes = text.encode("utf8") + b"\x00"
                relative_offset = current_pos - string_offset_pos
                struct.pack_into("<I", new_data, string_offset_pos, relative_offset)
                new_data.extend(text_bytes)
                current_pos += len(text_bytes)

        # Сохранение нового файла
        with open(orig_file, "wb") as f:
            f.write(new_data)
        
        print(f"Файл {file_idx} успешно обновлен")

    print("Упаковка текстов завершена")

def main():
    parser = argparse.ArgumentParser(description='Инструмент для работы с текстовыми файлами игры')
    parser.add_argument('path', type=str, help='Путь к папке с файлами (например, "LinkData/LANG/ENG/LINKDATA_LANG_ENG")')
    parser.add_argument('--json', type=str, default="extracted_texts.json", help='Путь к JSON файлу (по умолчанию: extracted_texts.json)')
    
    args = parser.parse_args()
    string_path = Path(args.path)

    while True:
        print("\n1. Извлечь тексты")
        print("2. Упаковать тексты")
        print("3. Выход")
        
        choice = input("\nВыберите действие (1-3): ")
        
        if choice == "1":
            extract_texts(string_path)
        elif choice == "2":
            pack_texts(string_path, args.json)
        elif choice == "3":
            break
        else:
            print("Неверный выбор. Попробуйте снова.")

if __name__ == "__main__":
    main() 