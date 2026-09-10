import os
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend import data_update, datasource, store  # noqa: E402
from backend.main import app, _clear_model_caches  # noqa: E402


class TestPilotAndUpdate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous = {key: os.environ.get(key) for key in ("VISIONOPS_DB", "VISIONOPS_ADMIN_TOKEN", "VISIONOPS_CURRENT_DATASET")}
        os.environ["VISIONOPS_DB"] = str(Path(tempfile.gettempdir()) / "visionops_test_operations.db")
        os.environ["VISIONOPS_ADMIN_TOKEN"] = "test-admin-key"
        os.environ["VISIONOPS_CURRENT_DATASET"] = str(Path(tempfile.gettempdir()) / "visionops_test_current.parquet")
        for base in (os.environ["VISIONOPS_DB"], os.environ["VISIONOPS_CURRENT_DATASET"]):
            for suffix in ("", "-wal", "-shm"):
                path = Path(base + suffix)
                if path.exists():
                    path.unlink()
        store._ultimo_db_inicializado = None
        _clear_model_caches()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        for base in (os.environ["VISIONOPS_DB"], os.environ["VISIONOPS_CURRENT_DATASET"]):
            for suffix in ("", "-wal", "-shm"):
                path = Path(base + suffix)
                if path.exists():
                    path.unlink()
        for key, value in cls.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        store._ultimo_db_inicializado = None
        _clear_model_caches()

    def tearDown(self):
        _clear_model_caches()

    def test_pilot_measures_reaction_effort_and_ola(self):
        action = self.client.post("/api/actions", json={
            "ticketRef": "PILOT-1", "acao": "escalado", "abertoEm": "2026-09-09T10:00:00Z",
            "esforcoMinutos": 7, "exercicio": False,
        })
        self.assertEqual(action.status_code, 200)
        self.assertFalse(action.json()["exercicio"])
        outcome = self.client.post("/api/pilot/outcomes", json={
            "ticketRef": "PILOT-1", "olaViolado": False, "resolvidoEm": "2026-09-09T11:00:00Z",
            "esforcoMinutos": 3,
        })
        self.assertEqual(outcome.status_code, 200)
        metrics = self.client.get("/api/pilot/metrics").json()
        self.assertGreaterEqual(metrics["chamadosComDecisao"], 1)
        self.assertGreaterEqual(metrics["chamadosComDesfecho"], 1)
        self.assertGreaterEqual(metrics["esforcoTotalMinutos"], 10)
        self.assertIsNotNone(metrics["tempoReacaoMedioHoras"])
        self.assertEqual(metrics["taxaViolacaoOla"], 0)

    def test_historical_exercise_does_not_enter_pilot(self):
        before = self.client.get("/api/pilot/metrics").json()["chamadosComDecisao"]
        self.client.post("/api/actions", json={"ticketRef": "OLD-1", "acao": "atribuido", "exercicio": True})
        self.assertEqual(self.client.get("/api/pilot/metrics").json()["chamadosComDecisao"], before)

    def test_outcome_requires_operational_decision(self):
        response = self.client.post("/api/pilot/outcomes", json={"ticketRef": "UNKNOWN", "olaViolado": True})
        self.assertEqual(response.status_code, 422)

    def test_import_is_protected_and_updates_snapshot(self):
        record = {"Número": "NEW-2026", "Prioridade_Cod": 3, "Produto": "produto", "Categoria": "categoria",
                  "Grupo designado": "equipe", "Aberto": "2026-09-01T09:00:00", "Resolvido": "2026-09-01T12:00:00",
                  "Duracao_Horas": 3, "Status": "Resolvido"}
        self.assertEqual(self.client.post("/api/data/import", json={"itens": [record]}).status_code, 401)
        response = self.client.post("/api/data/import", headers={"X-VisionOps-Admin": "test-admin-key"}, json={"itens": [record], "retreinar": False})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["importacao"]["snapshotDepois"][:10], "2026-09-01")
        self.assertEqual(response.json()["retreino"]["status"], "pendente")
        loaded = datasource.carregar()
        self.assertEqual(int((loaded["Número"].astype(str) == "NEW-2026").sum()), 1)
        self.assertTrue(bool(loaded.loc[loaded["Número"].astype(str) == "NEW-2026", "Desfecho_Conhecido"].iloc[0]))

    def test_unresolved_records_are_not_known_outcomes(self):
        df = data_update.normalize_records([{"id": "OPEN-1", "prioridade": 2, "openedAt": "2026-09-02T10:00:00"}])
        self.assertFalse(bool(df["Desfecho_Conhecido"].iloc[0]))

    def test_retrain_failure_restores_previous_file(self):
        target = Path(os.environ["VISIONOPS_CURRENT_DATASET"])
        before = target.read_bytes()
        record = {"id": "TOO-SPARSE", "prioridade": 3, "openedAt": "2026-10-01T09:00:00",
                  "resolvedAt": "2026-10-01T11:00:00", "duracaoHoras": 2, "status": "Resolvido"}
        response = self.client.post("/api/data/import", headers={"X-VisionOps-Admin": "test-admin-key"}, json={"itens": [record], "retreinar": True})
        self.assertEqual(response.status_code, 422)
        self.assertIn("restaurada", response.json()["detail"])
        self.assertEqual(target.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
