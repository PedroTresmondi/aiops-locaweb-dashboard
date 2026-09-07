"""Testes das entregas da Sprint 4: fila em lote, ações, deriva, otimização,
segmentação e o contrato legado da Sprint 3."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("VISIONOPS_DB", str(Path(tempfile.gettempdir()) / "visionops_test_sprint4.db"))
for _sufixo in ("", "-wal", "-shm"):
    _arquivo = Path(os.environ["VISIONOPS_DB"] + _sufixo)
    if _arquivo.exists():
        _arquivo.unlink()

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402


class TestFilaOperacional(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_fila_do_snapshot_ordena_por_risco(self):
        resposta = self.client.get("/api/queue/sample", params={"data": "2025-11-18", "dias": 1})
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()
        self.assertEqual(corpo["origem"], "snapshot")
        self.assertGreater(corpo["resumo"]["total"], 10)
        riscos = [item["probabilidade"] for item in corpo["fila"]]
        self.assertEqual(riscos, sorted(riscos, reverse=True))
        # explicação individual presente
        self.assertEqual(len(corpo["fila"][0]["fatores"]), 4)
        # o resultado real do dia é anexado para conferência
        self.assertIn("violacoesReais", corpo["resumo"])
        self.assertTrue(all("violouReal" in item for item in corpo["fila"]))

    def test_fila_por_csv_e_persistencia_de_acao(self):
        payload = {
            "itens": [
                {"id": "T-1", "prioridade": 3, "produto": "lemg", "categoria": "cat85", "grupo": "Team05", "dataHora": "2026-01-02T09:00:00"},
                {"id": "T-2", "prioridade": 1, "produto": "x", "categoria": "y", "grupo": "Team11", "dataHora": "2025-12-15T14:00:00"},
            ],
            "referencia": "teste.csv",
            "persistir": True,
        }
        resposta = self.client.post("/api/queue/score", json=payload)
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()
        self.assertEqual(corpo["resumo"]["total"], 2)
        self.assertIsNotNone(corpo["loteId"])

        acao = self.client.post(
            "/api/actions",
            json={"ticketRef": "T-1", "acao": "atribuido", "probabilidade": 0.5, "faixa": "Alto", "loteId": corpo["loteId"], "perfil": "analista"},
        )
        self.assertEqual(acao.status_code, 200)

        resumo = self.client.get("/api/actions/summary").json()
        self.assertGreaterEqual(resumo["ticketsComAcao"], 1)
        self.assertGreaterEqual(resumo["riscoPriorizado"], 0.5)

    def test_acao_invalida_rejeitada(self):
        resposta = self.client.post("/api/actions", json={"ticketRef": "T-9", "acao": "inventada"})
        self.assertEqual(resposta.status_code, 422)


class TestGovernancaModelo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_deriva_detecta_quebra_de_regime(self):
        corpo = self.client.get("/api/drift").json()
        self.assertGreater(corpo["piorPsi"], 0.20)
        self.assertTrue(corpo["revalidacaoRecomendada"])
        volume = next(f for f in corpo["features"] if "Volume" in f["feature"])
        self.assertEqual(volume["nivel"], "alto")

    def test_status_do_modelo_expoe_janelas(self):
        corpo = self.client.get("/api/model-status").json()
        self.assertEqual(corpo["snapshot"], "2025-12-31")
        self.assertIn("12/2025", corpo["risco"]["holdout"])
        self.assertTrue(corpo["revalidacaoRecomendada"])
        self.assertTrue(corpo["motivos"])


class TestOtimizacaoESegmentacao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_milp_reproduz_secao_18(self):
        corpo = self.client.get("/api/optimization", params={"capacidade": 5}).json()
        self.assertEqual(round(corpo["coberturaPct"]), 66)
        selecionados = {item["produto"] for item in corpo["selecionados"]}
        self.assertEqual(selecionados, {"lsin", "lhco", "lcem", "lhvp", "lcsi"})
        self.assertGreater(corpo["precoSombra"], 0)
        # capacidade maior cobre mais risco (retorno marginal decrescente)
        maior = self.client.get("/api/optimization", params={"capacidade": 10}).json()
        self.assertGreater(maior["coberturaPct"], corpo["coberturaPct"])

    def test_segmentacao_kmeans_por_dimensao(self):
        corpo = self.client.get("/api/segmentation", params={"dimension": "Produto"}).json()
        self.assertIn(corpo["kEscolhido"], range(2, 7))
        self.assertEqual(corpo["clusters"][0]["posicao"], 0)
        # cluster 0 = mais crítico: maior taxa média
        taxas = [c["taxaMedia"] for c in corpo["clusters"]]
        self.assertEqual(taxas, sorted(taxas, reverse=True))


class TestContratoLegadoSprint3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_e_total(self):
        self.assertEqual(self.client.get("/health").json()["status"], "ok")
        self.assertEqual(self.client.get("/incidentes/total").json()["total_incidentes_no_banco"], 122_543)

    def test_previsao_gera_4_alvos_e_persiste(self):
        corpo = self.client.get("/previsao").json()
        alvos = {linha["alvo"] for linha in corpo}
        self.assertEqual(alvos, {"incidentes_total", "incidentes_kpi", "ola_violados", "duracao"})
        for linha in corpo:
            self.assertIn(linha["horizonte"], {"D+1", "D+7"})
            self.assertIn("rmse", linha)
        historico = self.client.get("/previsao/historico").json()
        self.assertGreaterEqual(len(historico), len(corpo))


if __name__ == "__main__":
    unittest.main()
