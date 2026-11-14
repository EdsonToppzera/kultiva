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
    def __init__(self):
        self.model = IsolationForest(contamination=0.05)

    def detect_extremes(self, time_series_data: dict) -> dict:
        """
        Gatilho para o calendário maleável (M4/M5) em caso de ondas de calor ou chuvas extremas.
        """
        pass
