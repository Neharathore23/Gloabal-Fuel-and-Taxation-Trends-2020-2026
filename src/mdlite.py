"""Minimal, safe Markdown -> HTML for the in-app documentation pages.

Supports headings, paragraphs, bullet/numbered lists, fenced code, pipe tables, blockquotes, **bold**, `code`
and [links](http(s)://...). All text is HTML-escaped first, so documentation files cannot inject markup.
"""
import re
from html import escape

_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def _inline(text: str) -> str:
    t = escape(text, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    return _LINK.sub(lambda m: f'<a href="{escape(m.group(2), quote=True)}" rel="noopener noreferrer">{m.group(1)}</a>', t)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def render(md: str) -> str:
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```"):
            buf, i = [], i + 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            out.append("<pre><code>" + escape("\n".join(buf), quote=False) + "</code></pre>")
            i += 1
        elif m := re.match(r"^(#{1,4})\s+(.*)", ln):
            n = len(m.group(1))
            out.append(f"<h{n}>{_inline(m.group(2))}</h{n}>")
            i += 1
        elif "|" in ln and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            head, i = _cells(ln), i + 2
            rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(_cells(lines[i]))
                i += 1
            out.append('<div class="table-responsive"><table class="table table-sm table-bordered"><thead><tr>'
                       + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rows)
                       + "</tbody></table></div>")
        elif re.match(r"^\s*([-*]|\d+\.)\s+", ln):
            tag = "ol" if re.match(r"^\s*\d+\.", ln) else "ul"
            items = []
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                items.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i]))
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + f"</{tag}>")
        elif ln.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i].lstrip("> "))
                i += 1
            out.append("<blockquote class='blockquote'>" + _inline(" ".join(buf)) + "</blockquote>")
        elif not ln.strip():
            i += 1
        else:
            buf = []
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,4}\s|```|\s*([-*]|\d+\.)\s|>)", lines[i]):
                buf.append(lines[i].strip())
                i += 1
            out.append("<p>" + _inline(" ".join(buf)) + "</p>")
    return "\n".join(out)
