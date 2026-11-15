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
_DEFAULT_MOCK_RESPONSE = (
    "Esta é uma explicação mockada gerada localmente. "
    "A rotação sugerida ajuda na infiltração de água."
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


def _format_alert_climate_details(detalhes_clima: dict[str, Any] | None) -> str:
    if not isinstance(detalhes_clima, dict) or not detalhes_clima:
        return "Sem medições detalhadas informadas."
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
        parts.append(f"chuva máxima registrada de {max_rain:.1f} mm")
    if max_temp is not None and max_temp > 0:
        parts.append(f"temperatura da superfície chegando a {max_temp:.1f} °C")
    if min_moist is not None:
        parts.append(f"umidade mínima do solo em {round(min_moist * 100)}%")
    return "; ".join(parts) if parts else "Dados climáticos de monitoramento do terreno."


def _build_alert_fallback(
    tipo_evento: str,
    severidade: str,
    cultura: str | None,
    resumo_adaptacao: str | None,
    detalhes_clima: dict[str, Any] | None,
) -> str:
    """Explicação acessível e prática para alertas climáticos [M5] em modo offline."""
    evento_key = str(tipo_evento or "").strip().lower()
    evento_label = _EVENT_LABELS.get(evento_key, str(tipo_evento or "alerta climático").replace("_", " "))
    sev_label = _translate_risk(severidade)
    cultura_txt = f" para a lavoura de {cultura.strip()}" if cultura and cultura.strip() else ""

    parts = [
        f"Atenção: identificamos um alerta de severidade {sev_label} para {evento_label}{cultura_txt}."
    ]
    climate_txt = _format_alert_climate_details(detalhes_clima)
    if isinstance(detalhes_clima, dict) and detalhes_clima:
        parts.append(f"Sinais observados no terreno: {climate_txt}.")

    action_txt = _ALERT_ACTIONS.get(
        evento_key,
        "Acompanhe a lavoura de perto nos próximos dias, proteja a cobertura do solo e "
        "ajuste adubações ou tratos culturais conforme a condição do tempo no terreno.",
    )
    parts.append(f"O que fazer na prática no campo: {action_txt}")

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
        self.alert_prompt = PromptTemplate(
            input_variables=["tipo_evento", "severidade", "cultura", "resumo_adaptacao", "detalhes_clima"],
            template=(
                "Você é um assistente amigo do pequeno produtor rural e da agricultura familiar.\n"
                "Alerta climático: {tipo_evento} | Severidade: {severidade} | Cultura: {cultura}\n"
                "Sinais climáticos: {detalhes_clima}\n"
                "Adaptação sugerida no calendário: {resumo_adaptacao}\n\n"
                "Explique em linguagem bem simples, calma e direta o que esse alerta significa "
                "e dê 2 ou 3 orientações práticas do que o agricultor pode fazer já no campo.\n\n"
                "MANDATÓRIO: Conclua lembrando que a ferramenta apoia a decisão, mas a decisão final "
                "é sempre do produtor."
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

    def _build_chains(self) -> None:
        self.chain = self.prompt | self.llm
        self.strategies_chain = self.strategies_prompt | self.llm
        self.alert_chain = self.alert_prompt | self.llm
        self.report_chain = self.report_prompt | self.llm
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

    def explain_alert(
        self,
        tipo_evento: str,
        severidade: str = "alta",
        cultura: str | None = None,
        resumo_adaptacao: str | None = None,
        detalhes_clima: dict[str, Any] | None = None,
    ) -> str:
        """Traduz alertas climáticos [M5] em orientações práticas de manejo com disclaimer."""
        self._sync_chains()
        payload = {
            "tipo_evento": str(tipo_evento or "alerta_climatico"),
            "severidade": str(severidade or "alta"),
            "cultura": str(cultura or "cultura monitorada"),
            "resumo_adaptacao": str(resumo_adaptacao or "Reavaliar agenda de campo"),
            "detalhes_clima": _format_alert_climate_details(detalhes_clima),
        }
        raw_text = ""
        try:
            response = self.alert_chain.invoke(payload)
            raw_text = _extract_text(response)
        except Exception:
            raw_text = ""

        if not raw_text or raw_text.strip() == _DEFAULT_MOCK_RESPONSE:
            raw_text = _build_alert_fallback(
                tipo_evento=tipo_evento,
                severidade=severidade,
                cultura=cultura,
                resumo_adaptacao=resumo_adaptacao,
                detalhes_clima=detalhes_clima,
            )

        return _ensure_disclaimer(raw_text)

    def explain_report(
        self,
        resumo_climatico: Any,
        vigor: Any = None,
        vulnerabilidade: Any = None,
        adaptacoes: Any = None,
        nome_propriedade: str | None = None,
    ) -> str:
        """Gera resumo acessível em linguagem simples para o relatório [M6] com disclaimer."""
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

        return _ensure_disclaimer(raw_text)

    generate_strategies_explanations = explain_strategies
