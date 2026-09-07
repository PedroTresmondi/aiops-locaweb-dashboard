import unittest

from fastapi.testclient import TestClient

from backend.main import app


class TestVisionOpsApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_overview_preserva_metricas_auditadas(self):
        response = self.client.get("/api/overview")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["snapshot"]["incidentes"], 122_543)
        self.assertEqual(body["snapshot"]["elegiveis"], 25_751)
        self.assertEqual(body["snapshot"]["violacoes"], 3_685)
        self.assertEqual(body["forecast"][0]["ponto"], 914)

    def test_triagem_usa_modelo_calibrado(self):
        response = self.client.post(
            "/api/triage",
            json={
                "prioridade": 3,
                "produto": "lemn",
                "categoria": "cat45",
                "grupo": "Team05",
                "data_hora": "2026-01-01T09:00:00",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["faixa"], "Alto")
        self.assertAlmostEqual(body["probabilidade"], 0.5666832609, places=5)
        self.assertEqual(len(body["evidencias"]), 4)

    def test_simulador_separa_premissa_de_previsao(self):
        response = self.client.post(
            "/api/capacity",
            json={
                "produtividade": 25,
                "ocupacao": 0.8,
                "indisponibilidade": 0.1,
                "analistas_atuais": 40,
                "horizonte": "D+1",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["cenarios"][1]["demanda"], 914)
        self.assertIn("premissa operacional", body["nota"])


if __name__ == "__main__":
    unittest.main()

