"""Pruebas del pipeline. Se ejecutan con:  python -m unittest discover -s tests -v

Corren el proceso completo sobre data/raw/ y escriben en una carpeta temporal,
así no tocan los archivos de data/processed/ ni de outputs/.
"""
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src import integracion, pipeline, validaciones


class TestPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        cls.base = base
        cls.res = pipeline.ejecutar(dir_processed=base / "processed", dir_outputs=base / "outputs")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_todos_los_controles_pasan(self):
        fallas = [r.control for r in self.res["resultados"] if not r.ok]
        self.assertEqual(fallas, [])

    def test_consolidado_tiene_el_tamano_esperado(self):
        self.assertEqual(self.res["consolidado"].shape, (2149, 19))
        self.assertEqual(self.res["consolidado"]["order_id"].nunique(), 830)

    def test_importe_total_conservado(self):
        total = round(self.res["consolidado"]["importe"].sum(), 2)
        self.assertEqual(total, 1249945.73)

    def test_huerfanas_separadas_y_no_borradas(self):
        h = self.res["huerfanas"]
        self.assertEqual(len(h), 6)
        self.assertEqual(sorted(h["order_id"]), ["19473", "19475", "19484", "19550", "19614", "A10363"])

    def test_se_escriben_los_archivos(self):
        for ruta in ["processed/northwind_consolidado.csv", "processed/northwind_huerfanas.csv",
                     "outputs/reporte_diagnostico.txt", "outputs/reporte_validaciones.txt"]:
            self.assertTrue((self.base / ruta).exists(), ruta)

    def test_ejecucion_repetida_da_el_mismo_resultado(self):
        otra = pipeline.ejecutar(dir_processed=self.base / "p2", dir_outputs=self.base / "o2")
        pd.testing.assert_frame_equal(self.res["consolidado"], otra["consolidado"])


class TestValidacionesDetectanErrores(unittest.TestCase):
    """Los controles deben fallar cuando los datos están dañados (no pasar en silencio)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        cls.res = pipeline.ejecutar(dir_processed=base / "processed", dir_outputs=base / "outputs")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _validar(self, orders=None, details=None, consolidado=None):
        r = self.res
        return validaciones.validar_pipeline(
            r["df_orders_raw"], r["df_details_raw"],
            r["orders"] if orders is None else orders,
            r["details"] if details is None else details,
            r["huerfanas"],
            r["consolidado"] if consolidado is None else consolidado,
            r["info_dup_details"], r["reconciliacion"])

    def _fallas(self, resultados):
        return [x.control for x in resultados if not x.ok]

    def test_detecta_cantidad_negativa(self):
        details = self.res["details"].copy()
        details.loc[details.index[0], "quantity"] = -5
        self.assertTrue(any("quantity" in c for c in self._fallas(self._validar(details=details))))

    def test_detecta_order_id_duplicado_en_orders(self):
        orders = pd.concat([self.res["orders"], self.res["orders"].iloc[[0]]])
        self.assertTrue(any("unicidad" in c for c in self._fallas(self._validar(orders=orders))))

    def test_la_union_falla_si_orders_tiene_claves_repetidas(self):
        orders = pd.concat([self.res["orders"], self.res["orders"].iloc[[0]]])
        with self.assertRaises(pd.errors.MergeError):
            integracion.integrar(self.res["details"], orders)

    def test_exigir_todos_ok_lanza_error(self):
        details = self.res["details"].copy()
        details.loc[details.index[0], "discount"] = 0.9
        with self.assertRaises(validaciones.ValidacionError):
            validaciones.exigir_todos_ok(self._validar(details=details))


if __name__ == "__main__":
    unittest.main()
