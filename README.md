# 平台数据读取工具说明

本项目用于调用平台接口并导出结果，当前主流程由 `main.py` 驱动：

- 从 `config/config.json` 读取本次要查询的 `query_keys`
- 从 `database/query_specs.json` 读取团队维护的字段映射
- 按 `type` 分组调用接口（`single` / `time_series`）
- 分别导出到 `result/` 目录

## 项目结构

```text
platform-reader/
├─ config/
│  └─ config.json             # 本次运行输入：query_keys + series_options
├─ database/
│  └─ query_specs.json        # 查询规格库：single/time_series 字段映射（合作者维护）
├─ result/
├─ utils/
│  ├─ __init__.py
│  ├─ data_read.py            # payload 构造、接口请求、DataFrame 组装
│  └─ misc.py                 # 常量、数据模型、规格加载与参数归一化
├─ main.py                    # 主入口，按 type 分组查询并分文件导出
├─ timestamp_handler.py       # 交互输入时间并写入 config/config.json 的 series_options
├─ test_data_read.py
├─ requirements.txt
└─ README.md
```

## 配置与规格

### 1) `database/query_specs.json`

团队维护的点位字段映射库，只记录字段映射，不包含时序查询参数。

**结构说明：**

- `single` 项：单点当前值查询的字段映射
  - 每项字段：`key`, `deviceID`, `deviceType`, `attr`
- `time_series` 项：时序数据查询的字段映射
  - 每项字段：`key`, `deviceID`, `deviceType`, `attr`

示例：

```json
{
  "single": {
    "test_001": {
      "key": "日累计运行费用",
      "deviceID": "101ijmk5rto4400",
      "deviceType": "economic_evaluation",
      "attr": "economic_evaluation"
    }
  },
  "time_series": {
    "新电锅炉2025-supplyTemperature": {
      "key": "1966069132271202313",
      "deviceID": "101mi71ei0o4400",
      "deviceType": "newBoiler2025",
      "attr": "supplyTemperature"
    }
  }
}
```

### 2) `config/config.json`

本次运行的输入配置：定义查询项与时序查询参数。

- `query_keys`：列表，每项是 `{ "name": "...", "type": "single|time_series" }`
- `series_options`：时序查询参数（只对 `time_series` 生效）

示例：

```json
{
    "query_keys": [
        {
            "name": "新电锅炉2025-supplyTemperature",
            "type": "time_series"
        }
    ],
    "series_options": {
        "startTime": 1773615890000,
        "endTime": 1773626690000,
        "downSample": "AVG",
        "interval": "3600",
        "intervalPeriod": "s",
        "groupBy": true,
        "removeOutliers": false
    }
}
```

## 结果输出

- `time_series` 查询结果：`result/series_result_<时间戳>.csv`
- `single` 查询结果：`result/single_result_<时间戳>.csv`

CSV 列结构统一为：

- 一列公共 `timestamp`
- 后续每列为对应 `query_keys` 的 `name`

## 安装与运行

```powershell
pip install -r .\requirements.txt
python .\main.py
```

## 常见问题

- `query_keys` 报错
    - 检查每项是否都是对象，并且包含 `name` 和 `type`

- `time_series` 报缺少参数
    - 检查 `config/config.json` 是否提供了对象类型的 `series_options`

- 查询 key 缺失
    - 检查 `query_keys.name` 是否在 `database/query_specs.json` 对应类型下存在

## 时间戳输入工具

`timestamp_handler.py` 用于交互读取时间字符串并转换为毫秒时间戳，复用 `utils/misc.py` 中的 `transfer_timestamp()`。

- 输入格式固定为：`YYYY-MM-DD HH:MM:SS`
- 若输入格式不合法，直接抛出 `ValueError`
- 若合法，会转换为 `series_options.startTime` 和 `series_options.endTime`
- 默认会写回 `config/config.json`

命令示例：

```powershell
python .\timestamp_handler.py
```

仅转换并打印，不写回文件：

```powershell
python .\timestamp_handler.py --print-only
```

自定义 `config.json` 路径：

```powershell
python .\timestamp_handler.py --config-path .\config\config.json
```
