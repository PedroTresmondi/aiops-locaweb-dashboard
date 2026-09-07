"""Otimização de alocação preventiva em D+1 (Programação Linear Inteira Mista).

Porta a Seção 18 do notebook de Machine Learning da Sprint 3. Diferença de método:
o notebook usa PuLP/CBC; aqui o mesmo modelo é resolvido com ``scipy.optimize.milp``
(scipy já é dependência do scikit-learn — nenhuma dependência nova). O modelo é
prescritivo, não preditivo: recebe a previsão real de volume D+1 e decide quais
produtos priorizar na revisão preventiva.

Extensões pedidas na Sprint 4 (cél. 105 do notebook):
- ``custo_por_produto``: custo de revisar cada produto (default uniforme = 1);
  a restrição de capacidade passa a ser Σ custo·y ≤ capacidade.
- ``capacidade`` exposta como parâmetro para ser calibrada com a operação real.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, linprog, milp

_CAPACIDADES_SENSIBILIDADE = [1, 2, 3, 5, 8, 10, 15, 20]


def _preparar(df: pd.DataFrame, previsao_d1_total: float) -> pd.DataFrame:
    base = df.copy()
    base["produto"] = base["Produto"].astype("string").str.strip()
    base = base[base["produto"].notna() & (base["produto"] != "")]

    agregado = (
        base.groupby("produto")
        .agg(
            incidentes_total=("Aberto", "size"),
            ola_violados=("OLA_Violado_Regra", "sum"),
        )
        .reset_index()
    )
    total_historico = float(agregado["ola_violados"].sum())
    if total_historico <= 0:
        raise ValueError("Sem violações históricas de OLA para distribuir a carga.")
    agregado["peso_risco"] = agregado["ola_violados"] / total_historico
    agregado["carga_estimada_d1"] = agregado["peso_risco"] * float(previsao_d1_total)

    categoria_dominante = base.groupby("produto")["Categoria"].agg(
        lambda serie: serie.mode().iloc[0] if not serie.mode().empty else "Não informado"
    )
    agregado["categoria_dominante"] = agregado["produto"].map(categoria_dominante).fillna("Não informado")
    return agregado.sort_values("carga_estimada_d1", ascending=False).reset_index(drop=True)


def _resolver_milp(
    carga: np.ndarray,
    custo: np.ndarray,
    capacidade: float,
    categorias: list[str],
    limite_por_categoria: int,
    forcar_top1: bool,
) -> np.ndarray:
    n = len(carga)
    restricoes = [LinearConstraint(custo, -np.inf, float(capacidade))]

    grupos: dict[str, list[int]] = {}
    for indice, categoria in enumerate(categorias):
        grupos.setdefault(categoria, []).append(indice)
    for indices in grupos.values():
        if len(indices) > limite_por_categoria:
            linha = np.zeros(n)
            linha[indices] = 1.0
            restricoes.append(LinearConstraint(linha, -np.inf, float(limite_por_categoria)))

    limite_inferior = np.zeros(n)
    if forcar_top1 and n:
        limite_inferior[int(np.argmax(carga))] = 1.0

    resultado = milp(
        c=-carga,
        constraints=restricoes,
        integrality=np.ones(n),
        bounds=Bounds(limite_inferior, np.ones(n)),
    )
    if not resultado.success:
        raise ValueError(f"MILP não encontrou solução viável: {resultado.message}")
    return np.round(resultado.x).astype(int)


def _preco_sombra(carga: np.ndarray, custo: np.ndarray, capacidade: float) -> float:
    """Dual da restrição de capacidade na relaxação linear: risco coberto por vaga extra."""
    relaxado = linprog(
        c=-carga,
        A_ub=[custo],
        b_ub=[float(capacidade)],
        bounds=[(0, 1)] * len(carga),
        method="highs",
    )
    if not relaxado.success or relaxado.ineqlin.marginals is None:
        return 0.0
    return float(abs(relaxado.ineqlin.marginals[0]))


def otimizar_alocacao(
    df: pd.DataFrame,
    previsao_d1_total: float,
    *,
    capacidade: float = 5,
    limite_por_categoria: int = 2,
    forcar_top1: bool = True,
    custo_por_produto: dict[str, float] | None = None,
) -> dict:
    agregado = _preparar(df, previsao_d1_total)
    produtos = agregado["produto"].tolist()
    carga = agregado["carga_estimada_d1"].to_numpy(dtype=float)
    categorias = agregado["categoria_dominante"].tolist()
    custo = np.array(
        [float((custo_por_produto or {}).get(produto, 1.0)) for produto in produtos]
    )

    selecao = _resolver_milp(
        carga, custo, capacidade, categorias, limite_por_categoria, forcar_top1
    )
    escolhidos = selecao.astype(bool)
    risco_coberto = float(carga[escolhidos].sum())
    risco_total = float(carga.sum())
    preco_sombra = _preco_sombra(carga, custo, capacidade)

    sensibilidade = []
    for capacidade_teste in _CAPACIDADES_SENSIBILIDADE:
        try:
            selecao_teste = _resolver_milp(
                carga, custo, capacidade_teste, categorias, limite_por_categoria, forcar_top1
            )
        except ValueError:
            continue
        coberto = float(carga[selecao_teste.astype(bool)].sum())
        sensibilidade.append(
            {
                "capacidade": capacidade_teste,
                "riscoCoberto": round(coberto, 1),
                "pctDoTotal": round(100 * coberto / risco_total, 1) if risco_total else 0.0,
            }
        )

    return {
        "previsaoD1Total": round(float(previsao_d1_total), 1),
        "capacidade": capacidade,
        "limitePorCategoria": limite_por_categoria,
        "custoUniforme": custo_por_produto is None,
        "riscoCoberto": round(risco_coberto, 1),
        "riscoTotal": round(risco_total, 1),
        "coberturaPct": round(100 * risco_coberto / risco_total, 1) if risco_total else 0.0,
        "precoSombra": round(preco_sombra, 1),
        "selecionados": [
            {
                "produto": produtos[i],
                "categoriaDominante": categorias[i],
                "cargaEstimadaD1": round(float(carga[i]), 1),
                "custo": round(float(custo[i]), 2),
            }
            for i in range(len(produtos))
            if escolhidos[i]
        ],
        "fila": [
            {
                "produto": linha.produto,
                "categoriaDominante": linha.categoria_dominante,
                "incidentesTotal": int(linha.incidentes_total),
                "olaViolados": int(linha.ola_violados),
                "cargaEstimadaD1": round(float(linha.carga_estimada_d1), 1),
                "selecionado": bool(escolhidos[posicao]),
            }
            for posicao, linha in enumerate(agregado.itertuples())
        ],
        "sensibilidade": sensibilidade,
    }
