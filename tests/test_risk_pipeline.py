from pathlib import Path
import sys
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from risk_pipeline import FEATURES_RISCO, executar_pipeline_risco  # noqa: E402


class TestPipelineRiscoOLA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = pd.read_parquet(ROOT / "dataset_limpo.parquet")
        cls.resultado = executar_pipeline_risco(cls.df)

    def test_nao_usa_vazamento_de_alvo(self):
        proibidas = {"Duracao_Horas", "Resolvido", "Encerrado", "OLA_Violado_KPI_Regra"}
        self.assertTrue(proibidas.isdisjoint(FEATURES_RISCO))

    def test_holdout_temporal_dezembro(self):
        metricas = self.resultado.metricas_holdout
        self.assertEqual(metricas["n_holdout"], 1438)
        self.assertEqual(metricas["n_violacoes_holdout"], 125)
        self.assertEqual(self.resultado.inicio_holdout.strftime("%Y-%m-%d"), "2025-12-01")
        self.assertEqual(self.resultado.fim_holdout.strftime("%Y-%m-%d"), "2025-12-31")

    def test_ensemble_tem_poder_preditivo_fora_da_amostra(self):
        metricas = self.resultado.metricas_holdout
        self.assertGreater(metricas["ROC_AUC"], 0.75)
        self.assertGreater(metricas["PR_AUC"], metricas["prevalencia"] * 2.5)
        self.assertGreater(metricas["lift_fila_alta"], 2.0)
        self.assertGreater(metricas["captura_violacoes"], 0.35)
        self.assertLess(metricas["taxa_revisada"], 0.20)

    def test_peso_escolhido_antes_do_holdout(self):
        self.assertAlmostEqual(self.resultado.peso_extra_trees, 0.5)
        self.assertIn("50% Extra Trees", self.resultado.benchmark_validacao.iloc[0]["modelo"])

    def test_score_interativo_valido(self):
        score = self.resultado.prever(
            2, "Não informado", "Não informado", "Team11", pd.Timestamp("2026-01-01 09:00")
        )
        self.assertGreaterEqual(score["probabilidade"], 0)
        self.assertLessEqual(score["probabilidade"], 1)
        self.assertIn(score["faixa"], {"Baixo", "Moderado", "Alto"})


if __name__ == "__main__":
    unittest.main()
