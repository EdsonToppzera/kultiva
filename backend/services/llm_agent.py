import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.language_models.fake import FakeListLLM
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

DISCLAIMER = (
    "Lembre-se: esta ferramenta serve para apoiar a decisão e identificar possibilidades, "
    "mas não substitui a sua experiência local. A decisão final é sempre sua."
)
STRATEGY_SEPARATOR = "---ESTRATEGIA---"

_RISK_LABELS = {
    "low": "baixo",
    "medium": "médio",
    "high": "alto",
    "baixo": "baixo",
    "medio": "médio",
    "médio": "médio",
    "alto": "alto",
    "critico": "crítico",
    "crítico": "crítico",
}


def _ensure_disclaimer(text: str) -> str:
    """Garante a presença do aviso mandatório sem duplicá-lo."""
    cleaned = str(text or "").strip()
    if not cleaned:
        return DISCLAIMER
    if "decisão final" not in cleaned.lower():
        return f"{cleaned}\n\n{DISCLAIMER}"
    return cleaned


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


def _translate_risk(risk: str) -> str:
    key = str(risk or "").strip().lower()
    return _RISK_LABELS.get(key, key or "não informado")


def _format_breakdown_highlights(breakdown: dict[str, Any] | None) -> str:
    """Traduz `score_breakdown` em pontos claros para o agricultor."""
    if not isinstance(breakdown, dict) or not breakdown:
        return ""

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

    if isinstance(farmer_priorities, dict) and farmer_priorities:
        prio_bits = [f"{k}: {v}" for k, v in farmer_priorities.items() if v is not None]
        if prio_bits:
            parts.append("prioridades do produtor -> " + ", ".join(prio_bits))

    return "; ".join(parts) if parts else "Sem dados extras do terreno informados."


def _format_strategies_block(strategies: list[dict[str, Any]]) -> str:
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
        line = (
            f"{idx}. Estratégia: {item['strategy']} | "
            f"Chance estimada de sucesso: {viab_txt} | "
            f"Risco de falta de água: {risk_txt} | "
            f"Benefícios: {benefits_txt}"
        )
        if breakdown_txt:
            line += f" | Detalhes: {breakdown_txt}"
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
) -> str:
    """Gera explicação individualizada em linguagem simples quando o LLM não delimita os blocos."""
    name = item["strategy"]
    is_current = "(atual)" in name.lower()
    risk_pt = _translate_risk(item["water_risk"])
    viab = item["viability"]
    viab_txt = f"{round(viab * 100)}%" if viab is not None else "boa"

    if is_current:
        intro = f"A opção {name} mostra como fica o resultado mantendo a prática atual da propriedade."
    elif is_best and current_name:
        intro = (
            f"A opção {name} se destaca como uma alternativa mais segura para o terreno "
            f"em comparação com {current_name}."
        )
    else:
        intro = f"A opção {name} é uma alternativa de rotação avaliada para o seu terreno."

    details = [
        f"Ela teve chance estimada de dar certo de {viab_txt} e risco de falta de água {risk_pt}."
    ]
    if item["benefits"]:
        details.append(f"Na prática, ajuda porque traz: {item['benefits']}.")

    breakdown_txt = _format_breakdown_highlights(item["score_breakdown"])
    if breakdown_txt:
        details.append(f"Pontos observados para a lavoura: {breakdown_txt}.")

    return f"{intro} {' '.join(details)}"


class RotationExplainerAgent:
    """Agente responsável por traduzir simulações agronômicas para linguagem simples."""

    def __init__(self, llm: Any = None):
        if llm is not None:
            self.llm = llm
        else:
            api_key = os.getenv("GOOGLE_API_KEY")
            # Mock para desenvolvimento local sem API Key
            if not api_key:
                self.llm = FakeListLLM(
                    responses=[
                        "Esta é uma explicação mockada gerada localmente. "
                        "A rotação sugerida ajuda na infiltração de água."
                    ]
                )
            else:
                self.llm = ChatGoogleGenerativeAI(
                    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                    temperature=0.2,
                    google_api_key=api_key,
                )

        self.prompt = PromptTemplate(
            input_variables=["crop", "benefits", "risks"],
            template=(
                "Você é um assistente amigo do pequeno produtor rural e da agricultura familiar.\n"
                "O sistema avaliou a estratégia: {crop}.\n"
                "Benefícios esperados: {benefits}.\n"
                "Riscos de água e clima: {risks}.\n\n"
                "Explique de forma simples, direta e sem palavras técnicas difíceis por que essa "
                "opção foi avaliada assim e o que observar na prática no campo.\n\n"
                "MANDATÓRIO: Conclua a resposta lembrando que esta ferramenta serve para apoiar a "
                "decisão e identificar possibilidades, mas não substitui a experiência local e que "
                "a decisão final é sempre do produtor."
            ),
        )
        self.strategies_prompt = PromptTemplate(
            input_variables=["strategies", "context"],
            template=(
                "Você é um assistente amigo do pequeno produtor rural e da agricultura familiar.\n"
                "Contexto do terreno e prioridades: {context}\n\n"
                "Estratégias de rotação avaliadas (na ordem):\n"
                "{strategies}\n\n"
                "Explique CADA estratégia acima em linguagem bem simples, clara e prática (sem jargões), "
                "comparando as alternativas com a prática marcada como (Atual) quando ela estiver na lista.\n"
                "REGRAS DE FORMATO:\n"
                f"1. Escreva todas as explicações nesta única resposta, na mesma ordem, separando cada "
                f"estratégia exatamente com {STRATEGY_SEPARATOR} em uma linha própria.\n"
                "2. Em cada explicação, cite o nome da estratégia, o risco de água e o benefício prático no campo.\n"
                "3. Termine CADA explicação lembrando que a ferramenta apoia a decisão, mas a decisão final "
                "é sempre do produtor."
            ),
        )
        self._build_chains()

    def _build_chains(self) -> None:
        self.chain = self.prompt | self.llm
        self.strategies_chain = self.strategies_prompt | self.llm
        self._chain_llm = self.llm

    def _sync_chains(self) -> None:
        # Permite que testes ou callers troquem `agent.llm` após o __init__.
        if self.llm is not self._chain_llm:
            self._build_chains()

    def generate_explanation(self, crop: str, benefits: str, risks: str) -> str:
        self._sync_chains()
        response = self.chain.invoke({"crop": crop, "benefits": benefits, "risks": risks})
        return _ensure_disclaimer(_extract_text(response))

    def explain_strategies(
        self,
        strategies: list[Any],
        field_metrics: dict[str, Any] | None = None,
        farmer_priorities: dict[str, Any] | None = None,
    ) -> list[str]:
        """Explica todas as estratégias em uma única chamada ao LLM, retornando 1 texto por estratégia."""
        if not strategies:
            return []

        normalized = [_normalize_strategy(s) for s in strategies]
        strategies_block = _format_strategies_block(normalized)
        context_block = _format_context(field_metrics, farmer_priorities)

        self._sync_chains()
        response = self.strategies_chain.invoke(
            {"strategies": strategies_block, "context": context_block}
        )
        raw_text = _extract_text(response)
        blocks = _split_strategy_blocks(raw_text, len(normalized))

        current_item = next(
            (s for s in normalized if "(atual)" in s["strategy"].lower()),
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
                text = blocks[idx].strip()
                if not text:
                    is_best = best_viability is not None and item["viability"] == best_viability
                    text = _build_simple_fallback_explanation(item, is_best, current_name)
                elif base_name and base_name.lower() not in text.lower():
                    text = f"{name}: {text}"
            else:
                is_best = best_viability is not None and item["viability"] == best_viability
                text = _build_simple_fallback_explanation(item, is_best, current_name)

            explanations.append(_ensure_disclaimer(text))

        return explanations

    generate_strategies_explanations = explain_strategies
