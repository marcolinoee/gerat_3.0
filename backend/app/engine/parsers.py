"""Parsers for inflow series files (vazoes.txt 13-col, CSV, XLSX) with security sanitization."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

import pandas as pd

MAX_INFLOW_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True)
class ParsedInflowRow:
    """Normalized monthly inflow row extracted from an uploaded file."""

    year: int
    month: int
    flow_m3s: float


def sanitize_csv_cell(value: str) -> str:
    """Sanitize a string cell to mitigate CSV/Formula Injection when exporting."""
    s = str(value)
    if s and s[0] in _CSV_INJECTION_PREFIXES:
        return "'" + s
    return s


def _validate_numeric_flow(raw: object, year: int, month: int) -> float:
    text = str(raw).strip()
    if text and text[0] in ("=", "@"):
        raise ValueError(f"Conteúdo inválido (possível fórmula) no ano {year}, mês {month}.")
    text = text.replace(",", ".")
    val = float(text)
    if val < 0:
        raise ValueError(f"Vazão negativa ({val}) encontrada no ano {year}, mês {month}.")
    return val


def parse_inflow_file(content: bytes, filename: str) -> list[ParsedInflowRow]:
    """Parse inflow series from:
    1. Legacy `vazoes.txt` (13 columns: YEAR JAN FEB ... DEC, whitespace or delimiter separated)
    2. CSV (either 13 columns YEAR + 12 months, or 3 columns year,month,flow_m3s)
    3. XLSX (same column layouts as CSV)
    """
    if len(content) > MAX_INFLOW_FILE_SIZE_BYTES:
        raise ValueError("Arquivo excede o limite máximo permitido de 5 MB.")
    if not content:
        raise ValueError("Arquivo vazio.")

    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "txt"

    if ext == "xlsx":
        df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        return _parse_dataframe(df)

    text = content.decode("utf-8-sig", errors="replace")

    if ext == "txt":
        return _parse_vazoes_txt(text)

    if ext == "csv":
        # Detect delimiter
        first_line = next((ln for ln in text.splitlines() if ln.strip()), "")
        sep = ";" if first_line.count(";") >= first_line.count(",") else ","
        df = pd.read_csv(io.StringIO(text), sep=sep)
        return _parse_dataframe(df)

    raise ValueError(f"Formato de arquivo não suportado: .{ext}. Use .txt, .csv ou .xlsx.")


def _parse_vazoes_txt(text: str) -> list[ParsedInflowRow]:
    rows: list[ParsedInflowRow] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        tokens = re.split(r"[\s;,]+", line)
        # Skip header line if first token isn't an integer year
        try:
            year = int(tokens[0])
        except ValueError:
            if line_no <= 2:
                continue
            raise ValueError(f"Linha {line_no}: ano inválido '{tokens[0]}'.")

        if len(tokens) < 13:
            raise ValueError(
                f"Linha {line_no}: esperado 13 colunas (ANO + 12 meses), encontrado {len(tokens)}."
            )

        for month in range(1, 13):
            flow = _validate_numeric_flow(tokens[month], year, month)
            rows.append(ParsedInflowRow(year=year, month=month, flow_m3s=flow))

    if not rows:
        raise ValueError("Nenhum registro válido de vazão encontrado no arquivo.")
    return rows


def _parse_dataframe(df: pd.DataFrame) -> list[ParsedInflowRow]:
    if df.empty:
        raise ValueError("Planilha/CSV sem dados.")

    cols_lower = [str(c).strip().lower() for c in df.columns]
    rows: list[ParsedInflowRow] = []

    # Format A: Long format (year, month, flow / flow_m3s / vazao)
    if len(df.columns) >= 3 and any(c in cols_lower for c in ("month", "mes", "mês")):
        year_col = next(
            (i for i, c in enumerate(cols_lower) if c in ("year", "ano")), 0
        )
        month_col = next(
            (i for i, c in enumerate(cols_lower) if c in ("month", "mes", "mês")), 1
        )
        flow_col = next(
            (
                i
                for i, c in enumerate(cols_lower)
                if c in ("flow_m3s", "flow", "vazao", "vazão", "valor", "q")
            ),
            2,
        )
        for _, rec in df.iterrows():
            if pd.isna(rec.iloc[year_col]) or pd.isna(rec.iloc[month_col]):
                continue
            year = int(rec.iloc[year_col])
            month = int(rec.iloc[month_col])
            if not (1 <= month <= 12):
                raise ValueError(f"Mês inválido ({month}) para o ano {year}.")
            flow = _validate_numeric_flow(rec.iloc[flow_col], year, month)
            rows.append(ParsedInflowRow(year=year, month=month, flow_m3s=flow))
        if not rows:
            raise ValueError("Nenhum registro válido encontrado.")
        return rows

    # Format B: Wide format (13 columns: Year + Jan..Dec)
    if len(df.columns) >= 13:
        for _, rec in df.iterrows():
            if pd.isna(rec.iloc[0]):
                continue
            year = int(rec.iloc[0])
            for month in range(1, 13):
                flow = _validate_numeric_flow(rec.iloc[month], year, month)
                rows.append(ParsedInflowRow(year=year, month=month, flow_m3s=flow))
        if not rows:
            raise ValueError("Nenhum registro válido encontrado.")
        return rows

    raise ValueError(
        "Layout não reconhecido. Envie 13 colunas (Ano + Jan..Dez) ou 3 colunas (year, month, flow_m3s)."
    )
