from pathlib import Path
import sys
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model_pipeline import FEATURES, executar_pipeline  # noqa: E402


class TestPipelineReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = pd.read_parquet(ROOT / "dataset_limpo.parquet")
        cls.resultado = executar_pipeline(cls.df)

    def test_metricas_ola_auditadas(self):
        self.assertEqual(len(self.df), 122543)
        self.assertEqual(int(self.df["Elegivel_KPI_Regra"].sum()), 25751)
        self.assertEqual(int(self.df["OLA_Violado_Regra"].sum()), 7090)
        self.assertEqual(int(self.df["OLA_Violado_KPI_Regra"].sum()), 3685)

    def test_features_e_periodo(self):
        self.assertEqual(len(FEATURES), 18)
        self.assertEqual(self.resultado.inicio_teste.strftime("%Y-%m-%d"), "2025-05-27")
        self.assertEqual(self.resultado.fim_teste.strftime("%Y-%m-%d"), "2025-12-24")

    def test_reproduz_metricas_sprint_3(self):
        metricas = self.resultado.metricas.set_index("horizonte")
        self.assertAlmostEqual(metricas.loc["D+1", "MAE"], 187.583422, places=5)
        self.assertAlmostEqual(metricas.loc["D+1", "RMSE"], 275.830192, places=5)
        self.assertAlmostEqual(metricas.loc["D+7", "MAE"], 181.217802, places=5)
        self.assertAlmostEqual(metricas.loc["D+7", "RMSE"], 267.126863, places=5)

    def test_previsoes_sao_calculadas_e_intervalos_validos(self):
        for horizonte in ["D+1", "D+7"]:
            previsao = self.resultado.previsoes[horizonte]
            self.assertGreater(previsao["ponto"], 0)
            self.assertLess(previsao["limite_inferior_80"], previsao["ponto"])
            self.assertGreater(previsao["limite_superior_80"], previsao["ponto"])


if __name__ == "__main__":
    unittest.main()
