import argparse
import json
from pathlib import Path

from utils.misc import CONFIG_DIR, normalize_series_options, transfer_timestamp

TIME_INPUT_FORMAT = "%Y-%m-%d %H:%M:%S"


def _load_config(path):
    if not path.exists():
        raise FileNotFoundError(f"未找到 config.json: {path}")

    with path.open("r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)

    if not isinstance(data, dict):
        raise ValueError("config.json 根节点必须是对象 (dict)")

    return data


def _prompt_time(label):
    print(f"请输入{label}，格式: YYYY-MM-DD HH:MM:SS")
    return input(f"{label}: ").strip()


def _build_series_options(start_ms, end_ms, existing_options):
    if existing_options is None:
        existing_options = {}
    if not isinstance(existing_options, dict):
        raise ValueError("config.json 中 series_options 必须是对象(dict)")

    merged = dict(existing_options)
    merged["startTime"] = start_ms
    merged["endTime"] = end_ms

    # 复用现有归一化逻辑，确保字段完整且值合法。
    return normalize_series_options(merged)


def _parse_args():
    parser = argparse.ArgumentParser(
        description="读取用户输入时间并转换为 config.json 所需毫秒时间戳"
    )
    parser.add_argument(
        "--config-path",
        default=str(CONFIG_DIR / "config.json"),
        help="config.json 路径，默认: config/config.json",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="仅打印转换结果，不写回 config.json",
    )
    return parser.parse_args()


def main():
    args = _parse_args()
    config_path = Path(args.config_path)

    start_text = _prompt_time("开始时间")
    end_text = _prompt_time("结束时间")

    start_ms = transfer_timestamp(start_text, fmt=TIME_INPUT_FORMAT)
    end_ms = transfer_timestamp(end_text, fmt=TIME_INPUT_FORMAT)

    if start_ms >= end_ms:
        raise ValueError("时间范围错误: startTime 必须小于 endTime")

    print("\n转换结果:")
    print(f"startTime: {start_ms}")
    print(f"endTime:   {end_ms}")

    if args.print_only:
        return

    data = _load_config(config_path)
    data["series_options"] = _build_series_options(
        start_ms,
        end_ms,
        data.get("series_options"),
    )

    with config_path.open("w", encoding="utf-8") as file_obj:
        json.dump(data, file_obj, ensure_ascii=False, indent=4)

    print(f"\n已写入: {config_path}")


if __name__ == "__main__":
    main()
