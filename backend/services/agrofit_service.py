import base64
import json
import logging
import os
import time
from typing import Any

import httpx

from backend.services.ecocrop_service import (
    evaluate_climate_comfort,
    normalize_botanical_family,
    resolve_scientific_name,
)
from backend.services.gaez_service import _normalize_text

logger = logging.getLogger(__name__)

AGROFIT_BASE_URL = os.getenv(
    "AGROFIT_BASE_URL",
    "https://api.cnptia.embrapa.br/agrofit/v1",
)
AGROAPI_TOKEN_URL = os.getenv(
    "AGROAPI_TOKEN_URL",
    "https://api.cnptia.embrapa.br/token",
)


def _slugify(text: str) -> str:
    return _normalize_text(text).replace(" ", "_") or "unknown"


def _extract_items(payload: Any) -> list[dict[str, Any]]:
    """Normaliza respostas paginadas ou em lista da AgroAPI (WSO2/Embrapa)."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("itens", "items", "data", "content", "resultados", "results"):
            val = payload.get(key)
            if isinstance(val, list):
                return [item for item in val if isinstance(item, dict)]
        if any(k in payload for k in ("nome_cientifico", "nome_comum", "praga", "cultura")):
            return [payload]
    return []


class AgrofitDataProvider:
    """
    Provedor direto da API AGROFIT (Embrapa AgroAPI v1) com autenticação OAuth2
    (`AGROFIT_ACCESS_TOKEN` ou `EMBRAPA_CONSUMER_KEY` + `EMBRAPA_CONSUMER_SECRET`)
    e cache em disco por nome científico. Não inventa dados quando não há
    credenciais ou resposta válida da API.
    """

    def __init__(
        self,
        data_path: str = "data",
        access_token: str | None = None,
        consumer_key: str | None = None,
        consumer_secret: str | None = None,
        base_url: str | None = None,
        token_url: str | None = None,
        timeout: float = 12.0,
    ):
        self.data_path = data_path
        self.access_token = access_token
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.base_url = base_url
        self.token_url = token_url
        self.timeout = float(timeout)
        self._oauth_token: str | None = None
        self._oauth_expires_at: float = 0.0

    def _cache_dir(self) -> str:
        return os.path.join(self.data_path, "agrofit_cache")

    def _active_base_url(self) -> str:
        return (self.base_url or AGROFIT_BASE_URL).rstrip("/")

    def _active_token_url(self) -> str:
        return self.token_url or AGROAPI_TOKEN_URL

    def has_credentials(self) -> bool:
        token = self.access_token or os.getenv("AGROFIT_ACCESS_TOKEN") or ""
        if token.strip():
            return True
        key = self.consumer_key or os.getenv("EMBRAPA_CONSUMER_KEY") or ""
        secret = self.consumer_secret or os.getenv("EMBRAPA_CONSUMER_SECRET") or ""
        return bool(key.strip() and secret.strip())

    def _get_bearer_token(self) -> str | None:
        explicit = (self.access_token or os.getenv("AGROFIT_ACCESS_TOKEN") or "").strip()
        if explicit:
            return explicit

        if self._oauth_token and time.monotonic() < self._oauth_expires_at - 30:
            return self._oauth_token

        key = (self.consumer_key or os.getenv("EMBRAPA_CONSUMER_KEY") or "").strip()
        secret = (self.consumer_secret or os.getenv("EMBRAPA_CONSUMER_SECRET") or "").strip()
        if not key or not secret:
            return None

        encoded = base64.b64encode(f"{key}:{secret}".encode("utf-8")).decode("ascii")
        try:
            resp = httpx.post(
                self._active_token_url(),
                headers={
                    "Authorization": f"Basic {encoded}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            token_data = resp.json()
            access = str(token_data.get("access_token") or "").strip()
            if not access:
                return None
            expires_in = float(token_data.get("expires_in") or 3600)
            self._oauth_token = access
            self._oauth_expires_at = time.monotonic() + max(60.0, expires_in)
            return access
        except Exception as exc:
            logger.warning("Falha ao obter token OAuth2 na Embrapa AgroAPI: %s", exc)
            return None

    def _parse_pests_from_records(
        self, records: list[dict[str, Any]], scientific_name: str
    ) -> tuple[list[dict[str, Any]], int]:
        pests_by_key: dict[str, dict[str, Any]] = {}
        products_count = 0

        for rec in records:
            if not isinstance(rec, dict):
                continue

            # Formato aninhado ou plano de /pragas ou /search/produtos-formulados
            praga_obj = rec.get("praga") if isinstance(rec.get("praga"), dict) else rec
            indicacoes = rec.get("indicacao_uso") or rec.get("indicacoes") or []
            if isinstance(indicacoes, list) and indicacoes:
                products_count += 1
                for ind in indicacoes:
                    if not isinstance(ind, dict):
                        continue
                    sci_ind = str(
                        ind.get("cultura_nome_cientifico")
                        or (ind.get("cultura") or {}).get("nome_cientifico", "")
                        or ""
                    ).strip()
                    if sci_ind and sci_ind.lower() != scientific_name.lower():
                        continue
                    p_nome = str(ind.get("praga_nome_comum") or ind.get("nome_comum") or "").strip()
                    p_sci = str(ind.get("praga_nome_cientifico") or ind.get("nome_cientifico") or "").strip()
                    p_tipo = str(ind.get("classe_agronomica") or ind.get("tipo") or "").strip() or None
                    if p_nome or p_sci:
                        k = f"{p_sci.lower()}|{p_nome.lower()}"
                        pests_by_key.setdefault(
                            k,
                            {
                                "nome_comum": p_nome or p_sci,
                                "nome_cientifico": p_sci or None,
                                "tipo": p_tipo,
                            },
                        )
                continue

            nome_comum = str(
                praga_obj.get("nome_comum")
                or praga_obj.get("praga_nome_comum")
                or praga_obj.get("nome")
                or ""
            ).strip()
            nome_sci = str(
                praga_obj.get("nome_cientifico")
                or praga_obj.get("praga_nome_cientifico")
                or ""
            ).strip()
            # Evita confundir registro da própria cultura com nome de praga
            if nome_sci.lower() == scientific_name.lower() and not praga_obj.get("praga_nome_cientifico"):
                continue
            tipo = str(
                praga_obj.get("tipo")
                or praga_obj.get("classe")
                or praga_obj.get("classe_agronomica")
                or ""
            ).strip() or None

            if nome_comum or nome_sci:
                k = f"{nome_sci.lower()}|{nome_comum.lower()}"
                pests_by_key.setdefault(
                    k,
                    {
                        "nome_comum": nome_comum or nome_sci,
                        "nome_cientifico": nome_sci or None,
                        "tipo": tipo,
                    },
                )
            if rec.get("numero_registro") or rec.get("marca_comercial") or rec.get("produto"):
                products_count += 1

        return list(pests_by_key.values()), products_count

    def fetch_crop_pests(
        self,
        scientific_name: str,
        common_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Consulta pragas e produtos fitossanitários registrados na API AGROFIT (v1)
        a partir do `Scientific Name`, com cache em disco e sem fallback inventado.
        """
        sci = (resolve_scientific_name(scientific_name) or str(scientific_name or "").strip())
        if not sci:
            return {
                "origem": "embrapa_agrofit_v1",
                "data_quality": "no_data",
                "reason": "missing_scientific_name",
                "scientific_name": "",
                "pests": [],
                "products_count": 0,
            }

        cache_path = os.path.join(self._cache_dir(), f"agrofit_{_slugify(sci)}.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, encoding="utf-8") as fp:
                    cached = json.load(fp)
                if isinstance(cached, dict) and cached.get("data_quality") == "agrofit_v1":
                    return cached
            except Exception as exc:
                logger.warning("Falha ao ler cache AGROFIT '%s': %s", cache_path, exc)

        token = self._get_bearer_token()
        if not token:
            return {
                "origem": "embrapa_agrofit_v1",
                "data_quality": "no_data",
                "reason": "missing_credentials",
                "scientific_name": sci,
                "pests": [],
                "products_count": 0,
            }

        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        base = self._active_base_url()
        query_name = common_name or sci
        raw_records: list[dict[str, Any]] = []
        any_request_ok = False

        endpoints = [
            (f"{base}/pragas", {"nome_cientifico_cultura": sci}),
            (f"{base}/search/produtos-formulados", {"cultura": query_name}),
        ]
        for url, params in endpoints:
            try:
                resp = httpx.get(url, headers=headers, params=params, timeout=self.timeout)
                if resp.status_code in (400, 404):
                    continue
                resp.raise_for_status()
                any_request_ok = True
                raw_records.extend(_extract_items(resp.json()))
            except Exception as exc:
                logger.warning("Falha ao consultar AGROFIT (%s): %s", url, exc)

        if not any_request_ok:
            return {
                "origem": "embrapa_agrofit_v1",
                "data_quality": "no_data",
                "reason": "api_unavailable",
                "scientific_name": sci,
                "pests": [],
                "products_count": 0,
            }

        pests, products_count = self._parse_pests_from_records(raw_records, sci)
        result = {
            "origem": "embrapa_agrofit_v1",
            "data_quality": "agrofit_v1",
            "scientific_name": sci,
            "pests": pests,
            "pests_count": len(pests),
            "products_count": products_count,
        }

        try:
            os.makedirs(self._cache_dir(), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as fp:
                json.dump(result, fp, ensure_ascii=False)
        except Exception as exc:
            logger.warning("Não foi possível salvar cache AGROFIT em disco: %s", exc)

        return result

    def fetch_crops_pests_map(
        self, scientific_names: list[str]
    ) -> dict[str, Any]:
        """Consulta em lote os dados fitossanitários AGROFIT por Scientific Name."""
        crops_map: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        any_valid = False
        for name in scientific_names:
            sci = resolve_scientific_name(name) or str(name or "").strip()
            if not sci:
                continue
            key = sci.lower()
            if key in seen:
                continue
            seen.add(key)
            res = self.fetch_crop_pests(sci)
            if res.get("data_quality") == "agrofit_v1":
                any_valid = True
                crops_map[key] = res

        return {
            "origem": "embrapa_agrofit_v1",
            "data_quality": "agrofit_v1" if any_valid else "no_data",
            "crops": crops_map,
        }


def _lookup_ecocrop_record(
    crop_name: str, ecocrop_crops: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not isinstance(ecocrop_crops, dict) or not ecocrop_crops:
        return None
    norm = _normalize_text(crop_name)
    if norm in ecocrop_crops and isinstance(ecocrop_crops[norm], dict):
        return ecocrop_crops[norm]
    sci = resolve_scientific_name(crop_name)
    if sci and sci.lower() in ecocrop_crops and isinstance(ecocrop_crops[sci.lower()], dict):
        return ecocrop_crops[sci.lower()]
    for rec in ecocrop_crops.values():
        if not isinstance(rec, dict):
            continue
        if sci and str(rec.get("scientific_name", "")).lower() == sci.lower():
            return rec
        if norm and norm in _normalize_text(str(rec.get("scientific_name", ""))):
            return rec
    return None


def _lookup_agrofit_record(
    crop_name: str,
    scientific_name: str | None,
    agrofit_crops: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(agrofit_crops, dict) or not agrofit_crops:
        return None
    candidates = [
        str(scientific_name or "").strip().lower(),
        _normalize_text(crop_name),
        str(crop_name or "").strip().lower(),
    ]
    for key in candidates:
        if key and isinstance(agrofit_crops.get(key), dict):
            return agrofit_crops[key]
    return None


def assess_phytosanitary_risk(
    strategy_crops: list[str],
    metrics: dict[str, float],
    temporal_features: dict[str, Any] | None = None,
    parsed_history: dict[str, Any] | None = None,
    farmer_priorities: dict[str, Any] | None = None,
    ecocrop_crops: dict[str, Any] | None = None,
    agrofit_crops: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Cruza taxonomia/faixas ECOCROP, dados AGROFIT por `Scientific Name` e gatilhos
    climáticos NASA (SMAP/ECOSTRESS/POWER) para calcular risco fitossanitário no
    `score_breakdown`, penalizando/alertando sem bloquear culturas de subsistência.
    """
    tf = temporal_features or {}
    history = parsed_history or {}
    priorities = farmer_priorities or {}
    praga_alvo = _normalize_text(str(priorities.get("praga_alvo") or ""))

    moisture = float(metrics.get("moisture", 0.25))
    temp_c = float(metrics.get("temp_c", 27.0))
    annual_rain_mm = float(metrics.get("annual_rain_mm", 1200.0))
    daily_rain = annual_rain_mm / 365.0
    dry_spell_max = int(tf.get("dry_spell_max", 0))

    climate_triggers: list[str] = []
    if moisture >= 0.35 or (daily_rain >= 8.0 and 20.0 <= temp_c <= 32.0):
        climate_triggers.append("umidade_elevada_risco_fungico")
    if temp_c >= 33.0 and (moisture <= 0.16 or dry_spell_max >= 4):
        climate_triggers.append("calor_seco_pragas_sugadoras")
    elif temp_c >= 35.0:
        climate_triggers.append("estresse_termico_foliar")

    families: list[str] = []
    scientific_names: list[str] = []
    warnings: list[str] = []
    agrofit_pests: list[str] = []
    agrofit_pests_count = 0
    agrofit_data_available = False
    ecocrop_comfort_statuses: list[str] = []

    risk_score = 0.0
    if "umidade_elevada_risco_fungico" in climate_triggers:
        risk_score += 0.18
        warnings.append(
            "Umidade elevada do solo/chuva (SMAP/GPM) favorece doenças fúngicas e bacterianas."
        )
    if "calor_seco_pragas_sugadoras" in climate_triggers:
        risk_score += 0.18
        warnings.append(
            "Calor e déficit hídrico (ECOSTRESS/SMAP) favorecem ácaros, tripes e lagartas."
        )
    elif "estresse_termico_foliar" in climate_triggers:
        risk_score += 0.10

    for crop_name in strategy_crops:
        eco_rec = _lookup_ecocrop_record(crop_name, ecocrop_crops)
        sci_name = (
            eco_rec.get("scientific_name")
            if isinstance(eco_rec, dict) and eco_rec.get("scientific_name")
            else resolve_scientific_name(crop_name)
        )
        if sci_name and sci_name not in scientific_names:
            scientific_names.append(sci_name)

        if isinstance(eco_rec, dict):
            fam = normalize_botanical_family(
                eco_rec.get("family_canonical") or eco_rec.get("family")
            )
            if fam:
                families.append(fam)
            comfort = evaluate_climate_comfort(eco_rec, temp_c, annual_rain_mm)
            status_c = str(comfort.get("status", "unknown"))
            ecocrop_comfort_statuses.append(status_c)
            if status_c == "stress":
                risk_score += 0.14
            elif status_c == "marginal":
                risk_score += 0.05
            for w in comfort.get("warnings", []):
                if w not in warnings:
                    warnings.append(w)

        agro_rec = _lookup_agrofit_record(crop_name, sci_name, agrofit_crops)
        if isinstance(agro_rec, dict) and agro_rec.get("data_quality") == "agrofit_v1":
            agrofit_data_available = True
            pests = agro_rec.get("pests") or []
            agrofit_pests_count += len(pests)
            for pest in pests:
                if not isinstance(pest, dict):
                    continue
                p_common = str(pest.get("nome_comum") or "").strip()
                p_sci = str(pest.get("nome_cientifico") or "").strip()
                label = f"{p_common} ({p_sci})" if p_common and p_sci else (p_common or p_sci)
                if label and label not in agrofit_pests:
                    agrofit_pests.append(label)
                if praga_alvo and (
                    praga_alvo in _normalize_text(p_common)
                    or praga_alvo in _normalize_text(p_sci)
                ):
                    risk_score += 0.22
                    warnings.append(
                        f"Atenção fitossanitária (AGROFIT): {crop_name} registra suscetibilidade "
                        f"à praga-alvo '{p_common or p_sci}'; recomenda-se monitoramento preventivo."
                    )

    if agrofit_data_available and agrofit_pests_count > 0 and climate_triggers:
        risk_score += min(0.16, 0.03 * agrofit_pests_count)
        warnings.append(
            f"AGROFIT identificou {agrofit_pests_count} praga(s) associada(s) sob gatilho climático ativo."
        )

    # Verifica repetição da mesma família botânica contra o histórico ou dentro da própria rotação
    same_family_as_history = False
    has_family_break = False
    if history.get("has_history") and history.get("ultimo_cultivo") and families:
        last_crop = str(history["ultimo_cultivo"])
        last_eco = _lookup_ecocrop_record(last_crop, ecocrop_crops)
        last_family = (
            normalize_botanical_family(
                last_eco.get("family_canonical") or last_eco.get("family")
            )
            if isinstance(last_eco, dict)
            else None
        )
        if last_family:
            if families[0] == last_family:
                same_family_as_history = True
                risk_score += 0.24
                warnings.append(
                    f"Mesma família botânica ({last_family}) do cultivo anterior; "
                    "risco de continuidade de pragas e patógenos de solo (cultivo não bloqueado)."
                )
            else:
                has_family_break = True
                risk_score = max(0.0, risk_score - 0.10)

    unique_families = list(dict.fromkeys(families))
    if len(families) >= 2 and len(unique_families) == 1:
        risk_score += 0.16
        warnings.append(
            f"Rotação dentro da mesma família botânica ({unique_families[0]}); "
            "alternar famílias ajuda a quebrar o ciclo de pragas."
        )

    risk_score = round(max(0.0, min(1.0, risk_score)), 3)
    if risk_score >= 0.55:
        risk_level = "high"
    elif risk_score >= 0.28:
        risk_level = "medium"
    else:
        risk_level = "low"

    # Penalização branda (-0.10 a +0.02): sinaliza risco sem jamais excluir culturas de subsistência
    if risk_score >= 0.20:
        penalty = round(-min(0.10, risk_score * 0.12), 4)
    elif has_family_break and len(unique_families) >= 2:
        penalty = 0.02
    else:
        penalty = 0.0

    return {
        "phytosanitary_risk": risk_level,
        "phytosanitary_risk_score": risk_score,
        "phytosanitary_penalty": penalty,
        "botanical_families": unique_families,
        "scientific_names": scientific_names,
        "same_family_as_history": same_family_as_history,
        "climate_triggers": climate_triggers,
        "ecocrop_comfort": ecocrop_comfort_statuses[0] if ecocrop_comfort_statuses else None,
        "agrofit_data_available": agrofit_data_available,
        "agrofit_pests_count": agrofit_pests_count if agrofit_data_available else None,
        "agrofit_pests_sample": agrofit_pests[:5],
        "subsistence_blocked": False,
        "warnings": warnings,
    }
