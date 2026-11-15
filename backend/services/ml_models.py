from typing import Any
import unicodedata

import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestRegressor

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

_LEGUMES = {
    "soja",
    "feijao",
    "feijao-caupi",
    "feijao-carioca",
    "feijao-de-porco",
    "amendoim",
    "crotalaria",
    "guandu",
}
_EXHAUSTIVE_CROPS = {
    "milho",
    "sorgo",
    "mandioca",
    "milheto",
    "pastagem",
    "algodao",
    "arroz",
}


def _canonical_crop(name: str) -> str:
    """Normaliza nome de cultura removendo acentos, espaços extras e '(atual)'."""
    cleaned = (
        str(name or "")
        .strip()
        .lower()
        .replace("(atual)", "")
        .replace("_", "-")
        .strip()
    )
    decomposed = unicodedata.normalize("NFKD", cleaned)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(ascii_text.split())


def _extract_crop_name(item: Any) -> str | None:
    """Extrai o nome da cultura a partir de string ou objeto CropOption."""
    if item is None or isinstance(item, bool):
        return None
    if isinstance(item, str):
        cleaned = item.strip()
        return cleaned or None
    if isinstance(item, dict):
        for key in ("officialName", "nome", "cultura", "name", "id"):
            val = item.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def _parse_crop_history(
    historico_cultivos: Any = None,
    farmer_priorities: dict[str, Any] | None = None,
    field_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normaliza histórico de cultivos (CropHistoryData, dict snake_case ou lista)."""
    raw = historico_cultivos
    if raw is None and isinstance(farmer_priorities, dict):
        raw = farmer_priorities.get("historico_cultivos")
    if raw is None and isinstance(field_metrics, dict):
        raw = field_metrics.get("historico_cultivos")

    empty = {
        "has_history": False,
        "ultimo_cultivo": None,
        "cultivo_anterior": None,
        "is_consecutive_monoculture": False,
        "crops": [],
    }
    if raw is None:
        return empty

    if isinstance(raw, dict):
        if raw.get("naoLembro") or raw.get("nao_lembro"):
            return empty

        if "culturas" in raw and isinstance(raw["culturas"], (list, tuple)):
            return _parse_crop_history(raw["culturas"])

        last_raw = raw.get("ultimoCultivo", raw.get("ultimo_cultivo"))
        prev_raw = raw.get("cultivoAnterior", raw.get("cultivo_anterior"))
        last_name = _extract_crop_name(last_raw)
        prev_name = _extract_crop_name(prev_raw)

        if last_name is None and prev_name is not None:
            last_name, prev_name = prev_name, None

        crops = [c for c in (prev_name, last_name) if c]
        if not crops:
            return empty
        last_canon = _canonical_crop(last_name or "")
        prev_canon = _canonical_crop(prev_name or "")
        return {
            "has_history": True,
            "ultimo_cultivo": last_canon,
            "cultivo_anterior": prev_canon or None,
            "is_consecutive_monoculture": bool(
                last_canon and prev_canon and last_canon == prev_canon
            ),
            "crops": crops,
        }

    if isinstance(raw, (list, tuple)):
        crops = [name for item in raw if (name := _extract_crop_name(item))]
        if not crops:
            return empty
        last_canon = _canonical_crop(crops[-1])
        prev_canon = _canonical_crop(crops[-2]) if len(crops) >= 2 else ""
        return {
            "has_history": True,
            "ultimo_cultivo": last_canon,
            "cultivo_anterior": prev_canon or None,
            "is_consecutive_monoculture": bool(
                last_canon and prev_canon and last_canon == prev_canon
            ),
            "crops": crops,
        }

    if isinstance(raw, str) and raw.strip():
        name = raw.strip()
        return {
            "has_history": True,
            "ultimo_cultivo": _canonical_crop(name),
            "cultivo_anterior": None,
            "is_consecutive_monoculture": False,
            "crops": [name],
        }

    return empty


def _same_crop(crop_a: str, crop_b: str) -> bool:
    if not crop_a or not crop_b:
        return False
    if crop_a == crop_b:
        return True
    feijao_comum = {"feijao", "feijao-carioca"}
    return crop_a in feijao_comum and crop_b in feijao_comum


def _compute_history_adjustment(
    strategy_name: str, parsed_history: dict[str, Any]
) -> float:
    """Calcula ajuste de viabilidade (-0.25 a +0.18) segundo histórico de cultivos."""
    if not parsed_history.get("has_history"):
        return 0.0

    last_crop = str(parsed_history.get("ultimo_cultivo") or "")
    if not last_crop or last_crop in {"pousio", "descanso da terra"}:
        return 0.0

    raw_parts = strategy_name.replace("→", "->").split("->")
    strategy_crops = [
        _canonical_crop(part) for part in raw_parts if _canonical_crop(part)
    ]
    if not strategy_crops:
        return 0.0

    first_crop = strategy_crops[0]
    has_legume = any(crop in _LEGUMES for crop in strategy_crops)
    is_mono = bool(parsed_history.get("is_consecutive_monoculture"))

    adj = 0.0

    # Penalidade por repetição da cultura anterior / monocultura contínua
    if _same_crop(first_crop, last_crop):
        adj -= 0.18 if is_mono else 0.12
        if not has_legume and all(crop in _EXHAUSTIVE_CROPS for crop in strategy_crops):
            adj -= 0.05
    elif (
        last_crop in _EXHAUSTIVE_CROPS
        and not has_legume
        and all(crop in _EXHAUSTIVE_CROPS for crop in strategy_crops)
    ):
        adj -= 0.05

    # Bônus por quebra de ciclo e fixação biológica de nitrogênio
    if not _same_crop(first_crop, last_crop):
        adj += 0.04
        if last_crop in _EXHAUSTIVE_CROPS:
            if first_crop in _LEGUMES:
                adj += 0.08
            elif has_legume:
                adj += 0.05
        if is_mono and has_legume:
            adj += 0.04

    return round(_clamp(adj, -0.25, 0.18), 4)


_VIABILITY_RF_MODEL: RandomForestRegressor | None = None


def _get_viability_rf_model() -> RandomForestRegressor:
    """
    Treina e armazena em cache um RandomForestRegressor determinístico para
    prever viabilidade agronômica considerando interações não-lineares de déficit
    hídrico, estresse térmico, estabilidade temporal e prioridades do produtor.
    """
    global _VIABILITY_RF_MODEL
    if _VIABILITY_RF_MODEL is not None:
        return _VIABILITY_RF_MODEL

    rng = np.random.default_rng(42)
    n_samples = 400
    moisture = rng.uniform(0.05, 0.48, n_samples)
    temp_c = rng.uniform(19.0, 43.0, n_samples)
    rain_idx = rng.uniform(0.10, 1.20, n_samples)
    water_demand = rng.uniform(0.25, 0.95, n_samples)
    heat_tolerance = rng.uniform(0.35, 0.95, n_samples)
    soil_benefit = rng.uniform(0.35, 0.95, n_samples)
    market = rng.uniform(0.45, 0.98, n_samples)
    water_priority = rng.integers(0, 2, n_samples).astype(float)
    temporal_stability = rng.uniform(0.30, 1.00, n_samples)

    x_train = np.column_stack(
        [
            moisture,
            temp_c,
            rain_idx,
            water_demand,
            heat_tolerance,
            soil_benefit,
            market,
            water_priority,
            temporal_stability,
        ]
    )

    moist_idx = np.clip(moisture / 0.35, 0.0, 1.0)
    rain_clipped = np.clip(rain_idx, 0.0, 1.0)
    supply = 0.6 * moist_idx + 0.4 * rain_clipped
    gap = water_demand - supply
    water_fit = np.clip(1.0 - np.maximum(gap, 0.0) * 1.8, 0.0, 1.0)
    heat_stress = np.clip((temp_c - 28.0) / 12.0, 0.0, 1.0)
    heat_fit = 1.0 - heat_stress * (1.0 - heat_tolerance)

    w_water = np.where(water_priority > 0.5, 0.60, 0.45)
    w_heat = np.where(water_priority > 0.5, 0.20, 0.25)
    w_soil = np.where(water_priority > 0.5, 0.15, 0.20)
    w_market = np.where(water_priority > 0.5, 0.05, 0.10)

    # Penalidade não-linear quando ocorre déficit hídrico severo junto com calor extremo
    combined_stress = 0.12 * np.maximum(gap, 0.0) * heat_stress
    stability_adj = (temporal_stability - 0.75) * 0.12
    y_train = np.clip(
        w_water * water_fit
        + w_heat * heat_fit
        + w_soil * soil_benefit
        + w_market * market
        - combined_stress
        + stability_adj,
        0.0,
        1.0,
    )

    model = RandomForestRegressor(
        n_estimators=50,
        max_depth=8,
        min_samples_leaf=2,
        random_state=42,
    )
    model.fit(x_train, y_train)
    _VIABILITY_RF_MODEL = model
    return model


class CropSimulator:
    """Simulador de rotações [M3]: combina modelo RandomForest + features temporais da NASA."""

    # Pesos do score (somam 1.0). Com prioridade hídrica a água pesa mais.
    _WEIGHTS = {"water": 0.45, "heat": 0.25, "soil": 0.20, "market": 0.10}
    _WEIGHTS_WATER_PRIORITY = {"water": 0.60, "heat": 0.20, "soil": 0.15, "market": 0.05}

    def __init__(self):
        self.ml_model = _get_viability_rf_model()

    # -- leitura robusta das métricas (provider real/mock ou fallback da API) --

    @staticmethod
    def _extract_temporal_features(
        field_metrics: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Extrai indicadores dinâmicos de estabilidade, tendência hídrica e veranico da série."""
        default_features = {
            "temporal_stability": 0.75,
            "moisture_trend": 0.0,
            "dry_spell_max": 0,
            "heat_days_ratio": 0.0,
        }
        m = field_metrics or {}
        if m.get("data_quality") == "no_data":
            return default_features

        ts = m.get("time_series")
        if not isinstance(ts, list) or len(ts) < 2:
            return default_features

        moist: list[float] = []
        temps: list[float] = []
        precips: list[float] = []
        for point in ts:
            if not isinstance(point, dict):
                continue
            mv = _to_float(point.get("soil_moisture", point.get("umidade_solo")))
            tv = _to_float(point.get("surface_temp_c", point.get("temperatura_media_c")))
            pv = _to_float(point.get("precipitation_mm", point.get("precipitacao_mm")))
            if mv is not None:
                moist.append(mv)
            if tv is not None:
                temps.append(tv)
            if pv is not None:
                precips.append(pv)

        moisture_trend = 0.0
        moist_cv = 0.0
        if len(moist) >= 2:
            x_idx = np.arange(len(moist), dtype=float)
            if float(np.ptp(moist)) > 0:
                moisture_trend = float(np.polyfit(x_idx, np.array(moist, dtype=float), 1)[0])
            moist_cv = float(np.std(moist) / max(float(np.mean(moist)), 0.05))

        precip_cv = 0.0
        dry_spell_max = 0
        if precips:
            precip_cv = float(np.std(precips) / max(float(np.mean(precips)), 2.0))
            current_dry = 0
            for pv in precips:
                if pv < 1.0:
                    current_dry += 1
                    dry_spell_max = max(dry_spell_max, current_dry)
                else:
                    current_dry = 0

        heat_days_ratio = (
            sum(1 for tv in temps if tv >= 33.0) / len(temps) if temps else 0.0
        )
        trend_penalty = min(0.30, abs(moisture_trend) * 12.0) if moisture_trend < 0 else 0.0
        temporal_stability = _clamp(
            1.0
            - 0.30 * min(1.0, moist_cv)
            - 0.15 * min(1.0, precip_cv)
            - trend_penalty
            - 0.15 * heat_days_ratio,
            0.25,
            1.0,
        )

        return {
            "temporal_stability": round(float(temporal_stability), 3),
            "moisture_trend": round(float(moisture_trend), 4),
            "dry_spell_max": int(dry_spell_max),
            "heat_days_ratio": round(float(heat_days_ratio), 3),
        }

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
        history_adjustment: float = 0.0,
        temporal_features: dict[str, Any] | None = None,
        is_bare_field: bool = False,
    ) -> dict[str, Any]:
        supply = self._water_supply(metrics)
        gap = water_demand - supply
        water_fit = _clamp(1.0 - max(gap, 0.0) * 1.8)
        heat_stress = _clamp((metrics["temp_c"] - 28.0) / 12.0)
        heat_fit = 1.0 - heat_stress * (1.0 - heat_tolerance)

        tf = temporal_features or {}
        temporal_stability = float(tf.get("temporal_stability", 0.75))
        moisture_trend = float(tf.get("moisture_trend", 0.0))
        dry_spell_max = int(tf.get("dry_spell_max", 0))

        rain_idx = _clamp(metrics["annual_rain_mm"] / 1200.0, 0.0, 1.5)
        features_row = np.array(
            [
                [
                    _clamp(metrics["moisture"], 0.02, 0.50),
                    _clamp(metrics["temp_c"], 15.0, 45.0),
                    rain_idx,
                    _clamp(water_demand),
                    _clamp(heat_tolerance),
                    _clamp(soil_benefit),
                    _clamp(market),
                    1.0 if water_priority else 0.0,
                    _clamp(temporal_stability, 0.25, 1.0),
                ]
            ],
            dtype=float,
        )
        ml_model_score = float(_clamp(float(self.ml_model.predict(features_row)[0])))

        adjusted_soil = _clamp(soil_benefit + history_adjustment)
        w = self._WEIGHTS_WATER_PRIORITY if water_priority else self._WEIGHTS
        formula_viability = (
            w["water"] * water_fit
            + w["heat"] * heat_fit
            + w["soil"] * soil_benefit
            + w["market"] * market
        )
        temporal_adj = (temporal_stability - 0.75) * 0.10
        bare_soil_bonus = 0.03 if (is_bare_field and soil_benefit >= 0.75) else 0.0

        raw_viability = (
            0.65 * formula_viability
            + 0.35 * ml_model_score
            + temporal_adj
            + bare_soil_bonus
        )
        viability = _clamp(raw_viability + history_adjustment)
        return {
            "viability": round(viability, 2),
            "water_risk": self._risk_from_gap(gap),
            "score_breakdown": {
                "water_fit": round(water_fit, 3),
                "heat_fit": round(heat_fit, 3),
                "soil_benefit": round(adjusted_soil, 3),
                "market": round(market, 3),
                "water_supply": round(supply, 3),
                "water_demand": round(water_demand, 3),
                "history_adjustment": round(history_adjustment, 4),
                "ml_model_score": round(ml_model_score, 3),
                "temporal_stability": round(temporal_stability, 3),
                "moisture_trend": round(moisture_trend, 4),
                "dry_spell_max": dry_spell_max,
                "bare_soil_bonus": round(bare_soil_bonus, 3),
            },
        }

    # -- API pública -----------------------------------------------------

    def simulate_rotation_strategies(
        self,
        field_metrics: dict[str, Any],
        farmer_priorities: dict[str, Any] | None = None,
        historico_cultivos: Any = None,
    ) -> list[dict[str, Any]]:
        """
        Gera e compara 3 estratégias de rotação, sempre incluindo a prática atual
        do agricultor (`farmer_priorities["pratica_atual"]`, padrão "Milho -> Soja").
        Considera `historico_cultivos` (parâmetro direto ou em `farmer_priorities`/
        `field_metrics`) para penalizar monocultura e bonificar quebra de ciclo.
        Quando `farmer_priorities["rotacoes_preferenciais"]` estiver presente, avalia
        e inclui a melhor rotação preferencial cadastrada pelo produtor no comparativo.
        """
        metrics = self._read_metrics(field_metrics)
        temporal_features = self._extract_temporal_features(field_metrics)
        is_bare_field = bool((field_metrics or {}).get("is_bare_field_period", False))
        water_priority = self._water_priority(farmer_priorities)
        priorities_dict = farmer_priorities or {}
        parsed_history = _parse_crop_history(
            historico_cultivos=historico_cultivos,
            farmer_priorities=priorities_dict,
            field_metrics=field_metrics,
        )
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
            history_adj = _compute_history_adjustment(item["strategy"], parsed_history)
            scored = self._score(
                metrics,
                item["water_demand"],
                item["heat_tolerance"],
                item["soil_benefit"],
                item["market"],
                water_priority,
                history_adjustment=history_adj,
                temporal_features=temporal_features,
                is_bare_field=is_bare_field,
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
            history_adj = _compute_history_adjustment(current_name, parsed_history)
            scored = self._score(
                metrics,
                0.65,
                0.55,
                0.40,
                0.70,
                water_priority,
                history_adjustment=history_adj,
                temporal_features=temporal_features,
                is_bare_field=is_bare_field,
            )
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

    def fallback_strategies(
        self,
        farmer_priorities: dict[str, Any] | None = None,
        field_metrics: dict[str, Any] | None = None,
        historico_cultivos: Any = None,
    ) -> list[dict[str, Any]]:
        """
        Gera fallback dinâmico com 3 estratégias e `score_breakdown` completo
        quando métricas de satélite estão ausentes ou parciais.
        """
        default_metrics: dict[str, Any] = {
            "umidade_solo_estimada": 0.25,
            "temperatura_media_c": 31.0,
            "precipitacao_estimada_mm": 900.0,
            "is_bare_field_period": False,
        }
        merged_metrics = (
            {**default_metrics, **field_metrics}
            if isinstance(field_metrics, dict) and field_metrics
            else default_metrics
        )
        return self.simulate_rotation_strategies(
            merged_metrics,
            farmer_priorities or {},
            historico_cultivos=historico_cultivos,
        )

    def predict_rotation_viability(
        self,
        soil_data: dict,
        climate_data: dict,
        crop_requirements: dict | None = None,
        historico_cultivos: Any = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """
        Compatível com a rota /api/v1/simulacoes/ (3 args -> dict) e com a
        simulação de 3 estratégias (2 args -> list).
        """
        if crop_requirements is None:
            return self.simulate_rotation_strategies(
                soil_data,
                climate_data,
                historico_cultivos=historico_cultivos,
            )

        metrics = self._read_metrics(climate_data)
        temporal_features = self._extract_temporal_features(climate_data)
        is_bare_field = bool((climate_data or {}).get("is_bare_field_period", False))
        priorities = (soil_data or {}).get("prioridades_terreno") or {}
        consumo = _to_float(crop_requirements.get("consumo_agua_mm")) or 450.0
        ciclo = _to_float(crop_requirements.get("tempo_colheita_dias")) or 90.0

        # Culturas de ciclo longo ficam mais expostas ao calor; sem dado de
        # benefício de solo/mercado, usa valores neutros.
        heat_tolerance = _clamp(0.8 - (ciclo / 365.0) * 0.3)
        parsed_history = _parse_crop_history(
            historico_cultivos=historico_cultivos,
            farmer_priorities=priorities if isinstance(priorities, dict) else None,
            field_metrics=soil_data if isinstance(soil_data, dict) else None,
        )
        crop_label = _extract_crop_name(crop_requirements) or ""
        history_adj = (
            _compute_history_adjustment(crop_label, parsed_history)
            if crop_label
            else 0.0
        )
        scored = self._score(
            metrics,
            water_demand=_clamp(consumo / 700.0),
            heat_tolerance=heat_tolerance,
            soil_benefit=0.5,
            market=0.6,
            water_priority=self._water_priority(priorities),
            history_adjustment=history_adj,
            temporal_features=temporal_features,
            is_bare_field=is_bare_field,
        )
        return {
            "viability_score": scored["viability"],
            "water_risk": scored["water_risk"],
            "score_breakdown": scored["score_breakdown"],
        }


def get_fallback_rotation_strategies(
    farmer_priorities: dict[str, Any] | None = None,
    field_metrics: dict[str, Any] | None = None,
    historico_cultivos: Any = None,
) -> list[dict[str, Any]]:
    """Atalho de módulo para gerar estratégias de fallback dinâmicas."""
    return CropSimulator().fallback_strategies(
        farmer_priorities=farmer_priorities,
        field_metrics=field_metrics,
        historico_cultivos=historico_cultivos,
    )


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

    def _compute_series_diagnostics(
        self,
        series: list[dict],
        values: dict[str, list[float | None]],
        temps: list[float],
        moist: list[float],
    ) -> dict[str, Any]:
        """Calcula tendência hídrica, índice de estresse térmico e score IsolationForest."""
        anomaly_score_min: float | None = None
        names = [n for n, col in values.items() if all(v is not None for v in col)]
        if names and len(series) >= self.MIN_POINTS_ML:
            x = np.array([values[n] for n in names], dtype=float).T
            scores = self.model.fit(x).decision_function(x)
            anomaly_score_min = round(float(np.min(scores)), 4)

        moisture_trend_per_day: float | None = None
        if len(moist) >= 2 and float(np.ptp(moist)) > 0:
            x_idx = np.arange(len(moist), dtype=float)
            slope = float(np.polyfit(x_idx, np.array(moist, dtype=float), 1)[0])
            moisture_trend_per_day = round(slope, 5)
        elif len(moist) >= 2:
            moisture_trend_per_day = 0.0

        heat_stress_index = 0.0
        if temps:
            max_temp = max(temps)
            hot_ratio = sum(1 for t in temps if t >= 33.0) / len(temps)
            heat_stress_index = round(
                _clamp(0.6 * _clamp((max_temp - 28.0) / 14.0) + 0.4 * hot_ratio),
                3,
            )

        return {
            "anomaly_score_min": anomaly_score_min,
            "moisture_trend_per_day": moisture_trend_per_day,
            "heat_stress_index": heat_stress_index,
        }

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

        diagnostics = self._compute_series_diagnostics(series, values, temps, moist)

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
                **diagnostics,
            },
        }
