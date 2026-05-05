import sys
import json
import datetime


def _print_text(value, prefix=""):
    if isinstance(value, dict):
        if not value:
            print(f"{prefix}{{}}")
            return
        for k, v in value.items():
            if isinstance(v, (dict, list)) and v:
                print(f"{prefix}{k}:")
                _print_text(v, prefix + "  ")
            else:
                print(f"{prefix}{k}: {v}")
    elif isinstance(value, list):
        if not value:
            print(f"{prefix}[]")
            return
        for item in value:
            if isinstance(item, (dict, list)) and item:
                print(f"{prefix}-")
                _print_text(item, prefix + "  ")
            else:
                print(f"{prefix}- {item}")
    else:
        print(f"{prefix}{value}")


def print_output(data, fmt="text"):
    if fmt == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        _print_text(data)


def success(data=None, fmt="text"):
    if data:
        print_output(data, fmt)
    sys.exit(0)


def error(message, code=1):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(code)


def warn(message):
    print(f"WARNING: {message}", file=sys.stderr)


def now():
    return datetime.datetime.now().isoformat()
