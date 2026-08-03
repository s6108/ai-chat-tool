from dataclasses import dataclass


@dataclass(frozen=True)
class SearchCapability:

    model_name: str

    search_type: str
    # mango / native

    provider: str

    supports_web: bool

    supports_x_search: bool



SEARCH_CAPABILITIES = {

    "DeepSeek": SearchCapability(
        model_name="DeepSeek",
        search_type="mango",
        provider="tavily",
        supports_web=True,
        supports_x_search=False,
    ),


    "Qwen": SearchCapability(
        model_name="Qwen",
        search_type="mango",
        provider="tavily",
        supports_web=True,
        supports_x_search=False,
    ),


    "Kimi": SearchCapability(
        model_name="Kimi",
        search_type="mango",
        provider="tavily",
        supports_web=True,
        supports_x_search=False,
    ),


    "Grok": SearchCapability(
        model_name="Grok",
        search_type="native",
        provider="xai",
        supports_web=True,
        supports_x_search=True,
    ),


    "Gemini": SearchCapability(
        model_name="Gemini",
        search_type="native",
        provider="google",
        supports_web=True,
        supports_x_search=False,
    ),


    "Claude": SearchCapability(
        model_name="Claude",
        search_type="native",
        provider="anthropic",
        supports_web=True,
        supports_x_search=False,
    ),

}

def get_search_capability(model_name: str) -> SearchCapability:
    """
    根据模型名称获取搜索能力配置
    """
    return SEARCH_CAPABILITIES.get(
        model_name
    )