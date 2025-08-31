import yaml
from pathlib import Path

_messages = None


def get_messages():
    # ленивый лоад yaml, чтобы не дергать диск каждый раз
    global _messages
    if _messages is None:
        path = Path(__file__).resolve().parent.parent / 'messages.yaml'
        with open(path, 'r', encoding='utf-8') as f:
            _messages = yaml.safe_load(f)
    return _messages
