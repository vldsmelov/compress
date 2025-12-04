from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.responses import JSONResponse
import json
import os
import requests
import re
from typing import List, Dict
from pathlib import Path

app = FastAPI(title="Purchase Analysis API")

# Конфигурация
# OLLAMA_HOST = os.getenv("OLLAMA_HOST", "ollama_ext")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "ollama")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:14b")

# Путь к папке data
THIS_FILE = Path(__file__).resolve()
AI_ECONOM_DIR = THIS_FILE.parents[0]

# Путь к файлу budget.json
BUDGET_FILE = AI_ECONOM_DIR / "data" / "budget.json"

LLM_CONFIG = {
    "url": f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/chat",
    "model": OLLAMA_MODEL,
    "temperature": 0.1,
    "max_tokens": 2000,
    "timeout": 60,
}

def clean_number_string(number_str: str) -> float:
    """
    Очищает строку с числом от пробелов, неразрывных пробелов и преобразует в float.
    """
    if not number_str or number_str.strip() == '':
        return 0.0
    
    # Заменяем неразрывные пробелы (\xa0) и обычные пробелы
    cleaned = number_str.replace('\xa0', '').replace(' ', '').replace(',', '.')
    
    # Удаляем все нецифровые символы кроме точки и минуса
    cleaned = re.sub(r'[^\d.-]', '', cleaned)
    
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0

def parse_spec_from_sections(sections_data: dict) -> dict:
    """
    Парсит спецификацию товаров из sections.json (особенно из part_16)
    и преобразует в нужный формат.
    """
    try:
        # Ищем part с таблицей товаров (обычно part_16)
        table_part = None
        for key, value in sections_data.items():
            if "TABLE:" in value and "Наименование и характеристика Товара" in value:
                table_part = value
                break
        
        if not table_part:
            raise ValueError("Не найдена таблица с товарами в sections.json")
        
        # Извлекаем строки таблицы
        lines = table_part.split('\n')
        items = []
        total_amount = 0
        
        for line in lines:
            if "TABLE:" in line and "|" in line:
                # Убираем префикс TABLE: и разбиваем по разделителю
                clean_line = line.replace("TABLE:", "").strip()
                columns = [col.strip() for col in clean_line.split('|')]
                
                # Пропускаем заголовки и итоговые строки
                if (len(columns) >= 6 and 
                    "Наименование" not in columns[1] and 
                    "ИТОГО" not in columns[1] and
                    "В том числе НДС" not in columns[1] and
                    columns[1] and not columns[1].isdigit()):
                    
                    try:
                        # Парсим данные товара
                        name = columns[1]
                        qty = clean_number_string(columns[2])
                        unit = columns[3]
                        price = clean_number_string(columns[4])
                        amount = clean_number_string(columns[5])
                        country = columns[6] if len(columns) > 6 else "Не указано"
                        
                        # Создаем объект товара
                        item = {
                            "name": name,
                            "qty": int(qty) if qty.is_integer() else qty,
                            "unit": unit,
                            "price": price,
                            "amount": amount,
                            "country": country
                        }
                        
                        items.append(item)
                        total_amount += amount
                        
                    except (ValueError, IndexError) as e:
                        print(f"Ошибка парсинга строки: {line}, ошибка: {e}")
                        continue
        
        # Создаем итоговый объект спецификации
        spec_data = {
            "items": items,
            "total": total_amount,
            "vat": 20,  # Из part_4 известно, что НДС 20%
            "warning": None
        }
        
        return spec_data
        
    except Exception as e:
        raise ValueError(f"Ошибка парсинга спецификации: {str(e)}")

def get_categories_for_items(item_names: List[str], available_categories: List[str]) -> List[str]:
    """
    ОДИН запрос в LLM для всех товаров.
    На вход: список названий товаров и список доступных категорий.
    На выход: список категорий той же длины и в том же порядке, что item_names.
    
    Если что-то пошло не так — все категории будут "Неопределенная категория".
    """

    if not item_names:
        return []

    # Базовое значение по умолчанию
    default_category = "Неопределенная категория"
    categories_result = [default_category] * len(item_names)

    categories_str = ", ".join(available_categories)

    # Формируем понятный промпт
    items_block = "\n".join(
        f"{idx + 1}. {name}" for idx, name in enumerate(item_names)
    )

    prompt = f"""
    Ты должен отнести каждый товар к одной из категорий бюджета.

    Доступные категории:
    {categories_str}

    Список товаров (важен порядок):
    {items_block}

    Верни СТРОГО корректный JSON-массив строк без комментариев и лишнего текста, например:
    ["Категория1", "Категория2", "Неопределенная категория", ...]

    Количество элементов в массиве ДОЛЖНО строго совпадать с количеством товаров,
    а порядок должен соответствовать списку товаров выше.
    Каждый элемент массива — это ИМЯ категории из доступных категорий
    или строка "{default_category}", если подходящей категории нет.
    """

    try:
        payload = {
            "model": LLM_CONFIG["model"],
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": LLM_CONFIG["temperature"],
                "num_predict": LLM_CONFIG["max_tokens"],
            },
        }

        response = requests.post(
            LLM_CONFIG["url"],
            json=payload,
            timeout=LLM_CONFIG["timeout"],
        )

        if response.status_code != 200:
            return categories_result

        result = response.json()
        content = result["message"]["content"]

        # Чистим контент от возможных ```json ... ```
        # Берём содержимое между первой '[' и последней ']'
        start = content.find('[')
        end = content.rfind(']')
        if start == -1 or end == -1 or end <= start:
            return categories_result

        json_str = content[start:end + 1].strip()

        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError:
            return categories_result

        if not isinstance(parsed, list):
            return categories_result

        # Делаем список той же длины, фильтруя неправильные значения
        cleaned: List[str] = []
        for i, cat in enumerate(parsed):
            if not isinstance(cat, str):
                cleaned.append(default_category)
                continue

            cat_clean = (
                cat.replace(".", "")
                .replace('"', "")
                .replace("'", "")
                .strip()
            )

            if cat_clean in available_categories:
                cleaned.append(cat_clean)
            else:
                cleaned.append(default_category)

        # Если длина не совпадает — обрежем/дополним
        if len(cleaned) < len(item_names):
            cleaned.extend([default_category] * (len(item_names) - len(cleaned)))
        elif len(cleaned) > len(item_names):
            cleaned = cleaned[:len(item_names)]

        return cleaned

    except Exception:
        # В случае любой ошибки — просто вернем "Неопределенная категория"
        return categories_result

@app.post("/upload-budget")
async def upload_budget(
    budget_data: str = Body(..., media_type="text/plain", description="JSON данные в теле запроса")
):
    """
    Загружает или заменяет файл budget.json из 1С
    Принимает plain text с JSON в теле запроса
    Content-Type: text/plain; charset=utf-8
    """
    
    try:
        # Парсим JSON из строки
        budget_json = json.loads(budget_data)
        
        # Валидация структуры
        if not isinstance(budget_json, list):
            raise ValueError("Данные бюджета должны быть массивом (списком)")
        
        # Проверяем, что все элементы имеют нужные поля
        valid_items = []
        for i, item in enumerate(budget_json):
            if not isinstance(item, dict):
                raise ValueError(f"Элемент {i} должен быть объектом (словарем)")
            
            # Проверяем наличие обязательных полей
            if "КатегорияБюджета" not in item:
                raise ValueError(f"Элемент {i} не содержит поле 'КатегорияБюджета'")
            
            if "ДоступныйЛимит" not in item:
                raise ValueError(f"Элемент {i} не содержит поле 'ДоступныйЛимит'")
            
            # Преобразуем значения к нужным типам
            valid_item = {
                "КатегорияБюджета": str(item["КатегорияБюджета"]).strip(),
                "ДоступныйЛимит": float(item["ДоступныйЛимит"])
            }
            
            # Добавляем дополнительные поля, если они есть
            for key, value in item.items():
                if key not in valid_item:
                    valid_item[key] = value
            
            valid_items.append(valid_item)
        
        # Сохраняем в файл
        with open(BUDGET_FILE, 'w', encoding='utf-8') as f:
            json.dump(valid_items, f, ensure_ascii=False, indent=2)
        
        # Получаем статистику
        categories = [item["КатегорияБюджета"] for item in valid_items]
        total_budget = sum(item["ДоступныйЛимит"] for item in valid_items)
        
        return {
            "status": "success",
            "message": "Бюджет успешно загружен из 1С",
            "details": {
                "file_path": str(BUDGET_FILE.absolute()),
                "categories_count": len(valid_items),
                "total_budget": total_budget,
                "categories": categories
            }
        }
        
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Невалидный JSON: {str(e)}")
    except ValueError as e:
        raise HTTPException(400, f"Некорректные данные: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Ошибка при сохранении файла: {str(e)}")

@app.get("/get-budget")
async def get_budget():
    """
    Возвращает текущий загруженный budget.json
    """
    try:
        if not BUDGET_FILE.exists():
            return {
                "status": "not_found",
                "message": "Файл budget.json не найден. Загрузите его через /upload-budget",
                "budget_data": []
            }
        
        with open(BUDGET_FILE, 'r', encoding='utf-8') as f:
            budget_data = json.load(f)
        
        return {
            "status": "success",
            "budget_data": budget_data
        }
        
    except Exception as e:
        raise HTTPException(500, f"Ошибка при чтении файла: {str(e)}")

@app.post("/analyze")
async def analyze_purchases(
    spec_file: UploadFile = File(..., description="JSON файл со спецификацией товаров (sections.json)")
):
    """
    Анализ покупок на основе загруженного sections.json и существующего budget.json
    """
    # Проверяем наличие budget.json
    if not BUDGET_FILE.exists():
        raise HTTPException(
            400, 
            "Файл budget.json не найден. Загрузите его через /upload-budget"
        )

    # Валидация типа файла
    if not spec_file.filename.endswith(".json"):
        raise HTTPException(400, "Файл должен быть в формате JSON")

    try:
        # Чтение budget.json из файла
        with open(BUDGET_FILE, 'r', encoding='utf-8') as f:
            budget_data = json.load(f)

        # Чтение и парсинг sections.json
        spec_content = await spec_file.read()
        sections_data = json.loads(spec_content)

        # Преобразуем sections.json в нужный формат спецификации
        spec_data = parse_spec_from_sections(sections_data)

    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Ошибка парсинга JSON: {str(e)}")
    except ValueError as e:
        raise HTTPException(400, f"Ошибка преобразования спецификации: {str(e)}")
    except Exception as e:
        raise HTTPException(400, f"Ошибка чтения файлов: {str(e)}")

    # Валидация структуры spec данных
    if not isinstance(spec_data, dict) or "items" not in spec_data:
        raise HTTPException(400, "Spec файл должен содержать объект с полем 'items'")

    if not isinstance(spec_data["items"], list):
        raise HTTPException(400, "Поле 'items' в spec файле должно быть массивом")

    for item in spec_data["items"]:
        if not all(key in item for key in ["name", "qty", "unit", "price", "amount"]):
            raise HTTPException(
                400,
                "Каждый товар должен содержать поля: name, qty, unit, price, amount",
            )

    try:
        # Создаем словарь бюджетов
        budget_dict: Dict[str, float] = {
            item["КатегорияБюджета"]: item["ДоступныйЛимит"] for item in budget_data
        }
        available_categories = list(budget_dict.keys())

        # 1) Собираем ВСЕ имена товаров
        item_names = [item["name"] for item in spec_data["items"]]

        # 2) Один запрос к LLM, получаем список категорий
        categories_for_items = get_categories_for_items(item_names, available_categories)
        llm_requests_count = 1 if item_names else 0

        # 3) Присваиваем категорию каждому товару
        categorized_items_by_category: Dict[str, List[dict]] = {}

        for idx, item in enumerate(spec_data["items"]):
            category = categories_for_items[idx] if idx < len(categories_for_items) else "Неопределенная категория"
            item_with_category = {
                "name": item["name"],
                "qty": item["qty"],
                "unit": item["unit"],
                "price": item["price"],
                "amount": item["amount"],
                "country": item.get("country", "Не указано"),
                "category": category,
            }

            if category not in categorized_items_by_category:
                categorized_items_by_category[category] = []

            # Для ответа по категориям сделаем "русские" ключи в товарах
            categorized_items_by_category[category].append(
                {
                    "название": item_with_category["name"],
                    "количество": item_with_category["qty"],
                    "единица_измерения": item_with_category["unit"],
                    "цена_за_единицу": item_with_category["price"],
                    "сумма_покупки": item_with_category["amount"],
                    "страна": item_with_category["country"],
                    "категория": item_with_category["category"],
                }
            )

        # 4) Формируем отчет по категориям в нужном формате
        categories_output = []

        for category, items in categorized_items_by_category.items():
            total_amount = sum(item["сумма_покупки"] for item in items)
            available_budget = budget_dict.get(category, 0)

            needed_amount = max(0, total_amount - available_budget)
            enough = available_budget >= total_amount  # True/False

            categories_output.append(
                {
                    "категория": category,
                    "товары": items,
                    "доступный_бюджет_категории": available_budget,
                    "общая_сумма_товаров": total_amount,
                    "необходимая_сумма": needed_amount,
                    "хватает": enough,
                }
            )

        # Итоговый ответ
        return {
            "categories": categories_output,
            "total_spec_amount": spec_data["total"],
            "items_count": len(spec_data["items"]),
            "budget_source": "data/budget.json",
        }

    except Exception as e:
        raise HTTPException(500, f"Ошибка при анализе: {str(e)}")

@app.get("/")
async def root():
    """Проверка работы API"""
    return {
        "message": "Purchase Analysis API is working!",
        "status": "ok",
        "endpoints": {
            "POST /upload-budget": "Загрузить бюджет из 1С (text/plain)",
            "GET /get-budget": "Получить текущий budget.json",
            "POST /analyze": "Анализ спецификации (требует sections.json)",
            "POST /parse-spec": "Только парсинг sections.json"
        }
    }

@app.post("/parse-spec")
async def parse_specification(spec_file: UploadFile = File(..., description="Sections.json файл")):
    """
    Отдельный эндпоинт для преобразования sections.json в формат спецификации
    """
    if not spec_file.filename.endswith(".json"):
        raise HTTPException(400, "Файл должен быть в формате JSON")

    try:
        spec_content = await spec_file.read()
        sections_data = json.loads(spec_content)
        
        spec_data = parse_spec_from_sections(sections_data)
        
        return {
            "status": "success",
            "spec_data": spec_data
        }
        
    except Exception as e:
        raise HTTPException(400, f"Ошибка преобразования: {str(e)}")