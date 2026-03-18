import json
import requests

from utils.misc import BASE_URL, ATTR_LIST_ENDPOINT, DATABASE_DIR, DEFAULT_QUERY_SPECS_PATH


def fetch_device_attr_list(device_id, token=None):
    """
    从 /admin-api/dt/seb-device-base/attr_list 接口获取设备属性列表数据
    """
    # 构造接口 URL
    url = BASE_URL + ATTR_LIST_ENDPOINT

    # 查询参数
    params = {
        "deviceId": device_id
    }

    # 请求头, 根据实际情况增减
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/javascript, */*; q=0.01"
    }

    # 如果需要鉴权（如 JWT / Bearer Token）
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # 发送 GET 请求
    resp = requests.get(url, params=params, headers=headers, timeout=10)

    # 简单的异常处理
    resp.raise_for_status()  # 如果 HTTP 状态码不是 200, 会抛异常

    # 一般后端会返回 JSON
    try:
        data = resp.json()
    except ValueError:
        print("返回内容不是 JSON：")
        print(resp.text)
        return None

    return data


def build_time_series_mapping(attr_list_result):
    """
    将 attr_list 返回结果转换为 query_specs.json 中 time_series 的映射。
    键名格式: deviceNameZh-attr
    字段映射: id->key, deviceId->deviceID, deviceName->deviceType, attr->attr
    """
    mappings = {}
    if not isinstance(attr_list_result, dict):
        return mappings

    data_list = attr_list_result.get("data", [])
    if not isinstance(data_list, list):
        return mappings

    for item in data_list:
        if not isinstance(item, dict):
            continue

        device_name_zh = item.get("deviceNameZh")
        attr = item.get("attr")
        key = item.get("id")
        device_id = item.get("deviceId")
        device_name = item.get("deviceName")

        # 核心字段不完整时跳过，避免写入无效映射。
        if not device_name_zh or not attr or not key or not device_id or not device_name:
            continue

        mapping_name = f"{device_name_zh}-{attr}"
        mappings[mapping_name] = {
            "key": str(key),
            "deviceID": str(device_id),
            "deviceType": str(device_name),
            "attr": str(attr)
        }

    return mappings


def save_time_series_mappings(mappings, query_specs_path=DEFAULT_QUERY_SPECS_PATH):
    """
    将新的 time_series 映射合并写入 query_specs.json。
    仅更新 time_series，保留 single 和其他已有结构。
    """
    if not mappings:
        return 0

    query_specs = {}
    if query_specs_path.exists():
        with open(query_specs_path, "r", encoding="utf-8") as f:
            query_specs = json.load(f)

    if not isinstance(query_specs, dict):
        query_specs = {}

    time_series = query_specs.get("time_series", {})
    if not isinstance(time_series, dict):
        time_series = {}

    time_series.update(mappings)
    query_specs["time_series"] = time_series

    with open(query_specs_path, "w", encoding="utf-8") as f:
        json.dump(query_specs, f, ensure_ascii=False, indent=4)

    return len(mappings)


if __name__ == "__main__":
    # 如果需要先登录拿 token, 可以在这里自己写登录逻辑, 然后把 token 传进去
    # 下面先假设不需要 token, 或者你手动填入一个：
    TOKEN = None
    # TOKEN = "你的token字符串"

    # 让用户输入设备 ID
    device_id = ["401o40mrpek4400", "101lvr0oamo4400", "101mi71ei0o4400"]

    all_time_series_mappings = {}

    # 调用函数获取数据
    for id in device_id:
        try:
            result = fetch_device_attr_list(id, token=TOKEN)
            print("接口返回数据：")
            print(result)

            save_path = DATABASE_DIR / f"{id}_attr_list.json"
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
            print(f"已保存到 {save_path}")

            all_time_series_mappings.update(build_time_series_mapping(result))
        except requests.HTTPError as e:
            print("HTTP 请求失败：", e)
        except requests.RequestException as e:
            print("请求出现错误：", e)

    saved_count = save_time_series_mappings(all_time_series_mappings)
    print(f"已更新 {saved_count} 条 time_series 映射到 {DEFAULT_QUERY_SPECS_PATH}")
