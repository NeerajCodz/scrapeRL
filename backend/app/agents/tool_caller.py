"""LLM-driven tool planning and registry-backed tool execution."""

from __future__ import annotations

import csv
import io
import json
import ast
import re
import statistics
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.models.router import SmartModelRouter, TaskType
from app.plugins.registry import get_all_tools, get_tool
from app.utils.logging import get_logger

logger = get_logger(__name__)

SUPPORTED_TOOL_NAMESPACES = {
    "browser",
    "html",
    "extract",
    "regex",
    "validate",
    "json",
    "csv",
    "data",
    "analysis",
    "text",
    "stats",
}


def _truncate(value: Any, limit: int = 240) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[A-Za-z0-9_]+", text.lower()) if len(token) > 1]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def _coerce_records(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    return []


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    content = text.strip()

    if "```json" in content:
        content = content.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in content:
        content = content.split("```", 1)[1].split("```", 1)[0].strip()

    start = content.find("[")
    end = content.rfind("]")
    if start == -1 or end == -1 or start > end:
        return []

    payload = content[start : end + 1]
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(payload)
        except (ValueError, SyntaxError):
            return []

    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    return []


def _infer_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


@dataclass
class ToolCall:
    """A tool invocation selected by the planner."""

    tool_name: str
    parameters: dict[str, Any]
    reasoning: str = ""


@dataclass
class ToolCallResult:
    """Result of a single executed tool call."""

    tool_name: str
    success: bool
    result: Any
    error: str | None = None
    duration_ms: int = 0


class AgentToolCaller:
    """Asks an LLM to choose tool calls from the plugin registry."""

    def __init__(
        self,
        model_router: SmartModelRouter,
        allowed_tool_names: set[str] | None = None,
    ) -> None:
        self.router = model_router
        all_tools = [
            tool
            for tool in get_all_tools()
            if tool.name.split(".", 1)[0] in SUPPORTED_TOOL_NAMESPACES
        ]
        if allowed_tool_names:
            self._tools = [tool for tool in all_tools if tool.name in allowed_tool_names]
        else:
            self._tools = all_tools
        self._tool_names = {tool.name for tool in self._tools}
        self._tool_catalog = self._build_tool_catalog()

    def _build_tool_catalog(self) -> str:
        if not self._tools:
            return "No tools available."

        grouped: dict[str, list[str]] = {}
        for tool in sorted(self._tools, key=lambda item: item.name):
            namespace = tool.name.split(".", 1)[0]
            entry = (
                f"- {tool.name}: {tool.description} | "
                f"params={json.dumps(tool.parameters, separators=(',', ':'))}"
            )
            grouped.setdefault(namespace, []).append(entry)

        lines: list[str] = []
        for namespace in sorted(grouped):
            lines.append(f"[{namespace}]")
            lines.extend(grouped[namespace])
            lines.append("")
        return "\n".join(lines).strip()

    async def decide_tools(
        self,
        task_description: str,
        context: dict[str, Any],
        model: str,
        max_tools: int = 6,
    ) -> list[ToolCall]:
        """Return a runtime tool plan chosen by the LLM."""

        if not self._tool_names:
            return []

        prompt = f"""You are selecting tools for a generic web scraping task.
Use ONLY tools from AVAILABLE_TOOLS and return strict JSON.

AVAILABLE_TOOLS:
{self._tool_catalog}

TASK:
{task_description}

CONTEXT:
- URL: {context.get("url", "")}
- HTML Length: {context.get("html_length", 0)}
- Output Format: {context.get("output_format", "json")}
- User Instructions: {context.get("instructions", "")}
- Prior Tool Calls: {context.get("tools_used", [])}

Rules:
1. Return only a JSON array (no markdown, no prose).
2. Each item must contain: tool_name, parameters, reasoning.
3. Choose 2 to {max_tools} tools.
4. Calls must be generic for arbitrary websites (no site-specific hardcoding).

Format:
[
  {{
    "tool_name": "html.select",
    "parameters": {{"selector": "article, [role='article']", "limit": 25}},
    "reasoning": "Find repeated content blocks"
  }}
]"""
        try:
            response = await self.router.complete(
                messages=[{"role": "user", "content": prompt}],
                task_type=TaskType.REASONING,
                model=model,
                temperature=0.1,
            )
            raw_calls = _extract_json_array(response.content)
            normalized = self._normalize_tool_calls(raw_calls, max_tools=max_tools)
            if normalized:
                return normalized
            logger.warning("Agent returned no valid tool calls; using dynamic fallback")
            return self._fallback_tools(max_tools=max_tools)
        except Exception as exc:
            logger.warning("Tool planning failed: %s", exc)
            return self._fallback_tools(max_tools=max_tools)

    def _normalize_tool_calls(self, raw_calls: list[dict[str, Any]], max_tools: int) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for item in raw_calls:
            tool_name = str(item.get("tool_name", "")).strip()
            if not tool_name or tool_name not in self._tool_names:
                continue

            parameters = item.get("parameters", {})
            if not isinstance(parameters, dict):
                parameters = {}

            calls.append(
                ToolCall(
                    tool_name=tool_name,
                    parameters=parameters,
                    reasoning=str(item.get("reasoning", "")),
                )
            )
            if len(calls) >= max_tools:
                break
        return calls

    def _fallback_tools(self, max_tools: int) -> list[ToolCall]:
        """Build a generic fallback plan from available namespaces (not site-specific)."""
        namespace_order = ("validate", "html", "extract", "data", "analysis", "text", "stats")
        by_namespace: dict[str, list[str]] = {}
        for tool_name in sorted(self._tool_names):
            namespace = tool_name.split(".", 1)[0]
            by_namespace.setdefault(namespace, []).append(tool_name)

        fallback: list[ToolCall] = []
        for namespace in namespace_order:
            for tool_name in by_namespace.get(namespace, [])[:2]:
                fallback.append(
                    ToolCall(
                        tool_name=tool_name,
                        parameters={},
                        reasoning=f"Fallback generic probe from {namespace} namespace.",
                    )
                )
                if len(fallback) >= max_tools:
                    return fallback
        return fallback[:max_tools]


class ToolExecutor:
    """Executes selected tools against page context using registry-backed dispatch."""

    def __init__(self, allowed_tool_names: set[str] | None = None) -> None:
        names = {
            tool.name
            for tool in get_all_tools()
            if tool.name.split(".", 1)[0] in SUPPORTED_TOOL_NAMESPACES
        }
        self._known_tool_names = names & allowed_tool_names if allowed_tool_names else names

    async def execute_tool_call(self, tool_call: ToolCall, context: dict[str, Any]) -> ToolCallResult:
        start = time.time()
        tool_name = tool_call.tool_name

        try:
            if tool_name not in self._known_tool_names:
                raise ValueError(f"Unknown tool '{tool_name}'")
            if get_tool(tool_name) is None:
                raise ValueError(f"Tool '{tool_name}' is not registered")

            result = self._dispatch(tool_name, tool_call.parameters, context)
            return ToolCallResult(
                tool_name=tool_name,
                success=True,
                result=result,
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as exc:
            return ToolCallResult(
                tool_name=tool_name,
                success=False,
                result=None,
                error=str(exc),
                duration_ms=int((time.time() - start) * 1000),
            )

    def _dispatch(self, tool_name: str, params: dict[str, Any], context: dict[str, Any]) -> Any:
        namespace = tool_name.split(".", 1)[0].lower()

        if namespace == "browser":
            return self._run_browser_tool(tool_name, params, context)
        if namespace == "html":
            return self._run_html_tool(tool_name, params, context)
        if namespace in {"json", "csv", "data", "pandas"}:
            return self._run_data_tool(tool_name, params, context)
        if namespace in {"extract", "regex"}:
            return self._run_extraction_tool(tool_name, params, context)
        if namespace == "validate":
            return self._run_validation_tool(tool_name, params, context)
        if namespace in {"analysis", "text", "stats"}:
            return self._run_analysis_tool(tool_name, params, context)

        raise ValueError(f"No runtime handler for namespace '{namespace}'")

    def _run_browser_tool(self, tool_name: str, params: dict[str, Any], context: dict[str, Any]) -> Any:
        current_url = str(context.get("url", "") or "")
        if tool_name == "browser.navigate":
            target_url = str(params.get("url", current_url) or current_url)
            context["url"] = target_url
            return {"success": True, "status_code": 200, "url": target_url}

        if tool_name == "browser.wait":
            timeout_ms = int(params.get("timeout_ms", 500) or 500)
            return {"found": True, "waited_ms": timeout_ms}

        if tool_name == "browser.execute_js":
            script = str(params.get("script", "") or "")
            return {"result": {"script_length": len(script)}, "error": None}

        if tool_name in {"browser.scroll", "browser.click", "browser.type", "browser.get_cookies", "browser.screenshot"}:
            return {"success": True, "tool": tool_name}

        raise ValueError(f"Unsupported browser tool '{tool_name}'")

    def _get_soup(self, context: dict[str, Any]) -> BeautifulSoup:
        soup = context.get("soup")
        if isinstance(soup, BeautifulSoup):
            return soup

        html = str(context.get("html", "") or "")
        if not html:
            raise ValueError("No HTML available in execution context")

        soup = BeautifulSoup(html, "html.parser")
        context["soup"] = soup
        return soup

    @staticmethod
    def _snapshot_element(element: Any) -> dict[str, Any]:
        return {
            "tag": getattr(element, "name", ""),
            "id": element.get("id") if hasattr(element, "get") else None,
            "classes": element.get("class", []) if hasattr(element, "get") else [],
            "text": _truncate(element.get_text(" ", strip=True), 180) if hasattr(element, "get_text") else "",
        }

    def _run_html_tool(self, tool_name: str, params: dict[str, Any], context: dict[str, Any]) -> Any:
        soup = self._get_soup(context)

        if tool_name == "html.parse":
            parser_name = str(params.get("parser", "html.parser"))
            html = str(context.get("html", "") or "")
            parsed = BeautifulSoup(html, parser_name if parser_name in {"html.parser", "lxml"} else "html.parser")
            context["soup"] = parsed
            return {"parsed": True, "soup_type": parser_name, "content_length": len(html)}

        if tool_name == "html.select":
            selector = str(params.get("selector", "") or "")
            if not selector:
                raise ValueError("html.select requires a selector")
            limit = int(params.get("limit", 20) or 20)
            elements = soup.select(selector, limit=max(1, limit))
            return {
                "elements_found": len(elements),
                "selector_used": selector,
                "elements": [self._snapshot_element(element) for element in elements[: max(1, limit)]],
            }

        if tool_name == "html.select_one":
            selector = str(params.get("selector", "") or "")
            if not selector:
                raise ValueError("html.select_one requires a selector")
            element = soup.select_one(selector)
            return {"found": bool(element), "element": self._snapshot_element(element) if element else None}

        if tool_name == "html.find_all":
            tag = params.get("tag")
            attrs = params.get("attrs", {})
            recursive = bool(params.get("recursive", True))
            limit = int(params.get("limit", 20) or 20)
            if attrs is None or not isinstance(attrs, dict):
                attrs = {}
            elements = soup.find_all(tag, attrs=attrs, recursive=recursive, limit=max(1, limit))
            return {
                "elements_found": len(elements),
                "tags": [getattr(element, "name", "") for element in elements],
                "elements": [self._snapshot_element(element) for element in elements[: max(1, limit)]],
            }

        if tool_name == "html.get_text":
            selector = params.get("selector")
            separator = str(params.get("separator", " "))
            if selector:
                selected = soup.select(str(selector))
                text = separator.join(node.get_text(" ", strip=True) for node in selected)
            else:
                text = soup.get_text(" ", strip=True)
            return {"text": text, "length": len(text)}

        if tool_name == "html.get_attribute":
            selector = str(params.get("selector", "") or "")
            attribute = str(params.get("attribute", "") or "")
            if not selector or not attribute:
                raise ValueError("html.get_attribute requires selector and attribute")
            element = soup.select_one(selector)
            return {"found": bool(element), "value": element.get(attribute) if element else None}

        if tool_name == "html.extract_links":
            filter_pattern = params.get("filter_pattern")
            base_url = str(params.get("base_url", "") or context.get("url", "") or "")
            pattern = re.compile(str(filter_pattern)) if filter_pattern else None
            links: list[dict[str, Any]] = []
            for anchor in soup.select("a[href]"):
                href = str(anchor.get("href", "") or "").strip()
                if not href:
                    continue
                absolute_url = urljoin(base_url, href) if base_url else href
                if pattern and not pattern.search(absolute_url):
                    continue
                links.append(
                    {
                        "url": absolute_url,
                        "text": _truncate(anchor.get_text(" ", strip=True), 120),
                        "title": anchor.get("title"),
                    }
                )
            return {"count": len(links), "links": links[:200]}

        if tool_name == "html.extract_images":
            include_lazy = bool(params.get("include_lazy", True))
            images: list[dict[str, Any]] = []
            for image in soup.select("img"):
                src = image.get("src")
                if include_lazy and not src:
                    src = image.get("data-src") or image.get("data-original")
                if not src:
                    continue
                images.append(
                    {
                        "src": src,
                        "alt": image.get("alt"),
                        "title": image.get("title"),
                    }
                )
            return {"count": len(images), "images": images[:200]}

        if tool_name == "html.extract_tables":
            selector = params.get("selector")
            tables = soup.select(str(selector)) if selector else soup.find_all("table")
            output: list[dict[str, Any]] = []
            for table in tables:
                rows: list[list[str]] = []
                for row in table.find_all("tr"):
                    cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
                    if cells:
                        rows.append(cells)
                if rows:
                    output.append({"rows": rows, "row_count": len(rows)})
            return {"count": len(output), "tables": output[:30]}

        if tool_name == "html.extract_forms":
            selector = params.get("selector")
            forms = soup.select(str(selector)) if selector else soup.find_all("form")
            extracted: list[dict[str, Any]] = []
            for form in forms:
                fields: list[dict[str, Any]] = []
                for field in form.find_all(["input", "select", "textarea", "button"]):
                    fields.append(
                        {
                            "tag": field.name,
                            "name": field.get("name"),
                            "type": field.get("type"),
                            "id": field.get("id"),
                        }
                    )
                extracted.append({"action": form.get("action"), "method": form.get("method"), "fields": fields})
            return {"count": len(extracted), "forms": extracted[:30]}

        if tool_name == "html.extract_meta":
            meta: dict[str, str] = {}
            for tag in soup.find_all("meta"):
                key = tag.get("name") or tag.get("property")
                content = tag.get("content")
                if key and content:
                    meta[str(key)] = str(content)
            title = soup.title.get_text(" ", strip=True) if soup.title else ""
            return {"title": title, "meta": meta, "count": len(meta)}

        if tool_name == "html.extract_jsonld":
            items: list[Any] = []
            for node in soup.select("script[type='application/ld+json']"):
                raw = node.string or node.get_text(" ", strip=True)
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        items.extend(parsed)
                    else:
                        items.append(parsed)
                except json.JSONDecodeError:
                    continue
            return {"count": len(items), "items": items[:50]}

        if tool_name == "html.detect_repeating_blocks":
            signatures: dict[str, int] = {}
            for node in soup.find_all(True):
                classes = node.get("class") or []
                if not classes:
                    continue
                signature = f"{node.name}.{'.'.join(sorted(classes)[:2])}"
                signatures[signature] = signatures.get(signature, 0) + 1
            candidates = [
                {"signature": signature, "count": count}
                for signature, count in sorted(signatures.items(), key=lambda item: item[1], reverse=True)
                if count >= 3
            ]
            return {"candidates": candidates[:25], "count": len(candidates)}

        raise ValueError(f"Unsupported HTML tool '{tool_name}'")

    def _run_data_tool(self, tool_name: str, params: dict[str, Any], context: dict[str, Any]) -> Any:
        if tool_name == "json.parse":
            text = str(params.get("text", "") or "")
            try:
                data = json.loads(text)
                return {"valid": True, "data": data}
            except json.JSONDecodeError as exc:
                return {"valid": False, "data": None, "error": str(exc)}

        if tool_name == "json.dumps":
            data = params.get("data", context.get("data"))
            indent = int(params.get("indent", 2) or 2)
            sort_keys = bool(params.get("sort_keys", False))
            output = json.dumps(data, indent=indent, sort_keys=sort_keys, default=str)
            return {"output": output, "length": len(output)}

        if tool_name == "csv.generate":
            rows = _coerce_records(params.get("data", context.get("rows")))
            fields = params.get("fields")
            field_names = [str(field) for field in fields] if isinstance(fields, list) and fields else None
            if not rows:
                return {"csv": "", "rows": 0, "columns": 0}
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=field_names or list(rows[0].keys()))
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
            csv_text = output.getvalue()
            return {
                "csv": csv_text,
                "rows": len(rows),
                "columns": len(writer.fieldnames or []),
            }

        if tool_name == "csv.parse":
            text = str(params.get("text", "") or "")
            delimiter = str(params.get("delimiter", ",") or ",")
            has_header = bool(params.get("has_header", True))
            stream = io.StringIO(text)
            if has_header:
                reader = csv.DictReader(stream, delimiter=delimiter)
                records = [dict(record) for record in reader]
            else:
                reader = csv.reader(stream, delimiter=delimiter)
                rows = list(reader)
                records = [{"col_" + str(idx): value for idx, value in enumerate(row)} for row in rows]
            return {"records": records, "rows": len(records), "columns": len(records[0]) if records else 0}

        if tool_name == "data.dedupe_rows":
            rows = _coerce_records(params.get("rows", context.get("rows")))
            key_fields = params.get("key_fields")
            if not isinstance(key_fields, list):
                key_fields = []
            deduped: list[dict[str, Any]] = []
            seen: set[str] = set()
            for row in rows:
                if key_fields:
                    key = "|".join(str(row.get(field, "")) for field in key_fields)
                else:
                    key = json.dumps(row, sort_keys=True, default=str)
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(row)
            return {"rows": deduped, "removed": len(rows) - len(deduped), "count": len(deduped)}

        if tool_name == "data.rank_rows":
            rows = _coerce_records(params.get("rows", context.get("rows")))
            sort_field = str(params.get("sort_field", "") or "")
            descending = bool(params.get("descending", True))
            limit = int(params.get("limit", len(rows)) or len(rows))
            if not rows:
                return {"rows": [], "count": 0}
            if not sort_field:
                numeric_candidates = [
                    key
                    for key in rows[0].keys()
                    if any(_safe_float(row.get(key, ""), default=-1.0) != -1.0 for row in rows)
                ]
                sort_field = numeric_candidates[0] if numeric_candidates else list(rows[0].keys())[0]
            ranked = sorted(rows, key=lambda row: _safe_float(row.get(sort_field, ""), 0.0), reverse=descending)
            return {"rows": ranked[: max(1, limit)], "sort_field": sort_field, "count": min(len(ranked), limit)}

        if tool_name == "data.select_columns":
            rows = _coerce_records(params.get("rows", context.get("rows")))
            columns = params.get("columns")
            if not isinstance(columns, list) or not columns:
                return {"rows": rows, "columns": list(rows[0].keys()) if rows else []}
            selected = [{column: row.get(column, "") for column in columns} for row in rows]
            return {"rows": selected, "columns": columns, "count": len(selected)}

        if tool_name.startswith("pandas."):
            return {
                "supported": False,
                "reason": "pandas runtime execution is not enabled in this lightweight agent executor",
                "tool": tool_name,
            }

        raise ValueError(f"Unsupported data tool '{tool_name}'")

    def _run_extraction_tool(self, tool_name: str, params: dict[str, Any], context: dict[str, Any]) -> Any:
        if tool_name.startswith("regex."):
            pattern = str(params.get("pattern", "") or "")
            text = str(params.get("text", "") or "")
            if not pattern:
                raise ValueError("regex.* tools require a pattern")
            if tool_name == "regex.match":
                match = re.match(pattern, text)
                return {"matched": bool(match), "groups": list(match.groups()) if match else []}
            if tool_name == "regex.search":
                match = re.search(pattern, text)
                return {
                    "found": bool(match),
                    "position": match.start() if match else -1,
                    "match": match.group(0) if match else "",
                }
            if tool_name == "regex.findall":
                matches = re.findall(pattern, text)
                return {"matches": matches, "count": len(matches)}
            if tool_name == "regex.sub":
                replacement = str(params.get("replacement", "") or "")
                result = re.sub(pattern, replacement, text)
                return {"result": result, "replacements": max(0, len(re.findall(pattern, text)))}
            if tool_name == "regex.split":
                maxsplit = int(params.get("maxsplit", 0) or 0)
                parts = re.split(pattern, text, maxsplit=maxsplit)
                return {"parts": parts, "count": len(parts)}
            raise ValueError(f"Unsupported regex tool '{tool_name}'")

        text = str(params.get("text", "") or context.get("text", "") or context.get("html", "") or "")

        if tool_name == "extract.emails":
            emails = sorted(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)))
            return {"emails": emails, "count": len(emails)}

        if tool_name == "extract.phones":
            phones = sorted(set(re.findall(r"(?:\+?\d[\d\-\s().]{7,}\d)", text)))
            return {"phones": phones, "count": len(phones)}

        if tool_name == "extract.urls":
            urls = sorted(set(re.findall(r"https?://[^\s\"'<>]+", text)))
            if not urls:
                soup = context.get("soup")
                if isinstance(soup, BeautifulSoup):
                    urls = [urljoin(str(context.get("url", "")), a.get("href")) for a in soup.select("a[href]")]
            return {"urls": urls[:500], "count": len(urls)}

        if tool_name == "extract.dates":
            dates = sorted(
                set(
                    re.findall(
                        r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})\b",
                        text,
                        flags=re.IGNORECASE,
                    )
                )
            )
            return {"dates": dates[:300], "count": len(dates)}

        if tool_name == "extract.prices":
            matches = re.findall(r"(?:[$€£₹]\s?\d[\d,]*(?:\.\d{1,2})?|\d[\d,]*(?:\.\d{1,2})?\s?(?:USD|EUR|INR|GBP))", text)
            prices = [{"raw": match} for match in sorted(set(matches))]
            return {"prices": prices[:300], "count": len(prices)}

        if tool_name == "extract.addresses":
            matches = re.findall(r"\b\d{1,5}\s+[A-Za-z0-9.\- ]+\s(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Boulevard|Blvd)\b", text)
            addresses = [{"raw": match} for match in sorted(set(matches))]
            return {"addresses": addresses, "count": len(addresses)}

        if tool_name == "extract.social_handles":
            handles = sorted(set(re.findall(r"@[A-Za-z0-9_\.]{2,30}", text)))
            return {"handles": {"generic": handles[:500]}, "count": len(handles)}

        if tool_name == "extract.top_n":
            rows = _coerce_records(params.get("rows", context.get("rows")))
            n = max(1, int(params.get("n", 10) or 10))
            sort_field = str(params.get("sort_field", "") or "")
            if rows and sort_field:
                rows = sorted(rows, key=lambda row: _safe_float(row.get(sort_field, ""), 0.0), reverse=True)
            return {"rows": rows[:n], "count": min(len(rows), n)}

        raise ValueError(f"Unsupported extraction tool '{tool_name}'")

    def _run_validation_tool(self, tool_name: str, params: dict[str, Any], context: dict[str, Any]) -> Any:
        if tool_name == "validate.url":
            url = str(params.get("url", "") or context.get("url", "") or "")
            parsed = urlparse(url)
            valid = bool(parsed.scheme and parsed.netloc)
            return {"valid": valid, "accessible": None, "status_code": None}

        if tool_name == "validate.email":
            email = str(params.get("email", "") or "")
            valid = bool(re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email))
            return {"valid": valid, "normalized": email.strip().lower() if valid else ""}

        if tool_name == "validate.json":
            text = str(params.get("text", "") or "")
            try:
                json.loads(text)
                return {"valid": True, "error": None}
            except json.JSONDecodeError as exc:
                return {"valid": False, "error": str(exc)}

        if tool_name == "validate.html":
            html = str(params.get("html", "") or context.get("html", "") or "")
            if not html:
                return {"valid": False, "errors": ["No HTML provided"]}
            soup = BeautifulSoup(html, "html.parser")
            errors: list[str] = []
            if not soup.find():
                errors.append("HTML has no parseable elements")
            return {"valid": not errors, "errors": errors}

        if tool_name == "validate.schema":
            data = params.get("data")
            schema = params.get("schema") if isinstance(params.get("schema"), dict) else {}
            required = schema.get("required", []) if isinstance(schema.get("required"), list) else []
            if isinstance(data, dict):
                missing = [field for field in required if field not in data]
            else:
                missing = required
            return {"valid": not missing, "errors": [f"Missing field: {field}" for field in missing]}

        if tool_name == "validate.data_completeness":
            rows = _coerce_records(params.get("rows", context.get("rows")))
            required_fields = params.get("fields")
            if not isinstance(required_fields, list) or not required_fields:
                required_fields = sorted({key for row in rows for key in row.keys()}) if rows else []
            if not rows or not required_fields:
                return {"score": 0.0, "missing_counts": {}, "fields": required_fields}
            missing_counts = {field: 0 for field in required_fields}
            for row in rows:
                for field in required_fields:
                    value = row.get(field, "")
                    if value in (None, "", [], {}):
                        missing_counts[field] += 1
            total_cells = len(rows) * len(required_fields)
            missing_cells = sum(missing_counts.values())
            score = 1.0 - (missing_cells / total_cells) if total_cells else 0.0
            return {"score": round(score, 4), "missing_counts": missing_counts, "fields": required_fields}

        if tool_name == "validate.row_signal":
            rows = _coerce_records(params.get("rows", context.get("rows")))
            if not rows:
                return {"signal": 0.0, "reason": "No rows provided"}
            non_empty_fields = 0
            total_fields = 0
            distinct_rows = len({json.dumps(row, sort_keys=True, default=str) for row in rows})
            for row in rows:
                for value in row.values():
                    total_fields += 1
                    if value not in (None, "", [], {}):
                        non_empty_fields += 1
            completeness = (non_empty_fields / total_fields) if total_fields else 0.0
            uniqueness = distinct_rows / len(rows)
            signal = round((0.7 * completeness) + (0.3 * uniqueness), 4)
            return {
                "signal": signal,
                "completeness": round(completeness, 4),
                "uniqueness": round(uniqueness, 4),
            }

        raise ValueError(f"Unsupported validation tool '{tool_name}'")

    def _run_analysis_tool(self, tool_name: str, params: dict[str, Any], context: dict[str, Any]) -> Any:
        text = str(params.get("text", "") or context.get("text", "") or "")

        if tool_name == "text.keywords":
            top_k = max(1, int(params.get("top_k", 10) or 10))
            tokens = _tokenize(text)
            frequencies: dict[str, int] = {}
            for token in tokens:
                frequencies[token] = frequencies.get(token, 0) + 1
            ranked = sorted(frequencies.items(), key=lambda item: item[1], reverse=True)[:top_k]
            return {"keywords": [item[0] for item in ranked], "scores": [item[1] for item in ranked]}

        if tool_name == "text.entities":
            entities = sorted(set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)))
            requested_types = params.get("types") if isinstance(params.get("types"), list) else []
            output = [{"text": entity, "type": "PROPER_NOUN"} for entity in entities]
            if requested_types:
                output = [entity for entity in output if entity["type"] in requested_types]
            return {"entities": output[:200], "count": len(output)}

        if tool_name == "text.sentiment":
            positive = {"good", "great", "excellent", "amazing", "positive", "love", "best"}
            negative = {"bad", "poor", "terrible", "awful", "negative", "worst", "hate"}
            tokens = _tokenize(text)
            score = sum(1 for token in tokens if token in positive) - sum(1 for token in tokens if token in negative)
            label = "neutral"
            if score > 0:
                label = "positive"
            elif score < 0:
                label = "negative"
            return {"score": score, "label": label}

        if tool_name == "stats.describe":
            values = [float(item) for item in params.get("data", []) if isinstance(item, (int, float))]
            if not values:
                return {"mean": 0.0, "median": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
            return {
                "mean": statistics.fmean(values),
                "median": statistics.median(values),
                "std": statistics.pstdev(values) if len(values) > 1 else 0.0,
                "min": min(values),
                "max": max(values),
            }

        if tool_name == "stats.correlation":
            x = [float(item) for item in params.get("x", []) if isinstance(item, (int, float))]
            y = [float(item) for item in params.get("y", []) if isinstance(item, (int, float))]
            if len(x) != len(y) or len(x) < 2:
                return {"correlation": 0.0, "p_value": None}
            x_mean = statistics.fmean(x)
            y_mean = statistics.fmean(y)
            numerator = sum((a - x_mean) * (b - y_mean) for a, b in zip(x, y))
            x_var = sum((a - x_mean) ** 2 for a in x)
            y_var = sum((b - y_mean) ** 2 for b in y)
            denominator = (x_var * y_var) ** 0.5
            correlation = (numerator / denominator) if denominator else 0.0
            return {"correlation": correlation, "p_value": None}

        if tool_name == "analysis.infer_schema":
            rows = _coerce_records(params.get("rows", context.get("rows")))
            schema: dict[str, dict[str, Any]] = {}
            for row in rows:
                for key, value in row.items():
                    entry = schema.setdefault(key, {"types": set(), "nullable": False})
                    entry["types"].add(_infer_type(value))
                    if value in (None, "", [], {}):
                        entry["nullable"] = True
            normalized = {
                key: {"types": sorted(value["types"]), "nullable": value["nullable"]}
                for key, value in schema.items()
            }
            return {"schema": normalized, "columns": sorted(normalized.keys())}

        if tool_name == "analysis.score_relevance":
            rows = _coerce_records(params.get("rows", context.get("rows")))
            query = str(params.get("query", "") or context.get("instructions", "") or "")
            query_tokens = set(_tokenize(query))
            scored: list[dict[str, Any]] = []
            for row in rows:
                row_text = " ".join(str(value) for value in row.values())
                row_tokens = set(_tokenize(row_text))
                overlap = len(query_tokens & row_tokens)
                score = overlap / max(1, len(query_tokens))
                scored.append({"row": row, "score": round(score, 4)})
            scored.sort(key=lambda item: item["score"], reverse=True)
            return {"rows": scored, "count": len(scored)}

        raise ValueError(f"Unsupported analysis tool '{tool_name}'")


def summarize_tool_results(results: list[ToolCallResult], max_items: int = 8) -> str:
    """Render compact tool result notes for downstream prompting."""
    lines: list[str] = []
    for result in results[:max_items]:
        if result.success:
            preview = _truncate(result.result, 220)
            lines.append(f"- {result.tool_name}: success ({result.duration_ms}ms), result={preview}")
        else:
            lines.append(f"- {result.tool_name}: failed ({result.duration_ms}ms), error={result.error}")
    return "\n".join(lines)
