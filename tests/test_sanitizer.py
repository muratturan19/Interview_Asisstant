import json

from backend import _sanitize_evaluation_text


def test_sanitize_preserves_plain_json():
    payload = '{"score": 4}'
    assert _sanitize_evaluation_text(payload) == payload
    assert json.loads(_sanitize_evaluation_text(payload)) == {"score": 4}


def test_sanitize_strips_triple_backtick_fences():
    payload = """```json
{"score": 3}
```"""
    assert _sanitize_evaluation_text(payload) == '{"score": 3}'


def test_sanitize_strips_tilde_fences():
    payload = """~~~
{"score": 2}
~~~"""
    assert _sanitize_evaluation_text(payload) == '{"score": 2}'


def test_sanitize_handles_inline_fences():
    payload = "```{\"score\": 5}```"
    assert _sanitize_evaluation_text(payload) == '{"score": 5}'
