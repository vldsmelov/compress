"""
SB Check Service - анализ компаний по чек-листу
"""

import os
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Текущий файл: .../api/app/services/sb_check_service.py
THIS_FILE = Path(__file__).resolve()
# Родители:
#   parents[0] -> .../api/app/services
#   parents[1] -> .../api/app       ← здесь лежит assets/
APP_DIR = THIS_FILE.parents[1]

# Файл по умолчанию: <APP_DIR>/assets/sb_data.json
# В контейнере это будет /opt/app/app/assets/sb_data.json
DEFAULT_SB_DATA_FILE = APP_DIR / "assets" / "sb_data.json"



@dataclass
class CheckResult:
    """
    Результат проверки компании по чек-листу
    """
    company_name: str
    html_report: str
    globas_score: Optional[int]
    good_count: int
    bad_count: int


class SBCheckService:
    """
    Сервис проверки компаний по чек-листу (SB Check).
    """

    # Какие ответы считаем "хорошими" для каждого пункта чек-листа
    CHECKLIST_POSITIVE_ANSWERS = {
        1: {"Нет"},                 # ЕГРЮЛ недостоверность
        2: {"Нет"},                 # Ликвидация/банкротство/реорганизация
        3: {"Да"},                  # Совпадение ИНН/ОГРН/адрес/директор
        4: {"Да"},                  # Срок действия компании >= 3 лет
        5: {"Да"},                  # Достаточно персонала
        6: {"Да"},                  # Наличие сертификатов/лицензий
        7: {"Да"},                  # Наличие активов
        8: {"Нет"},                 # Долги по налогам/ФССП/кредитным линиям
        9: {"Нет"},                 # Активные суды
        10: {"Нет"},                # Долги по исп. листам
        11: {"Имеется"},            # Опыт госконтрактов
        12: {"Не состоит"},         # Реестр недобросовестных поставщиков
        13: {"Не зарегистрирован"}, # Адрес массовой регистрации
        14: {"Не состоит"},         # Директор дисквалифицирован
        15: {"Не состоит"},         # Директор номинальный
        16: {"Имеется"},            # Доверенности на подписантов
        17: {"Нет"},                # Банки блокировали счета
        18: {"Имеется"},            # Справка ФНС об отсутствии задолженности
        19: {"Не выявляли"},        # Нарушения по итогам проверок
    }

    def __init__(self, data_file_path: Optional[str] = None) -> None:
        """
        Порядок приоритета пути к JSON с компаниями:

        1) Переменная окружения SB_CHECK_DATA_FILE
        2) Явно переданный параметр data_file_path
        3) Значение по умолчанию: <PROJECT_ROOT>/assets/sb_data.json
           (в твоём случае: /opt/app/assets/sb_data.json)
        """

        env_path = os.getenv("SB_CHECK_DATA_FILE")
        if env_path:
            self.data_file = Path(env_path)
        elif data_file_path:
            self.data_file = Path(data_file_path)
        else:
            self.data_file = DEFAULT_SB_DATA_FILE

        logger.info(f"SB Check service initialized with data file: {self.data_file}")

    # ----------------- ВНУТРЕННИЕ ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ -----------------

    def _load_data(self) -> List[Dict[str, Any]]:
        """
        Загружает список компаний из JSON-файла.
        """
        if not self.data_file.exists():
            raise FileNotFoundError(f"Файл {self.data_file} не найден")

        if self.data_file.is_dir():
            raise IsADirectoryError(f"{self.data_file} — это директория, а должен быть файл JSON")

        with self.data_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # Поддержка случая, когда внутри лежит один объект, а не массив
        if isinstance(data, dict):
            data = [data]

        logger.info(f"Loaded {len(data)} company records from {self.data_file}")
        return data

    def _find_company_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Ищет компанию по подстроке в поле name (без учёта регистра).
        """
        try:
            data = self._load_data()
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load data: {e}")
            return None

        name_lower = name.lower()
        for item in data:
            if "name" in item and name_lower in str(item["name"]).lower():
                logger.info(f"Found company: {item.get('name')}")
                return item

        logger.warning(f"Company not found: {name}")
        return None

    def _classify_status(self, point_number: int, value: str) -> str:
        """
        Классифицирует статус как 'good', 'bad' или 'neutral'.
        """
        positive = self.CHECKLIST_POSITIVE_ANSWERS.get(point_number, set())

        if positive:
            return "good" if value in positive else "bad"

        if value in {"Да", "Имеется", "Не выявляли"}:
            return "good"
        if value in {"Нет", "Не имеется", "Не состоит", "Выявляли"}:
            return "bad"

        return "neutral"

    def _get_score_style(self, score: Optional[int]) -> Tuple[str, str, str]:
        """
        Возвращает (bg_color, text_color, label) для скоринга Globas.
        """
        if score is None:
            return "#f3f4f6", "#4b5563", "Нет данных"

        if score < 50:
            return "#fef2f2", "#b91c1c", "Низкий уровень"
        elif score < 70:
            return "#fffbeb", "#92400e", "Средний уровень"
        else:
            return "#ecfdf5", "#047857", "Высокий уровень"

    def _build_html_report(self, company: Dict[str, Any]) -> Tuple[str, int, int]:
        """
        Собирает HTML-отчёт по компании и считает good/bad статусы.
        """
        checklist = company.get("checklist", {})
        company_name = company.get("name", "")

        rows_html = ""
        good_count = 0
        bad_count = 0

        for key, value in checklist.items():
            parts = key.split("_", 1)
            if len(parts) != 2:
                continue

            num_str, text_raw = parts
            try:
                num = int(num_str)
            except ValueError:
                num = 0

            text = text_raw.replace("_", " ")

            status = self._classify_status(num, value)

            if status == "good":
                bg_color = "#dcfce7"
                text_color = "#166534"
                good_count += 1
            elif status == "bad":
                bg_color = "#fee2e2"
                text_color = "#b91c1c"
                bad_count += 1
            else:
                bg_color = "#f3f4f6"
                text_color = "#111827"

            rows_html += f"""
            <tr>
                <td class="num">{num}</td>
                <td class="text">{text}</td>
                <td class="status">
                    <span class="status-pill" style="background:{bg_color}; color:{text_color};">
                        {value}
                    </span>
                </td>
            </tr>
            """

        globas_score = company.get("globas_score", None)
        score_bg, score_color, score_label = self._get_score_style(globas_score)

        html = f"""
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8" />
            <title>Checklist — {company_name}</title>
            <style>
                * {{
                    box-sizing: border-box;
                }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
                    margin: 0;
                    padding: 0;
                    background: #e5e7eb;
                }}
                .page-wrapper {{
                    max-width: 1000px;
                    margin: 32px auto 40px;
                    padding: 0 16px;
                }}
                .card {{
                    background: #ffffff;
                    border-radius: 16px;
                    box-shadow: 0 18px 40px rgba(15, 23, 42, 0.18);
                    padding: 24px 24px 28px;
                }}

                .header-row {{
                    display: flex;
                    align-items: flex-start;
                    justify-content: space-between;
                    gap: 16px;
                    margin-bottom: 16px;
                }}
                h1 {{
                    font-size: 22px;
                    margin: 0 0 4px;
                    color: #111827;
                }}
                .subtitle {{
                    margin: 0;
                    color: #6b7280;
                    font-size: 13px;
                }}

                .score-card {{
                    min-width: 180px;
                    padding: 10px 12px;
                    border-radius: 12px;
                    background: {score_bg};
                    color: {score_color};
                    text-align: right;
                }}
                .score-label {{
                    font-size: 11px;
                    text-transform: uppercase;
                    letter-spacing: 0.08em;
                    opacity: 0.8;
                }}
                .score-value {{
                    font-size: 26px;
                    font-weight: 700;
                    line-height: 1.1;
                    margin-top: 4px;
                }}
                .score-caption {{
                    font-size: 11px;
                    margin-top: 2px;
                }}

                .summary {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 10px;
                    margin-bottom: 16px;
                    font-size: 13px;
                }}
                .summary-pill {{
                    padding: 6px 10px;
                    border-radius: 999px;
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    background: #f3f4f6;
                    color: #374151;
                }}
                .summary-pill.good {{
                    background: #dcfce7;
                    color: #166534;
                }}
                .summary-pill.bad {{
                    background: #fee2e2;
                    color: #b91c1c;
                }}

                table {{
                    border-collapse: collapse;
                    width: 100%;
                    font-size: 14px;
                    margin-bottom: 18px;
                }}
                th, td {{
                    padding: 9px 10px;
                    vertical-align: middle;
                }}
                th {{
                    background: #f9fafb;
                    border-bottom: 1px solid #e5e7eb;
                    text-align: left;
                    font-size: 11px;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                    color: #6b7280;
                }}
                td {{
                    border-bottom: 1px solid #e5e7eb;
                    color: #111827;
                }}
                tr:last-child td {{
                    border-bottom: none;
                }}
                td.num {{
                    width: 50px;
                    font-weight: 600;
                    text-align: center;
                    color: #374151;
                }}
                td.text {{
                    padding-right: 16px;
                }}
                td.status {{
                    width: 240px;
                    text-align: right;
                }}
                .status-pill {{
                    display: inline-block;
                    padding: 4px 10px;
                    border-radius: 999px;
                    font-weight: 600;
                    font-size: 13px;
                }}

                .legend {{
                    margin-top: 6px;
                    font-size: 11px;
                    color: #6b7280;
                }}
                .legend span {{
                    display: inline-flex;
                    align-items: center;
                    padding: 3px 8px;
                    margin-right: 6px;
                    border-radius: 999px;
                    border: 1px solid #e5e7eb;
                    gap: 6px;
                    background: #f9fafb;
                }}
                .legend-dot {{
                    width: 8px;
                    height: 8px;
                    border-radius: 999px;
                }}

                .divider {{
                    margin: 22px 0 20px;
                    border: none;
                    border-top: 1px solid #e5e7eb;
                }}

                .company-info {{
                    margin-top: 4px;
                }}
                .company-info h2 {{
                    margin: 0 0 14px;
                    font-size: 16px;
                    color: #111827;
                }}
                .info-grid {{
                    display: grid;
                    grid-template-columns: 1fr;
                    gap: 10px;
                }}
                @media (min-width: 640px) {{
                    .info-grid {{
                        grid-template-columns: 1fr 1fr;
                    }}
                }}
                .info-row {{
                    background: #f9fafb;
                    border-radius: 10px;
                    padding: 8px 10px;
                    display: flex;
                    flex-direction: column;
                }}
                .info-label {{
                    font-size: 11px;
                    text-transform: uppercase;
                    letter-spacing: 0.06em;
                    color: #6b7280;
                    margin-bottom: 4px;
                }}
                .info-value {{
                    font-size: 13px;
                    color: #111827;
                    word-break: break-word;
                }}
            </style>
        </head>
        <body>
            <div class="page-wrapper">
                <div class="card">
                    <div class="header-row">
                        <div>
                            <h1>{company_name}</h1>
                            <p class="subtitle">Checklist компании: оценка ключевых рисков и параметров контрагента</p>
                        </div>
                        <div class="score-card">
                            <div class="score-label">Скоринг Globas</div>
                            <div class="score-value">{globas_score if globas_score is not None else "—"}</div>
                            <div class="score-caption">{score_label}</div>
                        </div>
                    </div>

                    <div class="summary">
                        <div class="summary-pill good">
                            ✅ Хороших статусов: <strong>{good_count}</strong>
                        </div>
                        <div class="summary-pill bad">
                            ⚠ Проблемных статусов: <strong>{bad_count}</strong>
                        </div>
                    </div>

                    <table>
                        <tr>
                            <th>№</th>
                            <th>Наименование проверки</th>
                            <th>Статус</th>
                        </tr>
                        {rows_html}
                    </table>

                    <div class="legend">
                        <span>
                            <span class="legend-dot" style="background:#dcfce7;"></span>
                            Хороший статус
                        </span>
                        <span>
                            <span class="legend-dot" style="background:#fee2e2;"></span>
                            Неблагополучный статус
                        </span>
                    </div>

                    <hr class="divider" />

                    <div class="company-info">
                        <h2>Информация о компании</h2>
                        <div class="info-grid">
                            <div class="info-row">
                                <div class="info-label">Наименование</div>
                                <div class="info-value">{company.get("name", "")}</div>
                            </div>
                            <div class="info-row">
                                <div class="info-label">ИНН</div>
                                <div class="info-value">{company.get("inn", "")}</div>
                            </div>
                            <div class="info-row">
                                <div class="info-label">ИИН</div>
                                <div class="info-value">{company.get("iin", "")}</div>
                            </div>
                            <div class="info-row">
                                <div class="info-label">ОГРН</div>
                                <div class="info-value">{company.get("ogrn", "")}</div>
                            </div>
                            <div class="info-row">
                                <div class="info-label">Адрес</div>
                                <div class="info-value">{company.get("address", "")}</div>
                            </div>
                            <div class="info-row">
                                <div class="info-label">Директор</div>
                                <div class="info-value">{company.get("director", "")}</div>
                            </div>
                            <div class="info-row">
                                <div class="info-label">Дата регистрации</div>
                                <div class="info-value">{company.get("registration_date", "")}</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        return html, good_count, bad_count

    # ----------------- ПУБЛИЧНЫЕ МЕТОДЫ СЕРВИСА -----------------

    async def analyze_company(self, company_name: str) -> CheckResult:
        """
        Найти компанию и собрать по ней отчёт.
        """
        logger.info(f"Starting company analysis for: {company_name}")

        company = self._find_company_by_name(company_name)
        if not company:
            raise ValueError(f"Компания '{company_name}' не найдена")

        html_report, good_count, bad_count = self._build_html_report(company)
        globas_score = company.get("globas_score", None)

        return CheckResult(
            company_name=company.get("name", ""),
            html_report=html_report,
            globas_score=globas_score,
            good_count=good_count,
            bad_count=bad_count,
        )

    async def get_companies_list(self, limit: int = 20) -> List[Dict[str, str]]:
        """
        Получить список доступных компаний (имя, ИНН, адрес).
        """
        try:
            data = self._load_data()
        except Exception as e:
            logger.error(f"Failed to load companies list: {e}")
            return []

        companies: List[Dict[str, str]] = []
        for item in data[:limit]:
            companies.append(
                {
                    "name": item.get("name", "Unknown"),
                    "inn": item.get("inn", ""),
                    "address": item.get("address", ""),
                }
            )

        return companies


@lru_cache()
def get_sb_check_service(data_file_path: Optional[str] = None) -> SBCheckService:
    """Return a cached SBCheckService instance."""

    return SBCheckService(data_file_path)


__all__ = ["CheckResult", "SBCheckService", "get_sb_check_service"]
