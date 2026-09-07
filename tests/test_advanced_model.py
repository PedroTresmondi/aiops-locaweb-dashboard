"""Testes do modelo avançado de previsão (feriados + Poisson + recência + rolling-origin)."""

from pathlib import Path
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model_pipeline import executar_pipeline, feriados_nacionais, _domingo_de_pascoa  # noqa: E402


class TestFeriados(unittest.TestCase):
    def test_domingo_de_pascoa_conhecido(self):
        self.assertEqual(_domingo_de_pascoa(2023).isoformat(), "2023-04-09")
        self.assertEqual(_domingo_de_pascoa(2025).isoformat(), "2025-04-20")
        self.assertEqual(_domingo_de_pascoa(2026).isoformat(), "2026-04-05")

    def test_feriados_nacionais_2025(self):
        tabela = feriados_nacionais(range(2025, 2026))
        datas = set(tabela["data"].dt.strftime("%Y-%m-%d"))
        self.assertIn("2025-01-01", datas)  # Confraternização
        self.assertIn("2025-03-04", datas)  # Carnaval (terça)
        self.assertIn("2025-04-18", datas)  # Sexta-feira Santa
        self.assertIn("2025-11-20", datas)  # Consciência Negra (nacional desde 2024)
        self.assertIn("2025-12-25", datas)  # Natal


class TestModeloAvancado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        df = pd.read_parquet(ROOT / "dataset_limpo.parquet")
        cls.avancado = executar_pipeline(df).avancado

    def test_backtest_rolling_origin_tem_muitos_pontos(self):
        for linha in self.avancado["metricas"].itertuples():
            self.assertGreaterEqual(linha.n_pontos, 40)  # muito mais que o holdout único

    def test_ganha_do_baseline_linear(self):
        for linha in self.avancado["metricas"].itertuples():
            self.assertGreater(linha.ganho_vs_baseline, 0)
            self.assertLess(linha.bt_MAE, linha.baseline_bt_MAE)

    def test_competitivo_com_o_ensemble_operacional(self):
        # empata ou fica dentro de 10% do ensemble operacional (que foi tunado nessa janela)
        for linha in self.avancado["metricas"].itertuples():
            self.assertLess(linha.bt_MAE, linha.operacional_bt_MAE * 1.10)

    def test_previsoes_validas_e_feriado_detectado(self):
        previsoes = self.avancado["previsoes"]
        for dados in previsoes.values():
            self.assertGreater(dados["ponto"], 0)
            self.assertLessEqual(dados["limite_inferior_80"], dados["ponto"])
            self.assertGreaterEqual(dados["limite_superior_80"], dados["ponto"])
        # 01/01/2026 é feriado — o modelo tem de marcar isso
        self.assertEqual(previsoes["D+1"]["alvo_feriado"], 1)

    def test_feriados_do_periodo_listados(self):
        feriados = self.avancado["feriados"]
        self.assertGreater(len(feriados), 20)  # ~13/ano × 3 anos
        nomes = set(feriados["nome"])
        self.assertIn("Natal", nomes)
        self.assertIn("Carnaval (terça)", nomes)


if __name__ == "__main__":
    unittest.main()
