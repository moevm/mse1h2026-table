import sys
import json
import datetime


def print_output(data, fmt="text"):
    if fmt == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        if isinstance(data, dict):
            for k, v in data.items():
                print(f"{k}: {v}")
        else:
            print(data)


def success(data=None, fmt="text"):
    if data:
        print_output(data, fmt)
    sys.exit(0)


def error(message, code=1):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(code)


def now():
    return datetime.datetime.now().isoformat()
