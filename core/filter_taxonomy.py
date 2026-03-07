# -*- coding: utf-8 -*-
"""
Loader de taxonomia de filtros do Quiz.

Permite configurar filtros avancados via JSON externo sem alterar o codigo.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.app_paths import get_data_dir

_SECTION_KEYS = ["disciplinas", "assuntos", "bancas", "cargos", "anos", "status"]

_DEFAULT_TAXONOMY: Dict[str, Any] = {
    "version": 1,
    "sections": [
        {
            "key": "disciplinas",
            "label": "Disciplinas",
            "options": [
                {"id": "direito_constitucional", "label": "Direito Constitucional"},
                {"id": "direito_administrativo", "label": "Direito Administrativo"},
                {"id": "direito_penal", "label": "Direito Penal"},
                {"id": "processo_penal", "label": "Processo Penal"},
                {"id": "portugues", "label": "Portugues"},
                {"id": "matematica", "label": "Matematica"},
                {"id": "raciocinio_logico", "label": "Raciocinio Logico"},
                {"id": "informatica", "label": "Informatica"},
                {"id": "gestao_publica", "label": "Gestao Publica"},
                {"id": "contabilidade", "label": "Contabilidade"},
                {"id": "legislacao_especial", "label": "Legislacao Especial"},
                {"id": "administracao_geral", "label": "Administracao Geral"},
                {"id": "administracao_publica", "label": "Administracao Publica"},
                {"id": "etica_servico_publico", "label": "Etica no Servico Publico"},
            ],
        },
        {
            "key": "assuntos",
            "label": "Assuntos",
            "options": [
                {"id": "principios", "label": "Principios"},
                {"id": "competencias", "label": "Competencias"},
                {"id": "atos_administrativos", "label": "Atos administrativos"},
                {"id": "poderes_administracao", "label": "Poderes da administracao"},
                {"id": "licitacoes", "label": "Licitacoes"},
                {"id": "responsabilidade_civil_estado", "label": "Responsabilidade civil do estado"},
                {"id": "controle_administracao", "label": "Controle da administracao"},
                {"id": "servidor_publico", "label": "Servidor publico"},
                {"id": "contratos", "label": "Contratos"},
                {"id": "seguranca_informacao", "label": "Seguranca da informacao"},
                {"id": "redes", "label": "Redes"},
                {"id": "banco_dados", "label": "Banco de dados"},
            ],
        },
        {
            "key": "bancas",
            "label": "Bancas",
            "options": [
                {"id": "cespe_cebraspe", "label": "CESPE/CEBRASPE"},
                {"id": "fgv", "label": "FGV"},
                {"id": "vunesp", "label": "VUNESP"},
                {"id": "fcc", "label": "FCC"},
                {"id": "ibfc", "label": "IBFC"},
                {"id": "aocp", "label": "AOCP"},
                {"id": "iades", "label": "IADES"},
                {"id": "fundatec", "label": "FUNDATEC"},
            ],
        },
        {
            "key": "cargos",
            "label": "Cargos",
            "options": [
                {"id": "analista", "label": "Analista"},
                {"id": "tecnico", "label": "Tecnico"},
                {"id": "assistente", "label": "Assistente"},
                {"id": "agente", "label": "Agente"},
                {"id": "policial", "label": "Policial"},
                {"id": "fiscal", "label": "Fiscal"},
                {"id": "auditor", "label": "Auditor"},
                {"id": "professor", "label": "Professor"},
                {"id": "desenvolvedor", "label": "Desenvolvedor"},
                {"id": "infraestrutura", "label": "Infraestrutura"},
            ],
        },
        {
            "key": "anos",
            "label": "Anos",
            "year_range": {"start": 2015, "end": "current", "descending": True},
            "options": [],
        },
        {
            "key": "status",
            "label": "Status",
            "options": [
                {
                    "id": "nao_resolvi",
                    "label": "Nao resolvi",
                    "aliases": ["Nao resolvidas", "Não resolvidas", "nao_resolvidas"],
                },
                {"id": "resolvi", "label": "Resolvi", "aliases": ["Resolvidas", "revisao pendente"]},
                {"id": "acertei", "label": "Acertei", "aliases": ["Corretas", "Acertos"]},
                {
                    "id": "errei",
                    "label": "Errei",
                    "aliases": ["Erradas", "Erradas recentes", "Marcadas com erro"],
                },
            ],
        },
    ],
}

_CACHE: Optional[Dict[str, Any]] = None


def _slugify(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def _normalize_option(raw: Any, fallback_id: str) -> Optional[Dict[str, Any]]:
    if isinstance(raw, dict):
        label = str(raw.get("label") or raw.get("name") or "").strip()
        opt_id = _slugify(str(raw.get("id") or ""))
        aliases_raw = raw.get("aliases") or []
    else:
        label = str(raw or "").strip()
        opt_id = ""
        aliases_raw = []

    if not opt_id:
        opt_id = _slugify(label) or _slugify(fallback_id)
    if not label:
        label = opt_id.replace("_", " ").title()
    if not opt_id:
        return None

    aliases: List[str] = []
    if isinstance(aliases_raw, list):
        aliases = [str(a).strip() for a in aliases_raw if str(a).strip()]

    return {"id": opt_id, "label": label, "aliases": aliases}


def _expand_year_range(section: Dict[str, Any]) -> List[Dict[str, Any]]:
    yr = section.get("year_range")
    if not isinstance(yr, dict):
        return []
    start = int(yr.get("start") or 2015)
    end_raw = yr.get("end", "current")
    if isinstance(end_raw, str) and end_raw.strip().lower() == "current":
        end = int(datetime.date.today().year)
    else:
        end = int(end_raw)
    if end < start:
        start, end = end, start
    descending = bool(yr.get("descending", True))
    years = list(range(start, end + 1))
    if descending:
        years.reverse()
    return [{"id": str(y), "label": str(y), "aliases": []} for y in years]


def _normalize_section(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    key = _slugify(raw.get("key"))
    if key not in _SECTION_KEYS:
        return None
    label = str(raw.get("label") or key.replace("_", " ").title()).strip()

    options: List[Dict[str, Any]] = []
    options_raw = raw.get("options") or []
    if isinstance(options_raw, list):
        for idx, item in enumerate(options_raw):
            opt = _normalize_option(item, f"{key}_{idx+1}")
            if opt:
                options.append(opt)

    if key == "anos":
        range_opts = _expand_year_range(raw)
        if range_opts:
            options = range_opts

    dedup: List[Dict[str, Any]] = []
    seen = set()
    for opt in options:
        oid = str(opt.get("id") or "").strip()
        if not oid or oid in seen:
            continue
        seen.add(oid)
        dedup.append(opt)

    return {"key": key, "label": label, "options": dedup}


def _normalize_taxonomy(raw: Any) -> Dict[str, Any]:
    default_sections = [_normalize_section(s) for s in _DEFAULT_TAXONOMY["sections"]]
    default_map = {s["key"]: s for s in default_sections if s}

    custom_sections_raw: List[Any] = []
    if isinstance(raw, dict):
        if isinstance(raw.get("sections"), list):
            custom_sections_raw = raw.get("sections") or []
        else:
            # formato alternativo: {"disciplinas":[...], "bancas":[...]}
            for key in _SECTION_KEYS:
                if key in raw:
                    custom_sections_raw.append({"key": key, "label": key.title(), "options": raw.get(key) or []})

    custom_map: Dict[str, Dict[str, Any]] = {}
    for sec_raw in custom_sections_raw:
        sec = _normalize_section(sec_raw)
        if sec:
            custom_map[sec["key"]] = sec

    merged_sections: List[Dict[str, Any]] = []
    for key in _SECTION_KEYS:
        base = deepcopy(default_map.get(key) or {"key": key, "label": key.title(), "options": []})
        custom = custom_map.get(key)
        if custom:
            base["label"] = custom.get("label") or base["label"]
            if custom.get("options"):
                base["options"] = custom["options"]
        if key == "anos" and not base.get("options"):
            base["options"] = _expand_year_range({"year_range": {"start": 2015, "end": "current", "descending": True}})
        merged_sections.append(base)

    return {"version": 1, "sections": merged_sections}


def _candidate_paths() -> List[Path]:
    project_root = Path(__file__).resolve().parent.parent
    paths: List[Path] = []

    env_path = (os.getenv("QUIZVANCE_FILTERS_PATH") or "").strip()
    if env_path:
        paths.append(Path(env_path))

    paths.append(Path.cwd() / "filter_taxonomy.json")
    paths.append(get_data_dir() / "filter_taxonomy.json")
    paths.append(project_root / "assets" / "filter_taxonomy.json")

    dedup: List[Path] = []
    seen = set()
    for p in paths:
        key = str(p.resolve()) if p.is_absolute() else str(p)
        if key in seen:
            continue
        seen.add(key)
        dedup.append(p)
    return dedup


def get_quiz_filter_taxonomy(refresh: bool = False) -> Dict[str, Any]:
    global _CACHE
    if _CACHE is not None and not refresh:
        return deepcopy(_CACHE)

    for candidate in _candidate_paths():
        try:
            if not candidate.exists() or not candidate.is_file():
                continue
            with open(candidate, "r", encoding="utf-8") as f:
                raw = json.load(f)
            normalized = _normalize_taxonomy(raw)
            normalized["source"] = str(candidate)
            _CACHE = normalized
            return deepcopy(normalized)
        except Exception:
            continue

    fallback = _normalize_taxonomy(_DEFAULT_TAXONOMY)
    fallback["source"] = "internal-default"
    _CACHE = fallback
    return deepcopy(fallback)

