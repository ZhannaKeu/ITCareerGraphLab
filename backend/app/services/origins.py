"""User-declared origins, not independently established evidence.

CSV labels such as 'expert' or 'survey' are claims and never verification statuses.
"""
DISCLOSURE = {
    "protocol": "provenance-v1",
    "declared_by": "dataset owner",
    "independently_verified": False,
    "statement": "Большая часть датасетов подготовлена с помощью ИИ и пока не прошла экспертную верификацию.",
    "weights": "Role skill weights вычислены Python в Google Colab. Некоторые веса ML-библиотек основаны на источниках, найденных ИИ; точные ссылки и перечень затронутых строк пока не предоставлены.",
    "curriculum": "Названия дисциплин перенесены из реального учебного плана по сообщению владельца. Сам документ и реквизиты источника пока не представлены; это не подтверждает course-skill mappings.",
    "requirements": "Junior/Middle requirements предварительно сформированы ИИ.",
    "prerequisites": "Prerequisite relationships предварительно сформированы ИИ.",
    "course_mappings": "Course-skill mappings предварительно сформированы ИИ.",
    "other": "Происхождение остальных записей на уровне строки не установлено.",
    "interpretation": "Показатели — результаты модели на выбранных данных и допущениях, не фактическая сложность, время обучения или доказательство качества рекомендаций.",
    "verification_policy": "Каждая исходная запись Unverified. Expert Verified / Source Verified — явные заявления рецензента с сохранёнными именем и основанием; автоматической проверки полномочий или достоверности нет.",
}
