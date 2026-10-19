#!/usr/bin/env python3
"""A small SAS-to-R converter for common DATA steps and simple procedures.

This is intentionally a basic converter.  It produces base-R code and does not
try to cover the full SAS language.  Unsupported features are reported as
warnings (and, where useful, as TODO comments in the generated R script).

Usage:
    python3 sas_to_r.py input.sas
    python3 sas_to_r.py input.sas -o output.R
    python3 sas_to_r.py input.sas --stdout
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ConversionResult:
    code: str
    warnings: list[str] = field(default_factory=list)


class ConversionError(Exception):
    """Raised for input that cannot be converted at all."""


# ---------------------------------------------------------------------------
# Helpers used by the generated R code
# ---------------------------------------------------------------------------

HELPER_CODE = {
    ".sas_mean": (
        ".sas_mean <- function(...) {\n"
        "  args <- list(...)\n"
        "  if (length(args) == 1L) return(args[[1L]])\n"
        "  values <- do.call(cbind, args)\n"
        "  result <- rowMeans(values, na.rm = TRUE)\n"
        "  result[is.nan(result)] <- NA_real_\n"
        "  result\n"
        "}"
    ),
    ".sas_sum": (
        ".sas_sum <- function(...) {\n"
        "  args <- list(...)\n"
        "  if (length(args) == 1L) return(args[[1L]])\n"
        "  rowSums(do.call(cbind, args), na.rm = TRUE)\n"
        "}"
    ),
    ".sas_min": (
        ".sas_min <- function(...) {\n"
        "  args <- list(...)\n"
        "  if (length(args) == 1L) return(args[[1L]])\n"
        "  do.call(pmin, c(args, list(na.rm = TRUE)))\n"
        "}"
    ),
    ".sas_max": (
        ".sas_max <- function(...) {\n"
        "  args <- list(...)\n"
        "  if (length(args) == 1L) return(args[[1L]])\n"
        "  do.call(pmax, c(args, list(na.rm = TRUE)))\n"
        "}"
    ),
    ".sas_median": (
        ".sas_median <- function(...) {\n"
        "  args <- list(...)\n"
        "  if (length(args) == 1L) return(args[[1L]])\n"
        "  apply(do.call(cbind, args), 1, median, na.rm = TRUE)\n"
        "}"
    ),
    ".sas_sd": (
        ".sas_sd <- function(...) {\n"
        "  args <- list(...)\n"
        "  values <- do.call(cbind, args)\n"
        "  result <- apply(values, 1, sd, na.rm = TRUE)\n"
        "  result[rowSums(!is.na(values)) == 1L] <- 0\n"
        "  result\n"
        "}"
    ),
    ".sas_var": (
        ".sas_var <- function(...) {\n"
        "  args <- list(...)\n"
        "  values <- do.call(cbind, args)\n"
        "  result <- apply(values, 1, var, na.rm = TRUE)\n"
        "  result[rowSums(!is.na(values)) == 1L] <- 0\n"
        "  result\n"
        "}"
    ),
    ".sas_summary": (
        ".sas_summary <- function(x) {\n"
        "  values <- x[!is.na(x)]\n"
        "  n <- length(values)\n"
        "  c(\n"
        "    n = n,\n"
        "    mean = if (n > 0) mean(values) else NA_real_,\n"
        "    sd = if (n > 1) sd(values) else NA_real_,\n"
        "    min = if (n > 0) min(values) else NA_real_,\n"
        "    max = if (n > 0) max(values) else NA_real_\n"
        "  )\n"
        "}"
    ),
}


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def extract_datalines(text: str) -> tuple[str, dict[str, list[str]]]:
    """Replace DATALINES/CARDS blocks with placeholders.

    A data block runs from a line containing ``datalines;`` (or ``cards;``)
    until the next line that consists only of a semicolon.
    """
    lines = text.splitlines()
    out: list[str] = []
    blocks: dict[str, list[str]] = {}
    keyword_re = re.compile(r"(?i)(?<![\w])(datalines|cards)\s*;")
    index = 0
    i = 0

    while i < len(lines):
        line = lines[i]
        match = keyword_re.search(line)
        if not match:
            out.append(line)
            i += 1
            continue

        placeholder = f"__DATALINES_{index}__"
        out.append(line[: match.start()] + placeholder + ";" + line[match.end() :])
        i += 1

        data_lines: list[str] = []
        while i < len(lines) and not re.fullmatch(r"\s*;\s*", lines[i]):
            data_lines.append(lines[i])
            i += 1
        if i >= len(lines):
            raise ConversionError(
                "Found DATALINES without a closing line containing only ';'."
            )
        i += 1  # Skip the line containing the closing semicolon.

        blocks[placeholder] = data_lines
        index += 1

    return "\n".join(out), blocks


def strip_comments(text: str) -> str:
    """Remove SAS block comments and ``* ... ;`` comment statements."""
    out: list[str] = []
    i = 0
    n = len(text)
    quote: str | None = None
    statement_start = True

    while i < n:
        ch = text[i]

        if quote is not None:
            out.append(ch)
            if ch == quote:
                # SAS escapes a quote by doubling it.
                if i + 1 < n and text[i + 1] == quote:
                    out.append(quote)
                    i += 2
                    continue
                quote = None
            i += 1
            continue

        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end == -1:
                raise ConversionError("Unterminated /* ... */ comment.")
            out.append(" ")
            i = end + 2
            continue

        if ch in "'\"":
            quote = ch
            out.append(ch)
            statement_start = False
            i += 1
            continue

        if statement_start and ch == "*":
            # A SAS comment statement: * comment text ;
            j = i + 1
            inner_quote: str | None = None
            while j < n:
                c = text[j]
                if inner_quote is not None:
                    if c == inner_quote:
                        if j + 1 < n and text[j + 1] == inner_quote:
                            j += 2
                            continue
                        inner_quote = None
                elif c in "'\"":
                    inner_quote = c
                elif c == ";":
                    j += 1
                    break
                j += 1
            out.append(" ")
            i = j
            continue

        out.append(ch)
        if ch == ";":
            statement_start = True
        elif not ch.isspace():
            statement_start = False
        i += 1

    return "".join(out)


def split_statements(text: str) -> list[str]:
    """Split SAS text on semicolons that are outside quoted strings."""
    statements: list[str] = []
    start = 0
    i = 0
    n = len(text)
    quote: str | None = None

    while i < n:
        ch = text[i]
        if quote is not None:
            if ch == quote:
                if i + 1 < n and text[i + 1] == quote:
                    i += 2
                    continue
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == ";":
            statements.append(text[start:i])
            start = i + 1
        i += 1

    if text[start:].strip():
        statements.append(text[start:])
    return statements


def normalize_whitespace(text: str) -> str:
    """Collapse whitespace, but leave whitespace inside strings alone."""
    out: list[str] = []
    pending_space = False
    quote: str | None = None
    i = 0

    while i < len(text):
        ch = text[i]
        if quote is not None:
            out.append(ch)
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    out.append(quote)
                    i += 2
                    continue
                quote = None
            i += 1
            continue

        if ch in "'\"":
            if pending_space and out:
                out.append(" ")
            pending_space = False
            quote = ch
            out.append(ch)
        elif ch.isspace():
            pending_space = True
        else:
            if pending_space and out:
                out.append(" ")
            pending_space = False
            out.append(ch)
        i += 1

    return "".join(out).strip()


def first_word(text: str) -> str:
    match = re.match(r"\s*([A-Za-z_%][A-Za-z0-9_%]*)", text)
    return match.group(1).lower() if match else ""


def r_string(value: str) -> str:
    """Return a double-quoted R string literal."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def sas_string_to_plain(raw: str) -> str:
    """Turn a SAS quoted string literal into plain text."""
    if len(raw) < 2 or raw[0] not in "'\"":
        return raw
    quote = raw[0]
    body = raw[1:-1]
    return body.replace(quote * 2, quote)


def dataset_r_name(sas_name: str) -> str:
    """Map a SAS dataset reference to an R object name."""
    name = sas_name.strip().strip("'\"")
    name = name.split(".")[-1]
    name = re.sub(r"[^A-Za-z0-9_.]", "_", name)
    if not name:
        return "data"
    if not re.match(r"[A-Za-z]", name):
        name = "data_" + name
    if name in {
        "if", "else", "repeat", "while", "function", "for", "in", "next",
        "break", "TRUE", "FALSE", "NULL", "Inf", "NaN", "NA", "invisible",
    }:
        name += "_"
    return name


def parse_var_list(text: str) -> list[str]:
    """Extract SAS variable names from a simple variable list."""
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)


def split_model_equation(text: str) -> tuple[str, str] | None:
    """Split a SAS MODEL equation at the first top-level '='."""
    depth = 0
    quote: str | None = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote is not None:
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    i += 2
                    continue
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "=" and depth == 0:
            return text[:i], text[i + 1 :]
        i += 1
    return None


def datalines_text(lines: list[str], types: list[str] | None) -> str:
    """Join DATALINES, turning SAS numeric missing values into NA.

    ``read.table(colClasses = "numeric")`` does not accept "." as a missing
    value, while SAS uses "." for numeric missing values.
    """
    if not types:
        return "\n".join(lines)

    prepared: list[str] = []
    missing_re = re.compile(r"\.[A-Za-z_]?")
    for line in lines:
        fields = line.split()
        for index, field in enumerate(fields):
            if index < len(types) and types[index] == "numeric":
                if missing_re.fullmatch(field):
                    fields[index] = "NA"
        prepared.append(" ".join(fields))
    return "\n".join(prepared)


# ---------------------------------------------------------------------------
# Expression translation
# ---------------------------------------------------------------------------

WORD_OPERATORS = {
    "and": "&",
    "or": "|",
    "not": "!",
    "eq": "==",
    "ne": "!=",
    "gt": ">",
    "lt": "<",
    "ge": ">=",
    "le": "<=",
}

CONSTANTS = {
    "true": "TRUE",
    "false": "FALSE",
    "null": "NULL",
    "na": "NA",
    "nan": "NaN",
    "inf": "Inf",
    "pi": "pi",
}

FUNCTIONS = {
    "abs": "abs",
    "ceil": "ceiling",
    "ceiling": "ceiling",
    "date": "Sys.Date",
    "day": "as.integer(format",
    "exp": "exp",
    "floor": "floor",
    "int": "trunc",
    "length": "nchar",
    "log": "log",
    "lowcase": "tolower",
    "max": ".sas_max",
    "mean": ".sas_mean",
    "median": ".sas_median",
    "min": ".sas_min",
    "missing": "is.na",
    "month": "as.integer(format",
    "round": "round",
    "sd": ".sas_sd",
    "sqrt": "sqrt",
    "std": ".sas_sd",
    "strip": "trimws",
    "substr": "substr",
    "sum": ".sas_sum",
    "today": "Sys.Date",
    "toupper": "toupper",
    "tolower": "tolower",
    "trim": "trimws",
    "trimn": "trimws",
    "upcase": "toupper",
    "var": ".sas_var",
    "year": "as.integer(format",
}

PASSTHROUGH_FUNCTIONS = {
    "format", "ifelse", "is.na", "nchar", "paste", "paste0", "seq_len",
    "substr", "substring", "trimws", "toupper", "tolower", "trunc",
}


@dataclass
class Token:
    kind: str
    value: str


def tokenize_expression(expr: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(expr)

    while i < n:
        ch = expr[i]

        if ch.isspace():
            i += 1
            continue

        if ch in "'\"":
            quote = ch
            start = i
            i += 1
            while i < n:
                if expr[i] == quote:
                    if i + 1 < n and expr[i + 1] == quote:
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            tokens.append(Token("string", expr[start:i]))
            continue

        if ch.isalpha() or ch == "_":
            start = i
            i += 1
            while i < n and (expr[i].isalnum() or expr[i] == "_"):
                i += 1
            tokens.append(Token("word", expr[start:i]))
            continue

        if ch.isdigit() or (ch == "." and i + 1 < n and expr[i + 1].isdigit()):
            start = i
            i += 1
            while i < n and (expr[i].isdigit() or expr[i] == "."):
                i += 1
            if i < n and expr[i] in "eE":
                j = i + 1
                if j < n and expr[j] in "+-":
                    j += 1
                if j < n and expr[j].isdigit():
                    i = j + 1
                    while i < n and expr[i].isdigit():
                        i += 1
            tokens.append(Token("number", expr[start:i]))
            continue

        two = expr[i : i + 2]
        if two in {"**", "^=", "<>", "<=", ">=", "!=", "~="}:
            tokens.append(Token("operator", two))
            i += 2
            continue

        tokens.append(Token("operator", ch))
        i += 1

    return tokens


def _render_tokens(tokens: list[str]) -> str:
    out = ""
    binary_ops = {
        "+", "-", "*", "/", "^", "==", "!=", "<", ">", "<=", ">=", "&", "|",
        "!", "~", "%in%",
    }

    for token in tokens:
        if token in {")", "]"}:
            out = out.rstrip() + token
        elif token in {"(", "["}:
            out = out.rstrip() + token
        elif token == ",":
            out = out.rstrip() + ", "
        elif token in binary_ops:
            out = out.rstrip() + f" {token} "
        else:
            if out and not out.endswith((" ", "(", "[")):
                out += " "
            out += token

    return re.sub(r"\s+", " ", out).strip()


def translate_expression(
    expr: str,
    df_name: str,
    used_helpers: set[str],
    warnings: list[str],
) -> str:
    """Translate the common SAS expression syntax used in DATA steps."""
    tokens = tokenize_expression(expr)
    rendered: list[str] = []

    for index, token in enumerate(tokens):
        if token.kind == "string":
            rendered.append(r_string(sas_string_to_plain(token.value)))
            continue

        if token.kind == "number":
            rendered.append(token.value)
            continue

        if token.kind == "word":
            lower = token.value.lower()

            if lower in WORD_OPERATORS:
                rendered.append(WORD_OPERATORS[lower])
                continue
            if lower in CONSTANTS:
                rendered.append(CONSTANTS[lower])
                continue
            if lower in {"_n_", "n_"}:
                rendered.append(f"seq_len(nrow({df_name}))")
                continue

            next_is_call = (
                index + 1 < len(tokens) and tokens[index + 1].value == "("
            )
            if next_is_call:
                function = FUNCTIONS.get(lower)
                if function is None:
                    if lower not in PASSTHROUGH_FUNCTIONS:
                        warnings.append(
                            f"SAS function '{token.value}' is not translated; "
                            "check the generated R expression."
                        )
                    function = token.value
                if function.startswith(".sas_"):
                    used_helpers.add(function)
                # Functions that need a format argument are only partially
                # supported; keep the R call valid but leave a warning.
                if function == "as.integer(format":
                    warnings.append(
                        f"SAS date function '{token.value}' needs manual "
                        "formatting in R."
                    )
                    function = "as.integer(format"
                rendered.append(function)
                continue

            rendered.append(f"{df_name}${token.value}")
            continue

        value = token.value
        if value == "**":
            value = "^"
        elif value in {"^=", "<>", "~="}:
            value = "!="
        elif value == "=":
            value = "=="
        elif value == ".":
            value = "NA_real_"
        rendered.append(value)

    result = _render_tokens(rendered)

    # SAS comparisons with numeric missing values are usually written as
    # "x = ." / "x ne .".  Translate those to is.na().
    column = r"([A-Za-z_][A-Za-z0-9_]*\$[A-Za-z_][A-Za-z0-9_]*)"
    result = re.sub(
        rf"{column}\s*==\s*NA_real_", r"is.na(\1)", result
    )
    result = re.sub(
        rf"NA_real_\s*==\s*{column}", r"is.na(\1)", result
    )
    result = re.sub(
        rf"{column}\s*!=\s*NA_real_", r"!is.na(\1)", result
    )
    result = re.sub(
        rf"NA_real_\s*!=\s*{column}", r"!is.na(\1)", result
    )
    return result


# ---------------------------------------------------------------------------
# Converter
# ---------------------------------------------------------------------------

class SasToRConverter:
    def __init__(self, source_name: str = "<string>") -> None:
        self.source_name = source_name
        self.warnings: list[str] = []
        self.used_helpers: set[str] = set()
        self.dataset_names: dict[str, str] = {}
        self.last_dataset: str | None = None
        self.body: list[str] = []
        self.pca_index = 0
        self.cfa_index = 0
        self.reg_index = 0
        self.freq_index = 0
        self.logit_index = 0

    # -- small utilities -------------------------------------------------

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def register_dataset(self, sas_name: str, r_name: str) -> None:
        self.dataset_names[sas_name.lower()] = r_name
        self.last_dataset = r_name

    def resolve_dataset(self, sas_name: str) -> str:
        raw = sas_name.strip().strip("'\"")
        if raw.lower() == "_last_":
            if self.last_dataset:
                return self.last_dataset
            self.warn("DATA=_LAST_ was used before any dataset was created.")
            return "last_dataset"
        key = raw.lower()
        if key in self.dataset_names:
            return self.dataset_names[key]
        return dataset_r_name(raw)

    def add_lines(self, lines: list[str]) -> None:
        if self.body and lines and self.body[-1] != "":
            self.body.append("")
        self.body.extend(lines)

    # -- top level -------------------------------------------------------

    def convert(self, sas_code: str) -> ConversionResult:
        text, datalines = extract_datalines(sas_code)
        text = strip_comments(text)
        statements = [
            normalize_whitespace(statement)
            for statement in split_statements(text)
            if statement.strip()
        ]

        i = 0
        while i < len(statements):
            statement = statements[i]
            keyword = first_word(statement)

            if keyword == "data":
                i = self._handle_data_step(statements, i, datalines)
            elif keyword == "proc":
                i = self._handle_proc(statements, i)
            elif keyword in {"run", "quit"}:
                i += 1
            elif keyword == "libname":
                self.warn(
                    "LIBNAME statements are ignored; generated R code uses "
                    "the dataset's table name only."
                )
                i += 1
            elif keyword in {"title", "footnote", "options", "ods", "x", "dm"}:
                # Presentation/global statements have no direct base-R
                # equivalent and are intentionally skipped.
                i += 1
            elif keyword.startswith("%"):
                self.warn(f"SAS macro statement not converted: {statement}")
                self.body.append(f"# TODO: SAS macro statement: {statement}")
                i += 1
            elif keyword in {"filename", "infile"}:
                self.warn(
                    f"External-file statement not converted: {statement}"
                )
                self.body.append(f"# TODO: external file statement: {statement}")
                i += 1
            else:
                self.warn(f"Unsupported top-level statement: {statement}")
                self.body.append(f"# TODO: unsupported SAS statement: {statement}")
                i += 1

        header = [
            f"# Converted from {Path(self.source_name).name} by sas_to_r.py",
            "# R output; review warnings and generated code before use.",
        ]
        helper_lines: list[str] = []
        for name in HELPER_CODE:
            if name in self.used_helpers:
                helper_lines.extend(["", HELPER_CODE[name]])

        sections = header + helper_lines
        if self.body:
            sections.extend(["", *self.body])

        return ConversionResult(
            code="\n".join(sections).rstrip() + "\n",
            warnings=self.warnings,
        )

    # -- DATA steps ------------------------------------------------------

    def _handle_data_step(
        self,
        statements: list[str],
        start: int,
        datalines: dict[str, list[str]],
    ) -> int:
        header = statements[start]
        match = re.match(r"(?is)^data\s+([^\s/;]+)", header)
        if not match:
            self.warn(f"Could not read dataset name from: {header}")
            return start + 1

        sas_name = match.group(1)
        if sas_name.lower() == "_null_" or sas_name.lower().endswith("._null_"):
            self.warn("DATA _NULL_ is not supported; the step was skipped.")
            self.body.append(f"# TODO: DATA _NULL_ step: {header}")
            return self._find_block_end(statements, start + 1)

        r_name = dataset_r_name(sas_name)
        self.register_dataset(sas_name, r_name)
        step_statements, next_index = self._collect_block(statements, start + 1)
        self.add_lines(
            self._convert_data_step(sas_name, r_name, step_statements, datalines)
        )
        return next_index

    def _convert_data_step(
        self,
        sas_name: str,
        r_name: str,
        statements: list[str],
        datalines: dict[str, list[str]],
    ) -> list[str]:
        lines = [f"# ---- data step: {sas_name} ----"]

        source: str | None = None
        input_vars: list[str] | None = None
        input_types: list[str] | None = None
        data_block: list[str] | None = None
        input_seen = False

        # First pass: find the input source, input variables and DATALINES.
        for statement in statements:
            keyword = first_word(statement)
            if keyword == "set":
                body = re.sub(r"(?is)^set\s+", "", statement).strip()
                name = body.split()[0] if body else ""
                if not name:
                    self.warn(f"Could not read dataset name from: {statement}")
                elif source is not None:
                    self.warn("Only the first SET statement is used.")
                else:
                    source = self.resolve_dataset(name)
            elif keyword == "merge":
                self.warn(f"MERGE is not supported: {statement}")
            elif keyword == "input":
                input_seen = True
                input_vars, input_types = self._parse_input(statement)
            elif statement.upper().startswith("__DATALINES_"):
                if data_block is not None:
                    self.warn("Only the first DATALINES block is used.")
                data_block = datalines.get(statement.upper(), [])
            elif keyword == "infile":
                self.warn(
                    "INFILE is not supported; DATALINES input is assumed."
                )

        if source is not None and data_block is not None:
            self.warn(
                "Both SET and DATALINES are present; SET is used as the "
                "input source."
            )
            data_block = None

        # Initialise the R data frame.
        if source is not None:
            lines.append(f"{r_name} <- {source}")
            known_columns: set[str] | None = None
        elif data_block is not None:
            if input_vars is None:
                self.warn(
                    "DATALINES was found without a usable INPUT statement; "
                    "the data block was skipped."
                )
                lines.append(f"{r_name} <- data.frame()")
                known_columns = set()
            else:
                text = datalines_text(data_block, input_types)
                lines.append(f"{r_name} <- read.table(")
                lines.append(f"  text = {r_string(text)},")
                lines.append("  header = FALSE,")
                lines.append("  stringsAsFactors = FALSE,")
                lines.append("  comment.char = \"\",")
                if input_types and all(t == "numeric" for t in input_types):
                    lines.append("  colClasses = \"numeric\"")
                elif input_types and all(t == "character" for t in input_types):
                    lines.append("  colClasses = \"character\"")
                elif input_types:
                    classes = ", ".join(r_string(t) for t in input_types)
                    lines.append(f"  colClasses = c({classes})")
                else:
                    lines.append("  colClasses = \"character\"")
                lines.append(")")
                names = ", ".join(r_string(name) for name in input_vars)
                lines.append(f"names({r_name}) <- c({names})")
                known_columns = set(input_vars)
        elif input_seen:
            self.warn(
                "INPUT without DATALINES reads an external file, which this "
                "converter does not handle."
            )
            lines.append(f"{r_name} <- data.frame()")
            known_columns = set()
        else:
            self.warn(
                "DATA step has no SET or DATALINES source; an empty data "
                "frame was generated."
            )
            lines.append(f"{r_name} <- data.frame()")
            known_columns = set()

        assigned: set[str] = set()
        keep_vars: list[str] = []
        drop_vars: list[str] = []
        renames: list[tuple[str, str]] = []
        labels: list[tuple[str, str]] = []

        i = 0
        while i < len(statements):
            statement = statements[i]
            keyword = first_word(statement)
            lower = statement.lower()

            if keyword in {"set", "input", "infile"} or statement.upper().startswith(
                "__DATALINES_"
            ):
                i += 1
                continue

            if keyword == "keep":
                body = re.sub(r"(?is)^keep\s+", "", statement)
                if "_all_" in body.lower():
                    keep_vars = []
                else:
                    if "--" in body:
                        self.warn(
                            f"Variable ranges are not supported in: {statement}"
                        )
                    keep_vars.extend(parse_var_list(body))
                i += 1
                continue

            if keyword == "drop":
                body = re.sub(r"(?is)^drop\s+", "", statement)
                if "--" in body:
                    self.warn(
                        f"Variable ranges are not supported in: {statement}"
                    )
                drop_vars.extend(parse_var_list(body))
                i += 1
                continue

            if keyword == "rename":
                pairs = re.findall(
                    r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)",
                    statement,
                )
                if pairs:
                    renames.extend(pairs)
                else:
                    self.warn(f"Could not read RENAME statement: {statement}")
                i += 1
                continue

            if keyword == "label":
                found = self._parse_labels(statement)
                if found:
                    labels.extend(found)
                else:
                    self.warn(f"Could not read LABEL statement: {statement}")
                i += 1
                continue

            if keyword in {"format", "informat", "attrib", "length"}:
                self.warn(
                    f"SAS {keyword.upper()} statement ignored: {statement}"
                )
                i += 1
                continue

            if keyword in {"retain", "array", "by", "output"}:
                if keyword != "output":
                    self.warn(f"SAS {keyword.upper()} is not supported: {statement}")
                i += 1
                continue

            if keyword in {"do", "end", "select", "when", "otherwise", "link", "return"}:
                self.warn(f"SAS control-flow statement not converted: {statement}")
                lines.append(f"# TODO: SAS statement: {statement}")
                i += 1
                continue

            if keyword == "where":
                body = re.sub(r"(?is)^where\s+", "", statement)
                condition = translate_expression(
                    body, r_name, self.used_helpers, self.warnings
                )
                lines.append(
                    f"{r_name} <- {r_name}[which({condition}), , drop = FALSE]"
                )
                i += 1
                continue

            if keyword == "if":
                i = self._convert_if(
                    statements,
                    i,
                    r_name,
                    lines,
                    known_columns,
                    assigned,
                )
                continue

            if keyword == "else":
                self.warn(f"ELSE without a matching IF was skipped: {statement}")
                i += 1
                continue

            if lower in {"delete", "stop"}:
                self.warn(f"Standalone {keyword.upper()} is not supported.")
                i += 1
                continue

            if keyword in {"file", "put", "list", "call"}:
                self.warn(f"DATA step {keyword.upper()} is not supported: {statement}")
                i += 1
                continue

            assignment = re.match(
                r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", statement, re.S
            )
            if assignment:
                target, expression = assignment.groups()
                converted = translate_expression(
                    expression, r_name, self.used_helpers, self.warnings
                )
                lines.append(f"{r_name}${target} <- {converted}")
                assigned.add(target)
                if known_columns is not None:
                    known_columns.add(target)
                i += 1
                continue

            self.warn(f"Unsupported DATA statement: {statement}")
            lines.append(f"# TODO: unsupported SAS statement: {statement}")
            i += 1

        # Dataset-level metadata and variable selection are applied at the
        # end, matching SAS's output-dataset behaviour.  Renames happen first
        # so KEEP/DROP and LABEL names can be mapped to their final R names.
        rename_map = dict(renames)
        for old, new in renames:
            lines.append(
                f"names({r_name})[names({r_name}) == {r_string(old)}] <- "
                f"{r_string(new)}"
            )

        for variable, label in labels:
            variable = rename_map.get(variable, variable)
            lines.append(f"attr({r_name}${variable}, \"label\") <- {r_string(label)}")

        if keep_vars:
            keep_vars = [rename_map.get(name, name) for name in keep_vars]
            kept = ", ".join(r_string(name) for name in dict.fromkeys(keep_vars))
            lines.append(
                f"{r_name} <- {r_name}[, c({kept}), drop = FALSE]"
            )
        if drop_vars:
            drop_vars = [rename_map.get(name, name) for name in drop_vars]
            dropped = ", ".join(r_string(name) for name in dict.fromkeys(drop_vars))
            lines.append(
                f"{r_name} <- {r_name}[, setdiff(names({r_name}), "
                f"c({dropped})), drop = FALSE]"
            )

        return lines

    def _convert_if(
        self,
        statements: list[str],
        index: int,
        df_name: str,
        lines: list[str],
        known_columns: set[str] | None,
        assigned: set[str],
    ) -> int:
        statement = statements[index]
        match = re.match(r"(?is)^if\s+(.+?)\s+then\s+(.+)$", statement)
        if not match:
            condition_text = re.sub(r"(?is)^if\s+", "", statement).strip()
            condition = translate_expression(
                condition_text, df_name, self.used_helpers, self.warnings
            )
            lines.append(
                f"{df_name} <- {df_name}[which({condition}), , drop = FALSE]"
            )
            return index + 1

        condition_text, action = match.groups()
        condition = translate_expression(
            condition_text, df_name, self.used_helpers, self.warnings
        )

        if action.strip().lower() == "delete":
            lines.append(
                f"{df_name} <- {df_name}[which(!({condition})), , drop = FALSE]"
            )
            return index + 1

        assignment = re.match(
            r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", action, re.S
        )
        if not assignment:
            self.warn(f"Unsupported IF/THEN action: {statement}")
            lines.append(f"# TODO: unsupported IF/THEN: {statement}")
            return index + 1

        target, expression = assignment.groups()
        if_value = translate_expression(
            expression, df_name, self.used_helpers, self.warnings
        )

        # Handle a directly following ELSE.
        if index + 1 < len(statements) and first_word(statements[index + 1]) == "else":
            else_statement = statements[index + 1]
            else_action = re.sub(r"(?is)^else\s+", "", else_statement).strip()
            else_assignment = re.match(
                r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", else_action, re.S
            )
            if else_assignment:
                else_target, else_expression = else_assignment.groups()
                if else_target != target:
                    self.warn(
                        "IF/ELSE branches assign different variables; the "
                        "ELSE branch was skipped."
                    )
                else:
                    else_value = translate_expression(
                        else_expression,
                        df_name,
                        self.used_helpers,
                        self.warnings,
                    )
                    lines.append(
                        f"{df_name}${target} <- ifelse({condition}, "
                        f"{if_value}, {else_value})"
                    )
                    assigned.add(target)
                    if known_columns is not None:
                        known_columns.add(target)
                    return index + 2
            elif else_action.lower() == "delete":
                lines.append(
                    f"{df_name}${target} <- ifelse({condition}, {if_value}, NA)"
                )
                assigned.add(target)
                if known_columns is not None:
                    known_columns.add(target)
                return index + 2
            else:
                self.warn(
                    f"Unsupported ELSE action; ELSE was skipped: {else_statement}"
                )

        # IF without ELSE: keep existing values when the variable is known,
        # otherwise assign missing values where the condition is false.
        if target in assigned or (
            known_columns is not None and target in known_columns
        ):
            fallback = f"{df_name}${target}"
        else:
            fallback = "NA"
        lines.append(
            f"{df_name}${target} <- ifelse({condition}, {if_value}, {fallback})"
        )
        assigned.add(target)
        if known_columns is not None:
            known_columns.add(target)
        return index + 1

    def _parse_input(self, statement: str) -> tuple[list[str], list[str]]:
        body = re.sub(r"(?is)^input\s+", "", statement)
        tokens = body.split()
        names: list[str] = []
        types: list[str] = []

        for token in tokens:
            if token in {"@", "@@"} or token.startswith("@"):
                continue
            if token.startswith("$"):
                if names:
                    types[-1] = "character"
                continue
            if re.fullmatch(r"\d+(?:\.\d*)?", token):
                # Numeric format such as 8. or 12.2
                continue
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token):
                names.append(token)
                types.append("numeric")
                continue
            self.warn(f"Unusual INPUT token ignored: {token}")

        if not names:
            self.warn(f"Could not find variables in INPUT statement: {statement}")
        return names, types

    def _parse_labels(self, statement: str) -> list[tuple[str, str]]:
        body = re.sub(r"(?is)^label\s+", "", statement)
        pattern = re.compile(
            r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"(\"(?:[^\"]|\"\")*\"|'(?:[^']|'')*')"
        )
        return [
            (name, sas_string_to_plain(raw))
            for name, raw in pattern.findall(body)
        ]

    def _collect_block(
        self, statements: list[str], start: int
    ) -> tuple[list[str], int]:
        block: list[str] = []
        i = start
        while i < len(statements):
            keyword = first_word(statements[i])
            if keyword in {"run", "quit", "data", "proc"}:
                break
            block.append(statements[i])
            i += 1
        if i < len(statements) and first_word(statements[i]) in {"run", "quit"}:
            i += 1
        return block, i

    def _find_block_end(self, statements: list[str], start: int) -> int:
        _, next_index = self._collect_block(statements, start)
        return next_index

    # -- Procedures ------------------------------------------------------

    def _handle_proc(self, statements: list[str], start: int) -> int:
        header = statements[start]
        body_text = re.sub(r"(?is)^proc\s+", "", header)
        match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*(.*)", body_text, re.S)
        if not match:
            self.warn(f"Could not read PROC statement: {header}")
            return start + 1

        proc_name = match.group(1).lower()
        options = self._parse_options(match.group(2))
        proc_statements, next_index = self._collect_proc_block(statements, start + 1)

        handler = {
            "sort": self._proc_sort,
            "print": self._proc_print,
            "means": self._proc_means,
            "freq": self._proc_freq,
            "contents": self._proc_contents,
            "univariate": self._proc_univariate,
            "corr": self._proc_corr,
            "princomp": self._proc_princomp,
            "calis": self._proc_calis,
            "reg": self._proc_reg,
            "logistic": self._proc_logistic,
        }.get(proc_name)

        if handler is None:
            self.warn(f"PROC {proc_name.upper()} is not supported.")
            self.body.append(
                f"# TODO: PROC {proc_name.upper()} was not converted."
            )
        else:
            if self.body and self.body[-1] != "":
                self.body.append("")
            handler(proc_name, options, proc_statements)

        return next_index

    def _collect_proc_block(
        self, statements: list[str], start: int
    ) -> tuple[list[str], int]:
        block: list[str] = []
        i = start
        while i < len(statements):
            keyword = first_word(statements[i])
            if keyword in {"run", "quit", "data", "proc"}:
                break
            block.append(statements[i])
            i += 1
        if i < len(statements) and first_word(statements[i]) in {"run", "quit"}:
            i += 1
        return block, i

    def _parse_options(self, text: str) -> dict[str, str | bool]:
        options: dict[str, str | bool] = {}
        pattern = re.compile(
            r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"(\"[^\"]*\"|'[^']*'|[^\s]+)|([A-Za-z_][A-Za-z0-9_]*)"
        )
        for match in pattern.finditer(text):
            if match.group(1):
                value = match.group(2).strip()
                if value[:1] in "'\"" and value[-1:] == value[:1]:
                    value = value[1:-1]
                options[match.group(1).lower()] = value
            else:
                options[match.group(3).lower()] = True
        return options

    def _get_dataset(
        self, options: dict[str, str | bool], default_last: bool = True
    ) -> str:
        if "data" in options and isinstance(options["data"], str):
            return self.resolve_dataset(options["data"])
        if default_last and self.last_dataset:
            return self.last_dataset
        self.warn("Procedure has no DATA= option; using 'data'.")
        return "data"

    def _get_var_statement(self, statements: list[str]) -> list[str]:
        variables: list[str] = []
        for statement in statements:
            if first_word(statement) == "var":
                variables.extend(
                    parse_var_list(
                        re.sub(r"(?is)^var\s+", "", statement)
                    )
                )
        return variables

    def _get_weight_variable(self, statements: list[str]) -> str | None:
        """Return the variable named in a simple WEIGHT statement."""
        weights: list[str] = []
        for statement in statements:
            if first_word(statement) == "weight":
                body = re.sub(r"(?is)^weight\s+", "", statement)
                variables = parse_var_list(body)
                if variables:
                    weights.extend(variables)
                else:
                    self.warn(f"Could not read WEIGHT statement: {statement}")
        if len(weights) > 1:
            self.warn("More than one WEIGHT variable was found; the first is used.")
        return weights[0] if weights else None

    def _proc_sort(
        self,
        proc_name: str,
        options: dict[str, str | bool],
        statements: list[str],
    ) -> None:
        source = self._get_dataset(options)
        out = (
            self.resolve_dataset(options["out"])
            if isinstance(options.get("out"), str)
            else source
        )
        by_text = " ".join(
            re.sub(r"(?is)^by\s+", "", statement)
            for statement in statements
            if first_word(statement) == "by"
        )
        tokens = by_text.split()
        keys: list[str] = []
        key_vars: list[str] = []
        descending = False

        for token in tokens:
            if token.lower() == "descending":
                descending = True
                continue
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token):
                self.warn(f"Unusual BY variable ignored: {token}")
                descending = False
                continue
            key_vars.append(token)
            if descending:
                keys.append(f"-xtfrm({source}${token})")
            else:
                keys.append(f"{source}${token}")
            descending = False

        self.body.append(f"# ---- proc sort: {source} -> {out} ----")
        if keys:
            order_text = ", ".join(keys)
            self.body.append(
                f"{out} <- {source}[order({order_text}), , drop = FALSE]"
            )
        else:
            self.warn("PROC SORT has no BY variables; the data were copied.")
            self.body.append(f"{out} <- {source}")

        if options.get("nodupkey"):
            if key_vars:
                key_text = ", ".join(r_string(name) for name in key_vars)
                self.body.append(
                    f"{out} <- {out}[!duplicated({out}[, c({key_text}), "
                    "drop = FALSE]), , drop = FALSE]"
                )
            else:
                self.warn("NODUPKEY without BY variables was ignored.")
        if options.get("noduprecs"):
            self.body.append(f"{out} <- unique({out})")

        self.register_dataset(out, out)

    def _proc_print(
        self,
        proc_name: str,
        options: dict[str, str | bool],
        statements: list[str],
    ) -> None:
        source = self._get_dataset(options)
        variables = self._get_var_statement(statements)
        where_text = next(
            (
                re.sub(r"(?is)^where\s+", "", statement)
                for statement in statements
                if first_word(statement) == "where"
            ),
            None,
        )
        if any(first_word(statement) == "by" for statement in statements):
            self.warn("BY processing in PROC PRINT is not reproduced.")
        if any(first_word(statement) == "id" for statement in statements):
            self.warn("ID statement in PROC PRINT is ignored.")

        frame = source
        if where_text:
            condition = translate_expression(
                where_text, source, self.used_helpers, self.warnings
            )
            frame = f"{source}[which({condition}), , drop = FALSE]"
        if variables:
            variable_text = ", ".join(r_string(name) for name in variables)
            expression = f"{frame}[, c({variable_text}), drop = FALSE]"
        else:
            expression = frame

        if options.get("noobs"):
            self.body.append(f"# ---- proc print: {source} ----")
            self.body.append(f"print({expression}, row.names = FALSE)")
        else:
            self.body.append(f"# ---- proc print: {source} ----")
            self.body.append(f"print({expression})")

    def _proc_means(
        self,
        proc_name: str,
        options: dict[str, str | bool],
        statements: list[str],
    ) -> None:
        source = self._get_dataset(options)
        variables = self._get_var_statement(statements)
        classes: list[str] = []
        for statement in statements:
            if first_word(statement) == "class":
                classes.extend(
                    parse_var_list(
                        re.sub(r"(?is)^class\s+", "", statement)
                    )
                )
        if any(first_word(statement) == "by" for statement in statements):
            self.warn("BY processing in PROC MEANS is not reproduced.")
        if any(first_word(statement) == "weight" for statement in statements):
            self.warn("WEIGHT statement in PROC MEANS is ignored.")

        self.used_helpers.add(".sas_summary")
        self.body.append(f"# ---- proc means: {source} ----")
        if variables:
            variable_text = ", ".join(r_string(name) for name in variables)
            value_frame = f"{source}[c({variable_text})]"
        else:
            value_frame = f"{source}[vapply({source}, is.numeric, logical(1))]"

        if classes:
            if variables:
                response = "cbind(" + ", ".join(variables) + ")"
                formula = response + " ~ " + " + ".join(classes)
                self.body.append(
                    f"print(aggregate({formula}, data = {source}, "
                    "FUN = .sas_summary, na.action = na.pass))"
                )
            else:
                class_pairs = ", ".join(
                    f"{name} = {source}${name}" for name in classes
                )
                self.body.append(
                    f"print(aggregate({value_frame}, by = list({class_pairs}), "
                    "FUN = .sas_summary))"
                )
        else:
            self.body.append(
                f"print(sapply({value_frame}, .sas_summary))"
            )

    def _proc_freq(
        self,
        proc_name: str,
        options: dict[str, str | bool],
        statements: list[str],
    ) -> None:
        source = self._get_dataset(options)
        tables_statements = [
            statement for statement in statements if first_word(statement) == "tables"
        ]
        weight = self._get_weight_variable(statements)
        if any(first_word(statement) == "by" for statement in statements):
            self.warn("BY processing in PROC FREQ is not reproduced.")
        if not tables_statements:
            self.warn("PROC FREQ without a TABLES statement was skipped.")
            return

        self.body.append(f"# ---- proc freq: {source} ----")
        for statement in tables_statements:
            body = re.sub(r"(?is)^tables\s+", "", statement).strip()
            table_options = ""
            if "/" in body:
                body, table_options = body.split("/", 1)
            option_words = set(
                re.findall(r"[a-z_][a-z0-9_]*", table_options.lower())
            )
            body = re.sub(r"\s*\*\s*", "*", body.strip())
            specs = body.split()

            for spec in specs:
                variables = [name for name in spec.split("*") if name]
                if not variables or not all(
                    re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)
                    for name in variables
                ):
                    self.warn(f"Could not read TABLES specification: {spec}")
                    continue

                self.freq_index += 1
                table_name = f"freq_table_{self.freq_index}"
                if weight:
                    rhs = " + ".join(variables)
                    table_expression = (
                        f"xtabs({weight} ~ {rhs}, data = {source})"
                    )
                else:
                    args = ", ".join(f"{source}${name}" for name in variables)
                    table_expression = f"table({args})"
                self.body.append(f"{table_name} <- {table_expression}")
                self.body.append(f"print({table_name})")

                if "row" in option_words:
                    if len(variables) == 2:
                        self.body.append(
                            f"print(round(prop.table({table_name}, 1), 3))"
                        )
                    else:
                        self.warn("ROW percentages require a two-way table.")
                if "col" in option_words:
                    if len(variables) == 2:
                        self.body.append(
                            f"print(round(prop.table({table_name}, 2), 3))"
                        )
                    else:
                        self.warn("COL percentages require a two-way table.")
                if "cell" in option_words:
                    self.body.append(
                        f"print(round(prop.table({table_name}), 3))"
                    )
                if "expected" in option_words:
                    if len(variables) == 2:
                        self.body.append(
                            f"print(round(outer(rowSums({table_name}), "
                            f"colSums({table_name})) / sum({table_name}), 3))"
                        )
                    else:
                        self.warn("EXPECTED counts require a two-way table.")
                if "chisq" in option_words:
                    if len(variables) <= 2:
                        self.body.append(
                            f"print(chisq.test({table_name}, correct = FALSE))"
                        )
                    else:
                        self.warn(
                            "CHISQ is supported for one- or two-way tables; "
                            f"skipped for {spec}."
                        )
                if "fisher" in option_words:
                    if len(variables) == 2:
                        self.body.append(f"print(fisher.test({table_name}))")
                    else:
                        self.warn("FISHER's exact test requires a two-way table.")

    def _proc_contents(
        self,
        proc_name: str,
        options: dict[str, str | bool],
        statements: list[str],
    ) -> None:
        source = self._get_dataset(options)
        self.body.append(f"# ---- proc contents: {source} ----")
        self.body.append(f"str({source})")

    def _proc_univariate(
        self,
        proc_name: str,
        options: dict[str, str | bool],
        statements: list[str],
    ) -> None:
        source = self._get_dataset(options)
        variables = self._get_var_statement(statements)
        if variables:
            variable_text = ", ".join(r_string(name) for name in variables)
            frame = f"{source}[c({variable_text})]"
        else:
            frame = f"{source}[vapply({source}, is.numeric, logical(1))]"
        self.body.append(f"# ---- proc univariate: {source} ----")
        self.body.append(f"print(summary({frame}))")

    def _proc_corr(
        self,
        proc_name: str,
        options: dict[str, str | bool],
        statements: list[str],
    ) -> None:
        source = self._get_dataset(options)
        variables = self._get_var_statement(statements)
        weight = self._get_weight_variable(statements)
        if any(first_word(statement) == "with" for statement in statements):
            self.warn("WITH statement in PROC CORR is not reproduced.")
        if any(first_word(statement) == "by" for statement in statements):
            self.warn("BY processing in PROC CORR is not reproduced.")

        method = "pearson"
        if options.get("spearman"):
            method = "spearman"
        if options.get("kendall"):
            method = "kendall"
        if weight and method != "pearson":
            self.warn(
                f"Weighted {method} correlations are not supported; Pearson "
                "weights via cov.wt() are used instead."
            )

        if variables:
            variable_text = ", ".join(r_string(name) for name in variables)
            frame = f"{source}[c({variable_text})]"
        else:
            frame = f"{source}[vapply({source}, is.numeric, logical(1))]"

        self.body.append(f"# ---- proc corr: {source} ----")
        if weight:
            if variables:
                complete_text = ", ".join(
                    r_string(name) for name in variables + [weight]
                )
                self.body.append(
                    f"corr_data <- {source}[complete.cases("
                    f"{source}[, c({complete_text})]), ]"
                )
                corr_frame = f"corr_data[, c({variable_text})]"
            else:
                self.body.append(
                    f"corr_vars <- setdiff(names({source})[vapply({source}, "
                    f"is.numeric, logical(1))], {r_string(weight)})"
                )
                self.body.append(
                    f"corr_data <- {source}[complete.cases({source}[, "
                    f"c(corr_vars, {r_string(weight)})]), ]"
                )
                corr_frame = "corr_data[, corr_vars]"
            self.body.append(
                f"print(round(cov.wt({corr_frame}, wt = corr_data${weight}, "
                "cor = TRUE)$cor, 3))"
            )
        else:
            self.body.append(
                f"print(round(cor({frame}, use = \"pairwise.complete.obs\", "
                f"method = \"{method}\"), 3))"
            )

    def _proc_princomp(
        self,
        proc_name: str,
        options: dict[str, str | bool],
        statements: list[str],
    ) -> None:
        source = self._get_dataset(options)
        variables = self._get_var_statement(statements)
        weight = self._get_weight_variable(statements)
        use_correlation = not bool(options.get("cov"))
        if options.get("cov") and options.get("corr"):
            self.warn("Both COV and CORR were specified; COV is used.")

        self.pca_index += 1
        pca_name = f"pca_{self.pca_index}"
        self.body.append(f"# ---- proc princomp: {source} ----")

        if variables:
            variable_text = ", ".join(r_string(name) for name in variables)
            frame = f"{source}[c({variable_text})]"
        else:
            frame = f"{source}[vapply({source}, is.numeric, logical(1))]"

        r_scale = "TRUE" if use_correlation else "FALSE"
        if weight is None:
            self.body.append(
                f"{pca_name} <- stats::prcomp(stats::na.omit({frame}), "
                f"center = TRUE, scale. = {r_scale})"
            )
            self.body.append(f"print(summary({pca_name}))")
            return

        # Weighted PCA in base R: use the weighted covariance/correlation
        # matrix and its eigendecomposition.
        pca_data = f"pca_data_{self.pca_index}"
        if variables:
            complete_vars = variables + [weight]
            complete_text = ", ".join(r_string(name) for name in complete_vars)
            self.body.append(
                f"{pca_data} <- {source}[complete.cases("
                f"{source}[, c({complete_text})]), ]"
            )
            matrix = f"{pca_data}[, c({variable_text})]"
        else:
            pca_vars = f"pca_vars_{self.pca_index}"
            self.body.append(
                f"{pca_vars} <- setdiff(names({source})[vapply({source}, "
                f"is.numeric, logical(1))], {r_string(weight)})"
            )
            self.body.append(
                f"{pca_data} <- {source}[complete.cases("
                f"{source}[, c({pca_vars}, {r_string(weight)})]), ]"
            )
            matrix = f"{pca_data}[, {pca_vars}]"

        covariance = "TRUE" if use_correlation else "FALSE"
        matrix_part = "$cor" if use_correlation else "$cov"
        self.body.append(
            f"{pca_name} <- eigen(stats::cov.wt({matrix}, "
            f"wt = {pca_data}${weight}, cor = {covariance}){matrix_part})"
        )
        self.body.append(f"print({pca_name}$values)")
        self.body.append(f"print({pca_name}$vectors)")

    def _proc_reg(
        self,
        proc_name: str,
        options: dict[str, str | bool],
        statements: list[str],
    ) -> None:
        source = self._get_dataset(options)
        weight = self._get_weight_variable(statements)
        model_statements = [
            statement for statement in statements
            if first_word(statement) == "model"
        ]
        if not model_statements:
            self.warn("PROC REG without a MODEL statement was skipped.")
            return

        for statement in model_statements:
            body = re.sub(r"(?is)^model\s+", "", statement).strip()
            model_options = ""
            if "/" in body:
                body, model_options = body.split("/", 1)
            if "=" not in body:
                self.warn(f"Could not read MODEL statement: {statement}")
                continue

            equation = split_model_equation(body)
            if equation is None:
                self.warn(f"Could not read MODEL statement: {statement}")
                continue
            left, right = equation
            dependent = parse_var_list(left)
            if not dependent:
                self.warn(f"Could not read dependent variable: {statement}")
                continue
            if len(dependent) > 1:
                self.warn(
                    "Only the first dependent variable in MODEL is used: "
                    f"{statement}"
                )

            terms = right.split()
            if not terms:
                terms = ["1"]
            formula = f"{dependent[0]} ~ {' + '.join(terms)}"
            if "noint" in model_options.lower():
                formula += " - 1"

            self.reg_index += 1
            fit_name = f"reg_fit_{self.reg_index}"
            weight_arg = (
                f", weights = {source}${weight}" if weight else ""
            )
            self.body.append(f"# ---- proc reg: {source} ----")
            self.body.append(
                f"{fit_name} <- stats::lm({formula}, data = {source}"
                f"{weight_arg})"
            )
            self.body.append(f"print(summary({fit_name}))")

    def _proc_logistic(
        self,
        proc_name: str,
        options: dict[str, str | bool],
        statements: list[str],
    ) -> None:
        source = self._get_dataset(options)
        weight = self._get_weight_variable(statements)
        class_variables: list[str] = []
        for statement in statements:
            if first_word(statement) != "class":
                continue
            class_text = re.sub(
                r"(?is)^class\s+", "", statement
            ).split("/", 1)[0]
            class_text = re.sub(r"\([^)]*\)", " ", class_text)
            class_variables.extend(
                name.lower() for name in parse_var_list(class_text)
            )
        model_statements = [
            statement for statement in statements
            if first_word(statement) == "model"
        ]
        if not model_statements:
            self.warn("PROC LOGISTIC without a MODEL statement was skipped.")
            return
        if options.get("descending"):
            self.warn(
                "DESCENDING in PROC LOGISTIC is not applied; use an "
                "event= specification if the modeled outcome matters."
            )

        for statement in model_statements:
            body = re.sub(r"(?is)^model\s+", "", statement).strip()
            model_options = ""
            if "/" in body:
                body, model_options = body.split("/", 1)
            if "=" not in body:
                self.warn(f"Could not read MODEL statement: {statement}")
                continue

            equation = split_model_equation(body)
            if equation is None:
                self.warn(f"Could not read MODEL statement: {statement}")
                continue
            left, right = equation
            if "/" in left:
                self.warn(
                    "Events/trials syntax in PROC LOGISTIC is not supported: "
                    f"{statement}"
                )
                continue
            response_part = re.sub(r"\([^)]*\)", " ", left)
            response_variables = parse_var_list(response_part)
            if not response_variables:
                self.warn(f"Could not read response variable: {statement}")
                continue
            if len(response_variables) > 1:
                self.warn(
                    "Only the first response variable in MODEL is used: "
                    f"{statement}"
                )
            response = response_variables[0]

            event_match = re.search(
                r"(?i)event\s*=\s*['\"]?([^'\")\s]+)", left
            )
            if event_match:
                response_expression = (
                    f"I({response} == {r_string(event_match.group(1))})"
                )
            else:
                response_expression = response

            right = re.sub(r"\s*\*\s*", "*", right.strip())
            right_terms = right.split() if right.strip() else ["1"]
            converted_terms: list[str] = []
            for term in right_terms:
                pieces = term.split("*")
                pieces = [
                    f"factor({piece})" if piece.lower() in class_variables
                    else piece
                    for piece in pieces
                ]
                converted_terms.append("*".join(pieces))
            formula = (
                f"{response_expression} ~ {' + '.join(converted_terms)}"
            )
            option_words = set(
                re.findall(r"[a-z_][a-z0-9_]*", model_options.lower())
            )
            if "noint" in option_words:
                formula += " - 1"

            self.logit_index += 1
            fit_name = f"logit_fit_{self.logit_index}"
            weight_arg = (
                f", weights = {source}${weight}" if weight else ""
            )
            self.body.append(f"# ---- proc logistic: {source} ----")
            self.body.append(
                f"{fit_name} <- stats::glm({formula}, data = {source}, "
                f"family = stats::binomial(){weight_arg})"
            )
            self.body.append(f"print(summary({fit_name}))")
            if "expb" in option_words:
                coefficient_name = f"{fit_name}_coef"
                standard_error_name = f"{fit_name}_se"
                self.body.append(
                    f"{coefficient_name} <- stats::coef({fit_name})"
                )
                self.body.append(
                    f"{standard_error_name} <- "
                    f"sqrt(diag(stats::vcov({fit_name})))"
                )
                self.body.append(
                    f"print(exp(cbind(OR = {coefficient_name}, "
                    f"`2.5 %` = {coefficient_name} - "
                    f"1.96 * {standard_error_name}, "
                    f"`97.5 %` = {coefficient_name} + "
                    f"1.96 * {standard_error_name})))"
                )

    def _proc_calis(
        self,
        proc_name: str,
        options: dict[str, str | bool],
        statements: list[str],
    ) -> None:
        source = self._get_dataset(options)
        weight = self._get_weight_variable(statements)

        path_statements = [
            statement for statement in statements
            if first_word(statement) == "path"
        ]
        lineqs_statements = [
            statement for statement in statements
            if first_word(statement) == "lineqs"
        ]
        if any(first_word(statement) in {"ram", "matrix"} for statement in statements):
            self.warn(
                "RAM/MATRIX specifications in PROC CALIS are not supported; "
                "use a PATH statement for CFA conversion."
            )

        measurement: dict[str, list[str]] = {}
        structural: list[str] = []

        if path_statements:
            path_pairs: list[tuple[str, list[str]]] = []
            path_text = " ".join(
                re.sub(r"(?is)^path\s+", "", statement)
                for statement in path_statements
            )
            for match in re.finditer(
                r"([A-Za-z_][A-Za-z0-9_]*)\s*->\s*([^,]+)", path_text
            ):
                factor = match.group(1)
                indicators = re.sub(r"\([^)]*\)", " ", match.group(2))
                path_pairs.append((factor, parse_var_list(indicators)))

            factors = {factor for factor, _ in path_pairs}
            for factor, variables in path_pairs:
                for variable in variables:
                    if variable in factors:
                        if variable != factor:
                            structural.append(f"{variable} ~ {factor}")
                    elif variable not in measurement.setdefault(factor, []):
                        measurement[factor].append(variable)
            if not path_pairs:
                self.warn(
                    "Could not read a PROC CALIS PATH specification. "
                    "Expected syntax such as 'F1 -> x1 x2'."
                )
            if lineqs_statements:
                self.warn(
                    "Both PATH and LINEQS were found; PATH is used for CFA."
                )
        elif lineqs_statements:
            lineqs_text = " ".join(
                re.sub(r"(?is)^lineqs\s+", "", statement)
                for statement in lineqs_statements
            )
            equations: list[tuple[str, list[str]]] = []
            for equation in lineqs_text.split(","):
                if "=" not in equation:
                    continue
                left, right = equation.split("=", 1)
                factors = parse_var_list(left)
                if not factors:
                    continue
                terms: list[str] = []
                for term in re.split(r"\s*[+\-]\s*", right):
                    term = re.sub(r"\([^)]*\)", " ", term)
                    names = parse_var_list(term)
                    for name in names:
                        if re.fullmatch(r"(?i)(e|d|u|err|error)\d+", name):
                            continue
                        if name not in terms:
                            terms.append(name)
                equations.append((factors[0], terms))

            factor_names = {factor for factor, _ in equations}
            for factor, terms in equations:
                for term in terms:
                    if term in factor_names:
                        if term != factor:
                            structural.append(f"{factor} ~ {term}")
                    else:
                        if term not in measurement.setdefault(factor, []):
                            measurement[factor].append(term)
            if equations:
                self.warn(
                    "LINEQS was converted to a lavaan measurement model "
                    "heuristically; review factor loadings and error terms."
                )

        model_lines = [
            f"{factor} =~ " + " + ".join(variables)
            for factor, variables in measurement.items()
            if variables
        ] + structural
        if not model_lines:
            self.warn(
                "No usable CFA model was found in PROC CALIS; the step was "
                "skipped."
            )
            self.body.append("# TODO: could not read a PROC CALIS CFA model.")
            return

        self.cfa_index += 1
        model_name = f"cfa_model_{self.cfa_index}"
        fit_name = f"cfa_fit_{self.cfa_index}"
        self.body.append(f"# ---- proc calis: {source} ----")
        self.body.append("# Requires lavaan: install.packages(\"lavaan\")")
        self.body.append(f"{model_name} <- '")
        for line in model_lines:
            self.body.append(line)
        self.body.append("'")
        weight_arg = (
            f", sampling_weights = {r_string(weight)}" if weight else ""
        )
        self.body.append(
            f"{fit_name} <- lavaan::cfa({model_name}, data = {source}"
            f"{weight_arg})"
        )
        self.body.append(
            f"print(summary({fit_name}, fit_measures = TRUE))"
        )


# ---------------------------------------------------------------------------
# Public API and command line
# ---------------------------------------------------------------------------

def convert_sas(sas_code: str, source_name: str = "<string>") -> ConversionResult:
    """Convert SAS source text to an R script."""
    return SasToRConverter(source_name).convert(sas_code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert basic SAS code to R code."
    )
    parser.add_argument("input", help="SAS file to convert")
    parser.add_argument(
        "-o",
        "--output",
        help="R output file (default: input with .R extension)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Write R code to standard output instead of a file",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    try:
        sas_code = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {input_path}: {exc}", file=sys.stderr)
        return 2

    try:
        result = convert_sas(sas_code, source_name=str(input_path))
    except ConversionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.stdout:
        sys.stdout.write(result.code)
    else:
        output_path = (
            Path(args.output) if args.output else input_path.with_suffix(".R")
        )
        try:
            output_path.write_text(result.code, encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write {output_path}: {exc}", file=sys.stderr)
            return 2
        print(f"Wrote {output_path}")

    if result.warnings:
        print(f"{len(result.warnings)} warning(s):", file=sys.stderr)
        for warning in result.warnings:
            print(f"  - {warning}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
