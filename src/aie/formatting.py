"""Display formats and claim markers.

Every number placed in a customer-facing document is followed by an
invisible HTML comment naming the fact it came from:

    81.2%<!--claim:site-02@2026-09:efficiency-->

The integrity engine reads these markers, recomputes each fact on its own,
and fails the document if any displayed number disagrees. A number with no
marker is flagged as unsupported. Claim reference grammar:

    [SITE@PERIOD:]metric                current value
    [SITE@PERIOD:]delta:metric          current - previous period (signed: "-4.0 pts")
    [SITE@PERIOD:]absdelta:metric       size of the change, unsigned, for prose ("down 4.0 pts")
    [SITE@PERIOD:]delta:breakdown[key]  change in one breakdown item (absdelta: works too)
    [SITE@PERIOD:]baseline:metric       trailing baseline mean
    target:metric                       target from the pack spec
    [SITE@PERIOD:]breakdown[key]        one item of a breakdown

`N<!--literal-->` marks a number that is not a data claim (for example a
count of checks). It is allowed but recorded in the validation report.
"""

from __future__ import annotations


def fmt_value(value, fmt: str) -> str:
    if value is None:
        return "n/a"
    if fmt == "pct1":
        return f"{value * 100:.1f}%"
    if fmt == "int":
        return f"{int(round(value)):,}"
    if fmt == "num2":
        return f"{value:,.2f}"
    return f"{value:,.1f}"


def fmt_delta(delta, fmt: str) -> str:
    if delta is None:
        return "n/a"
    if abs(delta) < 5e-11:
        delta = 0.0
    if fmt == "pct1":
        return f"{delta * 100:+.1f} pts"
    if fmt == "int":
        return f"{int(round(delta)):+,}"
    if fmt == "num2":
        return f"{delta:+,.2f}"
    return f"{delta:+,.1f}"


def claim(text: str, ref: str) -> str:
    if text == "n/a":
        return text
    return f"{text}<!--claim:{ref}-->"


def literal(text: str) -> str:
    return f"{text}<!--literal-->"
