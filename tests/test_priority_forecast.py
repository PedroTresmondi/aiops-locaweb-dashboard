import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.datasource import carregar
from backend.main import app, priority_model
from backend.priority_forecast import preparar_features, prever_prioridades, serie_prioridade


class TestPriorityForecast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = carregar()
        cls.resultado = prever_prioridades(cls.df)

    def test_tem_p2_p3_nos_dois_horizontes(self):
        self.assertEqual({(f['prioridade'], f['horizonte']) for f in self.resultado['previsoes']}, {(2, 'D+1'), (2, 'D+7'), (3, 'D+1'), (3, 'D+7')})
        for f in self.resultado['previsoes']:
            self.assertEqual(f['dataAlvo'], '2026-01-01' if f['horizonte'] == 'D+1' else '2026-01-07')
            self.assertLessEqual(0, f['inferior'])
            self.assertLessEqual(f['inferior'], f['ponto'])
            self.assertGreaterEqual(f['superior'], f['ponto'])

    def test_metricas_recalculaveis_sem_esconder_regressoes(self):
        for f in self.resultado['previsoes']:
            bt = pd.DataFrame(f['backtest'])
            self.assertAlmostEqual(f['validacao']['mae'], (bt.real - bt.previsto).abs().mean(), delta=.02)
            self.assertAlmostEqual(f['validacao']['maeBaseline'], (bt.real - bt.baseline).abs().mean(), delta=.02)
            self.assertLess(f['selecao']['fim'], f['validacao']['inicio'])
        self.assertTrue(any(f['validacao']['ganho'] < 0 for f in self.resultado['previsoes']))

    def test_dias_sem_incidentes_permanecem_no_calendario(self):
        df = pd.DataFrame({'Aberto': pd.to_datetime(['2025-01-01', '2025-01-03']), 'Prioridade_Cod': [2, 3]})
        self.assertEqual(serie_prioridade(df, 2).tolist(), [1., 0., 0.])
        self.assertEqual(serie_prioridade(df, 3).tolist(), [0., 0., 1.])

    def test_features_nao_mudam_quando_o_futuro_muda(self):
        serie = pd.Series(np.arange(100, dtype=float), index=pd.date_range('2025-01-01', periods=100))
        for dias in (1, 7):
            original, features = preparar_features(serie, dias)
            alterada = serie.copy()
            alterada.iloc[61:] = 100000
            mudou, _ = preparar_features(alterada, dias)
            pd.testing.assert_frame_equal(original.loc[:serie.index[60], features], mudou.loc[:serie.index[60], features])
            self.assertEqual(original.baseline.iloc[-1], serie.iloc[-1 - (7 - dias)])

    def test_selecao_nao_muda_com_resultados_do_teste(self):
        extras = self.df[pd.to_datetime(self.df.Aberto) >= '2025-12-01']
        alterado = prever_prioridades(pd.concat([self.df, extras], ignore_index=True))
        for original, modificado in zip(self.resultado['previsoes'], alterado['previsoes']):
            self.assertEqual(original['modelo'], modificado['modelo'])
            self.assertEqual(original['selecao'], modificado['selecao'])

    def test_historico_insuficiente_rejeitado(self):
        with self.assertRaisesRegex(ValueError, 'insuficiente'):
            prever_prioridades(self.df[pd.to_datetime(self.df.Aberto) >= '2025-12-01'])

    def test_api_e_erro_de_dados(self):
        with TestClient(app) as client:
            response = client.get('/api/forecast/priorities')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()['previsoes']), 4)
            with patch('backend.main.priority_model', side_effect=ValueError('Histórico insuficiente')):
                self.assertEqual(client.get('/api/forecast/priorities').status_code, 422)
        priority_model.cache_clear()


if __name__ == '__main__':
    unittest.main()
