"""Probe: extra_body 对 reasoning_content（思维链）的控制效果。

手动探测脚本，不以 test_ 开头，pytest 不收集。
凭据从环境变量读取，缺省打印提示后退出，不发起请求：
- OPENAI_API_KEY（必填）
- OPENAI_BASE_URL（可选，缺省 token-plan-cn.xiaomimimo.com/v1）
- OPENAI_MODEL（可选，缺省 mimo-v2.5-pro）

用法（PowerShell）：
  $env:OPENAI_API_KEY = "..."   # 必填
  uv run python tests/thinking_probe.py
"""

import os
import sys
import time

API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
BASE_URL = os.environ.get(
    "OPENAI_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1"
).strip()
MODEL = os.environ.get("OPENAI_MODEL", "mimo-v2.5-pro").strip()

if not API_KEY:
    print(
        "缺 OPENAI_API_KEY 环境变量，退出（不发起请求）。",
        file=sys.stderr,
    )
    sys.exit(1)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from openai import OpenAI

MESSAGES = [
    {"role": "system", "content": "You are a helpful assistant."},
    {
        "role": "user",
        "content": "A clock shows 3:15, what is the angle between the hour and minute hand?",
    },
]


def probe(label, extra_body):
    kwargs = dict(model=MODEL, messages=MESSAGES, stream=True)
    if extra_body is not None:
        kwargs["extra_body"] = extra_body

    reasoning = 0
    t0 = time.perf_counter()
    for chunk in OpenAI(api_key=API_KEY, base_url=BASE_URL).chat.completions.create(
        **kwargs
    ):
        if (
            chunk.choices
            and chunk.choices[0].delta
            and getattr(chunk.choices[0].delta, "reasoning_content", None)
        ):
            reasoning += len(chunk.choices[0].delta.reasoning_content)
    elapsed = time.perf_counter() - t0
    return reasoning, round(elapsed, 1)


r_none, t_none = probe("none", None)
r_on, t_on = probe("enabled", {"thinking": {"type": "enabled"}})
r_off, t_off = probe("disabled", {"thinking": {"type": "disabled"}})

print()
print("=" * 55)
print(f"  {'extra_body':<30} reasoning chars     time")
print(f"  {'-' * 30} {'-' * 14} {'-' * 6}")
print(f"  不传                    {r_none:>5} chars        {t_none:>4.1f}s")
print(f"  thinking=enabled        {r_on:>5} chars        {t_on:>4.1f}s")
print(f"  thinking=disabled       {r_off:>5} chars        {t_off:>4.1f}s")
print("=" * 55)

if r_none > 0 and r_off == 0:
    print("  默认: 有推理 → disabled 关闭了推理 (参数生效)")
elif r_none == 0 and r_on > 0:
    print("  默认: 无推理 → enabled 开启了推理 (参数生效)")
elif r_none > 0 and r_off > 0:
    print("  默认: 有推理 → disabled 未关闭推理 (参数无效)")
elif r_none == 0 and r_on == 0:
    print("  默认: 无推理 → enabled 未开启推理 (参数无效)")
print("=" * 55)