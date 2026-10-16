# 语言测试

测试环境：macOS 26.4.1、Apple Silicon；2026-10-16。

使用同一句话的五种语言版本，检查中英双向，以及日语、法语、韩语分别与中文、英文的双向翻译。共 14 个方向，每种引擎各调用一次。

中文示例为“今天的天气很好。”；英文为“The weather is pleasant today.”；日文为“今日は天気がいいです。”；法文为“Il fait beau aujourd’hui.”；韩文为“오늘은 날씨가 좋아요.”。

这些检查直接指定源语言和目标语言。应用默认将中文译为英文，将其他语言译为简体中文。也可在浮窗中分别调整原文和译文语言。

| 翻译源 | 返回预期目标语言 | 样例中发现的问题 |
| --- | --- | --- |
| 系统原生 | 14/14 | 无 |
| 轻量云端 | 14/14 | 无 |
| 本机 qwen2.5:7b | 12/14 | 中文译日语残留原文，中文译韩语夹杂中文和解释 |

结果按译文是否为空和目标语言识别结果进行检查，下面保留完整输出供人工查看。专业文本和长段落还需要结合实际内容判断译文质量。

## 系统原生

| 方向 | 译文 | 检查结果 |
| --- | --- | --- |
| en → zh-CN | 今天天气很好。 | 通过 |
| zh-CN → en | The weather is very nice today. | 通过 |
| ja → zh-CN | 今天天气很好。 | 通过 |
| zh-CN → ja | 本日の天気は良好です。 | 通过 |
| ja → en | The weather is nice today. | 通过 |
| en → ja | 本日は天気が快適です。 | 通过 |
| fr → zh-CN | 今天天气很好。 | 通过 |
| zh-CN → fr | Il fait très beau aujourd'hui. | 通过 |
| fr → en | The weather is nice today. | 通过 |
| en → fr | Le temps est agréable aujourd'hui. | 通过 |
| ko → zh-CN | 今天天气很好。 | 通过 |
| zh-CN → ko | 오늘 날씨가 좋습니다. | 通过 |
| ko → en | The weather is nice today. | 通过 |
| en → ko | 오늘 날씨가 쾌적합니다. | 通过 |

## 轻量云端

| 方向 | 译文 | 检查结果 |
| --- | --- | --- |
| en → zh-CN | 今天天气宜人。 | 通过 |
| zh-CN → en | The weather is very good today. | 通过 |
| ja → zh-CN | 今天天气很好。 | 通过 |
| zh-CN → ja | 今日はとても良い天気です。 | 通过 |
| ja → en | The weather is nice today. | 通过 |
| en → ja | 今日は気持ちの良い天気です。 | 通过 |
| fr → zh-CN | 今天天气很好。 | 通过 |
| zh-CN → fr | Il fait très beau aujourd'hui. | 通过 |
| fr → en | The weather today is good. | 通过 |
| en → fr | Le temps est agréable aujourd'hui. | 通过 |
| ko → zh-CN | 今天天气很好。 | 通过 |
| zh-CN → ko | 오늘은 날씨가 아주 좋습니다. | 通过 |
| ko → en | The weather is nice today. | 通过 |
| en → ko | 오늘은 날씨가 좋습니다. | 通过 |

## 本机 qwen2.5:7b

| 方向 | 译文 | 检查结果 |
| --- | --- | --- |
| en → zh-CN | 今天的天气很宜人。 | 通过 |
| zh-CN → en | The weather today is very good. | 通过 |
| ja → zh-CN | 今天天气很好。 | 通过 |
| zh-CN → ja | 今天的天气很好。 | 需复核 |
| ja → en | Today the weather is nice. | 通过 |
| en → ja | 今日は天気が良いです。 | 通过 |
| fr → zh-CN | 今天天气不错。 | 通过 |
| zh-CN → fr | Le temps aujourd'hui est très beau. | 通过 |
| fr → en | It is nice weather today. | 通过 |
| en → fr | Le temps est agréable aujourd'hui. | 通过 |
| ko → zh-CN | 今天天气很好。 | 通过 |
| zh-CN → ko | 오늘의 날씨가非常好。 (This is a direct translation, but typically in Korean, we would say "오늘의 날씨가 좋습니다.") | 需复核 |
| ko → en | Today is a nice day. | 通过 |
| en → ko | 오늘 날씨가 좋습니다. | 通过 |
