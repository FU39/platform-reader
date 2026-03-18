"""
数字孪生设备属性数据接口测试脚本
支持两个接口:
1. 获取当前设备点位实时数据
2. 获取设备属性时序参数数据
"""

import json
import requests

from utils import check_connectivity
from data_read import query_single_param, query_time_series_param


def test_single_param():
    """测试获取单个设备点位实时数据"""
    print("\n" + "=" * 60)
    print("测试 1: 获取当前设备点位实时数据")
    print("=" * 60)

    payload = [
        {
            "key": "test_single_param_001",
            "deviceID": "101ijmk5rto4400",
            "deviceType": "economic_evaluation",
            "attr": "economic_evaluation",
        }
    ]

    try:
        query_single_param(payload, query_keys=["test_single_param_001"], timeout=10, verbose=True)
    except requests.exceptions.RequestException as e:
        print(f"✗ 请求异常: {str(e)}")
    except json.JSONDecodeError as e:
        print(f"✗ JSON解析异常: {str(e)}")


def test_batch_query():
    """测试批量查询"""
    print("\n" + "=" * 60)
    print("测试 3: 批量查询设备数据")
    print("=" * 60)

    payload = [
        {
            "key": "device_001",
            "deviceID": "101ijmk5rto4400",
            "deviceType": "economic_evaluation",
            "attr": "economic_evaluation",
        },
        {
            "key": "device_002",
            "deviceID": "101ijmm2hq44400",
            "deviceType": "economic_evaluation",
            "attr": "economic_evaluation",
        },
    ]

    try:
        query_single_param(payload, query_keys=["device_001", "device_002"], timeout=10, verbose=True)
    except requests.exceptions.RequestException as e:
        print(f"✗ 请求异常: {str(e)}")
    except json.JSONDecodeError as e:
        print(f"✗ JSON解析异常: {str(e)}")


def test_time_series_param():
    """测试获取设备属性时序参数数据"""
    print("\n" + "=" * 60)
    print("测试 2: 获取设备属性时序参数数据")
    print("=" * 60)

    start_time = 1773615890000
    end_time = 1773626690000

    payload = [
        {
            "key": "test_timeseries_001",
            "deviceID": "101ijmk5rto4400",
            "deviceType": "economic_evaluation",
            "attr": "economic_evaluation",
            "startTime": start_time,
            "endTime": end_time,
            "downSample": "AVG",
            "interval": "3600",
            "intervalPeriod": "s",
            "groupBy": True,
            "removeOutliers": False,
        }
    ]

    try:
        query_time_series_param(payload, query_keys=["test_timeseries_001"], timeout=10, verbose=True)
    except requests.exceptions.RequestException as e:
        print(f"✗ 请求异常: {str(e)}")
    except json.JSONDecodeError as e:
        print(f"✗ JSON解析异常: {str(e)}")


if __name__ == "__main__":
    if check_connectivity():
        test_single_param()
        test_time_series_param()
        test_batch_query()
    else:
        print("✗ 无法连接到服务器, 请检查网络和服务器状态")
