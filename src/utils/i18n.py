"""Lightweight internationalization module for IconifyGo.

Uses a Python dict for translations instead of Qt's QTranslator toolchain.
English strings serve as keys; Chinese translations are looked up via tr().
"""

import locale
import os
import json

_lang = "en"
_config_path = os.path.expanduser("~/.config/IconifyGo/settings.json")

_translations = {
    "zh": {
        # --- Tool tooltips ---
        "Pointer Tool": "指针工具",
        "Brush Tool": "画笔工具",
        "Eraser Tool": "橡皮擦工具",
        "Brush Shape": "画笔形状",
        "Brush Size": "画笔大小",
        "Auto Remove Background": "自动抠图",
        "Erase Watermark": "擦除水印",
        "Add Text or Emoji": "添加文字或表情",
        "Convert to Sketch Style": "转换为素描风格",
        "Reset to Original Image": "恢复原图",
        "Background Color": "背景颜色",
        "Adjust Subject Scale": "调整主体缩放",
        "Export Result": "导出结果",
        "Language": "语言",

        # --- Inpaint menu ---
        "Watermark Draw and Remove": "水印绘制与去除",
        "Watermark Brush": "水印画笔",
        "Watermark Eraser": "水印橡皮擦",
        "Traditional Algorithm (Progressive Inpainting)": "传统算法去除（渐进修复）",
        "Light": "轻度",
        "Medium": "中度",
        "Strong": "强度",
        "AI Intelligent Watermark Removal (first use requires model download)": "AI 智能去水印（首次需下载模型）",
        "AI Intelligent Erase": "AI 智能擦除",

        # --- Model menu ---
        "Select Matting Model": "选择抠图模型",

        # --- Export menu ---
        "Export Format": "导出格式",
        "Original Size PNG (.png)": "原始尺寸 PNG (.png)",
        "PNG 1024 (no alpha)": "PNG 1024（无透明通道）",
        "macOS Icon (.icns)": "macOS 图标 (.icns)",
        "macOS Iconset (folder)": "macOS Iconset（文件夹）",
        "Windows Icon (.ico)": "Windows 图标 (.ico)",
        "Android Icon Set": "Android 图标集",
        "PNG Image Set (all)": "PNG 图片集（全平台）",

        # --- Shape menu ---
        "Circle": "圆形",
        "Square": "方形",
        "Ellipse": "椭圆",

        # --- Scale menu ---
        "Subject Scale": "主体缩放",

        # --- Sketch menu ---
        "Sketch Style Conversion": "素描风格转换",
        "Fine Detail": "精细",
        "Classic Sketch": "经典",
        "Bold Sketch": "浓重",
        "Restore Original": "恢复原图",

        # --- Text settings ---
        "Type text or emoji": "键入文本或表情符号",
        "Size": "大小",
        "Cancel": "取消",
        "Confirm": "确认",
        "Enter here...": "在此输入...",
        "Regular": "常规",
        "Bold": "粗体",
        "Italic": "斜体",
        "Select Color": "选择颜色",
        "Select Background Color": "选择背景颜色",

        # --- Canvas ---
        "Click or Drag Image Here": "点击或拖拽图片到此处",

        # --- Preview gallery ---
        "No Background": "无背景",
        "macOS Classic": "macOS 经典",
        "iOS App Icon": "iOS 应用图标",
        "Android Icon": "Android 图标",
        "Folder (Center)": "文件夹（居中）",
        "Folder (Cover)": "文件夹（覆盖）",
        "Document (Center)": "文档（居中）",
        "Document (Cover)": "文档（覆盖）",

        # --- Main window: dialogs ---
        "Warning": "警告",
        "Error": "错误",
        "Success": "成功",
        "Notification": "通知",
        "No original image to restore.": "没有可恢复的原图。",
        "Please load an image first.": "请先加载图片。",
        "Please load an image or add text first.": "请先加载图片或添加文字。",
        "Watermark removal failed": "水印擦除失败",
        "Could not load image": "无法加载图片",
        "Background removal failed": "背景去除失败",
        "Failed to export": "导出失败",
        "Failed to export ICNS icon": "导出 ICNS 图标失败",
        "Failed to export ICO icon": "导出 ICO 图标失败",
        "Failed to export PNG set": "导出 PNG 图片集失败",
        "Exported successfully": "导出成功",
        "Exported PNG set": "已导出 PNG 图片集",
        "Download AI Model": "下载 AI 模型",
        "First use of AI smart erasure requires downloading a model (~200 MB).\nThe download will be cached locally, no repeat download needed later.\n\nStart download?": "首次使用 AI 智能擦除需要下载模型（约 200 MB）。\n下载将缓存到本地，后续无需重复下载。\n\n是否开始下载？",

        # --- Main window: status messages ---
        "Reset to original image": "已恢复原图",
        "Removing watermark...": "正在擦除水印...",
        "Download cancelled, you can try again": "下载已取消，可重新尝试",
        "Watermark removed successfully": "水印擦除成功",
        "Removing background...": "正在去除背景...",
        "Background removed successfully": "背景去除成功",
        "Restored original image": "已恢复原图",
        "Already at original image": "已是原图",
        "Converted to sketch style": "已转换为素描风格",
        "Downloading model": "下载模型",

        # --- File dialogs ---
        "Open Image": "打开图片",
        "Save PNG Image": "保存 PNG 图片",
        "Save ICNS Icon": "保存 ICNS 图标",
        "Save ICO Icon": "保存 ICO 图标",
        "Select Output Directory": "选择输出目录",

        # --- Inpaint worker progress ---
        "Downloading AI model...": "正在下载 AI 模型...",
        "Loading AI model into memory...": "正在加载 AI 模型...",
        "AI watermark removal in progress...": "AI 水印擦除进行中...",

        # --- Language menu ---
        "Simplified Chinese": "简体中文",
        "English": "English",
        "Language changed. The app will restart.": "语言已切换，应用将重新启动。",
    }
}


def detect_language():
    """Detect system language. Returns 'zh' or 'en'."""
    try:
        sys_lang = locale.getlocale()[0] or os.environ.get('LANG', '')
        if sys_lang.startswith('zh'):
            return "zh"
    except Exception:
        pass
    return "en"


def load_language():
    """Load language preference from config file, or auto-detect on first run."""
    global _lang
    try:
        if os.path.exists(_config_path):
            with open(_config_path, 'r') as f:
                settings = json.load(f)
                _lang = settings.get("language", detect_language())
        else:
            _lang = detect_language()
    except Exception:
        _lang = detect_language()


def save_language(lang):
    """Save language preference to config file."""
    global _lang
    _lang = lang
    try:
        os.makedirs(os.path.dirname(_config_path), exist_ok=True)
        settings = {}
        if os.path.exists(_config_path):
            with open(_config_path, 'r') as f:
                settings = json.load(f)
        settings["language"] = lang
        with open(_config_path, 'w') as f:
            json.dump(settings, f)
    except Exception:
        pass


def get_language():
    return _lang


def tr(key):
    """Translate a string key. Returns the English string (key) if no translation found."""
    if _lang == "zh":
        return _translations["zh"].get(key, key)
    return key


# Auto-load language preference on import
load_language()
