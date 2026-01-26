# http_client.py
import requests
from typing import Optional

from data.plugins.astrbot_plugin_wot.src.config.request import BaseConfig

# 导入基础配置类

def send_get_request(
        config: BaseConfig # 接收继承BaseConfig的配置类实例
) -> Optional[requests.Response]:
    """通用GET请求方法，统一处理配置和异常
    Args:
        config: 配置类实例（包含timeout、默认headers等）
    Returns:
        requests.Response: 响应对象；请求失败返回None
    """
    final_url = getattr(config, "base_url")
    final_params = getattr(config, "params", None)
    # 优先级：自定义headers > 配置类headers
    final_headers = getattr(config, "headers", {})
    # 超时时间取配置类的DEFAULT_TIMEOUT
    final_timeout = getattr(config, "DEFAULT_TIMEOUT", 10)

    try:
        response = requests.get(
            url=final_url,
            params=final_params,
            headers=final_headers,
            timeout=final_timeout,
            verify=True  # 可选：关闭SSL验证（如需）verify=False
        )
        # 统一校验响应状态码
        response.raise_for_status()  # 非200状态码抛出异常
        return response
    except requests.exceptions.Timeout:
        print(f"请求超时：URL={final_url}，超时时间={final_timeout}s")
        return None
    except requests.exceptions.ConnectionError:
        print(f"连接失败：URL={final_url}")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"HTTP错误：URL={final_url}，状态码={e.response.status_code}")
        return None
    except Exception as e:
        print(f"请求异常：URL={final_url}，异常信息={str(e)}")
        return None