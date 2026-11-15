from collections import OrderedDict
import hashlib
import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from langchain_core.language_models.fake import FakeListLLM
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

load_dotenv()

_MAX_RESPONSE_CACHE = 128


class StrategyExplanationItem(BaseModel):
    """Saída estruturada por estratégia gerada pelo Gemini."""

    estrategia: str = Field(description="Nome exato da estratégia avaliada")
    resumo: str = Field(
        description=(
            "1 ou 2 frases bem curtas e simples para pequeno agricultor familiar "
            "(palavras do dia a dia, sem siglas, sem jargões técnicos, sem saudações e sem Markdown)"
        )
    )
    acao_pratica: str = Field(
        description="1 dica curta e prática no campo, em linguagem simples"
    )


class StrategyExplanationsBatch(BaseModel):
    """Lote estruturado com 1 explicação por estratégia em ordem."""

    estrategias: list[StrategyExplanationItem]


class AlertExplanationStructured(BaseModel):
    """Saída estruturada para alertas climáticos [M5]."""

    diagnostico_simples: str = Field(
        description="Resumo calmo e simples do alerta para o produtor"
    )
    acoes_imediatas: list[str] = Field(
        description="2 ou 3 ações práticas e diretas para fazer já no campo"
    )

DISCLAIMER = (
    "Lembre-se: esta ferramenta serve para apoiar a decisão e identificar possibilidades, "
    "mas não substitui a sua experiência local. A decisão final é sempre sua."
)
DISCLAIMER_EN = (
    "Remember: this tool is designed to support your decision and highlight possibilities, "
    "but it does not replace your local experience. The final decision is always yours."
)
STRATEGY_SEPARATOR = "---ESTRATEGIA---"
_DEFAULT_MOCK_RESPONSE = (
    "Esta é uma explicação mockada gerada localmente. "
    "A rotação sugerida ajuda na infiltração de água."
)
_DEFAULT_MOCK_RESPONSE_EN = (
    "This is a locally generated mock explanation. "
    "The suggested rotation improves water infiltration."
)

_RISK_LABELS = {
    "low": "baixo",
    "medium": "médio",
    "high": "alto",
    "baixo": "baixo",
    "baixa": "baixa",
    "medio": "médio",
    "médio": "médio",
    "media": "média",
    "média": "média",
    "moderada": "moderada",
    "moderado": "moderado",
    "alto": "alto",
    "alta": "alta",
    "critico": "crítico",
    "crítico": "crítico",
    "critica": "crítica",
    "crítica": "crítica",
}

_RISK_LABELS_EN = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "baixo": "low",
    "baixa": "low",
    "medio": "medium",
    "médio": "medium",
    "media": "medium",
    "média": "medium",
    "moderada": "moderate",
    "moderado": "moderate",
    "alto": "high",
    "alta": "high",
    "critico": "critical",
    "crítico": "critical",
    "critica": "critical",
    "crítica": "critical",
}


def _normalize_lang(idioma: str | None) -> str:
    return "en" if str(idioma or "").strip().lower().startswith("en") else "pt"

_EVENT_LABELS = {
    "chuva_intensa": "chuva intensa",
    "onda_de_calor": "onda de calor",
    "seca": "seca e falta de umidade no solo",
    "geada": "risco de geada",
    "vendaval": "ventos fortes",
}

_ALERT_ACTIONS = {
    "chuva_intensa": (
        "Evite entrar com máquinas ou aplicar adubo e defensivos antes da chuva para não "
        "perder insumos levados pela enxurrada. Confira os sulcos, valas e curvas de nível "
        "para a água escoar sem carregar a terra fértil."
    ),
    "onda_de_calor": (
        "Mantenha palhada ou cobertura morta sobre a terra para refrescar as raízes e "
        "segurar a umidade. Se tiver irrigação, faça a rega bem cedo pela manhã ou no "
        "fim da tarde para a água não evaporar rápido."
    ),
    "seca": (
        "Evite revolver ou arar o solo seco para não perder a pouca umidade restante. "
        "Proteja o chão com cobertura vegetal ou palhada, adie novos plantios mais "
        "exigentes e priorize a irrigação nas áreas mais sensíveis."
    ),
    "geada": (
        "Proteja mudas mais sensíveis com cobertura leve ou palhada seca e evite "
        "adubação com excesso de nitrogênio agora para não deixar as brotações vulneráveis."
    ),
    "vendaval": (
        "Reforce estacas e tutoramentos, revise quebra-ventos e adie pulverizações "
        "até o vento baixar para evitar deriva e desperdício."
    ),
}


def _ensure_disclaimer(text: str, idioma: str = "pt") -> str:
    """Garante a presença do aviso mandatório sem duplicá-lo."""
    lang = _normalize_lang(idioma)
    disclaimer = DISCLAIMER_EN if lang == "en" else DISCLAIMER
    cleaned = str(text or "").strip()
    if not cleaned:
        return disclaimer
    lowered = cleaned.lower()
    if "decisão final" not in lowered and "final decision" not in lowered:
        return f"{cleaned}\n\n{disclaimer}"
    return cleaned


_GREETING_PREFIX_RE = re.compile(
    r"^(?:(?:ol[aá]|oi|bom dia|boa tarde|boa noite|hello|hi)\b[^.!?\n]*[.!?]\s*)"
    r"(?:(?:que bom|vamos dar uma olhada|confira abaixo|aqui est[aã]o|let's look|here are)[^.!?\n]*[.!?]\s*)*",
    flags=re.IGNORECASE,
)
_STRATEGY_LABEL_RE = re.compile(
    r"^(?:estrat[eé]gia|strategy|op[cç][aã]o|option)\s*:\s*",
    flags=re.IGNORECASE,
)


def _clean_farmer_text(text: str, strategy_name: str = "") -> str:
    """Remove Markdown bruto, saudações longas e rótulos repetitivos do texto do card."""
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""

    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"__(.+?)__", r"\1", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", cleaned)
    cleaned = re.sub(r"\*{2,}", "", cleaned)

    without_greeting = _GREETING_PREFIX_RE.sub("", cleaned).strip()
    if without_greeting and len(without_greeting) >= 25:
        cleaned = without_greeting

    without_label = _STRATEGY_LABEL_RE.sub("", cleaned).strip()
    if without_label:
        cleaned = without_label
        if strategy_name:
            low = cleaned.lower()
            if low.startswith(strategy_name.lower()):
                rest = cleaned[len(strategy_name) :].lstrip(" :—-\n")
                if rest and strategy_name.lower() in rest.lower():
                    cleaned = rest

    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _extract_text(response: Any) -> str:
    """Extrai texto limpo de respostas string ou BaseMessage do LangChain."""
    content = response.content if hasattr(response, "content") else response
    if isinstance(content, list):
        parts = [
            str(item["text"]) if isinstance(item, dict) and "text" in item else str(item)
            for item in content
        ]
        return "\n".join(parts).strip()
    return str(content).strip()


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _translate_risk(risk: str, idioma: str = "pt") -> str:
    key = str(risk or "").strip().lower()
    if _normalize_lang(idioma) == "en":
        return _RISK_LABELS_EN.get(key, key or "not informed")
    return _RISK_LABELS.get(key, key or "não informado")


def _format_breakdown_highlights(
    breakdown: dict[str, Any] | None, idioma: str = "pt"
) -> str:
    """Traduz `score_breakdown` em pontos claros para o agricultor."""
    if not isinstance(breakdown, dict) or not breakdown:
        return ""

    if _normalize_lang(idioma) == "en":
        labels = [
            ("water_fit", "water fit"),
            ("heat_fit", "heat tolerance"),
            ("soil_benefit", "soil health benefit"),
            ("market", "market ease"),
        ]
    else:
        labels = [
            ("water_fit", "encaixe com a água"),
            ("heat_fit", "tolerância ao calor"),
            ("soil_benefit", "melhoria do solo"),
            ("market", "facilidade de venda"),
        ]
    items: list[str] = []
    for key, label in labels:
        val = _to_float(breakdown.get(key))
        if val is not None:
            items.append(f"{label}: {round(val * 100)}%")

    gaez_suit = _to_float(breakdown.get("gaez_suitability"))
    if gaez_suit is not None:
        items.append(f"aptidão FAO GAEZ: {round(gaez_suit * 100)}%")

    yield_kg = _to_float(breakdown.get("attainable_yield_kg_ha"))
    if yield_kg is not None and yield_kg > 0:
        items.append(f"produtividade atingível estimada: {round(yield_kg)} kg/ha")

    phyto_risk = str(breakdown.get("phytosanitary_risk") or "").strip().lower()
    if phyto_risk in {"medium", "high"}:
        items.append(f"risco fitossanitário: {_translate_risk(phyto_risk)}")

    pests_count = breakdown.get("agrofit_pests_count")
    if isinstance(pests_count, int) and pests_count > 0:
        items.append(f"pragas mapeadas AGROFIT: {pests_count}")

    return ", ".join(items)


def _normalize_strategy(item: Any) -> dict[str, Any]:
    """Aceita dict, modelo Pydantic ou string e devolve estrutura uniforme."""
    if isinstance(item, dict):
        raw = item
    elif hasattr(item, "model_dump"):
        raw = item.model_dump()
    elif hasattr(item, "dict"):
        raw = item.dict()
    elif isinstance(item, str):
        raw = {"strategy": item}
    else:
        raw = {
            "strategy": getattr(item, "strategy", str(item)),
            "viability": getattr(item, "viability", None),
            "water_risk": getattr(item, "water_risk", ""),
            "benefits": getattr(item, "benefits", ""),
            "score_breakdown": getattr(item, "score_breakdown", None),
        }

    name = str(raw.get("strategy") or "").strip() or "Estratégia sugerida"
    breakdown = raw.get("score_breakdown")
    return {
        "strategy": name,
        "viability": _to_float(raw.get("viability")),
        "water_risk": str(raw.get("water_risk") or "").strip(),
        "benefits": str(raw.get("benefits") or "").strip(),
        "score_breakdown": breakdown if isinstance(breakdown, dict) else None,
    }


def _format_context(
    field_metrics: dict[str, Any] | None,
    farmer_priorities: dict[str, Any] | None,
) -> str:
    parts: list[str] = []
    if isinstance(field_metrics, dict) and field_metrics:
        moisture = _to_float(
            field_metrics.get("avg_soil_moisture_smap")
            or field_metrics.get("umidade_solo_estimada")
        )
        temp = _to_float(
            field_metrics.get("avg_surface_temp_ecostress")
            or field_metrics.get("temperatura_media_c")
        )
        rain_daily = _to_float(field_metrics.get("avg_precipitation_gpm"))
        rain_est = _to_float(field_metrics.get("precipitacao_estimada_mm"))
        if moisture is not None:
            parts.append(f"umidade média do solo: {moisture:.2f}")
        if temp is not None:
            parts.append(f"temperatura média da superfície: {temp:.1f} °C")
        if rain_daily is not None:
            parts.append(f"chuva média diária: {rain_daily:.1f} mm/dia")
        elif rain_est is not None:
            parts.append(f"chuva estimada: {rain_est:.0f} mm")
        if field_metrics.get("is_bare_field_period") is True:
            parts.append("solo com sinal de estar descoberto e seco no período")

        gaez = field_metrics.get("gaez")
        if isinstance(gaez, dict):
            input_level = gaez.get("input_level")
            if input_level:
                parts.append(f"regime FAO GAEZ: {input_level}")
            soil = gaez.get("soil")
            if isinstance(soil, dict) and soil:
                if soil.get("soil_group"):
                    parts.append(f"solo HWSD v2.01: {soil['soil_group']}")
                if soil.get("limiting_factor"):
                    parts.append(f"fator limitante do solo: {soil['limiting_factor']}")
                if soil.get("slope_range_pct"):
                    parts.append(
                        f"declividade: {soil['slope_range_pct']} (risco de erosão {soil.get('erosion_risk', 'não informado')})"
                    )

        z_scores = field_metrics.get("z_scores")
        if isinstance(z_scores, dict):
            z_bits: list[str] = []
            for label, key in (
                ("chuva", "precipitation_mm"),
                ("temperatura", "surface_temp_c"),
                ("umidade", "soil_moisture"),
            ):
                zv = _to_float(z_scores.get(key))
                if zv is not None:
                    z_bits.append(f"{label} z={zv:+.2f}")
            if z_bits:
                parts.append("desvio histórico (z-score): " + ", ".join(z_bits))

        srtm = field_metrics.get("srtm")
        if isinstance(srtm, dict):
            elev = _to_float(srtm.get("elevation_m"))
            slope_pct = _to_float(srtm.get("slope_pct"))
            erosion = srtm.get("erosion_risk")
            srtm_bits: list[str] = []
            if elev is not None:
                srtm_bits.append(f"elevação SRTM: {elev:.0f} m")
            if slope_pct is not None:
                srtm_bits.append(f"declividade: {slope_pct:.1f}%")
            if erosion:
                srtm_bits.append(f"risco de erosão {erosion}")
            if srtm_bits:
                parts.append(", ".join(srtm_bits))

        firms = field_metrics.get("firms")
        if isinstance(firms, dict) and firms.get("hotspots_count") is not None:
            count = int(firms.get("hotspots_count") or 0)
            fire_risk = firms.get("fire_risk", "baixo")
            nearest = _to_float(firms.get("nearest_fire_km"))
            firms_txt = f"focos de calor NASA FIRMS: {count} foco(s) (risco {fire_risk}"
            if nearest is not None:
                firms_txt += f", mais próximo a {nearest:.1f} km"
            firms_txt += ")"
            parts.append(firms_txt)

        hls = field_metrics.get("hls")
        if isinstance(hls, dict):
            hls_ndvi = _to_float(hls.get("ndvi_mean"))
            if hls_ndvi is not None:
                parts.append(f"vigor vegetativo HLS (NDVI): {hls_ndvi:.2f}")

    if isinstance(farmer_priorities, dict) and farmer_priorities:
        prio_bits = [f"{k}: {v}" for k, v in farmer_priorities.items() if v is not None]
        if prio_bits:
            parts.append("prioridades do produtor -> " + ", ".join(prio_bits))

    return "; ".join(parts) if parts else "Sem dados extras do terreno informados."


def _dedup_append(items: list[str], value: str | None) -> None:
    text = str(value or "").strip()
    if text and text not in items:
        items.append(text)


def _extract_clima_basico(
    fm: dict[str, Any],
) -> tuple[float | None, float | None, float | None, float | None]:
    moisture = _to_float(
        fm.get("avg_soil_moisture_smap")
        or fm.get("umidade_solo_estimada")
        or fm.get("soil_moisture")
    )
    temp_c = _to_float(
        fm.get("avg_surface_temp_ecostress")
        or fm.get("temperatura_media_c")
        or fm.get("surface_temp_c")
    )
    rain_daily = _to_float(fm.get("avg_precipitation_gpm"))
    annual_rain = _to_float(
        fm.get("precipitacao_estimada_mm") or fm.get("precipitation_mm")
    )
    if annual_rain is None and rain_daily is not None:
        annual_rain = rain_daily * 365.0
    return moisture, temp_c, rain_daily, annual_rain


def _lookup_ecocrop_profile(
    crop_name: str,
    eco_crops: dict[str, Any],
) -> dict[str, Any] | None:
    cleaned = str(crop_name or "").strip().lower()
    if not cleaned:
        return None
    for k, rec in eco_crops.items():
        if isinstance(rec, dict) and str(k).strip().lower() == cleaned:
            return rec
    try:
        from backend.services.ecocrop_service import resolve_scientific_name

        sci = resolve_scientific_name(crop_name)
        if sci:
            sci_low = sci.lower()
            for rec in eco_crops.values():
                if (
                    isinstance(rec, dict)
                    and str(rec.get("scientific_name") or "").strip().lower() == sci_low
                ):
                    return rec
    except Exception:
        pass
    return None


def synthesize_cross_insights(
    strategy: Any = None,
    field_metrics: dict[str, Any] | None = None,
    farmer_priorities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Cruza deterministicamente sinais NASA, FAO GAEZ (HWSD/SQ-IDX/CMIP6), ECOCROP e AGROFIT
    em evidências práticas sem chamar LLM nem inventar parâmetros ausentes.
    """
    fm = field_metrics if isinstance(field_metrics, dict) else {}
    item = _normalize_strategy(strategy) if strategy is not None else None
    bd = (item or {}).get("score_breakdown") or {}

    positivos: list[str] = []
    alertas: list[str] = []
    acoes: list[str] = []

    moisture, temp_c, rain_daily, annual_rain = _extract_clima_basico(fm)
    is_bare = bool(fm.get("is_bare_field_period"))

    # 1. Solo HWSD / SQ-IDX / Declividade x Clima NASA
    gaez = fm.get("gaez") if isinstance(fm.get("gaez"), dict) else {}
    soil = gaez.get("soil") if isinstance(gaez.get("soil"), dict) else {}
    soil_group = str(soil.get("soil_group") or "").strip()
    limiting = str(soil.get("limiting_factor") or "").strip()
    erosion_risk = str(soil.get("erosion_risk") or "").strip().lower()
    slope_pct = str(soil.get("slope_range_pct") or "").strip()

    heavy_rain = rain_daily is not None and rain_daily >= 10.0
    high_moisture = moisture is not None and moisture >= 0.35

    if soil_group and ("arenosol" in soil_group.lower() or "sq2" in limiting.lower() or "nutriente" in limiting.lower()):
        if heavy_rain:
            _dedup_append(
                alertas,
                f"Solo com baixa retenção ({soil_group}) sob chuva forte ({rain_daily:.1f} mm/dia): risco de lixiviação de nutrientes.",
            )
            _dedup_append(
                acoes,
                "Parcele a adubação de cobertura e evite aplicar adubo antes de chuva forte.",
            )
        else:
            _dedup_append(
                acoes,
                f"Em solo {soil_group}, reforce cobertura vegetal ou adubo verde para segurar nutrientes e umidade.",
            )

    if erosion_risk in {"alto", "critico", "crítico"} and (heavy_rain or is_bare):
        _dedup_append(
            alertas,
            f"Declividade {slope_pct or 'acentuada'} com risco {erosion_risk} de erosão no período.",
        )
        _dedup_append(
            acoes,
            "Plante em nível ou faixas e evite deixar o solo descoberto antes das chuvas.",
        )

    if ("sq4" in limiting.lower() or "drenagem" in limiting.lower() or "gleissolo" in soil_group.lower()) and high_moisture:
        _dedup_append(
            alertas,
            f"Restrição de drenagem ({limiting or soil_group}) com solo já úmido ({round(moisture * 100)}%).",
        )
        _dedup_append(
            acoes,
            "Priorize talhões mais altos ou revise os drenos para evitar encharcamento das raízes.",
        )

    # 2. Desvio histórico Z-score (A17) e solo exposto
    z_scores = fm.get("z_scores") if isinstance(fm.get("z_scores"), dict) else {}
    z_temp = _to_float(z_scores.get("surface_temp_c"))
    z_moist = _to_float(z_scores.get("soil_moisture"))
    z_rain = _to_float(z_scores.get("precipitation_mm"))
    z_flags: list[str] = []
    if z_temp is not None and z_temp >= 1.5:
        z_flags.append(f"calor z={z_temp:+.2f}")
    if z_moist is not None and z_moist <= -1.5:
        z_flags.append(f"solo seco z={z_moist:+.2f}")
    if z_rain is not None and z_rain >= 1.5:
        z_flags.append(f"chuva z={z_rain:+.2f}")
    if z_flags:
        _dedup_append(
            alertas,
            f"Desvio histórico forte no período ({', '.join(z_flags)}); acompanhe estresse inicial da lavoura.",
        )

    if is_bare:
        soil_ben = _to_float(bd.get("soil_benefit"))
        if soil_ben is not None and soil_ben >= 0.75:
            _dedup_append(
                positivos,
                "Solo hoje com sinal de estar descoberto: esta rotação ajuda a cobrir rápido a terra e fixar nitrogênio.",
            )
        else:
            _dedup_append(
                acoes,
                "Área com solo descoberto no satélite: mantenha palhada ou cobertura verde antes do próximo plantio.",
            )

    # 3. ECOCROP (TOPMIN/TOPMAX/ROPMIN) x Clima NASA para as culturas da estratégia
    eco_raw = fm.get("ecocrop") if isinstance(fm.get("ecocrop"), dict) else {}
    eco_crops = (
        eco_raw.get("crops")
        if isinstance(eco_raw.get("crops"), dict)
        else (eco_raw if isinstance(eco_raw, dict) else {})
    )
    if item and eco_crops:
        crop_names = [
            p.strip()
            for p in item["strategy"].replace("(Atual)", "").replace("(atual)", "").replace("→", "->").split("->")
            if p.strip()
        ]
        try:
            from backend.services.ecocrop_service import evaluate_climate_comfort

            for cname in crop_names:
                prof = _lookup_ecocrop_profile(cname, eco_crops)
                if not prof:
                    continue
                comfort = evaluate_climate_comfort(prof, temp_c, annual_rain)
                t_status = comfort.get("temperature_status")
                r_status = comfort.get("rainfall_status")
                topmin, topmax = prof.get("topmin"), prof.get("topmax")
                ropmin, ropmax = prof.get("ropmin"), prof.get("ropmax")

                if t_status == "optimal" and topmin is not None and topmax is not None:
                    _dedup_append(
                        positivos,
                        f"Temperatura atual ({temp_c:.1f} °C) dentro da faixa ótima ECOCROP de {cname} ({topmin:g}–{topmax:g} °C).",
                    )
                elif t_status in {"suboptimal", "outside_absolute"} and temp_c is not None and topmax is not None:
                    _dedup_append(
                        alertas,
                        f"Temperatura ({temp_c:.1f} °C) fora do ideal ECOCROP de {cname} ({topmin or prof.get('tmin')}–{topmax:g} °C).",
                    )
                    _dedup_append(
                        acoes,
                        f"Para {cname}, faça irrigações bem cedo ou no fim da tarde e mantenha palhada sobre o solo.",
                    )

                if r_status in {"suboptimal", "outside_absolute"} and annual_rain is not None and ropmin is not None:
                    _dedup_append(
                        alertas,
                        f"Chuva estimada ({annual_rain:.0f} mm/ano) abaixo do ideal ECOCROP de {cname} ({ropmin:g}–{ropmax or prof.get('rmax')} mm).",
                    )
        except Exception:
            pass

    # 4. Tendência futura CMIP6 (GAEZ v5) vs curto prazo
    cmip6_delta = _to_float(bd.get("cmip6_suitability_delta"))
    if cmip6_delta is not None:
        if cmip6_delta <= -0.03:
            _dedup_append(
                alertas,
                f"Projeção climática até 2040 (CMIP6) aponta queda de {abs(round(cmip6_delta * 100))}% na aptidão desta combinação.",
            )
            _dedup_append(
                acoes,
                "Use como transição nesta safra e vá testando opções mais rústicas (como sorgo, feijão-caupi ou mandioca).",
            )
        elif cmip6_delta >= 0.03:
            _dedup_append(
                positivos,
                f"Boa resiliência futura (CMIP6 +{round(cmip6_delta * 100)}% de aptidão estimada até 2040).",
            )

    # 5. AGROFIT x Família Botânica x Gatilhos climáticos
    pests_count = bd.get("agrofit_pests_count")
    same_family = bool(bd.get("same_family_as_history"))
    triggers = list(bd.get("phytosanitary_triggers") or [])
    if same_family:
        _dedup_append(
            alertas,
            "Repete a mesma família botânica do último cultivo (AGROFIT/ECOCROP), aumentando pressão de pragas de solo.",
        )
        _dedup_append(
            acoes,
            "Planeje alternar com leguminosa ou gramínea na safra seguinte para quebrar o ciclo de pragas.",
        )
    elif isinstance(pests_count, int) and pests_count > 0 and triggers:
        _dedup_append(
            alertas,
            f"Clima atual ativa alerta para {pests_count} praga(s) catalogadas (AGROFIT) nesta combinação.",
        )
        _dedup_append(
            acoes,
            "Agende vistoria semanal nas folhas e bordaduras durante os primeiros 21 dias após o plantio.",
        )

    resumo_bits = [*positivos[:1], *alertas[:3], *acoes[:1]]
    return {
        "pontos_positivos": positivos[:4],
        "alertas_manejo": alertas[:6],
        "acoes_praticas": acoes[:4],
        "resumo_cruzado": " ".join(resumo_bits),
    }


def _format_strategies_block(
    strategies: list[dict[str, Any]],
    field_metrics: dict[str, Any] | None = None,
    farmer_priorities: dict[str, Any] | None = None,
) -> str:
    lines: list[str] = []
    for idx, item in enumerate(strategies, start=1):
        viab_txt = (
            f"{round(item['viability'] * 100)}%"
            if item["viability"] is not None
            else "não informada"
        )
        risk_txt = _translate_risk(item["water_risk"])
        benefits_txt = item["benefits"] or "manutenção produtiva da área"
        breakdown_txt = _format_breakdown_highlights(item["score_breakdown"])
        cross = synthesize_cross_insights(item, field_metrics, farmer_priorities)
        line = (
            f"{idx}. Estratégia: {item['strategy']} | "
            f"Chance estimada de sucesso: {viab_txt} | "
            f"Risco de falta de água: {risk_txt} | "
            f"Benefícios: {benefits_txt}"
        )
        if breakdown_txt:
            line += f" | Detalhes: {breakdown_txt}"
        if cross["resumo_cruzado"]:
            line += f" | Cruzamento agronômico: {cross['resumo_cruzado']}"
        lines.append(line)
    return "\n".join(lines)


def _split_strategy_blocks(raw_text: str, expected_count: int) -> list[str] | None:
    """Tenta dividir a resposta única do LLM nos blocos de cada estratégia."""
    for sep in (STRATEGY_SEPARATOR, "|||"):
        if sep in raw_text:
            parts = [part.strip() for part in raw_text.split(sep) if part.strip()]
            if len(parts) == expected_count:
                return parts
    if expected_count == 1 and raw_text.strip():
        return [raw_text.strip()]
    return None


def _build_simple_fallback_explanation(
    item: dict[str, Any],
    is_best: bool,
    current_name: str | None,
    field_metrics: dict[str, Any] | None = None,
    farmer_priorities: dict[str, Any] | None = None,
    idioma: str = "pt",
) -> str:
    """Gera explicação curta e acessível para agricultor familiar quando o LLM não delimita os blocos."""
    lang = _normalize_lang(idioma)
    name = item["strategy"]
    is_current = "(atual)" in name.lower() or "(current)" in name.lower()
    risk_txt = _translate_risk(item["water_risk"], lang)
    viab = item["viability"]
    bd = item.get("score_breakdown") or {}
    yield_kg = _to_float(bd.get("attainable_yield_kg_ha"))
    clean_benefit = _clean_farmer_text(item.get("benefits") or "", name).rstrip(".")

    if lang == "en":
        viab_txt = f"{round(viab * 100)}%" if viab is not None else "good"
        if is_current:
            intro = f"{name} is what you already plant on this area."
        elif is_best and current_name:
            intro = f"{name} stands out as the safest choice for your land right now."
        else:
            intro = f"{name} is a solid alternative to vary what you plant."

        details = [
            f"Estimated {viab_txt} chance of doing well, with {risk_txt} risk of dry spells hurting the crop."
        ]
        if clean_benefit:
            details.append(f"Why it helps: {clean_benefit}.")
        if yield_kg is not None and yield_kg > 0 and "kg/ha" not in " ".join(details).lower():
            details.append(f"Expected harvest around {round(yield_kg)} kg/ha.")

        return f"{intro} {' '.join(details)}"

    viab_txt = f"{round(viab * 100)}%" if viab is not None else "boa"

    if is_current:
        intro = f"{name} mostra como fica se você mantiver o plantio atual."
    elif is_best and current_name:
        intro = f"{name} é a opção mais segura e indicada para a sua terra hoje."
    else:
        intro = f"{name} também é uma boa opção para alternar o plantio."

    details = [
        f"Tem cerca de {viab_txt} de chance de dar certo, com risco {risk_txt} de faltar água."
    ]
    if clean_benefit:
        lowered_ben = (
            clean_benefit[0].lower() + clean_benefit[1:]
            if len(clean_benefit) > 1 and not clean_benefit[:2].isupper()
            else clean_benefit
        )
        details.append(f"No dia a dia, {lowered_ben}.")
    if yield_kg is not None and yield_kg > 0 and "kg/ha" not in " ".join(details).lower():
        details.append(f"Pode render perto de {round(yield_kg)} kg/ha.")

    cross = synthesize_cross_insights(item, field_metrics, farmer_priorities)
    if cross["acoes_praticas"]:
        details.append(cross["acoes_praticas"][0])

    return f"{intro} {' '.join(details)}"


def _to_dict(obj: Any) -> dict[str, Any]:
    """Converte dict, modelo Pydantic ou objeto simples em dicionário."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if hasattr(obj, "__dict__"):
        return dict(vars(obj))
    return {}


def build_strategy_evidence(
    strategy: Any,
    field_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extrai bloco estruturado de evidências numéricas reais por estratégia (sem inventar dados)."""
    item = _normalize_strategy(strategy)
    bd = item.get("score_breakdown") or {}
    fm = field_metrics if isinstance(field_metrics, dict) else {}

    evidence: dict[str, Any] = {
        "strategy": item["strategy"],
        "viability_score": item["viability"],
        "viability_pct": (
            round(item["viability"] * 100, 1)
            if item["viability"] is not None
            else None
        ),
        "water_risk": item["water_risk"],
    }

    subscores: dict[str, float] = {}
    for k in (
        "water_fit",
        "heat_fit",
        "soil_benefit",
        "market",
        "gaez_suitability",
        "ecocrop_comfort",
    ):
        val = _to_float(bd.get(k))
        if val is not None:
            subscores[k] = round(val, 4)
    if subscores:
        evidence["score_breakdown"] = subscores

    pests_count = bd.get("agrofit_pests_count")
    if pests_count is not None:
        evidence["agrofit"] = {
            "pests_count": int(pests_count),
            "pests_sample": list(bd.get("agrofit_pests_sample") or [])[:5],
        }

    gaez = fm.get("gaez")
    if isinstance(gaez, dict) and gaez:
        soil = gaez.get("soil") if isinstance(gaez.get("soil"), dict) else {}
        evidence["gaez"] = {
            "input_level": gaez.get("input_level"),
            "soil_group": soil.get("soil_group"),
            "slope_range_pct": soil.get("slope_range_pct"),
            "limiting_factor": soil.get("limiting_factor"),
        }

    if isinstance(fm.get("z_scores"), dict):
        evidence["z_scores"] = fm["z_scores"]
    if isinstance(fm.get("srtm"), dict):
        evidence["srtm"] = fm["srtm"]
    if isinstance(fm.get("firms"), dict):
        evidence["firms"] = fm["firms"]
    if isinstance(fm.get("hls"), dict):
        evidence["hls"] = fm["hls"]

    cross = synthesize_cross_insights(strategy=item, field_metrics=fm)
    if cross["pontos_positivos"] or cross["alertas_manejo"] or cross["acoes_praticas"]:
        evidence["insights_cruzados"] = cross

    return evidence


def build_simulation_evidence(
    field_metrics: dict[str, Any] | None = None,
    strategies: list[Any] | None = None,
) -> dict[str, Any]:
    """Consolida evidências numéricas estruturadas da simulação para cards no frontend."""
    fm = field_metrics if isinstance(field_metrics, dict) else {}
    clima: dict[str, Any] = {}
    for out_k, in_keys in (
        ("soil_moisture", ("avg_soil_moisture_smap", "umidade_solo_estimada")),
        ("surface_temp_c", ("avg_surface_temp_ecostress", "temperatura_media_c")),
        ("precipitation_mm_day", ("avg_precipitation_gpm",)),
        ("precipitation_est_mm", ("precipitacao_estimada_mm",)),
    ):
        for k in in_keys:
            val = _to_float(fm.get(k))
            if val is not None:
                clima[out_k] = round(val, 4)
                break

    payload: dict[str, Any] = {
        "clima": clima,
        "z_scores": fm.get("z_scores") if isinstance(fm.get("z_scores"), dict) else None,
        "gaez": fm.get("gaez") if isinstance(fm.get("gaez"), dict) else None,
        "ecocrop": fm.get("ecocrop") if isinstance(fm.get("ecocrop"), dict) else None,
        "agrofit": fm.get("agrofit") if isinstance(fm.get("agrofit"), dict) else None,
        "srtm": fm.get("srtm") if isinstance(fm.get("srtm"), dict) else None,
        "firms": fm.get("firms") if isinstance(fm.get("firms"), dict) else None,
        "hls": fm.get("hls") if isinstance(fm.get("hls"), dict) else None,
    }
    terrain_cross = synthesize_cross_insights(strategy=None, field_metrics=fm)
    if terrain_cross["alertas_manejo"] or terrain_cross["acoes_praticas"]:
        payload["insights_cruzados"] = terrain_cross
    if strategies:
        payload["estrategias"] = [
            build_strategy_evidence(s, fm) for s in strategies
        ]
    return payload


def _format_alert_climate_details(
    detalhes_clima: dict[str, Any] | None,
    idioma: str = "pt",
) -> str:
    lang = _normalize_lang(idioma)
    if not isinstance(detalhes_clima, dict) or not detalhes_clima:
        return (
            "No detailed measurements provided."
            if lang == "en"
            else "Sem medições detalhadas informadas."
        )
    parts: list[str] = []
    max_rain = _to_float(
        detalhes_clima.get("max_precipitation_mm")
        or detalhes_clima.get("precipitacao_mm")
    )
    max_temp = _to_float(
        detalhes_clima.get("max_surface_temp_c")
        or detalhes_clima.get("temperatura_media_c")
    )
    min_moist = _to_float(
        detalhes_clima.get("min_soil_moisture")
        or detalhes_clima.get("umidade_solo")
    )
    if max_rain is not None and max_rain > 0:
        parts.append(
            f"peak rainfall of {max_rain:.1f} mm"
            if lang == "en"
            else f"chuva máxima registrada de {max_rain:.1f} mm"
        )
    if max_temp is not None and max_temp > 0:
        parts.append(
            f"surface temperature reaching {max_temp:.1f} °C"
            if lang == "en"
            else f"temperatura da superfície chegando a {max_temp:.1f} °C"
        )
    if min_moist is not None:
        parts.append(
            f"minimum soil moisture at {round(min_moist * 100)}%"
            if lang == "en"
            else f"umidade mínima do solo em {round(min_moist * 100)}%"
        )
    z_scores = detalhes_clima.get("z_scores")
    if isinstance(z_scores, dict):
        labels = (
            (("rainfall", "precipitation_mm"), ("temperature", "surface_temp_c"), ("soil moisture", "soil_moisture"))
            if lang == "en"
            else (("chuva", "precipitation_mm"), ("temperatura", "surface_temp_c"), ("umidade", "soil_moisture"))
        )
        for label, key in labels:
            zv = _to_float(z_scores.get(key))
            if zv is not None and abs(zv) >= 1.5:
                parts.append(
                    f"historical {label} deviation (z={zv:+.2f})"
                    if lang == "en"
                    else f"desvio histórico de {label} (z={zv:+.2f})"
                )
    if parts:
        return "; ".join(parts)
    return (
        "Field climate monitoring data."
        if lang == "en"
        else "Dados climáticos de monitoramento do terreno."
    )


_EVENT_LABELS_EN = {
    "chuva_intensa": "heavy rain",
    "tempestade": "storm",
    "heavy_rain": "heavy rain",
    "seca": "dry spell / drought",
    "drought": "drought",
    "onda_de_calor": "heatwave",
    "heatwave": "heatwave",
    "geada": "frost",
    "vendaval": "strong winds",
    "praga": "pest occurrence",
}

_ALERT_ACTIONS_EN = {
    "chuva_intensa": (
        "Check field drainage channels, avoid fertilizing or spraying right before rain, "
        "and protect newly planted beds or exposed soil."
    ),
    "seca": (
        "Prioritize irrigation during cooler hours (early morning or late afternoon) "
        "and reinforce soil mulch to retain moisture."
    ),
    "onda_de_calor": (
        "Irrigate during cooler hours, avoid foliar applications under strong sun, "
        "and monitor young plants for wilting."
    ),
    "praga": (
        "Inspect young leaves and plant bases, remove early outbreaks manually when possible, "
        "and prioritize biological or integrated pest management."
    ),
}


def _build_alert_fallback(
    tipo_evento: str,
    severidade: str,
    cultura: str | None,
    resumo_adaptacao: str | None,
    detalhes_clima: dict[str, Any] | None,
    idioma: str = "pt",
) -> str:
    """Explicação acessível e prática para alertas climáticos [M5] em modo offline."""
    lang = _normalize_lang(idioma)
    evento_key = str(tipo_evento or "").strip().lower()
    if lang == "en":
        evento_label = _EVENT_LABELS_EN.get(
            evento_key, str(tipo_evento or "weather alert").replace("_", " ")
        )
        sev_label = _translate_risk(severidade, idioma="en")
        cultura_txt = f" for your {cultura.strip()} crop" if cultura and cultura.strip() else ""
        parts = [
            f"Heads up: we identified a {sev_label}-severity alert for {evento_label}{cultura_txt}."
        ]
        climate_txt = _format_alert_climate_details(detalhes_clima, idioma="en")
        if isinstance(detalhes_clima, dict) and detalhes_clima:
            parts.append(f"Observed field signals: {climate_txt}.")
        action_txt = _ALERT_ACTIONS_EN.get(
            evento_key,
            "Monitor the field closely over the next few days, protect soil cover, "
            "and adjust fertilization or field operations according to local conditions.",
        )
        parts.append(f"What to do in the field: {action_txt}")
        if resumo_adaptacao and str(resumo_adaptacao).strip():
            parts.append(f"Suggested schedule adjustment: {str(resumo_adaptacao).strip()}.")
        return " ".join(parts)

    evento_label = _EVENT_LABELS.get(evento_key, str(tipo_evento or "alerta climático").replace("_", " "))
    sev_label = _translate_risk(severidade, idioma="pt")
    cultura_txt = f" para a lavoura de {cultura.strip()}" if cultura and cultura.strip() else ""

    parts = [
        f"Atenção: identificamos um alerta de severidade {sev_label} para {evento_label}{cultura_txt}."
    ]
    climate_txt = _format_alert_climate_details(detalhes_clima, idioma="pt")
    if isinstance(detalhes_clima, dict) and detalhes_clima:
        parts.append(f"Sinais observados no terreno: {climate_txt}.")

    action_txt = _ALERT_ACTIONS.get(
        evento_key,
        "Acompanhe a lavoura de perto nos próximos dias, proteja a cobertura do solo e "
        "ajuste adubações ou tratos culturais conforme a condição do tempo no terreno.",
    )
    parts.append(f"O que fazer na prática no campo: {action_txt}")

    if isinstance(detalhes_clima, dict) and detalhes_clima:
        cross = synthesize_cross_insights(strategy=None, field_metrics=detalhes_clima)
        if cross["acoes_praticas"]:
            parts.append(cross["acoes_praticas"][0])

    if resumo_adaptacao and str(resumo_adaptacao).strip():
        parts.append(f"Ajuste sugerido no calendário: {str(resumo_adaptacao).strip()}.")

    return " ".join(parts)


def _format_report_summary_fields(
    resumo_climatico: Any,
    vigor: Any,
    vulnerabilidade: Any,
    adaptacoes: Any,
    nome_propriedade: str | None,
) -> tuple[str | None, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Extrai blocos do relatório [M6], aceitando objeto completo ou seções isoladas."""
    raw_clima = _to_dict(resumo_climatico)
    if "resumo_climatico" in raw_clima and isinstance(
        raw_clima.get("resumo_climatico"), (dict, object)
    ):
        prop_name = nome_propriedade or raw_clima.get("nome_propriedade")
        clima = _to_dict(raw_clima.get("resumo_climatico"))
        vigor_d = _to_dict(vigor if vigor is not None else raw_clima.get("vigor"))
        vuln_d = _to_dict(
            vulnerabilidade if vulnerabilidade is not None else raw_clima.get("vulnerabilidade")
        )
        adapt_d = _to_dict(
            adaptacoes if adaptacoes is not None else raw_clima.get("adaptacoes")
        )
        return (str(prop_name) if prop_name else None), clima, vigor_d, vuln_d, adapt_d

    return (
        nome_propriedade,
        raw_clima,
        _to_dict(vigor),
        _to_dict(vulnerabilidade),
        _to_dict(adaptacoes),
    )


def _build_report_fallback(
    prop_name: str | None,
    clima: dict[str, Any],
    vigor_d: dict[str, Any],
    vuln_d: dict[str, Any],
    adapt_d: dict[str, Any],
) -> str:
    """Gera resumo acessível do relatório de adaptação [M6] em modo offline."""
    local_txt = f" da propriedade {prop_name}" if prop_name else " do seu terreno"
    sections: list[str] = [f"Resumo do acompanhamento{local_txt} no período analisado:"]

    clima_bits: list[str] = []
    umidade = _to_float(clima.get("umidade_media_solo"))
    if umidade is not None:
        umidade_pct = round(umidade * 100) if umidade <= 1.0 else round(umidade)
        clima_bits.append(f"umidade média do solo em torno de {umidade_pct}%")
    temp = _to_float(clima.get("temperatura_media_c"))
    if temp is not None:
        clima_bits.append(f"temperatura média da superfície de {temp:.1f} °C")
    chuva_total = _to_float(clima.get("precipitacao_total_mm"))
    if chuva_total is not None:
        clima_bits.append(f"chuva acumulada de {chuva_total:.1f} mm")
    dias_exposto = clima.get("dias_solo_exposto")
    if isinstance(dias_exposto, int):
        clima_bits.append(f"{dias_exposto} dia(s) com sinal de solo mais seco e descoberto")
    if clima_bits:
        sections.append("No clima e no solo, observamos " + ", ".join(clima_bits) + ".")

    classif = str(vigor_d.get("classificacao") or "").strip()
    tendencia = str(vigor_d.get("tendencia") or "").strip()
    if classif or tendencia:
        vigor_txt = f"A saúde e força da lavoura está classificada como {classif or 'acompanhada'}"
        if tendencia:
            vigor_txt += f", com tendência de {tendencia}"
        sections.append(f"{vigor_txt}.")
    elif vigor_d.get("descricao"):
        sections.append(str(vigor_d["descricao"]).strip())

    nivel_vuln = _translate_risk(str(vuln_d.get("nivel") or ""))
    total_alertas = vuln_d.get("total_alertas_periodo")
    if vuln_d:
        vuln_msg = f"O risco climático do terreno no período ficou em nível {nivel_vuln}"
        if total_alertas is not None:
            vuln_msg += f", com {total_alertas} alerta(s) registrado(s)"
        sections.append(f"{vuln_msg}.")

    total_ativ = adapt_d.get("total_atividades_periodo")
    total_ajust = adapt_d.get("total_ajustadas_por_alerta")
    ultimo_resumo = (
        adapt_d.get("ultimo_resumo_adaptacao") or adapt_d.get("acao_recomendada")
    )
    if total_ativ is not None or total_ajust is not None:
        ajust_n = int(total_ajust or 0)
        ativ_n = int(total_ativ or 0)
        if ajust_n > 0:
            sections.append(
                f"Para proteger a produção, {ajust_n} de {ativ_n} atividade(s) do "
                "calendário já foram adaptadas ao clima."
            )
        elif ativ_n > 0:
            sections.append(
                f"As {ativ_n} atividade(s) do calendário seguiram sem necessidade de "
                "reagendamento por alertas."
            )
    if ultimo_resumo:
        sections.append(f"Destaque de manejo: {str(ultimo_resumo).strip()}.")

    return " ".join(sections)


_CROP_NAMES_EN: dict[str, str] = {
    "feijão-caupi": "Cowpea",
    "feijao-caupi": "Cowpea",
    "feijão-de-corda": "Cowpea",
    "feijão-carioca": "Pinto bean",
    "feijao-carioca": "Pinto bean",
    "feijão-de-porco": "Jack bean",
    "feijão-guandu": "Pigeon pea",
    "batata-doce": "Sweet potato",
    "sorgo": "Sorghum",
    "milheto": "Pearl millet",
    "amendoim": "Peanut",
    "mandioca": "Cassava",
    "crotalária": "Sunn hemp",
    "crotalaria": "Sunn hemp",
    "milho": "Corn",
    "soja": "Soybean",
    "braquiária": "Brachiaria",
    "braquiaria": "Brachiaria",
    "gergelim": "Sesame",
    "girassol": "Sunflower",
    "algodão": "Cotton",
    "algodao": "Cotton",
    "arroz": "Rice",
    "mucuna": "Velvet bean",
    "guandu": "Pigeon pea",
    "feijão": "Beans",
    "descanso": "Rest",
    "(atual)": "(Current)",
}

_CROP_EN_PATTERN = re.compile(
    "|".join(re.escape(k) for k in sorted(_CROP_NAMES_EN.keys(), key=len, reverse=True)),
    re.IGNORECASE,
)


def _translate_strategy_name_en(name: str) -> str:
    if not name:
        return name
    return _CROP_EN_PATTERN.sub(
        lambda m: _CROP_NAMES_EN.get(m.group(0).lower(), m.group(0)),
        name,
    )


class RotationExplainerAgent:
    """Agente responsável por traduzir simulações agronômicas para linguagem simples."""

    def __init__(self, llm: Any = None):
        if llm is not None:
            self.llm = llm
        else:
            api_key = os.getenv("GOOGLE_API_KEY")
            # Mock para desenvolvimento local sem API Key
            if not api_key:
                self.llm = FakeListLLM(responses=[_DEFAULT_MOCK_RESPONSE])
            else:
                self.llm = ChatGoogleGenerativeAI(
                    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                    temperature=0.2,
                    google_api_key=api_key,
                )

        self._response_cache: OrderedDict[str, Any] = OrderedDict()

        self.prompt = PromptTemplate(
            input_variables=["crop", "benefits", "risks"],
            template=(
                "Você é um assistente amigo do pequeno produtor rural e da agricultura familiar.\n"
                "O sistema avaliou a estratégia: {crop}.\n"
                "Benefícios esperados: {benefits}.\n"
                "Riscos de água e clima: {risks}.\n\n"
                "Explique de forma simples, direta e sem palavras técnicas difíceis por que essa "
                "opção foi avaliada assim e o que observar na prática no campo. Use apenas os dados informados.\n\n"
                "MANDATÓRIO: Conclua a resposta lembrando que esta ferramenta serve para apoiar a "
                "decisão e identificar possibilidades, mas não substitui a experiência local e que "
                "a decisão final é sempre do produtor."
            ),
        )
        self.strategies_prompt = PromptTemplate(
            input_variables=["strategies", "context"],
            template=(
                "Você conversa direto com um pequeno produtor da agricultura familiar.\n"
                "Contexto do terreno e prioridades: {context}\n\n"
                "Opções de plantio avaliadas (na ordem):\n"
                "{strategies}\n\n"
                "Explique CADA opção em palavras bem simples do dia a dia da roça, como se estivesse "
                "conversando na beira do terreiro (curto, claro e acolhedor).\n"
                "REGRAS OBRIGATÓRIAS:\n"
                f"1. Escreva todas as explicações nesta resposta, na mesma ordem, separando cada opção "
                f"exatamente com {STRATEGY_SEPARATOR} em uma linha própria.\n"
                "2. NÃO escreva saudação ('Olá, amigo produtor', 'Que bom...') nem texto antes da primeira opção.\n"
                "3. NÃO use Markdown (nunca use **, *, # ou traços de lista). Escreva só texto simples.\n"
                "4. Use NO MÁXIMO 2 a 3 frases curtas por opção (fácil de ler no celular): "
                "diga com o nome das plantas por que ela ajuda (ou pede cuidado com água) no objetivo do produtor "
                "e dê 1 dica prática de campo. Traduza números e siglas em palavras simples "
                "(nunca cite GAEZ, ECOCROP, CMIP6, AGROFIT, LRLM, z-score ou 'fixação biológica').\n"
                "5. Termine CADA bloco exatamente com uma frase curta: 'A decisão final é sempre sua.'"
            ),
        )
        self.structured_strategies_prompt = PromptTemplate(
            input_variables=["strategies", "context"],
            template=(
                "Você conversa direto com um pequeno produtor da agricultura familiar.\n"
                "Contexto do terreno e prioridades: {context}\n\n"
                "Opções avaliadas (mantenha exatamente esta ordem):\n"
                "{strategies}\n\n"
                "Para cada opção, escreva em palavras bem simples da roça (sem saudações, sem Markdown ** ou *, "
                "e sem siglas técnicas como GAEZ, ECOCROP, CMIP6, AGROFIT ou LRLM):\n"
                "- `resumo`: 1 ou 2 frases curtas dizendo o que esperar dela e do risco de faltar água.\n"
                "- `acao_pratica`: 1 dica curta e direta do que fazer no campo."
            ),
        )
        self.alert_prompt = PromptTemplate(
            input_variables=["tipo_evento", "severidade", "cultura", "resumo_adaptacao", "detalhes_clima"],
            template=(
                "Você é um assistente amigo do pequeno produtor rural e da agricultura familiar.\n"
                "Alerta climático: {tipo_evento} | Severidade: {severidade} | Cultura: {cultura}\n"
                "Sinais climáticos: {detalhes_clima}\n"
                "Adaptação sugerida no calendário: {resumo_adaptacao}\n\n"
                "Explique em linguagem bem simples, calma e direta o que esse alerta significa "
                "e dê 2 ou 3 orientações práticas do que o agricultor pode fazer já no campo. "
                "Responda estritamente no idioma indicado nas instruções de resumo/sinais quando solicitado.\n\n"
                "MANDATÓRIO: Conclua lembrando que a ferramenta apoia a decisão, mas a decisão final "
                "é sempre do produtor."
            ),
        )
        self.structured_alert_prompt = PromptTemplate(
            input_variables=["tipo_evento", "severidade", "cultura", "resumo_adaptacao", "detalhes_clima"],
            template=(
                "Você é um assistente amigo do pequeno produtor rural e da agricultura familiar.\n"
                "Alerta climático: {tipo_evento} | Severidade: {severidade} | Cultura: {cultura}\n"
                "Sinais climáticos: {detalhes_clima}\n"
                "Adaptação sugerida no calendário: {resumo_adaptacao}\n\n"
                "Explique em linguagem simples e calma o alerta em `diagnostico_simples` e liste 2 ou 3 "
                "ações práticas imediatas em `acoes_imediatas`, usando apenas os dados informados. "
                "Responda estritamente no idioma indicado nas instruções de resumo/sinais quando solicitado."
            ),
        )
        self.report_prompt = PromptTemplate(
            input_variables=["propriedade", "clima", "vigor", "vulnerabilidade", "adaptacoes"],
            template=(
                "Você é um assistente amigo do pequeno produtor rural e da agricultura familiar.\n"
                "Propriedade: {propriedade}\n"
                "Resumo climático: {clima}\n"
                "Vigor do terreno: {vigor}\n"
                "Vulnerabilidade: {vulnerabilidade}\n"
                "Adaptações de calendário: {adaptacoes}\n\n"
                "Faça um resumo executivo curto, encorajador e em linguagem simples para o agricultor "
                "entender como a terra e o plantio responderam ao clima neste período.\n\n"
                "MANDATÓRIO: Conclua lembrando que a ferramenta apoia a decisão, mas a decisão final "
                "é sempre do produtor."
            ),
        )
        self._build_chains()

    def clear_cache(self) -> None:
        """Limpa o cache em memória de respostas do agente."""
        self._response_cache.clear()

    @staticmethod
    def _make_cache_key(prefix: str, payload: Any) -> str:
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"{prefix}:{digest}"

    def _cache_get(self, key: str) -> Any | None:
        if key not in self._response_cache:
            return None
        value = self._response_cache.pop(key)
        self._response_cache[key] = value
        return value

    def _cache_set(self, key: str, value: Any) -> None:
        if key in self._response_cache:
            self._response_cache.pop(key)
        self._response_cache[key] = value
        while len(self._response_cache) > _MAX_RESPONSE_CACHE:
            self._response_cache.popitem(last=False)

    def _build_chains(self) -> None:
        self.chain = self.prompt | self.llm
        self.strategies_chain = self.strategies_prompt | self.llm
        self.alert_chain = self.alert_prompt | self.llm
        self.report_chain = self.report_prompt | self.llm
        self._default_strategies_chain = self.strategies_chain
        self._default_alert_chain = self.alert_chain
        self.structured_strategies_chain = None
        self.structured_alert_chain = None

        if not isinstance(self.llm, FakeListLLM) and hasattr(self.llm, "with_structured_output"):
            try:
                self.structured_strategies_chain = (
                    self.structured_strategies_prompt
                    | self.llm.with_structured_output(StrategyExplanationsBatch)
                )
                self.structured_alert_chain = (
                    self.structured_alert_prompt
                    | self.llm.with_structured_output(AlertExplanationStructured)
                )
            except Exception:
                self.structured_strategies_chain = None
                self.structured_alert_chain = None

        self._chain_llm = self.llm

    def _sync_chains(self) -> None:
        # Permite que testes ou callers troquem `agent.llm` após o __init__.
        if self.llm is not self._chain_llm:
            self._build_chains()

    def generate_explanation(
        self, crop: str, benefits: str, risks: str, idioma: str = "pt"
    ) -> str:
        lang = _normalize_lang(idioma)
        self._sync_chains()
        if isinstance(self.llm, FakeListLLM) and lang == "en":
            return _ensure_disclaimer(_DEFAULT_MOCK_RESPONSE_EN, "en")
        crop_prompt = _translate_strategy_name_en(crop) if lang == "en" else crop
        benefits_prompt = (
            f"{benefits}\n[IMPORTANT: Respond strictly in English in simple, clear language.]"
            if lang == "en"
            else benefits
        )
        response = self.chain.invoke(
            {"crop": crop_prompt, "benefits": benefits_prompt, "risks": risks}
        )
        return _ensure_disclaimer(_extract_text(response), lang)

    def _try_structured_strategies(
        self,
        strategies_block: str,
        context_block: str,
        expected_count: int,
        idioma: str = "pt",
    ) -> list[str] | None:
        if (
            self.structured_strategies_chain is None
            or self.strategies_chain is not self._default_strategies_chain
        ):
            return None
        lang = _normalize_lang(idioma)
        try:
            parsed = self.structured_strategies_chain.invoke(
                {"strategies": strategies_block, "context": context_block}
            )
            items = getattr(parsed, "estrategias", None)
            if isinstance(parsed, dict):
                items = parsed.get("estrategias")
            if not isinstance(items, list) or len(items) != expected_count:
                return None

            blocks: list[str] = []
            prefix = "In practice:" if lang == "en" else "Na prática:"
            for entry in items:
                entry_dict = _to_dict(entry)
                resumo = str(entry_dict.get("resumo") or "").strip()
                acao = str(entry_dict.get("acao_pratica") or "").strip()
                if not resumo:
                    return None
                blocks.append(f"{resumo} {prefix} {acao}" if acao else resumo)
            return blocks
        except Exception:
            return None

    def explain_strategies(
        self,
        strategies: list[Any],
        field_metrics: dict[str, Any] | None = None,
        farmer_priorities: dict[str, Any] | None = None,
        idioma: str = "pt",
    ) -> list[str]:
        """Explica todas as estratégias em uma única chamada ao LLM (com saída estruturada e cache)."""
        if not strategies:
            return []

        lang = _normalize_lang(idioma)
        normalized = [_normalize_strategy(s) for s in strategies]
        if lang == "en":
            for item in normalized:
                item["strategy"] = _translate_strategy_name_en(item["strategy"])
        strategies_block = _format_strategies_block(
            normalized, field_metrics=field_metrics, farmer_priorities=farmer_priorities
        )
        base_context_block = _format_context(field_metrics, farmer_priorities)
        context_block = (
            f"IMPORTANT: Respond strictly in English (simple, clear language for farmers). {base_context_block}"
            if lang == "en"
            else base_context_block
        )

        self._sync_chains()
        cache_key = self._make_cache_key(
            "strategies",
            {
                "idioma": lang,
                "strategies_block": strategies_block,
                "context_block": context_block,
                "llm_id": id(self.llm),
                "chain_id": id(self.strategies_chain),
            },
        )
        cached = self._cache_get(cache_key)
        if isinstance(cached, list) and len(cached) == len(normalized):
            return list(cached)

        blocks: list[str] | None = None
        if not (isinstance(self.llm, FakeListLLM) and lang == "en"):
            blocks = self._try_structured_strategies(
                strategies_block, context_block, len(normalized), idioma=lang
            )
            if blocks is None:
                response = self.strategies_chain.invoke(
                    {"strategies": strategies_block, "context": context_block}
                )
                raw_text = _extract_text(response)
                blocks = _split_strategy_blocks(raw_text, len(normalized))

        current_item = next(
            (
                s
                for s in normalized
                if "(atual)" in s["strategy"].lower()
                or "(current)" in s["strategy"].lower()
            ),
            None,
        )
        current_name = current_item["strategy"] if current_item else None
        best_viability = max(
            (s["viability"] for s in normalized if s["viability"] is not None),
            default=None,
        )

        explanations: list[str] = []
        for idx, item in enumerate(normalized):
            name = item["strategy"]
            base_name = name.replace("(Atual)", "").replace("(atual)", "").strip()
            if blocks is not None:
                text = _clean_farmer_text(blocks[idx], name)
                if not text:
                    is_best = best_viability is not None and item["viability"] == best_viability
                    text = _build_simple_fallback_explanation(
                        item, is_best, current_name, field_metrics, farmer_priorities, idioma=lang
                    )
                elif base_name and base_name.lower() not in text.lower():
                    text = f"{name}: {text}"
            else:
                is_best = best_viability is not None and item["viability"] == best_viability
                text = _build_simple_fallback_explanation(
                    item, is_best, current_name, field_metrics, farmer_priorities, idioma=lang
                )

            explanations.append(_ensure_disclaimer(text, lang))

        self._cache_set(cache_key, list(explanations))
        return explanations

    def explain_strategies_structured(
        self,
        strategies: list[Any],
        field_metrics: dict[str, Any] | None = None,
        farmer_priorities: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Retorna explicação textual (com disclaimer) + bloco de evidências numéricas por estratégia."""
        texts = self.explain_strategies(
            strategies=strategies,
            field_metrics=field_metrics,
            farmer_priorities=farmer_priorities,
        )
        return [
            {
                "explicacao": texto,
                "evidencias": build_strategy_evidence(strategy, field_metrics),
            }
            for strategy, texto in zip(strategies, texts)
        ]

    def _try_structured_alert(
        self, payload: dict[str, str], idioma: str = "pt"
    ) -> str:
        if (
            self.structured_alert_chain is None
            or self.alert_chain is not self._default_alert_chain
        ):
            return ""
        lang = _normalize_lang(idioma)
        try:
            parsed = self.structured_alert_chain.invoke(payload)
            data = _to_dict(parsed)
            diag = str(data.get("diagnostico_simples") or "").strip()
            acoes = [
                str(a).strip()
                for a in (data.get("acoes_imediatas") or [])
                if str(a).strip()
            ]
            if not diag:
                return ""
            if acoes:
                prefix = (
                    "What to do in the field"
                    if lang == "en"
                    else "O que fazer na prática no campo"
                )
                return f"{diag} {prefix}: {'; '.join(acoes)}."
            return diag
        except Exception:
            return ""

    def explain_alert(
        self,
        tipo_evento: str,
        severidade: str = "alta",
        cultura: str | None = None,
        resumo_adaptacao: str | None = None,
        detalhes_clima: dict[str, Any] | None = None,
        idioma: str = "pt",
    ) -> str:
        """Traduz alertas climáticos [M5] em orientações práticas de manejo com disclaimer e cache."""
        self._sync_chains()
        lang = _normalize_lang(idioma)
        climate_details = _format_alert_climate_details(detalhes_clima, idioma=lang)
        if lang == "en":
            climate_details = (
                f"{climate_details} | Language requirement: write your entire response in English."
            )
        payload = {
            "tipo_evento": str(tipo_evento or ("weather_alert" if lang == "en" else "alerta_climatico")),
            "severidade": _translate_risk(severidade, idioma=lang) if lang == "en" else str(severidade or "alta"),
            "cultura": str(cultura or ("monitored crop" if lang == "en" else "cultura monitorada")),
            "resumo_adaptacao": str(
                resumo_adaptacao
                or ("Reassess field schedule" if lang == "en" else "Reavaliar agenda de campo")
            ),
            "detalhes_clima": climate_details,
        }
        cache_key = self._make_cache_key(
            "alert",
            {
                "payload": payload,
                "detalhes_raw": detalhes_clima,
                "idioma": lang,
                "llm_id": id(self.llm),
                "chain_id": id(self.alert_chain),
            },
        )
        cached = self._cache_get(cache_key)
        if isinstance(cached, str) and cached:
            return cached

        raw_text = self._try_structured_alert(payload, idioma=lang)
        if not raw_text:
            try:
                response = self.alert_chain.invoke(payload)
                raw_text = _extract_text(response)
            except Exception:
                raw_text = ""

        if not raw_text or raw_text.strip() in (_DEFAULT_MOCK_RESPONSE, _DEFAULT_MOCK_RESPONSE_EN):
            raw_text = _build_alert_fallback(
                tipo_evento=tipo_evento,
                severidade=severidade,
                cultura=cultura,
                resumo_adaptacao=resumo_adaptacao,
                detalhes_clima=detalhes_clima,
                idioma=lang,
            )

        final_text = _ensure_disclaimer(raw_text, idioma=lang)
        self._cache_set(cache_key, final_text)
        return final_text

    def explain_report(
        self,
        resumo_climatico: Any,
        vigor: Any = None,
        vulnerabilidade: Any = None,
        adaptacoes: Any = None,
        nome_propriedade: str | None = None,
    ) -> str:
        """Gera resumo acessível em linguagem simples para o relatório [M6] com disclaimer e cache."""
        prop_name, clima, vigor_d, vuln_d, adapt_d = _format_report_summary_fields(
            resumo_climatico=resumo_climatico,
            vigor=vigor,
            vulnerabilidade=vulnerabilidade,
            adaptacoes=adaptacoes,
            nome_propriedade=nome_propriedade,
        )
        self._sync_chains()
        payload = {
            "propriedade": prop_name or "Propriedade cadastrada",
            "clima": str(clima),
            "vigor": str(vigor_d),
            "vulnerabilidade": str(vuln_d),
            "adaptacoes": str(adapt_d),
        }
        cache_key = self._make_cache_key(
            "report",
            {
                "payload": payload,
                "llm_id": id(self.llm),
                "chain_id": id(self.report_chain),
            },
        )
        cached = self._cache_get(cache_key)
        if isinstance(cached, str) and cached:
            return cached

        raw_text = ""
        try:
            response = self.report_chain.invoke(payload)
            raw_text = _extract_text(response)
        except Exception:
            raw_text = ""

        if not raw_text or raw_text.strip() == _DEFAULT_MOCK_RESPONSE:
            raw_text = _build_report_fallback(
                prop_name=prop_name,
                clima=clima,
                vigor_d=vigor_d,
                vuln_d=vuln_d,
                adapt_d=adapt_d,
            )

        final_text = _ensure_disclaimer(raw_text)
        self._cache_set(cache_key, final_text)
        return final_text

    generate_strategies_explanations = explain_strategies
