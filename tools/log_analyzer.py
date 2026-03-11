"""
IncidentIQ - Log Analyzer Tool
Parses raw error logs and stack traces into structured incident context.
Supports: Python, Java, JavaScript/Node.js, Go, Ruby, C#
"""

import re
import json
from typing import Optional
from langchain_core.tools import tool


SEVERITY_PATTERNS = {
    "CRITICAL": [
        r"OutOfMemoryError", r"StackOverflowError", r"FATAL", r"OOMKilled",
        r"kernel panic", r"segfault", r"core dump", r"deadlock",
        r"data corruption", r"connection refused.*database",
    ],
    "HIGH": [
        r"NullPointerException", r"TypeError.*undefined", r"ConnectionError",
        r"TimeoutError", r"500 Internal Server", r"503 Service Unavailable",
        r"circuit.?breaker.*open", r"pool.*exhaust",
    ],
    "MEDIUM": [
        r"ValueError", r"IllegalArgumentException", r"404 Not Found",
        r"rate.?limit", r"deprecated", r"retry.*fail",
    ],
    "LOW": [
        r"WARNING", r"WARN", r"DeprecationWarning", r"slow query",
    ],
}

LANGUAGE_PATTERNS = {
    "python": {
        "markers": [r"Traceback \(most recent call last\)", r"File \".*\.py\"", r"\.py\", line \d+"],
        "error_extract": r"(\w+Error|\w+Exception|\w+Warning):\s*(.+)",
        "frame_extract": r'File "(.+?)", line (\d+), in (.+)',
    },
    "java": {
        "markers": [r"at [\w.$]+\([\w.]+\.java:\d+\)", r"Exception in thread", r"\.java:\d+\)"],
        "error_extract": r"([\w.]*(?:Exception|Error)):\s*(.*)",
        "frame_extract": r"at ([\w.$]+)\(([\w.]+\.java):(\d+)\)",
    },
    "javascript": {
        "markers": [r"at [\w./<>]+ \(.+\.js:\d+:\d+\)", r"\.js:\d+:\d+", r"node_modules/"],
        "error_extract": r"(\w+Error|\w+Exception):\s*(.*)",
        "frame_extract": r"at (?:(\S+) )?\(?(.+?):(\d+):(\d+)\)?",
    },
    "go": {
        "markers": [r"goroutine \d+", r"\.go:\d+", r"panic:"],
        "error_extract": r"panic:\s*(.*)|fatal error:\s*(.*)",
        "frame_extract": r"(\S+\.go):(\d+)",
    },
    "ruby": {
        "markers": [r"\.rb:\d+:in", r"from .+\.rb:\d+"],
        "error_extract": r"(\w+Error|\w+Exception):\s*(.*)",
        "frame_extract": r"(.+\.rb):(\d+):in `(.+)'",
    },
    "csharp": {
        "markers": [r"at [\w.]+\(.*\) in .+\.cs:line \d+", r"\.cs:line \d+"],
        "error_extract": r"(System\.[\w.]*Exception|[\w.]*Exception):\s*(.*)",
        "frame_extract": r"at (.+) in (.+\.cs):line (\d+)",
    },
}

SERVICE_PATTERNS = [
    r"(?:service|svc|app|api|server)[=:\s/]+([A-Za-z][\w-]+)",
    r"([A-Za-z][\w-]*(?:Service|Controller|Handler|Manager|Worker|Server|Gateway|Proxy))",
    r"\[([A-Za-z][\w-]+)\]",  # bracketed service names like [payment-service]
]


def detect_language(log_text: str) -> str:
    """Detect the programming language from log/stack trace patterns."""
    scores = {}
    for lang, patterns in LANGUAGE_PATTERNS.items():
        score = 0
        for marker in patterns["markers"]:
            matches = re.findall(marker, log_text)
            score += len(matches)
        scores[lang] = score
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "unknown"


def extract_error_info(log_text: str, language: str) -> dict:
    """Extract the primary error type and message."""
    if language in LANGUAGE_PATTERNS:
        pattern = LANGUAGE_PATTERNS[language]["error_extract"]
        match = re.search(pattern, log_text)
        if match:
            groups = [g for g in match.groups() if g]
            return {
                "error_type": groups[0] if groups else "Unknown",
                "error_message": groups[1] if len(groups) > 1 else groups[0],
            }
    # Fallback: look for common patterns
    generic = re.search(r"(ERROR|FATAL|CRITICAL)[:\s]+(.+?)(?:\n|$)", log_text, re.IGNORECASE)
    if generic:
        return {"error_type": generic.group(1), "error_message": generic.group(2).strip()}
    return {"error_type": "Unknown", "error_message": log_text[:200].strip()}


def extract_stack_frames(log_text: str, language: str) -> list:
    """Extract stack trace frames."""
    frames = []
    if language in LANGUAGE_PATTERNS:
        pattern = LANGUAGE_PATTERNS[language]["frame_extract"]
        for match in re.finditer(pattern, log_text):
            groups = match.groups()
            frames.append({
                "file": groups[0] if groups else "",
                "line": groups[1] if len(groups) > 1 else "",
                "function": groups[2] if len(groups) > 2 else "",
            })
    return frames[:10]  # Top 10 frames


def detect_severity(log_text: str) -> str:
    """Detect incident severity based on error patterns."""
    for severity, patterns in SEVERITY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, log_text, re.IGNORECASE):
                return severity
    return "MEDIUM"


def extract_services(log_text: str) -> list:
    """Extract service/component names mentioned in the log."""
    services = set()
    for pattern in SERVICE_PATTERNS:
        for match in re.finditer(pattern, log_text):
            name = match.group(1)
            if len(name) > 2 and name.lower() not in {"the", "and", "for", "error", "warning", "info", "debug"}:
                services.add(name)
    return list(services)[:5]


def extract_timestamps(log_text: str) -> list:
    """Extract timestamps from log entries."""
    patterns = [
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",
        r"\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}",
        r"\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}",
    ]
    timestamps = []
    for pattern in patterns:
        timestamps.extend(re.findall(pattern, log_text))
    return timestamps[:5]


@tool
def analyze_log(log_text: str) -> str:
    """
    Analyze a raw error log or stack trace and extract structured incident context.
    
    Takes raw log text and returns: detected language, error type, error message,
    severity level, affected services, stack frames, and timestamps.
    Use this tool FIRST when investigating any incident to understand what happened.
    
    Args:
        log_text: The raw error log, stack trace, or incident description to analyze.
    """
    language = detect_language(log_text)
    error_info = extract_error_info(log_text, language)
    frames = extract_stack_frames(log_text, language)
    severity = detect_severity(log_text)
    services = extract_services(log_text)
    timestamps = extract_timestamps(log_text)

    result = {
        "detected_language": language,
        "error_type": error_info["error_type"],
        "error_message": error_info["error_message"],
        "severity": severity,
        "affected_services": services,
        "stack_frames": frames,
        "timestamps": timestamps,
        "total_lines": len(log_text.strip().split("\n")),
        "search_query_suggestion": f"{error_info['error_type']} {error_info['error_message'][:80]}",
    }

    return json.dumps(result, indent=2)


# For direct testing
if __name__ == "__main__":
    sample_python_log = """
    Traceback (most recent call last):
      File "/app/services/payment_service.py", line 142, in process_payment
        result = db_pool.execute(query, params)
      File "/app/db/connection.py", line 89, in execute
        conn = self._get_connection()
      File "/app/db/connection.py", line 45, in _get_connection
        raise ConnectionError("Connection pool exhausted: max_connections=20 reached")
    ConnectionError: Connection pool exhausted: max_connections=20 reached
    
    2024-01-15T03:42:18.234Z [PaymentService] ERROR - Failed to process payment for order_id=ORD-98234
    """
    print(analyze_log.invoke(sample_python_log))
