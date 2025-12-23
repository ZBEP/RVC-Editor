import locale
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def get_system_language():
    try:
        # Windows
        if os.name == 'nt':
            import ctypes
            windll = ctypes.windll.kernel32
            lang_id = windll.GetUserDefaultUILanguage()
            primary = lang_id & 0x3FF
            if primary == 0x19:  # Russian
                return 'ru'
            elif primary == 0x04:  # Chinese
                return 'zh'
            else:
                return 'en'
        else:
            # Linux/Mac
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
    
    "Default": {"ru": "По умолчанию", "zh": "默认"},
    "Minimal Index": {"ru": "Мин. индекс", "zh": "最小索引"},
    "Low Index, No Protect": {"ru": "Низкий индекс, без защиты", "zh": "低索引无保护"},
    "Low Index, Min Protect": {"ru": "Низкий индекс, мин. защита", "zh": "低索引最小保护"},
    "Medium": {"ru": "Средний", "zh": "中等"},
    "High Index, No Protect": {"ru": "Высокий индекс, без защиты", "zh": "高索引无保护"},
    "High Index, Max Protect": {"ru": "Высокий индекс, макс. защита", "zh": "高索引最大保护"},
    
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
    "Files:": {"ru": "файлов:", "zh": "文件:"},
    "presets:": {"ru": "пресетов:", "zh": "预设:"},
    "total operations:": {"ru": "всего операций:", "zh": "总操作:"},
    "Operation": {"ru": "Операция", "zh": "操作"},
    "Multi-convert completed:": {"ru": "Мульти-конверт завершён:", "zh": "批量转换完成:"},
    
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
    "Ctrl+wheel=zoom  Shift+wheel=scroll  wheel(R)=version  I=marker  2xclick=bounds": {
        "ru": "Ctrl+колесо=зум  Shift+колесо=скролл  колесо(R)=версия  I=маркер  2×клик=границы",
        "zh": "Ctrl+滚轮=缩放  Shift+滚轮=滚动  滚轮(R)=版本  I=标记  双击=边界"
    },
    "Delete current version": {"ru": "Удалить текущую версию", "zh": "删除当前版本"},
    "Keep only current": {"ru": "Оставить только текущую", "zh": "仅保留当前"},
    "Delete part (restore)": {"ru": "Удалить часть (восстановить)", "zh": "删除片段（恢复）"},
    "Delete part files": {"ru": "Удалить файлы части", "zh": "删除片段文件"},
    "Flatten to single file": {"ru": "Свести в общий файл", "zh": "合并为单个文件"},
    "Version deleted": {"ru": "Версия удалена", "zh": "版本已删除"},
    "Other versions deleted": {"ru": "Другие версии удалены", "zh": "其他版本已删除"},
    "Part deleted, data restored": {"ru": "Часть удалена, данные восстановлены", "zh": "片段已删除，数据已恢复"},
    "Part files deleted": {"ru": "Файлы части удалены", "zh": "片段文件已删除"},
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
    
    "RVC Voice Converter": {"ru": "RVC Конвертер голоса", "zh": "RVC语音转换器"},
    "Log": {"ru": "Лог", "zh": "日志"},
    "Editor": {"ru": "Редактор", "zh": "编辑器"},
    "Conversion": {"ru": "Конвертация", "zh": "转换"},
    "Multi-convert": {"ru": "Мульти-конверт", "zh": "批量转换"},
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
    "Convert files from folder with different parameters": {
        "ru": "Конвертация файлов из папки с разными параметрами",
        "zh": "使用不同参数转换文件夹中的文件"
    },
    "Folders, pitch and format from 'Conversion' tab": {
        "ru": "Папки, тон и формат берутся с вкладки «Конвертация»",
        "zh": '文件夹、音高和格式取自"转换"选项卡'
    },
    "Presets (Index rate / Protect)": {"ru": "Пресеты (Влияние индекса / Защита)", "zh": "预设（索引率/保护）"},
    "Select all": {"ru": "Выбрать все", "zh": "全选"},
    "Deselect all": {"ru": "Сбросить все", "zh": "取消全选"},
    "Fixed parameters": {"ru": "Фиксированные параметры", "zh": "固定参数"},
    "Run multi-convert": {"ru": "Запустить мульти-конверт", "zh": "运行批量转换"},
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
    "RMS:": {"ru": "RMS:", "zh": "RMS:"},
    "Presets reset to default": {"ru": "Пресеты сброшены на стандартные", "zh": "预设已重置为默认"},
    "reloading model...": {"ru": "перезагрузка модели...", "zh": "重新加载模型..."},
    "Load model:": {"ru": "Загружать модель:", "zh": "加载模型:"},
    "ON": {"ru": "ВКЛ", "zh": "开"},
    "OFF": {"ru": "ВЫКЛ", "zh": "关"},
    "Input folder does not exist": {"ru": "Входная папка не существует", "zh": "输入文件夹不存在"},
    "Failed to load model": {"ru": "Не удалось загрузить модель", "zh": "无法加载模型"},
    "No files to convert": {"ru": "Нет файлов для конвертации", "zh": "没有要转换的文件"},
    "Select at least one preset": {"ru": "Выберите хотя бы один пресет", "zh": "请至少选择一个预设"},
    "Error: model not selected": {"ru": "Ошибка: модель не выбрана", "zh": "错误：未选择模型"},
    "(no index)": {"ru": "(no index)", "zh": "(no index)"},
    "(includes hop_length for crepe)": {"ru": "(включает hop_length для crepe)", "zh": "(包含crepe的hop_length)"},
    "toggle": {"ru": "переключить", "zh": "切换"},
    "if model empty - unchanged": {"ru": "если модель пустая — не меняется", "zh": "如果模型为空则不变"},
    "Load pitch:": {"ru": "Загружать тон:", "zh": "加载音高:"},
    "Load F0 method:": {"ru": "Загружать F0 метод:", "zh": "加载F0方法:"},
    
    "Preset save error:": {"ru": "Ошибка сохранения пресета:", "zh": "预设保存错误:"},
    "Missing:": {"ru": "Отсутствуют:", "zh": "缺少:"},
    "Press Enter...": {"ru": "Нажмите Enter...", "zh": "按Enter键..."},
    "Starting...": {"ru": "Запуск...", "zh": "启动中..."},
    "mangio-crepe folder not found:": {"ru": "Папка mangio-crepe не найдена:", "zh": "未找到mangio-crepe文件夹:"},
    "mangio-crepe files updated:": {"ru": "Обновлены файлы mangio-crepe:", "zh": "mangio-crepe文件已更新:"},
}


def tr(key: str) -> str:
    if CURRENT_LANG == 'en':
        return key
    
    if key in TRANSLATIONS:
        trans = TRANSLATIONS[key]
        if CURRENT_LANG in trans:
            return trans[CURRENT_LANG]
    
    return key


def set_language(lang: str):
    global CURRENT_LANG
    if lang in ('ru', 'en', 'zh'):
        CURRENT_LANG = lang


def get_language() -> str:
    return CURRENT_LANG