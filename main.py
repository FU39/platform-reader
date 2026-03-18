from collections import defaultdict
from datetime import datetime
import json
import requests

from utils.misc import BASE_URL, CONFIG_DIR, RESULT_DIR, check_connectivity
from utils.data_read import (
    build_single_param_payload,
    build_time_series_payload,
    query_single_param,
    query_time_series_param,
)


def _load_main_input():
    config_path = CONFIG_DIR / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"未找到主函数输入文件: {config_path}")

    with config_path.open("r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)

    if not isinstance(data, dict):
        raise ValueError("config.json 根节点必须是对象 (dict)")

    query_keys = data.get("query_keys")
    if not isinstance(query_keys, list) or not query_keys:
        raise ValueError("config.json 中 query_keys 必须是非空数组")

    grouped_names = defaultdict(list)
    for idx, item in enumerate(query_keys, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"query_keys 第 {idx} 项必须是对象, 例如 {{'name': 'x', 'type': 'time_series'}}")

        name = str(item.get("name", "")).strip()
        query_type = str(item.get("type", "")).strip().lower()
        if not name:
            raise ValueError(f"query_keys 第 {idx} 项缺少 name")
        if query_type not in {"single", "time_series"}:
            raise ValueError(f"query_keys 第 {idx} 项 type 非法: {query_type}, 仅支持 single/time_series")

        grouped_names[query_type].append(name)

    series_options = data.get("series_options")
    if grouped_names.get("time_series") and not isinstance(series_options, dict):
        raise ValueError("当 query_keys 包含 time_series 时, config.json 必须提供对象类型的 series_options")

    return grouped_names, (series_options or {})


if __name__ == "__main__":
    current_time = datetime.now().strftime("%Y%m%d-%H%M%S")
    print(f"服务器地址: {BASE_URL}")
    print(f"读取时间: {current_time}")

    grouped_names, series_options = _load_main_input()

    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    if not check_connectivity():
        raise ConnectionError("\n无法连接到服务器, 请检查网络和服务器状态")

    try:
        time_series_keys = grouped_names.get("time_series", [])
        if time_series_keys:
            series_payload = build_time_series_payload(time_series_keys, series_options=series_options)
            series_df = query_time_series_param(series_payload, query_keys=time_series_keys, timeout=10, verbose=True)
            series_result_path = RESULT_DIR / f"series_result_{current_time}.csv"
            series_df.to_csv(series_result_path, index=False)
            print(f"\n✓ 已保存时序结果到: {series_result_path}")

        single_keys = grouped_names.get("single", [])
        if single_keys:
            single_payload = build_single_param_payload(single_keys)
            single_df = query_single_param(single_payload, query_keys=single_keys, timeout=10, verbose=True)
            single_result_path = RESULT_DIR / f"single_result_{current_time}.csv"
            single_df.to_csv(single_result_path, index=False)
            print(f"\n✓ 已保存单点结果到: {single_result_path}")

    except requests.exceptions.RequestException as e:
        print(f"✗ 请求异常: {str(e)}")
    except json.JSONDecodeError as e:
        print(f"✗ JSON解析异常: {str(e)}")

    print('\n' + '=' * 60 + "\n读取结束\n" + '=' * 60)
