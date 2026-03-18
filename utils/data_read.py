import json
import requests
import pandas as pd
from datetime import datetime
from dataclasses import asdict

from utils.misc import BASE_URL, SINGLE_PARAM_ENDPOINT, TIME_SERIES_ENDPOINT
from utils.misc import (
    TIME_SERIES_PAYLOAD_FIELDS,
    get_single_specs,
    get_time_series_specs,
    normalize_series_options,
)


def _to_datetime(ts):
    if isinstance(ts, int):
        return datetime.fromtimestamp(ts / 1000)
    if isinstance(ts, str):
        ts_text = ts.strip()
        if ts_text:
            return datetime.fromtimestamp(int(ts_text) / 1000)
    return None


def _build_paired_df(series_by_key, query_keys):
    """构建单 timestamp 列 + 多值列的结果表."""
    if not query_keys:
        return pd.DataFrame()

    merged_df = None
    for key in query_keys:
        rows = series_by_key.get(key, [])
        records = []
        for ts, val in rows:
            dt = _to_datetime(ts)
            if dt is not None:
                records.append({"timestamp": dt, key: val})

        key_df = pd.DataFrame(records)
        if key_df.empty:
            key_df = pd.DataFrame(columns=["timestamp", key])
        else:
            key_df = key_df.groupby("timestamp", as_index=False).last()

        if merged_df is None:
            merged_df = key_df
        else:
            merged_df = pd.merge(merged_df, key_df, on="timestamp", how="outer")

    if merged_df is None:
        return pd.DataFrame(columns=["timestamp", *query_keys])

    merged_df = merged_df.sort_values("timestamp").reset_index(drop=True)
    expected_cols = ["timestamp", *query_keys]
    return merged_df.reindex(columns=expected_cols)


def _print_series(series_by_key, query_keys):
    for key in query_keys:
        rows = series_by_key.get(key, [])
        if not rows:
            continue

        print(f"\n[{key}]")
        for ts, val in rows:
            dt = _to_datetime(ts)
            if dt is not None:
                print(f"    {dt.strftime('%Y-%m-%d %H:%M:%S')} -> {val}")


def build_single_param_payload(query_keys, *, config_path=None):
    """用外部配置文件中的 single 规格组装 querySingleParam 需要的 payload.

    参数:
        query_keys: list[str], 你想查询的条目索引列表.
        config_path: 可选, 查询规格 JSON 文件路径.

    返回:
        list[dict], 可直接传给 requests.post(..., json=payload)
    """

    if not isinstance(query_keys, (list, tuple)) or not query_keys:
        raise ValueError("query_keys 必须是非空 list/tuple, 例如 ['device_001']")

    single_specs = get_single_specs(config_path)

    payload_items = []
    missing = []
    for query_key in query_keys:
        spec = single_specs.get(query_key)
        if spec is None:
            missing.append(query_key)
            continue

        payload_items.append(asdict(spec))

    if missing:
        msg = (
            "single 配置缺失, 无法组装 payload. 请检查 query_specs.json.\n"
            f"缺失条目: {json.dumps(missing, ensure_ascii=False, indent=4)}"
        )
        raise KeyError(msg)

    return payload_items


def query_single_param(payload_items, *, query_keys=None, timeout=10, verbose=True, title=None):
    """调用 querySingleParam: 既支持单条, 也支持批量.

    参数:
        payload_items: list[dict], 请求体 (JSON 数组).
        query_keys: 可选, 与 payload_items 对齐的别名列表, 用作返回 DataFrame 列名.
        timeout: 请求超时 (秒).
        verbose: True 时打印详细字段.
        title: 打印用标题, 默认不变更.

    返回:
        pandas.DataFrame: 每个 query_key 两列 (<key>_timestamp, <key>).
    """

    if title:
        print("\n" + "=" * 60)
        print(title)
        print("=" * 60)

    if not isinstance(payload_items, list) or not payload_items:
        raise ValueError("payload 必须是非空 list (JSON 数组), 例如 [{'key': 'x', ...}]")

    if query_keys is None:
        query_keys = [str(item.get("key", f"item_{idx + 1}")) for idx, item in enumerate(payload_items)]
    if len(query_keys) != len(payload_items):
        raise ValueError("query_keys 数量必须与 payload_items 数量一致")

    url = BASE_URL + SINGLE_PARAM_ENDPOINT

    print(f"请求 URL: {url}")
    print(f"查询条目数: {len(payload_items)}")
    print(f"请求数据: {json.dumps(payload_items, ensure_ascii=False, indent=4)}")

    response = requests.post(url, json=payload_items, timeout=timeout)
    print(f"\n状态码: {response.status_code}")
    print(f"响应时间: {response.elapsed.total_seconds():.2f}s")

    response_data = response.json()
    print("\n响应结果:")
    print(json.dumps(response_data, ensure_ascii=False, indent=4))

    if response_data.get("code") != 0:
        print(f"✗ 错误信息: {response_data.get('msg')}")
        return _build_paired_df({}, query_keys)

    data_list = response_data.get("data", [])
    series_by_key = {key: [] for key in query_keys}

    for idx, item in enumerate(data_list):
        if idx >= len(query_keys):
            break
        series_by_key[query_keys[idx]].append((item.get("timestamp"), item.get("value")))

    result_df = _build_paired_df(series_by_key, query_keys)

    if verbose:
        _print_series(series_by_key, query_keys)
    else:
        print(f"\n✓ 成功返回 {len(result_df)} 行, 列: {result_df.columns.tolist()}")

    return result_df


def build_time_series_payload(query_keys, *, series_options, config_path=None):
    """组装 queryTimeSeriesParam payload: 映射字段来自 query_specs, 参数来自 series_options."""

    if not isinstance(query_keys, (list, tuple)) or not query_keys:
        raise ValueError("query_keys 必须是非空 list/tuple, 例如 ['device_001']")

    normalized_options = normalize_series_options(series_options)
    time_series_specs = get_time_series_specs(config_path)

    payload_items = []
    missing = []
    for query_key in query_keys:
        spec = time_series_specs.get(query_key)
        if spec is None:
            missing.append(query_key)
            continue

        item = asdict(spec)
        item.update(normalized_options)
        payload_items.append(item)

    if missing:
        msg = (
            "time_series 配置缺失, 无法组装 payload. 请检查 query_specs.json.\n"
            f"缺失条目: {json.dumps(missing, ensure_ascii=False, indent=4)}"
        )
        raise KeyError(msg)

    return payload_items


def query_time_series_param(payload_items, *, query_keys=None, timeout=10, verbose=True, title=None):
    """调用 queryTimeSeriesParam: 支持单条和批量时序查询.

    参数:
        payload_items: list[dict], 请求体 (JSON 数组).
        query_keys: 可选, 与 payload_items 对齐的别名列表, 用作返回 DataFrame 列名.
        timeout: 请求超时 (秒).
        verbose: True 时打印详细时序数据.
        title: 打印用标题, 默认不变更.

    返回:
        pandas.DataFrame: 每个 query_key 两列 (<key>_timestamp, <key>).
    """

    if title:
        print("\n" + "=" * 60)
        print(title)
        print("=" * 60)

    if not isinstance(payload_items, list) or not payload_items:
        raise ValueError("payload 必须是非空 list (JSON 数组), 例如 [{'key': 'x', ...}]")

    if query_keys is None:
        query_keys = [str(item.get("key", f"item_{idx + 1}")) for idx, item in enumerate(payload_items)]
    if len(query_keys) != len(payload_items):
        raise ValueError("query_keys 数量必须与 payload_items 数量一致")

    required_fields = TIME_SERIES_PAYLOAD_FIELDS

    normalized_payload = []
    for idx, item in enumerate(payload_items):
        if not isinstance(item, dict):
            raise ValueError(f"payload 第 {idx + 1} 项必须是 dict")

        missing_fields = [field for field in required_fields if field not in item]
        if missing_fields:
            raise ValueError(
                f"payload 第 {idx + 1} 项缺少字段: {json.dumps(missing_fields, ensure_ascii=False)}"
            )

        start_time = item["startTime"]
        end_time = item["endTime"]
        if not isinstance(start_time, int) or not isinstance(end_time, int):
            raise ValueError(f"payload 第 {idx + 1} 项的 startTime/endTime 必须是毫秒时间戳(int)")
        if start_time >= end_time:
            raise ValueError(f"payload 第 {idx + 1} 项时间范围错误: startTime 必须小于 endTime")

        normalized_item = dict(item)
        if hasattr(normalized_item.get("downSample"), "value"):
            normalized_item["downSample"] = normalized_item["downSample"].value
        normalized_payload.append(normalized_item)

    url = BASE_URL + TIME_SERIES_ENDPOINT

    print(f"请求 URL: {url}")
    print(f"查询条目数: {len(normalized_payload)}")
    print(f"请求数据: {json.dumps(normalized_payload, ensure_ascii=False, indent=4)}")

    response = requests.post(url, json=normalized_payload, timeout=timeout)
    print(f"\n状态码: {response.status_code}")
    print(f"响应时间: {response.elapsed.total_seconds():.2f}s")

    response_data = response.json()
    print("\n响应结果:")
    print(json.dumps(response_data, ensure_ascii=False, indent=4))

    if response_data.get("code") != 0:
        print(f"✗ 错误信息: {response_data.get('msg')}")
        return _build_paired_df({}, query_keys)

    data_list = response_data.get("data", [])
    series_by_key = {key: [] for key in query_keys}

    for idx, item in enumerate(data_list):
        if idx >= len(query_keys):
            break

        timestamps = item.get("timestamp", [])
        values = item.get("value", [])
        rows = list(zip(timestamps, values))
        series_by_key[query_keys[idx]].extend(rows)

    result_df = _build_paired_df(series_by_key, query_keys)

    if verbose:
        _print_series(series_by_key, query_keys)
    else:
        print(f"\n✓ 成功返回 {len(result_df)} 行, 列: {result_df.columns.tolist()}")

    return result_df
