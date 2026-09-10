"""Importação controlada de incidentes recentes para revalidação dos modelos."""

from __future__ import annotations

import os
import unicodedata
from pathlib import Path

import pandas as pd

from backend import datasource


def current_path() -> Path:
    configured = os.environ.get("VISIONOPS_CURRENT_DATASET")
    return Path(configured) if configured else datasource.ROOT / ".visionops" / "current.parquet"


def _key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return "".join(c for c in text if c.isalnum())


def _read(record: dict, *names: str):
    normalized = {_key(k): v for k, v in record.items()}
    return next((normalized[_key(name)] for name in names if _key(name) in normalized), None)


def normalize_records(records: list[dict]) -> pd.DataFrame:
    rows = []
    errors = []
    seen = set()
    for index, record in enumerate(records, start=2):
        number = str(_read(record, "Número", "numero", "id", "ticketRef") or "").strip()
        priority = pd.to_numeric(_read(record, "Prioridade_Cod", "prioridade_num", "prioridade"), errors="coerce")
        opened = pd.to_datetime(_read(record, "Aberto", "aberto", "dataHora", "openedAt"), errors="coerce")
        if not number or pd.isna(priority) or int(priority) not in (1, 2, 3, 4, 5) or pd.isna(opened):
            errors.append(f"linha {index}: informe número, prioridade de 1 a 5 e data de abertura válida")
            continue
        if number in seen:
            errors.append(f"linha {index}: número duplicado {number}")
            continue
        seen.add(number)
        resolved = pd.to_datetime(_read(record, "Resolvido", "resolvido", "resolvedAt"), errors="coerce")
        duration = pd.to_numeric(_read(record, "Duracao_Horas", "duracao_horas", "duracaoHoras"), errors="coerce")
        if pd.isna(duration) and pd.notna(resolved):
            duration = (resolved - opened).total_seconds() / 3600
        if pd.notna(duration) and float(duration) < 0:
            errors.append(f"linha {index}: duração não pode ser negativa")
            continue
        rows.append({
            "Número": number, "Prioridade_Cod": int(priority),
            "Produto": str(_read(record, "Produto", "produto") or "Não informado").strip(),
            "Categoria": str(_read(record, "Categoria", "categoria") or "Não informado").strip(),
            "Subcategoria": _read(record, "Subcategoria", "subcategoria"),
            "Grupo designado": str(_read(record, "Grupo designado", "grupo", "assignmentGroup") or "Não informado").strip(),
            "Item de configuração": _read(record, "Item de configuração", "itemConfiguracao", "configurationItem"),
            "Aberto": opened, "Resolvido": resolved, "Encerrado": resolved,
            "Duracao_Horas": duration, "Status": str(_read(record, "Status", "status") or ("Resolvido" if pd.notna(resolved) else "Aberto")),
            "Aberto por": _read(record, "Aberto por", "abertoPor"),
            "Incidente Pai": _read(record, "Incidente Pai", "incidentePai", "parentIncident"),
            "Desfecho_Conhecido": bool(pd.notna(duration)),
        })
    if errors:
        raise ValueError("; ".join(errors[:10]))
    if not rows:
        raise ValueError("Nenhum incidente válido foi enviado.")
    return datasource._garantir_regras(pd.DataFrame(rows))


def import_records(records: list[dict]) -> dict:
    incoming = normalize_records(records)
    base = datasource.carregar()
    before_count = len(base)
    before_snapshot = pd.to_datetime(base["Aberto"]).max()
    combined = pd.concat([base, incoming], ignore_index=True)
    combined = combined.sort_values("Aberto").drop_duplicates("Número", keep="last")
    combined = datasource._garantir_regras(combined)
    target = current_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp.parquet")
    combined.to_parquet(temporary, index=False)
    os.replace(temporary, target)
    after_snapshot = pd.to_datetime(combined["Aberto"]).max()
    return {
        "recebidos": len(incoming), "novos": max(0, len(combined) - before_count),
        "atualizados": len(incoming) - max(0, len(combined) - before_count),
        "totalAntes": before_count, "totalDepois": len(combined),
        "snapshotAntes": before_snapshot.isoformat(), "snapshotDepois": after_snapshot.isoformat(),
        "desfechosConhecidosRecebidos": int(incoming["Desfecho_Conhecido"].sum()),
        "arquivo": target.name,
    }


def status() -> dict:
    df = datasource.carregar()
    path = current_path()
    return {
        "origem": "base atualizada" if path.exists() else datasource.origem(),
        "persistenciaConfigurada": bool(os.environ.get("VISIONOPS_CURRENT_DATASET")),
        "arquivoAtualizadoExiste": path.exists(),
        "incidentes": len(df), "snapshot": pd.to_datetime(df["Aberto"]).max().date().isoformat(),
        "desfechosConhecidos": int(df.get("Desfecho_Conhecido", pd.Series(True, index=df.index)).sum()),
        "notaPersistencia": "O caminho da base atualizada precisa apontar para disco persistente em produção. No Render gratuito, o arquivo local pode ser perdido em novo deploy.",
    }
