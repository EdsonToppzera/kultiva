from typing import Any
from sklearn.ensemble import IsolationForest
# Importações futuras para XGBoost/RandomForest


class CropSimulator:
    def __init__(self):
        # Inicializar modelos estatísticos
        pass

    def simulate_rotation_strategies(
        self, field_metrics: dict, farmer_priorities: dict
    ) -> list[dict[str, Any]]:
        """
        Input:
          field_metrics (dict): Umidade (SMAP), Temp (ECOSTRESS) processados.
          farmer_priorities (dict): Ex: {"water_conservation": True}
        Output:
          list: Exatamente 3 estratégias de rotação (incluindo a atual).
        """
        return [
            {"strategy": "Milho -> Soja (Atual)", "viability": 0.70, "water_risk": "high"},
            {"strategy": "Sorgo -> Feijão-caupi", "viability": 0.88, "water_risk": "low"},
            {"strategy": "Milheto -> Amendoim", "viability": 0.82, "water_risk": "medium"},
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
