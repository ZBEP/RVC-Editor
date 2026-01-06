import locale
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def get_system_language():
    try:
        if os.name == 'nt':
            import ctypes
            windll = ctypes.windll.kernel32
            lang_id = windll.GetUserDefaultUILanguage()
            primary = lang_id & 0x3FF
            if primary == 0x19:
                return 'ru'
            elif primary == 0x04:
                return 'zh'
            else:
                return 'en'
        else:
            lang = locale.getdefaultlocale()[0]
            if lang:
                lang = lang.lower()[:2]
                if lang in ('ru', 'zh'):
                    return lang
    except:
        pass
    return 'en'


CURRENT_LANG = get_system_language()

TRANSLATIONS = {
    "Ready": {"ru": "Готов", "zh": "就绪"},
    "Source": {"ru": "Исходник", "zh": "源"},
    "Error": {"ru": "Ошибка", "zh": "错误"},
    "Error:": {"ru": "Ошибка:", "zh": "错误:"},
    "Warning": {"ru": "Внимание", "zh": "警告"},
    "Confirm": {"ru": "Подтверждение", "zh": "确认"},
    "Done": {"ru": "Готово", "zh": "完成"},
    "Done:": {"ru": "Готово:", "zh": "完成:"},
    "Delete": {"ru": "Удалить", "zh": "删除"},
    "Save": {"ru": "Сохранить", "zh": "保存"},
    "Load": {"ru": "Загрузить", "zh": "加载"},
    "Cancel": {"ru": "Отмена", "zh": "取消"},
    "Yes": {"ru": "Да", "zh": "是"},
    "No": {"ru": "Нет", "zh": "否"},
    "or": {"ru": "или", "zh": "或"},
    "of": {"ru": "из", "zh": "/"},
    "successful": {"ru": "успешно", "zh": "成功"},
    "Nothing to undo": {"ru": "Нечего отменять", "zh": "没有可撤销的操作"},
    "Nothing to redo": {"ru": "Нечего повторять", "zh": "没有可重做的操作"},
    "ms": {"ru": " мс", "zh": "毫秒"},
    "Silent": {"ru": "Тишина", "zh": "静音"},
    "Silent part created": {"ru": "Тихая часть создана", "zh": "静音片段已创建"},
    "Volume part:": {"ru": "Часть с громкостью:", "zh": "音量片段:"},
    "Volume:": {"ru": "Громкость:", "zh": "音量:"},
    "Select a region first": {"ru": "Сначала выделите область", "zh": "请先选择区域"},
    "Initializing RVC...": {"ru": "Инициализация RVC...", "zh": "正在初始化RVC..."},
    "Loading configuration...": {"ru": "Загрузка конфигурации...", "zh": "加载配置..."},
    "Loading VC module...": {"ru": "Загрузка VC модуля...", "zh": "加载VC模块..."},
    "RVC initialized": {"ru": "RVC инициализирован", "zh": "RVC已初始化"},
    "Device:": {"ru": "Устройство:", "zh": "设备:"},
    "Half precision:": {"ru": "Half precision:", "zh": "半精度:"},
    "Initialization error:": {"ru": "Ошибка инициализации:", "zh": "初始化错误:"},
    "Model already loaded": {"ru": "Модель уже загружена", "zh": "模型已加载"},
    "Loading model:": {"ru": "Загрузка модели:", "zh": "加载模型:"},
    "Loading": {"ru": "Загрузка", "zh": "加载中"},
    "Model loaded": {"ru": "Модель загружена", "zh": "模型已加载"},
    "Load result: model initialized": {"ru": "Результат загрузки: модель инициализирована", "zh": "加载结果：模型已初始化"},
    "Model loaded successfully": {"ru": "Модель успешно загружена", "zh": "模型加载成功"},
    "Model load error:": {"ru": "Ошибка загрузки модели:", "zh": "模型加载错误:"},
    "Converter not initialized!": {"ru": "Конвертер не инициализирован!", "zh": "转换器未初始化！"},
    "Converting:": {"ru": "Конвертация:", "zh": "转换:"},
    "Conversion error:": {"ru": "Ошибка конвертации:", "zh": "转换错误:"},
    "Conversion error": {"ru": "Ошибка конвертации", "zh": "转换错误"},
    "Error: conversion result is empty": {"ru": "Ошибка: результат конвертации пустой", "zh": "错误：转换结果为空"},
    "Saved:": {"ru": "Сохранено:", "zh": "已保存:"},
    "FFmpeg not found, saved as WAV": {"ru": "FFmpeg не найден, сохранено как WAV", "zh": "未找到FFmpeg，已保存为WAV"},
    "MP3 conversion error:": {"ru": "Ошибка конвертации в MP3:", "zh": "MP3转换错误:"},
    "M4A conversion error:": {"ru": "Ошибка конвертации в M4A:", "zh": "M4A转换错误:"},
    "No audio files in folder:": {"ru": "Нет аудиофайлов в папке:", "zh": "文件夹中没有音频文件:"},
    "Files found:": {"ru": "Найдено файлов:", "zh": "找到文件:"},
    "File": {"ru": "Файл", "zh": "文件"},
    "Processed:": {"ru": "Обработано:", "zh": "已处理:"},
    "Linear blend": {"ru": "Линейное смешивание", "zh": "线性混合"},
    "Smooth blend": {"ru": "Плавное смешивание", "zh": "平滑混合"},
    "Original": {"ru": "Исходное", "zh": "原始"},
    "Version": {"ru": "Версия", "zh": "版本"},
    "Result": {"ru": "Результат", "zh": "结果"},
    "Load WAV": {"ru": "Загрузите WAV", "zh": "加载WAV"},
    "Project loaded": {"ru": "Проект загружен", "zh": "项目已加载"},
    "Project load error:": {"ru": "Ошибка загрузки проекта:", "zh": "项目加载错误:"},
    "(no model)": {"ru": "(нет модели)", "zh": "(无模型)"},
    "Audio error:": {"ru": "Ошибка аудио:", "zh": "音频错误:"},
    "Device scan error:": {"ru": "Ошибка сканирования устройств:", "zh": "设备扫描错误:"},
    "(file not selected)": {"ru": "(файл не выбран)", "zh": "(未选择文件)"},
    "Run": {"ru": "Запуск", "zh": "运行"},
    "Selected:": {"ru": "Выделено:", "zh": "选择:"},
    "Delete current version": {"ru": "Удалить текущую версию", "zh": "删除当前版本"},
    "Keep only current": {"ru": "Оставить только текущую", "zh": "仅保留当前"},
    "Delete part (restore)": {"ru": "Удалить часть (восстановить)", "zh": "删除片段（恢复）"},
    "Flatten to single file": {"ru": "Свести в общий файл", "zh": "合并为单个文件"},
    "Version deleted": {"ru": "Версия удалена", "zh": "版本已删除"},
    "Other versions deleted": {"ru": "Другие версии удалены", "zh": "其他版本已删除"},
    "Part deleted, data restored": {"ru": "Часть удалена, данные восстановлены", "zh": "片段已删除，数据已恢复"},
    "Parts flattened": {"ru": "Части сведены в общий файл", "zh": "片段已合并"},
    "Markers:": {"ru": "Маркеры:", "zh": "标记:"},
    "Marker:": {"ru": "Маркер:", "zh": "标记:"},
    "Delete all markers": {"ru": "Удалить все маркеры", "zh": "删除所有标记"},
    "Marker deleted:": {"ru": "Маркер удалён:", "zh": "标记已删除:"},
    "All markers deleted": {"ru": "Все маркеры удалены", "zh": "所有标记已删除"},
    "Load file first": {"ru": "Сначала загрузите файл", "zh": "请先加载文件"},
    "Conversion in progress": {"ru": "Конвертация уже выполняется", "zh": "转换正在进行中"},
    "No selection. Convert entire file?": {"ru": "Нет выделения. Конвертировать весь файл?", "zh": "无选择。转换整个文件？"},
    "Converter not ready": {"ru": "Конвертер не готов", "zh": "转换器未就绪"},
    "Fragment too short": {"ru": "Слишком короткий фрагмент", "zh": "片段太短"},
    "Converting": {"ru": "Конвертация", "zh": "转换中"},
    "Conversion...": {"ru": "Конвертация...", "zh": "转换中..."},
    "No result": {"ru": "Нет результата", "zh": "无结果"},
    "Loaded:": {"ru": "Загружен:", "zh": "已加载:"},
    "File not found:": {"ru": "Файл не найден:", "zh": "文件未找到:"},
    "Load error:": {"ru": "Ошибка загрузки:", "zh": "加载错误:"},
    "base": {"ru": "база", "zh": "基础"},
    "Copied:": {"ru": "Скопировано:", "zh": "已复制:"},
    "Pasted:": {"ru": "Вставлено:", "zh": "已粘贴:"},
    "Nothing to paste": {"ru": "Нечего вставлять", "zh": "没有可粘贴的内容"},
    "No result to copy": {"ru": "Нет результата для копирования", "zh": "没有可复制的结果"},
    "Place cursor first": {"ru": "Сначала установите курсор", "zh": "请先放置光标"},
    "RVC Editor": {"ru": "RVC Editor", "zh": "RVC Editor"},
    "Log": {"ru": "Лог", "zh": "日志"},
    "Editor": {"ru": "Редактор", "zh": "编辑器"},
    "Conversion": {"ru": "Конвертация", "zh": "转换"},
    "Model": {"ru": "Модель", "zh": "模型"},
    "Model:": {"ru": "Модель:", "zh": "模型:"},
    "Index:": {"ru": "Индекс:", "zh": "索引:"},
    "Folders": {"ru": "Папки", "zh": "文件夹"},
    "Input:": {"ru": "Вход:", "zh": "输入:"},
    "Output:": {"ru": "Выход:", "zh": "输出:"},
    "Audio files found:": {"ru": "Найдено аудиофайлов:", "zh": "找到音频文件:"},
    "Folder does not exist": {"ru": "Папка не существует", "zh": "文件夹不存在"},
    "Parameters": {"ru": "Параметры", "zh": "参数"},
    "(2xclick on label = reset)": {"ru": "(2×клик по названию = сброс)", "zh": "(双击标签=重置)"},
    "F0 Method:": {"ru": "Метод F0:", "zh": "F0方法:"},
    "Analysis step:": {"ru": "Шаг анализа:", "zh": "分析步长:"},
    "(less = more accurate)": {"ru": "(меньше = точнее)", "zh": "(越小越精确)"},
    "Pitch:": {"ru": "Тон:", "zh": "音高:"},
    "Pitch filter:": {"ru": "Фильтр тональности:", "zh": "音高过滤:"},
    "Index influence:": {"ru": "Влияние индекса:", "zh": "索引影响:"},
    "Volume mix:": {"ru": "Микс громкости:", "zh": "音量混合:"},
    "Consonant protection:": {"ru": "Защита согласных:", "zh": "辅音保护:"},
    "Resample:": {"ru": "Ресемплинг:", "zh": "重采样:"},
    "(0=off)": {"ru": "(0=выкл)", "zh": "(0=关闭)"},
    "Presets:": {"ru": "Пресеты:", "zh": "预设:"},
    "Reset presets to default": {"ru": "Сбросить пресеты на стандартные", "zh": "重置预设为默认"},
    "On load (F1-F12):": {"ru": "При загрузке (F1-F12):", "zh": "加载时(F1-F12):"},
    "Tone": {"ru": "Тон", "zh": "音高"},
    "F0 method": {"ru": "F0 метод", "zh": "F0方法"},
    "Format:": {"ru": "Формат:", "zh": "格式:"},
    "Convert": {"ru": "Конвертировать", "zh": "转换"},
    "Models:": {"ru": "Моделей:", "zh": "模型:"},
    "indexes:": {"ru": "индексов:", "zh": "索引:"},
    "Parameters reset": {"ru": "Параметры сброшены", "zh": "参数已重置"},
    "First select a model": {"ru": "Сначала выберите модель", "zh": "请先选择模型"},
    "Preset": {"ru": "Пресет", "zh": "预设"},
    "saved": {"ru": "сохранён", "zh": "已保存"},
    "loaded": {"ru": "загружен", "zh": "已加载"},
    "is empty": {"ru": "пуст", "zh": "为空"},
    "click = save": {"ru": "Клик = сохранить", "zh": "点击=保存"},
    "click = overwrite": {"ru": "Клик = перезаписать", "zh": "点击=覆盖"},
    "Protect:": {"ru": "Защита:", "zh": "保护:"},
    "Filter:": {"ru": "Фильтр:", "zh": "过滤:"},
    "Presets reset to default": {"ru": "Пресеты сброшены на стандартные", "zh": "预设已重置为默认"},
    "reloading model...": {"ru": "перезагрузка модели...", "zh": "重新加载模型..."},
    "Load model:": {"ru": "Загружать модель:", "zh": "加载模型:"},
    "ON": {"ru": "ВКЛ", "zh": "开"},
    "OFF": {"ru": "ВЫКЛ", "zh": "关"},
    "Input folder does not exist": {"ru": "Входная папка не существует", "zh": "输入文件夹不存在"},
    "Failed to load model": {"ru": "Не удалось загрузить модель", "zh": "无法加载模型"},
    "No files to convert": {"ru": "Нет файлов для конвертации", "zh": "没有要转换的文件"},
    "Error: model not selected": {"ru": "Ошибка: модель не выбрана", "zh": "错误：未选择模型"},
    "(no index)": {"ru": "(no index)", "zh": "(no index)"},
    "(includes hop_length for crepe)": {"ru": "(включает hop_length для crepe)", "zh": "(包含crepe的hop_length)"},
    "toggle": {"ru": "переключить", "zh": "切换"},
    "if model empty - unchanged": {"ru": "если модель пустая - не меняется", "zh": "如果模型为空则不变"},
    "Load pitch:": {"ru": "Загружать тон:", "zh": "加载音高:"},
    "Load F0 method:": {"ru": "Загружать F0 метод:", "zh": "加载F0方法:"},
    "Part moved:": {"ru": "Часть перемещена:", "zh": "片段已移动:"},
    "Preset save error:": {"ru": "Ошибка сохранения пресета:", "zh": "预设保存错误:"},
    "Missing:": {"ru": "Отсутствуют:", "zh": "缺少:"},
    "Press Enter...": {"ru": "Нажмите Enter...", "zh": "按Enter键..."},
    "Starting...": {"ru": "Запуск...", "zh": "启动中..."},
    "mangio-crepe folder not found:": {"ru": "Папка mangio-crepe не найдена:", "zh": "未找到mangio-crepe文件夹:"},
    "mangio-crepe files updated:": {"ru": "Обновлены файлы mangio-crepe:", "zh": "mangio-crepe文件已更新:"},
    "hint_f0_method": {
        "ru": "Алгоритм извлечения основного тона (F0):\n\n• rmvpe - лучший баланс качества и скорости, рекомендуется\n• mangio-crepe - высокая точность, медленнее, есть настройка шага\n• crepe - точный, но медленный\n• harvest - хорош для низких голосов\n• pm - быстрый, но менее точный",
        "zh": "基频(F0)提取算法:\n\n• rmvpe - 质量和速度的最佳平衡，推荐使用\n• mangio-crepe - 高精度，较慢，可调步长\n• crepe - 精确但慢\n• harvest - 适合低音\n• pm - 快但不太精确",
        "en": "Pitch extraction algorithm (F0):\n\n• rmvpe - best balance of quality and speed, recommended\n• mangio-crepe - high accuracy, slower, adjustable step\n• crepe - accurate but slow\n• harvest - good for low voices\n• pm - fast but less accurate"
    },
    "hint_hop_length": {
        "ru": "Шаг анализа для crepe методов.\n\nМеньшее значение = более точное определение тона,\nно медленнее обработка.\n\n• 64-128 - высокая точность (медленно)\n• 128-256 - баланс (рекомендуется)\n• 256-512 - быстрая обработка",
        "zh": "crepe方法的分析步长。\n\n值越小 = 音高检测越精确，\n但处理越慢。\n\n• 64-128 - 高精度（慢）\n• 128-256 - 平衡（推荐）\n• 256-512 - 快速处理",
        "en": "Analysis step for crepe methods.\n\nLower value = more accurate pitch detection,\nbut slower processing.\n\n• 64-128 - high accuracy (slow)\n• 128-256 - balanced (recommended)\n• 256-512 - fast processing"
    },
    "hint_pitch": {
        "ru": "Сдвиг тона в полутонах.\n\n• +12 - мужской исходник → женская модель\n• -12 - женский исходник → мужская модель",
        "zh": "以半音为单位的音高偏移。\n\n• +12 - 男声原始 → 女声模型\n• -12 - 女声原始 → 男声模型",
        "en": "Pitch shift in semitones.\n\n• +12 - male source → female model\n• -12 - female source → male model"
    },
    "hint_filter_radius": {
        "ru": "Медианная фильтрация кривой тона.\nСглаживает резкие скачки высоты тона.\n\n• 0 - без фильтрации\n• 3 - умеренное сглаживание (рекомендуется)\n• 7 - сильное сглаживание\n\nБольшие значения могут сгладить вибрато.",
        "zh": "音高曲线的中值滤波。\n平滑音高的突然跳变。\n\n• 0 - 无滤波\n• 3 - 适度平滑（推荐）\n• 7 - 强平滑\n\n较大值可能会平滑掉颤音。",
        "en": "Median filtering of pitch curve.\nSmooths sudden pitch jumps.\n\n• 0 - no filtering\n• 3 - moderate smoothing (recommended)\n• 7 - strong smoothing\n\nHigher values may smooth out vibrato."
    },
    "hint_index_rate": {
        "ru": "Влияние индекса голоса на тембр.\n\n• 0.0 - индекс не используется\n• 0.5 - умеренное влияние\n• 0.9-1.0 - максимальное сходство с моделью\n\nВысокие значения лучше передают тембр,\nно могут добавить артефакты.",
        "zh": "语音索引对音色的影响。\n\n• 0.0 - 不使用索引\n• 0.5 - 适度影响\n• 0.9-1.0 - 与模型最大相似度\n\n高值更好地传达音色，\n但可能产生伪影。",
        "en": "Voice index influence on timbre.\n\n• 0.0 - index not used\n• 0.5 - moderate influence\n• 0.9-1.0 - maximum similarity to model\n\nHigher values better convey timbre,\nbut may add artifacts."
    },
    "hint_rms_mix_rate": {
        "ru": "Микширование громкости исходника и результата.\n\n• 0.0 - громкость полностью от модели\n• 0.25 - небольшой вклад исходника (рекомендуется)\n• 1.0 - громкость полностью от исходника\n\nПомогает сохранить динамику оригинала.",
        "zh": "原始和结果音量的混合。\n\n• 0.0 - 完全来自模型的音量\n• 0.25 - 原始略有贡献（推荐）\n• 1.0 - 完全来自原始的音量\n\n有助于保持原始的动态。",
        "en": "Volume mixing of source and result.\n\n• 0.0 - volume entirely from model\n• 0.25 - slight source contribution (recommended)\n• 1.0 - volume entirely from source\n\nHelps preserve original dynamics."
    },
    "hint_protect": {
        "ru": "Защита согласных звуков от искажений.\n\n• 0.0 - без защиты (максимальное преобразование)\n• 0.33 - умеренная защита (рекомендуется)\n• 0.5 - сильная защита\n\nВысокие значения сохраняют чёткость согласных,\nно голос может быть менее похож на модель.",
        "zh": "保护辅音免受失真。\n\n• 0.0 - 无保护（最大转换）\n• 0.33 - 适度保护（推荐）\n• 0.5 - 强保护\n\n高值保持辅音清晰，\n但声音可能不太像模型。",
        "en": "Consonant protection from distortion.\n\n• 0.0 - no protection (maximum conversion)\n• 0.33 - moderate protection (recommended)\n• 0.5 - strong protection\n\nHigher values preserve consonant clarity,\nbut voice may be less similar to model."
    },
    "hint_resample_sr": {
        "ru": "Частота дискретизации выходного аудио.\n\n• 0 - без изменения (рекомендуется)\n• 44100 - стандартное CD качество\n• 48000 - стандарт для видео\n\nИспользуйте, если нужен конкретный формат.",
        "zh": "输出音频的采样率。\n\n• 0 - 不改变（推荐）\n• 44100 - 标准CD质量\n• 48000 - 视频标准\n\n如果需要特定格式则使用。",
        "en": "Output audio sample rate.\n\n• 0 - no change (recommended)\n• 44100 - standard CD quality\n• 48000 - video standard\n\nUse if specific format is needed."
    },
}


def tr(key: str) -> str:
    if key in TRANSLATIONS:
        trans = TRANSLATIONS[key]
        if CURRENT_LANG in trans:
            return trans[CURRENT_LANG]
        if 'en' in trans:
            return trans['en']
    return key


def set_language(lang: str):
    global CURRENT_LANG
    if lang in ('ru', 'en', 'zh'):
        CURRENT_LANG = lang


def get_language() -> str:
    return CURRENT_LANG