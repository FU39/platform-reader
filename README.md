# 平台数据读取工具说明

本项目用于调用平台两个接口并导出结果：

- `querySingleParam`：读取点位当前值
- `queryTimeSeriesParam`：读取点位时序数据

当前主流程由 `main.py` 驱动，读取 `config/data_name.json` 中的 `query_keys`，然后调用时序接口并把结果写入 `result/` 目录。

## 目录结构

```text
code/
├─ config/
│  ├─ data_name.json        # 主函数输入配置（本次运行要查哪些 key）
│  └─ query_specs.json      # 查询规格库（团队维护的点位字典）
├─ result/                  # 导出的 CSV 结果目录
├─ data_read.py             # payload 构造 + 接口请求 + 结果 DataFrame
├─ main.py                  # 主入口：读取 data_name.json 并导出 CSV
├─ test_data_read.py        # 手工测试脚本（示例 payload）
├─ utils.py                 # 常量、数据模型、配置加载与校验
├─ requirements.txt
└─ README.md
```

## 核心文件职责

- `utils.py`
  - 定义接口地址、配置路径（如 `CONFIG_DIR`、`RESULT_DIR`）
  - 定义 `QuerySingleSpec` / `QueryTimeSeriesSpec`
  - 负责读取并校验 `config/query_specs.json`

- `data_read.py`
  - `build_single_param_payload` / `build_time_series_payload`：按 `query_keys` 从规格库构造请求体
  - `query_single_param` / `query_time_series_param`：发送请求并返回 `DataFrame`
  - 结果列结构：每个 `query_key` 输出两列：`<key>_timestamp` 和 `<key>`

- `main.py`
  - 从 `config/data_name.json` 读取本次运行的 `query_keys`
  - 调用 `build_time_series_payload` + `query_time_series_param`
  - 保存到 `result/series_result_<时间戳>.csv`

## `query_specs.json` 维护

`config/query_specs.json` 是“查询规格库”，可以理解为项目内的点位字典。它把“业务别名 key”映射为接口真正需要的字段。

### 维护说明

- 主流程和构造函数都依赖它来生成请求 payload
- 新增/修改点位时，通常只需要改这里，不必改 Python 代码
- 团队协作时，统一维护这份文件可以减少硬编码和口径不一致

### 结构说明

`query_specs.json` 包含两大块：

- `single`：单点当前值查询规格
- `time_series`：时序查询规格

示例（节选）：

```json
{
  "single": {
    "test_001": {
      "key": "日累计运行费用KKKKKK",
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
      "attr": "supplyTemperature",
      "startTime": 1773615890000,
      "endTime": 1773626690000,
      "downSample": "AVG",
      "interval": "3600",
      "intervalPeriod": "s",
      "groupBy": true,
      "removeOutliers": false
    }
  }
}
```

### 协作者维护建议

- `time_series` 中每个条目至少保证：`key/deviceID/deviceType/attr/startTime/endTime`
- `startTime`、`endTime` 使用毫秒时间戳，且 `startTime < endTime`
- `downSample` 建议统一使用大写（如 `AVG`）
- 新增 key 时，命名建议语义化，方便业务侧直接引用

## 如何配置 `data_name.json`

`config/data_name.json` 用于指定“本次主函数运行要查哪些 key”。

当前 `main.py` 只读取一个字段：`query_keys`。

### 最小可用配置

```json
{
  "query_keys": [
    "新电锅炉2025-supplyTemperature"
  ]
}
```

### 多 key 配置示例

```json
{
  "query_keys": [
    "test_001",
    "test_002",
    "新电锅炉2025-supplyTemperature"
  ]
}
```

> 注意：`query_keys` 里的每一项都必须在 `config/query_specs.json` 的 `time_series` 中存在。

## 运行方式

```powershell
python .\main.py
```

运行成功后，会在 `result/` 下生成类似文件：

- `series_result_20260319-153000.csv`

## 输出结果说明

导出的 CSV 按 key 成对输出列。例如配置了两个 key：`A`、`B`，列名会是：

- `A_timestamp`, `A`, `B_timestamp`, `B`

即：每个 key 对应一列时间戳和一列数值，便于各点位独立对齐和查看。

## 常见问题

- 提示找不到 `data_name.json`
  - 检查文件是否位于 `config/data_name.json`

- 提示某个 key 缺失
  - 检查该 key 是否已在 `config/query_specs.json` 的 `time_series` 下配置

- 提示时间范围错误
  - 检查 `startTime`、`endTime` 的毫秒时间戳和先后关系
