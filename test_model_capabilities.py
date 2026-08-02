from services.model_capabilities import (
    get_native_search_models,
    get_vision_models,
    rank_models_for_task,
)

print("数学：", rank_models_for_task("math")[:5])
print("代码：", rank_models_for_task("coding")[:5])
print("新闻：", rank_models_for_task(
    "news",
    prefer_chinese_models=False,
    require_native_search=True,
)[:5])
print("视觉：", rank_models_for_task("vision", require_vision=True)[:5])
print("原生搜索模型：", get_native_search_models())
print("视觉模型：", get_vision_models())
