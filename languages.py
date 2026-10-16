"""Language choices shared by routing and the compact native picker."""

# code, menu title, badge label, prompt name
LANGUAGES = (
    ("zh-CN", "简体中文", "中文", "Simplified Chinese"),
    ("zh-TW", "繁体中文", "繁中", "Traditional Chinese"),
    ("en", "英语", "英语", "English"),
    ("ja", "日语", "日语", "Japanese"),
    ("ko", "韩语", "韩语", "Korean"),
    ("fr", "法语", "法语", "French"),
    ("de", "德语", "德语", "German"),
    ("es", "西班牙语", "西班牙语", "Spanish"),
    ("it", "意大利语", "意大利语", "Italian"),
    ("pt", "葡萄牙语", "葡萄牙语", "Portuguese"),
    ("ru", "俄语", "俄语", "Russian"),
    ("ar", "阿拉伯语", "阿拉伯语", "Arabic"),
    ("hi", "印地语", "印地语", "Hindi"),
    ("th", "泰语", "泰语", "Thai"),
    ("vi", "越南语", "越南语", "Vietnamese"),
    ("id", "印度尼西亚语", "印尼语", "Indonesian"),
    ("tr", "土耳其语", "土耳其语", "Turkish"),
    ("uk", "乌克兰语", "乌克兰语", "Ukrainian"),
    ("nl", "荷兰语", "荷兰语", "Dutch"),
    ("pl", "波兰语", "波兰语", "Polish"),
    ("sv", "瑞典语", "瑞典语", "Swedish"),
    ("da", "丹麦语", "丹麦语", "Danish"),
    ("fi", "芬兰语", "芬兰语", "Finnish"),
    ("nb", "挪威语", "挪威语", "Norwegian"),
    ("cs", "捷克语", "捷克语", "Czech"),
    ("ro", "罗马尼亚语", "罗马尼亚语", "Romanian"),
    ("hu", "匈牙利语", "匈牙利语", "Hungarian"),
    ("he", "希伯来语", "希伯来语", "Hebrew"),
    ("el", "希腊语", "希腊语", "Greek"),
)
CHOICES = {code: (title, badge, prompt) for code, title, badge, prompt in LANGUAGES}


def badge_label(code):
    return CHOICES[code][1] if code in CHOICES else code.split("-")[0].upper()


def prompt_name(code):
    return CHOICES[code][2] if code in CHOICES else code
