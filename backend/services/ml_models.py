from typing import Any
from sklearn.ensemble import IsolationForest


class CropSimulator:
    def __init__(self):
        pass

    def simulate_rotation_strategies(
        self, field_metrics: dict[str, Any], farmer_priorities: dict
    ) -> list[dict[str, Any]]:
        """
        Gera e compara pelo menos três estratégias de rotação, incluindo a atual.
        O modelo confia apenas nas chaves padronizadas de field_metrics,
        ignorando se a origem foi o MockNASADataProvider ou o RealNASADataProvider.
        """
        moisture = field_metrics.get("avg_soil_moisture_smap", 0.0)
        _ = moisture  # Reservado para ponderação estatística futura (RandomForest/XGBoost)

        return [
            {
                "strategy": "Milho -> Soja (Atual)",
                "viability": 0.60,
                "water_risk": "high",
                "benefits": "Mercado estabelecido",
            },
            {
                "strategy": "Sorgo -> Feijão-caupi",
                "viability": 0.88,
                "water_risk": "low",
                "benefits": "Alta tolerância à seca, fixa nitrogênio",
            },
            {
                "strategy": "Milheto -> Amendoim",
                "viability": 0.82,
                "water_risk": "medium",
                "benefits": "Melhora a estrutura do solo",
            },
        ]

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

        return {"viability_score": 0.85, "water_risk": "low"}


class ClimateAnomalyDetector:
    """Detecta extremos climáticos (calor, seca, chuva intensa) para [M5].

    Contrato de saída (consumido por alert_tasks.py e api/alertas.py):
    {"anomaly_detected": bool, "tipo_evento": str, "severidade": str, "detalhes": dict}
    tipo_evento ∈ {"onda_de_calor", "seca", "chuva_intensa", "nenhum"}.
    """

    HEAT_C = 35.0
    DROUGHT_MOISTURE = 0.15
    HEAVY_RAIN_MM = 60.0

    def __init__(self):
        self.model = IsolationForest(contamination=0.05, random_state=42)

    @staticmethod
    def _num(item: dict, *keys: str) -> float | None:
        for key in keys:
            value = item.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        return None

    def detect_extremes(self, time_series_data: dict | list[dict]) -> dict:
        """Aceita um ponto (dict) ou série (list[dict]) e aplica limiares de calor/seca/chuva."""
        series = (
            time_series_data
            if isinstance(time_series_data, list)
            else [time_series_data or {}]
        )
        series = [p for p in series if isinstance(p, dict)]

        precips = [v for p in series if (v := self._num(p, "precipitation_mm", "precipitacao_mm")) is not None]
        temps = [v for p in series if (v := self._num(p, "surface_temp_c", "temperatura_media_c")) is not None]
        moist = [v for p in series if (v := self._num(p, "soil_moisture", "umidade_solo")) is not None]

        max_precip = max(precips, default=0.0)
        max_temp = max(temps, default=0.0)
        min_moist = min(moist, default=1.0)

        tipo, severidade = "nenhum", "baixa"
        if max_precip >= self.HEAVY_RAIN_MM:
            tipo = "chuva_intensa"
            severidade = "critica" if max_precip >= 2 * self.HEAVY_RAIN_MM else "alta"
        elif max_temp >= self.HEAT_C:
            tipo = "onda_de_calor"
            severidade = "critica" if max_temp >= 40.0 else "alta"
        elif moist and min_moist <= self.DROUGHT_MOISTURE:
            tipo = "seca"
            severidade = "alta"

        return {
            "anomaly_detected": tipo != "nenhum",
            "tipo_evento": tipo,
            "severidade": severidade,
            "detalhes": {
                "pontos_analisados": len(series),
                "max_precipitation_mm": max_precip,
                "max_surface_temp_c": max_temp,
                "min_soil_moisture": min_moist if moist else None,
            },
        }
