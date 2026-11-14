from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest

# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


_WATER_SCARCE_WORDS = {"escassa", "baixa", "limitada", "scarce", "low", "limited"}

# Catálogo de rotações candidatas (atributos relativos 0–1; heurística até haver
# modelo treinado). `water_demand`: necessidade hídrica; `heat_tolerance` e
# `soil_benefit`: tolerância ao calor e melhoria do solo; `market`: mercado estabelecido.
_ROTATION_CATALOG: list[dict[str, Any]] = [
    {
        "strategy": "Milho -> Soja",
        "water_demand": 0.90,
        "heat_tolerance": 0.45,
        "soil_benefit": 0.45,
        "market": 0.95,
        "benefits": "Mercado estabelecido e cadeia de comercialização consolidada",
    },
    {
        "strategy": "Sorgo -> Feijão-caupi",
        "water_demand": 0.35,
        "heat_tolerance": 0.90,
        "soil_benefit": 0.80,
        "market": 0.60,
        "benefits": "Alta tolerância à seca, fixa nitrogênio",
    },
    {
        "strategy": "Milheto -> Amendoim",
        "water_demand": 0.55,
        "heat_tolerance": 0.75,
        "soil_benefit": 0.85,
        "market": 0.70,
        "benefits": "Melhora a estrutura do solo",
    },
    {
        "strategy": "Mandioca -> Crotalária",
        "water_demand": 0.45,
        "heat_tolerance": 0.85,
        "soil_benefit": 0.90,
        "market": 0.55,
        "benefits": "Rústica, cobre o solo e controla nematoides",
    },
    {
        "strategy": "Feijão -> Milho",
        "water_demand": 0.70,
        "heat_tolerance": 0.55,
        "soil_benefit": 0.70,
        "market": 0.85,
        "benefits": "Feijão fixa nitrogênio para o milho seguinte",
    },
]
_DEFAULT_CURRENT_PRACTICE = "Milho -> Soja"


class CropSimulator:
    """Simulador de rotações [M3]: calcula viabilidade a partir das métricas do talhão."""

    # Pesos do score (somam 1.0). Com prioridade hídrica a água pesa mais.
    _WEIGHTS = {"water": 0.45, "heat": 0.25, "soil": 0.20, "market": 0.10}
    _WEIGHTS_WATER_PRIORITY = {"water": 0.60, "heat": 0.20, "soil": 0.15, "market": 0.05}

    def __init__(self):
        pass

    # -- leitura robusta das métricas (provider real/mock ou fallback da API) --

    @staticmethod
    def _read_metrics(field_metrics: dict[str, Any] | None) -> dict[str, float]:
        m = field_metrics or {}
        has_data = m.get("data_quality") != "no_data"

        def pick(*keys: str) -> float | None:
            for key in keys:
                value = _to_float(m.get(key))
                if value is not None:
                    return value
            return None

        moisture = pick("avg_soil_moisture_smap") if has_data else None
        if moisture is None:
            moisture = pick("umidade_solo_estimada", "umidade_solo", "soil_moisture")
        temp = pick("avg_surface_temp_ecostress") if has_data else None
        if temp is None:
            temp = pick("temperatura_media_c", "surface_temp_c")

        daily_rain = pick("avg_precipitation_gpm") if has_data else None
        if daily_rain is not None:
            annual_rain = daily_rain * 365.0
        else:
            annual_rain = pick("precipitacao_estimada_mm", "precipitacao_mm", "precipitation_mm")

        return {
            "moisture": 0.25 if moisture is None else moisture,
            "temp_c": 27.0 if temp is None else temp,
            "annual_rain_mm": 1200.0 if annual_rain is None else annual_rain,
        }

    @staticmethod
    def _water_priority(priorities: dict[str, Any] | None) -> bool:
        p = priorities or {}
        agua = str(p.get("agua", "")).strip().lower()
        flag = p.get("water_conservation") or p.get("conservacao_agua")
        return agua in _WATER_SCARCE_WORDS or bool(flag)

    @staticmethod
    def _water_supply(metrics: dict[str, float]) -> float:
        moist_idx = _clamp(metrics["moisture"] / 0.35)
        rain_idx = _clamp(metrics["annual_rain_mm"] / 1200.0)
        return 0.6 * moist_idx + 0.4 * rain_idx

    @staticmethod
    def _risk_from_gap(gap: float) -> str:
        if gap > 0.15:
            return "high"
        if gap > -0.10:
            return "medium"
        return "low"

    def _score(
        self,
        metrics: dict[str, float],
        water_demand: float,
        heat_tolerance: float,
        soil_benefit: float,
        market: float,
        water_priority: bool,
    ) -> dict[str, Any]:
        supply = self._water_supply(metrics)
        gap = water_demand - supply
        water_fit = _clamp(1.0 - max(gap, 0.0) * 1.8)
        heat_stress = _clamp((metrics["temp_c"] - 28.0) / 12.0)
        heat_fit = 1.0 - heat_stress * (1.0 - heat_tolerance)

        w = self._WEIGHTS_WATER_PRIORITY if water_priority else self._WEIGHTS
        viability = (
            w["water"] * water_fit
            + w["heat"] * heat_fit
            + w["soil"] * soil_benefit
            + w["market"] * market
        )
        return {
            "viability": round(_clamp(viability), 2),
            "water_risk": self._risk_from_gap(gap),
            "score_breakdown": {
                "water_fit": round(water_fit, 3),
                "heat_fit": round(heat_fit, 3),
                "soil_benefit": round(soil_benefit, 3),
                "market": round(market, 3),
                "water_supply": round(supply, 3),
                "water_demand": round(water_demand, 3),
            },
        }

    # -- API pública -----------------------------------------------------

    def simulate_rotation_strategies(
        self, field_metrics: dict[str, Any], farmer_priorities: dict
    ) -> list[dict[str, Any]]:
        """
        Gera e compara 3 estratégias de rotação, sempre incluindo a prática atual
        do agricultor (`farmer_priorities["pratica_atual"]`, padrão "Milho -> Soja").
        Quando `farmer_priorities["rotacoes_preferenciais"]` estiver presente, avalia
        e inclui a melhor rotação preferencial cadastrada pelo produtor no comparativo.
        """
        metrics = self._read_metrics(field_metrics)
        water_priority = self._water_priority(farmer_priorities)
        priorities_dict = farmer_priorities or {}
        current_name = str(
            priorities_dict.get("pratica_atual") or _DEFAULT_CURRENT_PRACTICE
        ).strip()

        def normalize(name: str) -> str:
            return name.lower().replace("(atual)", "").replace("→", "->").replace(" ", "")

        catalog_by_norm: dict[str, dict[str, Any]] = {}
        for item in _ROTATION_CATALOG:
            catalog_by_norm[normalize(item["strategy"])] = {**item, "preferred": False}

        preferred_raw = priorities_dict.get("rotacoes_preferenciais") or []
        if isinstance(preferred_raw, list):
            for raw in preferred_raw:
                if isinstance(raw, str):
                    name = raw.strip()
                    if not name:
                        continue
                    base = catalog_by_norm.get(normalize(name), {})
                    entry = {
                        "strategy": name,
                        "water_demand": base.get("water_demand", 0.55),
                        "heat_tolerance": base.get("heat_tolerance", 0.70),
                        "soil_benefit": base.get("soil_benefit", 0.70),
                        "market": base.get("market", 0.65),
                        "benefits": base.get("benefits") or "Rotação preferencial cadastrada pelo produtor",
                        "preferred": True,
                    }
                    catalog_by_norm[normalize(name)] = entry
                elif isinstance(raw, dict):
                    culturas = raw.get("culturas")
                    name = str(
                        raw.get("strategy")
                        or raw.get("nome")
                        or (" -> ".join(culturas) if isinstance(culturas, list) else "")
                    ).strip()
                    if not name:
                        continue
                    base = catalog_by_norm.get(normalize(name), {})
                    entry = {
                        "strategy": name,
                        "water_demand": _clamp(
                            _to_float(raw.get("water_demand"))
                            if _to_float(raw.get("water_demand")) is not None
                            else base.get("water_demand", 0.55)
                        ),
                        "heat_tolerance": _clamp(
                            _to_float(raw.get("heat_tolerance"))
                            if _to_float(raw.get("heat_tolerance")) is not None
                            else base.get("heat_tolerance", 0.70)
                        ),
                        "soil_benefit": _clamp(
                            _to_float(raw.get("soil_benefit"))
                            if _to_float(raw.get("soil_benefit")) is not None
                            else base.get("soil_benefit", 0.70)
                        ),
                        "market": _clamp(
                            _to_float(raw.get("market"))
                            if _to_float(raw.get("market")) is not None
                            else base.get("market", 0.65)
                        ),
                        "benefits": str(
                            raw.get("benefits")
                            or raw.get("beneficios")
                            or base.get("benefits")
                            or "Rotação preferencial cadastrada pelo produtor"
                        ),
                        "preferred": True,
                    }
                    catalog_by_norm[normalize(name)] = entry

        results: list[dict[str, Any]] = []
        for item in catalog_by_norm.values():
            scored = self._score(
                metrics,
                item["water_demand"],
                item["heat_tolerance"],
                item["soil_benefit"],
                item["market"],
                water_priority,
            )
            results.append(
                {
                    "strategy": item["strategy"],
                    "viability": scored["viability"],
                    "water_risk": scored["water_risk"],
                    "benefits": item["benefits"],
                    "score_breakdown": scored["score_breakdown"],
                    "_preferred": bool(item.get("preferred", False)),
                }
            )

        current = next(
            (r for r in results if normalize(r["strategy"]) == normalize(current_name)),
            None,
        )
        if current is None:
            # Prática atual fora do catálogo: avalia com atributos médios.
            scored = self._score(metrics, 0.65, 0.55, 0.40, 0.70, water_priority)
            current = {
                "strategy": current_name,
                "viability": scored["viability"],
                "water_risk": scored["water_risk"],
                "benefits": "Prática atual do produtor",
                "score_breakdown": scored["score_breakdown"],
            }
        else:
            results.remove(current)
            current = {k: v for k, v in current.items() if k != "_preferred"}
        current = {**current, "strategy": f"{current['strategy']} (Atual)"}

        preferred_candidates = sorted(
            [r for r in results if r.get("_preferred")],
            key=lambda r: r["viability"],
            reverse=True,
        )
        selected_others: list[dict[str, Any]] = []
        if preferred_candidates:
            top_pref = preferred_candidates[0]
            selected_others.append(top_pref)
            remaining = [r for r in results if r is not top_pref]
            remaining_sorted = sorted(remaining, key=lambda r: r["viability"], reverse=True)
            if remaining_sorted:
                selected_others.append(remaining_sorted[0])
        else:
            selected_others = sorted(
                results, key=lambda r: r["viability"], reverse=True
            )[:2]

        cleaned_others = [
            {k: v for k, v in item.items() if k != "_preferred"}
            for item in selected_others
        ]
        return sorted([current, *cleaned_others], key=lambda r: r["viability"], reverse=True)

    def predict_rotation_viability(
        self,
        soil_data: dict,
        climate_data: dict,
        crop_requirements: dict | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """
        Compatível com a rota /api/v1/simulacoes/ (3 args -> dict) e com a
        simulação de 3 estratégias (2 args -> list).
        """
        if crop_requirements is None:
            return self.simulate_rotation_strategies(soil_data, climate_data)

        metrics = self._read_metrics(climate_data)
        priorities = (soil_data or {}).get("prioridades_terreno") or {}
        consumo = _to_float(crop_requirements.get("consumo_agua_mm")) or 450.0
        ciclo = _to_float(crop_requirements.get("tempo_colheita_dias")) or 90.0

        # Culturas de ciclo longo ficam mais expostas ao calor; sem dado de
        # benefício de solo/mercado, usa valores neutros.
        heat_tolerance = _clamp(0.8 - (ciclo / 365.0) * 0.3)
        scored = self._score(
            metrics,
            water_demand=_clamp(consumo / 700.0),
            heat_tolerance=heat_tolerance,
            soil_benefit=0.5,
            market=0.6,
            water_priority=self._water_priority(priorities),
        )
        return {
            "viability_score": scored["viability"],
            "water_risk": scored["water_risk"],
            "score_breakdown": scored["score_breakdown"],
        }


class ClimateAnomalyDetector:
    """Detecta extremos climáticos (calor, seca, chuva intensa) para [M5].

    Contrato de saída (consumido por alert_tasks.py e api/alertas.py):
    {"anomaly_detected": bool, "tipo_evento": str, "severidade": str, "detalhes": dict}
    tipo_evento ∈ {"onda_de_calor", "seca", "chuva_intensa", "nenhum"}.

    Duas camadas: (1) limiares absolutos; (2) IsolationForest sobre a série, que só
    dispara se o ponto isolado também for um outlier robusto (MAD), evitando
    falsos positivos em séries normais (contamination garante ~5% de outliers).
    """

    HEAT_C = 35.0
    DROUGHT_MOISTURE = 0.15
    HEAVY_RAIN_MM = 60.0
    MIN_POINTS_ML = 10
    ROBUST_Z = 3.5

    # (chave canônica, aliases aceitos)
    _FEATURES = {
        "precipitation_mm": ("precipitation_mm", "precipitacao_mm"),
        "surface_temp_c": ("surface_temp_c", "temperatura_media_c"),
        "soil_moisture": ("soil_moisture", "umidade_solo"),
    }

    def __init__(self):
        self.model = IsolationForest(contamination=0.05, random_state=42)

    @staticmethod
    def _num(item: dict, *keys: str) -> float | None:
        for key in keys:
            value = _to_float(item.get(key))
            if value is not None:
                return value
        return None

    def _extract(self, series: list[dict]) -> dict[str, list[float | None]]:
        return {
            name: [self._num(p, *aliases) for p in series]
            for name, aliases in self._FEATURES.items()
        }

    def _threshold_event(
        self, max_precip: float, max_temp: float, min_moist: float | None
    ) -> tuple[str, str]:
        if max_precip >= self.HEAVY_RAIN_MM:
            return "chuva_intensa", ("critica" if max_precip >= 2 * self.HEAVY_RAIN_MM else "alta")
        if max_temp >= self.HEAT_C:
            return "onda_de_calor", ("critica" if max_temp >= 40.0 else "alta")
        if min_moist is not None and min_moist <= self.DROUGHT_MOISTURE:
            return "seca", "alta"
        return "nenhum", "baixa"

    def _statistical_event(
        self, series: list[dict], values: dict[str, list[float | None]]
    ) -> tuple[str, list[int]]:
        """IsolationForest + z-score robusto. Retorna (tipo_evento, índices outliers)."""
        # Só features presentes em todos os pontos entram no modelo.
        names = [n for n, col in values.items() if all(v is not None for v in col)]
        if not names or len(series) < self.MIN_POINTS_ML:
            return "nenhum", []

        x = np.array([values[n] for n in names], dtype=float).T
        flags = self.model.fit(x).predict(x)  # -1 = outlier
        candidates = [i for i, f in enumerate(flags) if f == -1]

        # Só interessa o sentido de risco agrícola: chuva alta, calor alto, umidade baixa.
        direction = {"precipitation_mm": 1.0, "surface_temp_c": 1.0, "soil_moisture": -1.0}
        event_for = {
            "precipitation_mm": "chuva_intensa",
            "surface_temp_c": "onda_de_calor",
            "soil_moisture": "seca",
        }

        confirmed: list[tuple[float, str, int]] = []
        for j, name in enumerate(names):
            col = x[:, j]
            med = float(np.median(col))
            mad = float(np.median(np.abs(col - med)))
            if mad == 0.0:
                continue
            for i in candidates:
                z = direction[name] * 0.6745 * (col[i] - med) / mad
                if z >= self.ROBUST_Z:
                    confirmed.append((z, event_for[name], i))

        if not confirmed:
            return "nenhum", []
        confirmed.sort(reverse=True)
        tipo = confirmed[0][1]
        indices = sorted({i for _, ev, i in confirmed if ev == tipo})
        return tipo, indices

    def detect_extremes(self, time_series_data: dict | list[dict]) -> dict:
        """Aceita um ponto (dict) ou série (list[dict]); retorna o contrato descrito acima."""
        series = (
            time_series_data
            if isinstance(time_series_data, list)
            else [time_series_data or {}]
        )
        series = [p for p in series if isinstance(p, dict)]
        values = self._extract(series)

        precips = [v for v in values["precipitation_mm"] if v is not None]
        temps = [v for v in values["surface_temp_c"] if v is not None]
        moist = [v for v in values["soil_moisture"] if v is not None]

        max_precip = max(precips, default=0.0)
        max_temp = max(temps, default=0.0)
        min_moist = min(moist) if moist else None

        tipo, severidade = self._threshold_event(max_precip, max_temp, min_moist)
        metodo = "limiar"
        indices: list[int] = []

        if tipo == "nenhum":
            tipo_ml, indices = self._statistical_event(series, values)
            if tipo_ml != "nenhum":
                tipo, severidade, metodo = tipo_ml, "media", "isolation_forest"

        return {
            "anomaly_detected": tipo != "nenhum",
            "tipo_evento": tipo,
            "severidade": severidade,
            "detalhes": {
                "metodo": metodo,
                "pontos_analisados": len(series),
                "indices_outliers": indices,
                "max_precipitation_mm": max_precip,
                "max_surface_temp_c": max_temp,
                "min_soil_moisture": min_moist,
            },
        }
