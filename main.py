from datetime import datetime
import json
import requests

from utils import BASE_URL, CONFIG_DIR, RESULT_DIR, check_connectivity
from data_read import build_time_series_payload, query_time_series_param


def _load_main_input():
    data_name_path = CONFIG_DIR / "data_name.json"
    if not data_name_path.exists():
        raise FileNotFoundError(f"未找到主函数输入文件: {data_name_path}")

    with data_name_path.open("r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)

    if not isinstance(data, dict):
        raise ValueError("data_name.json 根节点必须是对象(dict)")

    query_keys = data.get("query_keys")
    if not isinstance(query_keys, list) or not query_keys:
        raise ValueError("data_name.json 中 query_keys 必须是非空数组")

    query_keys = [str(item).strip() for item in query_keys if str(item).strip()]
    if not query_keys:
        raise ValueError("data_name.json 中 query_keys 不能为空")

    return query_keys


if __name__ == "__main__":
    current_time = datetime.now().strftime("%Y%m%d-%H%M%S")
    print(f"服务器地址: {BASE_URL}")
    print(f"读取时间: {current_time}")

    query_keys = _load_main_input()

    result_name = f"series_result_{current_time}.csv"
    result_path = RESULT_DIR / result_name

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    if result_path.parent:
        result_path.parent.mkdir(parents=True, exist_ok=True)

    if not check_connectivity():
        raise ConnectionError("\n无法连接到服务器, 请检查网络和服务器状态")

    try:
        payload = build_time_series_payload(query_keys)
        result_df = query_time_series_param(payload, query_keys=query_keys, timeout=10, verbose=True)
        result_df.to_csv(result_path, index=False)
        print(f"\n✓ 已保存结果到: {result_path}")

    except requests.exceptions.RequestException as e:
        print(f"✗ 请求异常: {str(e)}")
    except json.JSONDecodeError as e:
        print(f"✗ JSON解析异常: {str(e)}")

    print('\n' + '=' * 60 + "\n读取结束\n" + '=' * 60)
