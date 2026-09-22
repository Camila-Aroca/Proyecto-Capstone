"""Pruebas del registro de modelos, de la preparacion del holdout y de su evaluacion.

Usan archivos temporales y dobles de prueba: no dependen de `data/processed/`
ni de los RAW reales.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

import scripts.run_pipeline as pipeline
import src.models.holdout as holdout_mod
from src.data.build_urgencias_comuna_marts import load_urgencias_source
from src.data.clean_poblacion_proyecciones import load_rm_population
from src.models.conformal import ConformalWrapper
from src.models.registry import HIBRIDO, available_models, build_model


class TestRegistro:
    def test_cada_nombre_produce_un_modelo_con_ese_nombre(self):
        for nombre in available_models():
            assert build_model(nombre).name == nombre

    def test_nombre_desconocido_falla_explicitamente(self):
        with pytest.raises(KeyError, match="no construible"):
            build_model("lightgbm_global_bottom_up")

    def test_variantes_conformes_envuelven_a_su_base(self):
        modelo = build_model(f"{HIBRIDO}_conformal")
        assert isinstance(modelo, ConformalWrapper)
        assert modelo.base.name == HIBRIDO

    def test_propaga_el_nivel_del_intervalo(self):
        assert build_model("poisson_glm_global", nivel=0.9).nivel == 0.9


class TestCargasParametrizadas:
    def test_urgencias_lee_los_anios_pedidos(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="urgencias_rm_2031"):
            load_urgencias_source(input_dir=tmp_path, years=(2031,))

    def test_poblacion_rechaza_anios_fuera_del_cuadro_ine(self):
        with pytest.raises(ValueError, match="fuera del cuadro INE"):
            load_rm_population(years=(2040,))


class TestAniosHoldout:
    def test_detecta_solo_anios_posteriores_al_entrenamiento(self, tmp_path):
        for ano in (2024, 2025, 2026, 2027):
            (tmp_path / f"urgencias_rm_{ano}.parquet").write_bytes(b"x")
        (tmp_path / "otro_archivo.parquet").write_bytes(b"x")
        assert holdout_mod.holdout_years(2025, tmp_path) == [2026, 2027]

    def test_sin_anios_posteriores_devuelve_vacio(self, tmp_path):
        (tmp_path / "urgencias_rm_2025.parquet").write_bytes(b"x")
        assert holdout_mod.holdout_years(2025, tmp_path) == []


class TestSnapshot:
    def _preparar(self, tmp_path, contenido_raw: bytes, manifiesto: list | None):
        raw_dir = tmp_path / "raw"
        proc_dir = tmp_path / "proc"
        raw_dir.mkdir()
        proc_dir.mkdir()
        (raw_dir / "AtencionesUrgencia2026.csv").write_bytes(contenido_raw)
        (proc_dir / "urgencias_rm_2026.parquet").write_bytes(b"procesado")
        manifest = tmp_path / "manifest.json"
        if manifiesto is not None:
            manifest.write_text(json.dumps(manifiesto), encoding="utf-8")
        return raw_dir, proc_dir, manifest

    def test_raw_sin_registro_en_el_manifiesto(self, tmp_path):
        raw_dir, proc_dir, manifest = self._preparar(tmp_path, b"datos", [])
        info = holdout_mod.snapshot_info([2026], raw_dir, proc_dir, manifest)
        fila = info.iloc[0]
        assert fila["estado_procedencia"] == "sin_registro"
        assert len(fila["raw_sha256"]) == 64
        assert len(fila["procesado_sha256"]) == 64

    def test_raw_registrado_coincide_con_el_ultimo_snapshot(self, tmp_path):
        from src.data.download_deis_sources import file_sha256

        raw_dir, proc_dir, manifest = self._preparar(tmp_path, b"datos", None)
        hash_raw = file_sha256(raw_dir / "AtencionesUrgencia2026.csv")
        manifest.write_text(
            json.dumps(
                [
                    {
                        "source_id": "deis_urgencias_2026",
                        "snapshots": [
                            {"raw_sha256": "viejo", "downloaded_at": "2026-01-01"},
                            {"raw_sha256": hash_raw, "downloaded_at": "2026-09-01"},
                        ],
                    }
                ]
            ),
            encoding="utf-8",
        )
        fila = holdout_mod.snapshot_info([2026], raw_dir, proc_dir, manifest).iloc[0]
        assert fila["estado_procedencia"] == "registrado"
        assert fila["procedencia_registrada_en"] == "2026-09-01"

    def test_raw_distinto_del_registrado(self, tmp_path):
        raw_dir, proc_dir, manifest = self._preparar(
            tmp_path,
            b"datos nuevos",
            [{"source_id": "deis_urgencias_2026", "snapshots": [{"raw_sha256": "otro"}]}],
        )
        fila = holdout_mod.snapshot_info([2026], raw_dir, proc_dir, manifest).iloc[0]
        assert fila["estado_procedencia"] == "difiere_del_registrado"


class TestSemanalHoldout:
    """Filtra con dobles de la carga, para probar solo las reglas de exclusion."""

    def _instalar_dobles(self, monkeypatch, fechas_por_semana, comunas):
        filas_fuente, filas_semanal = [], []
        for semana, n_dias in fechas_por_semana.items():
            for dia in range(n_dias):
                for comuna in comunas:
                    filas_fuente.append(
                        {
                            "ano": 2026, "semana": semana,
                            "fecha": pd.Timestamp("2026-01-04")
                            + pd.Timedelta(days=7 * (semana - 1) + dia),
                            "comuna_codigo": comuna, "id_causa": 36, "total": 1,
                        }
                    )
            for comuna in comunas:
                filas_semanal.append(
                    {
                        "comuna_codigo": comuna, "comuna_glosa": f"C{comuna}",
                        "ano": 2026, "semana": semana, "atenciones_id36": n_dias,
                    }
                )
        fuente = pd.DataFrame(filas_fuente)
        monkeypatch.setattr(holdout_mod, "load_urgencias_source", lambda **_: fuente)
        monkeypatch.setattr(
            holdout_mod,
            "load_rm_population",
            lambda **_: pd.DataFrame({"comuna_codigo": [], "ano": [], "poblacion": []}),
        )
        monkeypatch.setattr(
            holdout_mod, "build_weekly_mart", lambda *_: pd.DataFrame(filas_semanal)
        )

    def test_excluye_semanas_truncadas(self, monkeypatch):
        self._instalar_dobles(monkeypatch, {1: 7, 2: 7, 3: 3}, ["13101"])
        semanal, diag = holdout_mod.load_holdout_weekly([2026], self._ref(["13101"]))
        assert sorted(semanal["semana"]) == [1, 2]
        incompletas = diag["semanas_incompletas"]
        assert list(incompletas["semana"]) == [3]
        assert int(incompletas["dias"].iloc[0]) == 3

    def test_no_trata_la_semana_53_como_truncada(self, monkeypatch):
        # El fragmento de la semana 53 lo descarta `build_panel`; aqui no se reporta.
        self._instalar_dobles(monkeypatch, {1: 7, 53: 3}, ["13101"])
        _, diag = holdout_mod.load_holdout_weekly([2026], self._ref(["13101"]))
        assert diag["semanas_incompletas"].empty

    def test_excluye_y_cuantifica_comunas_sin_historia(self, monkeypatch):
        self._instalar_dobles(monkeypatch, {1: 7, 2: 7}, ["13101", "13132"])
        semanal, diag = holdout_mod.load_holdout_weekly([2026], self._ref(["13101"]))
        assert set(semanal["comuna_codigo"]) == {"13101"}
        nuevas = diag["comunas_sin_historia"]
        assert list(nuevas["comuna_codigo"]) == ["13132"]
        assert float(nuevas["share_holdout_pct"].iloc[0]) == pytest.approx(50.0)

    @staticmethod
    def _ref(comunas, volumenes=None):
        return pd.Series(volumenes or [1.0] * len(comunas), index=comunas)

    def test_comuna_que_deja_de_reportar_se_excluye_y_se_informa(self, monkeypatch):
        self._instalar_dobles(monkeypatch, {1: 7, 2: 7, 3: 7}, ["13101", "13102"])
        # 13102 deja de reportar desde la semana 3: no se rellena con ceros.
        original = holdout_mod.build_weekly_mart

        def sin_ultima_semana(*argumentos):
            semanal = original(*argumentos)
            corte = (semanal["comuna_codigo"] == "13102") & (semanal["semana"] == 3)
            return semanal[~corte]

        monkeypatch.setattr(holdout_mod, "build_weekly_mart", sin_ultima_semana)
        semanal, diag = holdout_mod.load_holdout_weekly(
            [2026], self._ref(["13101", "13102"], [99.0, 1.0])
        )
        assert set(semanal["comuna_codigo"]) == {"13101"}
        fila = diag["comunas_cobertura_incompleta"].iloc[0]
        assert fila["comuna_codigo"] == "13102"
        assert fila["semanas_con_datos"] == 2
        assert fila["semanas_esperadas"] == 3
        assert fila["ultima_semana_con_datos"] == 2
        assert fila["share_referencia_pct"] == pytest.approx(1.0)

    def test_comuna_con_historia_ausente_se_excluye(self, monkeypatch):
        self._instalar_dobles(monkeypatch, {1: 7}, ["13101"])
        semanal, diag = holdout_mod.load_holdout_weekly(
            [2026], self._ref(["13101", "13102"], [99.0, 1.0])
        )
        assert set(semanal["comuna_codigo"]) == {"13101"}
        assert int(diag["comunas_cobertura_incompleta"].iloc[0]["semanas_con_datos"]) == 0

    def test_exclusion_excesiva_hace_fallar_la_evaluacion(self, monkeypatch):
        self._instalar_dobles(monkeypatch, {1: 7}, ["13101"])
        # La comuna ausente pesa 50% del volumen: la evaluacion no representaria la RM.
        with pytest.raises(ValueError, match="representaria a la region"):
            holdout_mod.load_holdout_weekly(
                [2026], self._ref(["13101", "13102"], [1.0, 1.0])
            )


class TestEvaluacion:
    def test_evalua_baseline_conformes_y_recomendado(self):
        from scripts.evaluate_holdout_demanda_sm import REFERENCIA, models_to_evaluate

        nombres = models_to_evaluate(f"{HIBRIDO}_conformal")
        assert nombres[0] == REFERENCIA
        assert f"{HIBRIDO}_conformal" in nombres
        assert all(n.endswith("_conformal") for n in nombres[1:])
        # Un recomendado no conforme se agrega sin duplicar.
        assert models_to_evaluate("poisson_glm_global").count("poisson_glm_global") == 1

    def test_seleccion_no_construible_falla(self, tmp_path):
        from scripts.evaluate_holdout_demanda_sm import load_selection

        ruta = tmp_path / "seleccion.json"
        ruta.write_text(
            json.dumps({"modelo_recomendado": "hibrido_3niveles_wls_structural"}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="no es construible"):
            load_selection(ruta)

    def test_habilidad_controla_por_la_dificultad_del_periodo(self):
        from scripts.evaluate_holdout_demanda_sm import _lectura_degradacion

        # El MASE del modelo sube de 0,6 a 0,8, pero el baseline sube igual:
        # la habilidad se mantiene y no hay degradacion real.
        tabla, texto = _lectura_degradacion(
            "m",
            mase_holdout={"region": 0.8, "comuna": 0.8},
            mase_back={"region": 0.6, "comuna": 0.6},
            ref_holdout={"region": 1.0, "comuna": 1.0},
            ref_back={"region": 0.75, "comuna": 0.75},
        )
        assert (tabla["habilidad_backtest_pct"] == tabla["habilidad_holdout_pct"]).all()
        assert "conserva ventaja" in texto

    def test_lectura_vs_baseline_exige_significancia_en_ambos_niveles(self):
        from scripts.evaluate_holdout_demanda_sm import _lectura_vs_baseline

        base = {"n": 100, "proporcion_b_mejor": 0.7}
        _, supera = _lectura_vs_baseline(
            "m",
            {
                "region": {**base, "cambio_pct": -20.0, "p_valor": 0.01},
                "comuna": {**base, "cambio_pct": -5.0, "p_valor": 0.30},
            },
        )
        assert not supera

    def test_stage_registrado_despues_del_benchmark(self):
        stage = pipeline.STAGES["evaluate_holdout_demanda_sm"]
        assert stage["module"] == "scripts.evaluate_holdout_demanda_sm"
        assert set(stage["depends_on"]) == {
            "benchmark_demanda_sm",
            "clean_urgencias",
            "clean_poblacion_proyecciones",
        }
        orden = pipeline.PIPELINE_ORDER
        for upstream in stage["depends_on"]:
            assert orden.index(upstream) < orden.index("evaluate_holdout_demanda_sm")

    def test_json_invalido_no_pasa_la_validacion_de_outputs(self, tmp_path):
        roto = tmp_path / "x.json"
        roto.write_text("{no es json", encoding="utf-8")
        assert not pipeline.check_outputs_exist([str(roto)])
        valido = tmp_path / "y.json"
        valido.write_text(json.dumps({"a": 1}), encoding="utf-8")
        assert pipeline.check_outputs_exist([str(valido)])
