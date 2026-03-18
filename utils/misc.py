import json
from dataclasses import dataclass, fields
from enum import Enum
from functools import lru_cache
from pathlib import Path
from datetime import datetime

import requests

# 基础URL
BASE_URL = "http://117.78.40.159:50030"

# 接口路径
SINGLE_PARAM_ENDPOINT = "/admin-api/de/querySingleParam"
TIME_SERIES_ENDPOINT = "/admin-api/de/queryTimeSeriesParam"

# 默认查询规格文件路径
PROJECT_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_DIR / "config"
RESULT_DIR = PROJECT_DIR / "result"
DEFAULT_QUERY_SPECS_PATH = CONFIG_DIR / "query_specs.json"


class DownSampleMethod(Enum):
    LAST = 'LAST'  # 采样点 (实时数据-一段时间内的最新一笔)
    AVG = 'AVG'  # 平均值
    MIN = 'MIN'  # 最大值
    MAX = 'MAX'  # 最小值
    LAST_SUB_FIRST = 'LAST_SUB_FIRST'  # 最后-最先
    MAX_SUB_MIN = 'MAX_SUB_MIN'  # 最大值-最小值
    SUM = 'SUM'  # 总和
    EXTREME = 'EXTREME'  # 最大绝对值
    VARIANCE = 'VARIANCE'  # 方差
    FIRST = 'FIRST'  # 采样点 (实时数据-一段时间第一笔数据)


@dataclass(frozen=True)
class QuerySingleSpec:
    key: str
    deviceID: str
    deviceType: str
    attr: str


@dataclass(frozen=True)
class QueryTimeSeriesSpec:
    key: str
    deviceID: str
    deviceType: str
    attr: str


TIME_SERIES_OPTION_FIELDS = (
    "startTime",
    "endTime",
    "downSample",
    "interval",
    "intervalPeriod",
    "groupBy",
    "removeOutliers",
)

# queryTimeSeriesParam 的完整 payload 字段 = 映射字段 + 运行时选项字段
TIME_SERIES_PAYLOAD_FIELDS = tuple(field.name for field in fields(QueryTimeSeriesSpec)) + TIME_SERIES_OPTION_FIELDS


def _parse_downsample(value, *, alias):
    if isinstance(value, DownSampleMethod):
        return value

    if isinstance(value, str):
        normalized = value.strip().upper()
        try:
            return DownSampleMethod(normalized)
        except ValueError as err:
            valid_values = [item.value for item in DownSampleMethod]
            raise ValueError(
                f"time_series.{alias}.downSample 不合法: {value}, 允许值: {valid_values}"
            ) from err

    raise ValueError(f"time_series.{alias}.downSample 必须是字符串或 DownSampleMethod")


def _parse_bool(value, *, field_name):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    if isinstance(value, int) and value in (0, 1):
        return bool(value)

    raise ValueError(f"{field_name} 必须是布尔值, 或可转换为布尔值的字符串/0/1")


def _parse_single_specs(raw_specs):
    if not isinstance(raw_specs, dict):
        raise ValueError("配置文件中的 single 必须是对象(dict)")

    specs = {}
    for alias, item in raw_specs.items():
        if not isinstance(item, dict):
            raise ValueError(f"single.{alias} 必须是对象(dict)")

        required = ["key", "deviceID", "deviceType", "attr"]
        missing = [field for field in required if field not in item]
        if missing:
            raise ValueError(f"single.{alias} 缺少字段: {missing}")

        specs[alias] = QuerySingleSpec(
            key=str(item["key"]),
            deviceID=str(item["deviceID"]),
            deviceType=str(item["deviceType"]),
            attr=str(item["attr"]),
        )

    return specs


def normalize_series_options(raw_options):
    """归一化 data_name.json 中的 series_options."""
    if not isinstance(raw_options, dict):
        raise ValueError("data_name.json 中 series_options 必须是对象 (dict)")

    required = ["startTime", "endTime"]
    missing = [field for field in required if field not in raw_options]
    if missing:
        raise ValueError(f"series_options 缺少字段: {missing}")

    start_time = int(raw_options["startTime"])
    end_time = int(raw_options["endTime"])
    if start_time >= end_time:
        raise ValueError("series_options 时间范围错误: startTime 必须小于 endTime")

    downsample = _parse_downsample(raw_options.get("downSample", "AVG"), alias="series_options")

    return {
        "startTime": start_time,
        "endTime": end_time,
        "downSample": downsample.value,
        "interval": str(raw_options.get("interval", "3600")),
        "intervalPeriod": str(raw_options.get("intervalPeriod", "s")),
        "groupBy": _parse_bool(raw_options.get("groupBy", True), field_name="series_options.groupBy"),
        "removeOutliers": _parse_bool(
            raw_options.get("removeOutliers", False),
            field_name="series_options.removeOutliers",
        ),
    }


def _parse_time_series_specs(raw_specs):
    if not isinstance(raw_specs, dict):
        raise ValueError("配置文件中的 time_series 必须是对象(dict)")

    specs = {}
    for alias, item in raw_specs.items():
        if not isinstance(item, dict):
            raise ValueError(f"time_series.{alias} 必须是对象(dict)")

        required = ["key", "deviceID", "deviceType", "attr"]
        missing = [field for field in required if field not in item]
        if missing:
            raise ValueError(f"time_series.{alias} 缺少字段: {missing}")

        specs[alias] = QueryTimeSeriesSpec(
            key=str(item["key"]),
            deviceID=str(item["deviceID"]),
            deviceType=str(item["deviceType"]),
            attr=str(item["attr"]),
        )

    return specs


@lru_cache(maxsize=8)
def load_query_specs(config_path=None):
    """从外部 JSON 文件加载 single/time_series 查询规格.

    参数:
        config_path: 可选, 自定义配置文件路径; 不传时使用 DEFAULT_QUERY_SPECS_PATH.

    返回:
        tuple[dict[str, QuerySingleSpec], dict[str, QueryTimeSeriesSpec]]
    """

    path = Path(config_path) if config_path else DEFAULT_QUERY_SPECS_PATH
    if not path.exists():
        raise FileNotFoundError(f"查询规格文件不存在: {path}")

    with path.open("r", encoding="utf-8") as file_obj:
        raw = json.load(file_obj)

    if not isinstance(raw, dict):
        raise ValueError("查询规格文件根节点必须是对象(dict)")

    single_specs = _parse_single_specs(raw.get("single", {}))
    time_series_specs = _parse_time_series_specs(raw.get("time_series", {}))
    return single_specs, time_series_specs


def get_single_specs(config_path=None):
    return load_query_specs(config_path)[0]


def get_time_series_specs(config_path=None):
    return load_query_specs(config_path)[1]


def clear_query_specs_cache():
    """重新读取配置前可调用, 清除 load_query_specs 的缓存."""
    load_query_specs.cache_clear()


def transfer_timestamp(timestamp_text, *, fmt="%Y-%m-%d %H:%M:%S"):
    """将格式化时间字符串转换为毫秒时间戳."""
    if not isinstance(timestamp_text, str) or not timestamp_text.strip():
        raise ValueError(f"时间不能为空, 请输入格式为 {fmt} 的时间")

    text = timestamp_text.strip()
    try:
        dt = datetime.strptime(text, fmt)
    except ValueError as err:
        raise ValueError(f"时间格式错误: {text}, 期望格式: {fmt}") from err

    return int(dt.timestamp() * 1000)


def check_connectivity():
    """检查服务器连接状态"""
    print("\n" + "="*60)
    print("检查服务器连接状态")
    print("="*60)

    try:
        print(f"正在连接到: {BASE_URL}")
        response = requests.head(BASE_URL, timeout=5)
        print(f"✓ 服务器响应状态码: {response.status_code}")
        print("✓ 服务器连接正常")
        return True
    except requests.exceptions.ConnectTimeout:
        print("✗ 连接超时, 请检查服务器地址和网络连接")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"✗ 连接失败: {str(e)}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"✗ 请求异常: {str(e)}")
        return False
