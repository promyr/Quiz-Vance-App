# -*- coding: utf-8 -*-
"""
ServiÃ§o de AI Multi-Provider (Gemini + OpenAI)
Suporta Google Gemini e OpenAI GPT
"""


import json
import random
import time
import datetime
import warnings
import sys
import os
import re
import unicodedata
from typing import Optional, Dict, List, Any
from abc import ABC, abstractmethod

try:
    from core.error_monitor import log_event
except Exception:
    def log_event(name: str, data: str = "") -> None:
        _ = (name, data)

# Configurar encoding para UTF-8 em Windows
from core.encoding import configure_utf8
configure_utf8()

# Lazy imports para reduzir latencia de startup.
genai = None
OpenAI = None
GEMINI_AVAILABLE = None
OPENAI_AVAILABLE = None


def _ensure_gemini_available() -> bool:
    global genai, GEMINI_AVAILABLE
    if GEMINI_AVAILABLE is not None:
        return bool(GEMINI_AVAILABLE)
    try:
        from google import genai as _genai
        genai = _genai
        GEMINI_AVAILABLE = True
    except Exception:
        GEMINI_AVAILABLE = False
    return bool(GEMINI_AVAILABLE)


def _ensure_openai_available() -> bool:
    global OpenAI, OPENAI_AVAILABLE
    if OPENAI_AVAILABLE is not None:
        return bool(OPENAI_AVAILABLE)
    try:
        from openai import OpenAI as _OpenAI
        OpenAI = _OpenAI
        OPENAI_AVAILABLE = True
    except Exception:
        OPENAI_AVAILABLE = False
    return bool(OPENAI_AVAILABLE)


# ========== CLASSE BASE ==========
class AIProvider(ABC):
    """Classe base para providers de AI"""
    
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
    
    @abstractmethod
    def generate_text(self, prompt: str) -> Optional[str]:
        """Gera texto a partir de um prompt"""
        pass
    
    def extract_json_object(self, text: str) -> Optional[Dict]:
        """Extrai objeto JSON de texto"""
        try:
            text = text.strip().replace("```json", "").replace("```", "")
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(text[start:end + 1])
            return None
        except Exception:
            return None
    
    def extract_json_list(self, text: str) -> Optional[List]:
        """Extrai lista JSON de texto"""
        try:
            text = text.strip().replace("```json", "").replace("```", "")
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1:
                return json.loads(text[start:end + 1])
            return None
        except Exception:
            return None


# ========== GEMINI PROVIDER ==========
class GeminiProvider(AIProvider):
    """Provider para Google Gemini"""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        super().__init__(api_key, model)
        if not _ensure_gemini_available():
            raise ImportError("google-genai nao esta instalado")
        self.client = genai.Client(api_key=api_key)
        self.last_error_kind = ""
        self.last_error_message = ""
        self._fallback_models = self._build_fallback_models(model)
        self._quota_block_until = 0.0
        self._quota_next_log_at = 0.0

    def _build_fallback_models(self, model: str) -> List[str]:
        preferred = [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-3-flash-preview",
            "gemini-2.5-pro",
            "gemini-3-pro-preview",
        ]
        return [model] + [m for m in preferred if m != model]

    def _classify_error(self, message: str) -> str:
        msg = (message or "").lower()
        if "no module named" in msg or "modulenotfounderror" in msg:
            return "dependency"
        if "429" in msg or "quota exceeded" in msg or "rate limit" in msg:
            if "limit: 0" in msg or "perday" in msg or "per day" in msg:
                return "quota_hard"
            return "quota_soft"
        if "timeout" in msg or "temporar" in msg or "unavailable" in msg:
            return "transient"
        return "other"

    def _extract_retry_after_seconds(self, message: str) -> int:
        msg = str(message or "")
        patterns_s = [
            r"Please retry in\s+([0-9]+(?:\.[0-9]+)?)s",
            r"retryDelay['\"]?\s*:\s*['\"]([0-9]+(?:\.[0-9]+)?)s['\"]",
        ]
        patterns_ms = [
            r"retryDelay['\"]?\s*:\s*['\"]([0-9]+(?:\.[0-9]+)?)ms['\"]",
        ]
        for p in patterns_s:
            m = re.search(p, msg, re.IGNORECASE)
            if m:
                try:
                    return max(3, int(float(m.group(1)) + 0.999))
                except Exception:
                    pass
        for p in patterns_ms:
            m = re.search(p, msg, re.IGNORECASE)
            if m:
                try:
                    return max(3, int(float(m.group(1)) / 1000.0 + 0.999))
                except Exception:
                    pass
        return 30

    def _set_quota_cooldown(self, message: str) -> int:
        retry_s = self._extract_retry_after_seconds(message)
        block_until = time.monotonic() + min(300, retry_s)
        self._quota_block_until = max(self._quota_block_until, block_until)
        return retry_s

    def generate_text(self, prompt: str) -> Optional[str]:
        """Gera texto usando Gemini"""
        self.last_error_kind = ""
        self.last_error_message = ""
        now = time.monotonic()
        if now < self._quota_block_until:
            self.last_error_kind = "quota_soft"
            remaining = max(1, int(self._quota_block_until - now))
            if now >= self._quota_next_log_at:
                print(f"[GEMINI] Quota em cooldown (~{remaining}s). Pulando chamada.")
                self._quota_next_log_at = now + 10.0
            return None

        quota_models = []
        for idx, candidate_model in enumerate(self._fallback_models):
            try:
                response = self.client.models.generate_content(model=candidate_model, contents=prompt)
                text = getattr(response, "text", None)
                if text:
                    self.model = candidate_model
                    if idx > 0:
                        print(f"[GEMINI] Fallback ativado com sucesso: {candidate_model}")
                    return text
            except Exception as e:
                msg = str(e)
                kind = self._classify_error(msg)
                self.last_error_kind = kind
                self.last_error_message = msg
                if kind in ("quota_hard", "quota_soft") and idx < len(self._fallback_models) - 1:
                    quota_models.append(candidate_model)
                    continue
                if kind in ("quota_hard", "quota_soft"):
                    quota_models.append(candidate_model)
                if kind not in ("quota_hard", "quota_soft"):
                    print(f"[GEMINI] Erro ({candidate_model}): {e}")
                    break
        if quota_models:
            retry_s = self._set_quota_cooldown(self.last_error_message)
            modelos = ", ".join(quota_models)
            print(f"[GEMINI] Quota esgotada nos modelos [{modelos}]. Nova tentativa em ~{retry_s}s.")
        return None
# ========== OPENAI PROVIDER ==========
class OpenAIProvider(AIProvider):
    """Provider para OpenAI GPT"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        super().__init__(api_key, model)
        if not _ensure_openai_available():
            raise ImportError("openai nÃ£o estÃ¡ instalado")
        self.client = OpenAI(api_key=api_key)
        self.last_error_kind = ""
        self.last_error_message = ""

    def _classify_error(self, message: str) -> str:
        msg = (message or "").lower()
        if "no module named" in msg or "modulenotfounderror" in msg:
            return "dependency"
        if "rate limit" in msg or "quota" in msg or "429" in msg:
            return "quota_soft" if "per" in msg else "quota_hard"
        if "insufficient_quota" in msg:
            return "quota_hard"
        if "401" in msg or "unauthorized" in msg or "invalid api key" in msg:
            return "auth"
        if "timeout" in msg or "temporar" in msg or "unavailable" in msg:
            return "transient"
        return "other"
    
    def generate_text(self, prompt: str) -> Optional[str]:
        """Gera texto usando OpenAI"""
        self.last_error_kind = ""
        self.last_error_message = ""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            msg = str(e)
            self.last_error_kind = self._classify_error(msg)
            self.last_error_message = msg
            print(f"[OPENAI] Erro: {e}")
            return None


class GroqProvider(AIProvider):
    """Provider para Groq (API compativel com OpenAI)."""

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        super().__init__(api_key, model)
        if not _ensure_openai_available():
            raise ImportError("openai nao esta instalado")
        self.client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
        self.last_error_kind = ""
        self.last_error_message = ""

    def _classify_error(self, message: str) -> str:
        msg = (message or "").lower()
        if "no module named" in msg or "modulenotfounderror" in msg:
            return "dependency"
        if "rate limit" in msg or "quota" in msg or "429" in msg:
            return "quota_soft"
        if "401" in msg or "unauthorized" in msg or "invalid api key" in msg:
            return "auth"
        if "timeout" in msg or "temporar" in msg or "unavailable" in msg:
            return "transient"
        return "other"

    def generate_text(self, prompt: str) -> Optional[str]:
        self.last_error_kind = ""
        self.last_error_message = ""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
            )
            return response.choices[0].message.content
        except Exception as e:
            msg = str(e)
            self.last_error_kind = self._classify_error(msg)
            self.last_error_message = msg
            print(f"[GROQ] Erro: {e}")
            return None


# ========== FACTORY ==========
def create_ai_provider(provider_type: str, api_key: str, model: Optional[str] = None) -> AIProvider:
    """
    Cria provider de AI
    
    Args:
        provider_type: "gemini", "openai" ou "groq"
        api_key: Chave API
        model: Modelo especÃ­fico (opcional)
    
    Returns:
        Instance de AIProvider
    """
    provider = str(provider_type or "").strip().lower()
    if provider == "gemini":
        model = model or "gemini-2.5-flash"
        return GeminiProvider(api_key, model)
    elif provider == "openai":
        model = model or "gpt-4o-mini"
        return OpenAIProvider(api_key, model)
    elif provider == "groq":
        model = model or "llama-3.3-70b-versatile"
        return GroqProvider(api_key, model)
    else:
        raise ValueError(f"Provider desconhecido: {provider_type}")


# ========== SERVIÃ‡O DE AI ==========
class AIService:
    """ServiÃ§o centralizado de AI"""
    
    def __init__(self, provider: AIProvider, telemetry_opt_in: bool = False, user_anon: str = "anon"):
        self.provider = provider
        self.telemetry_opt_in = bool(telemetry_opt_in)
        self.user_anon = str(user_anon or "anon")

    def _emit_ai_event(
        self,
        event_name: str,
        feature_name: str,
        latency_ms: int = 0,
        error_code: str = "",
    ) -> None:
        if not self.telemetry_opt_in:
            return
        provider_name = str(self.provider.__class__.__name__.replace("Provider", "")).lower()
        payload = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds") + "Z",
            "feature_name": str(feature_name or "unknown"),
            "provider": provider_name,
            "model": str(getattr(self.provider, "model", "") or ""),
            "latency_ms": int(max(0, latency_ms or 0)),
            "error_code": str(error_code or ""),
            "user_anon": self.user_anon,
        }
        try:
            log_event(event_name, json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass

    def _call_provider_text(self, prompt: str, feature_name: str) -> Optional[str]:
        started = time.perf_counter()
        self._emit_ai_event("ai_call_started", feature_name=feature_name)
        error_code = ""
        try:
            text = self.provider.generate_text(prompt)
            if not text:
                error_code = self._provider_error_kind() or "empty_response"
            return text
        except Exception:
            error_code = "exception"
            raise
        finally:
            latency = int(max(0.0, (time.perf_counter() - started) * 1000.0))
            self._emit_ai_event(
                "ai_call_finished",
                feature_name=feature_name,
                latency_ms=latency,
                error_code=error_code,
            )
    
    def _normalize_quiz(self, data: Dict) -> Optional[Dict]:
        """Normaliza dados de quiz"""
        if not isinstance(data, dict):
            return None
        
        # Extrair pergunta
        pergunta = (
            data.get("pergunta") or
            data.get("question") or
            data.get("enunciado") or
            data.get("pergunta_texto")
        )
        
        # Extrair opÃ§Ãµes
        opcoes = (
            data.get("opcoes") or
            data.get("opÃ§Ãµes") or
            data.get("alternativas") or
            data.get("choices") or
            data.get("options")
        )
        
        # Extrair resposta correta
        correta = data.get("correta_index") or data.get("indice_correto")
        if correta is None:
            correta = (
                data.get("resposta_correta") or
                data.get("answer") or
                data.get("correct_answer")
            )
        
        # Extrair explicaÃ§Ã£o
        explicacao = (
            data.get("explicacao") or
            data.get("explicaÃ§Ã£o") or
            data.get("justificativa") or
            data.get("feedback") or
            data.get("explanation") or
            ""
        )
        assunto = (
            data.get("assunto") or
            data.get("subtema") or
            data.get("tema") or
            data.get("topico") or
            data.get("topic") or
            ""
        )
        
        # ValidaÃ§Ãµes
        if not isinstance(pergunta, str) or not pergunta.strip():
            return None
        if not isinstance(opcoes, list) or len(opcoes) < 2:
            return None
        
        # Normalizar opÃ§Ãµes
        opcoes_norm = []
        for op in opcoes:
            if isinstance(op, dict):
                texto = (
                    op.get("texto") or
                    op.get("text") or
                    op.get("opcao") or
                    op.get("option")
                )
                if texto is not None:
                    opcoes_norm.append(str(texto))
            else:
                opcoes_norm.append(str(op))
        
        opcoes_norm = [o.strip() for o in opcoes_norm if o and str(o).strip()]
        if len(opcoes_norm) < 2:
            return None
        if len(opcoes_norm) > 4:
            opcoes_norm = opcoes_norm[:4]
        
        # Normalizar Ã­ndice correto
        correta_idx = None
        if isinstance(correta, int):
            correta_idx = correta
        elif isinstance(correta, str):
            c = correta.strip().upper()
            if c in ("A", "B", "C", "D"):
                correta_idx = ["A", "B", "C", "D"].index(c)
            else:
                try:
                    correta_idx = int(c)
                except Exception:
                    correta_idx = None
        
        if correta_idx is None:
            correta_idx = 0
        correta_idx = max(0, min(correta_idx, len(opcoes_norm) - 1))
        
        normalized = {
            "pergunta": pergunta.strip(),
            "opcoes": opcoes_norm,
            "correta_index": correta_idx,
            "explicacao": str(explicacao).strip()
        }
        assunto_txt = str(assunto or "").strip()
        if assunto_txt:
            normalized["assunto"] = assunto_txt[:80]
        return normalized

    def validate_task_payload(self, task: str, payload: Any) -> tuple[bool, str]:
        task_name = str(task or "").strip().lower()
        if task_name == "quiz":
            if not isinstance(payload, dict):
                return False, "quiz_payload_not_dict"
            pergunta = str(payload.get("pergunta") or "").strip()
            opcoes = payload.get("opcoes")
            try:
                correta_index = int(payload.get("correta_index", 0))
            except Exception:
                return False, "quiz_correta_index_invalid"
            if not pergunta:
                return False, "quiz_pergunta_empty"
            if not isinstance(opcoes, list) or len(opcoes) < 2:
                return False, "quiz_opcoes_invalid"
            if correta_index < 0 or correta_index >= len(opcoes):
                return False, "quiz_correta_out_of_range"
            return True, "ok"
        if task_name == "flashcard":
            if not isinstance(payload, dict):
                return False, "flashcard_payload_not_dict"
            frente = str(payload.get("frente") or "").strip()
            verso = str(payload.get("verso") or "").strip()
            if not frente or not verso:
                return False, "flashcard_missing_fields"
            return True, "ok"
        if task_name == "study_plan_item":
            if not isinstance(payload, dict):
                return False, "study_plan_item_not_dict"
            if not str(payload.get("dia") or "").strip():
                return False, "study_plan_day_empty"
            if not str(payload.get("tema") or "").strip():
                return False, "study_plan_theme_empty"
            return True, "ok"
        if task_name == "study_summary":
            if not isinstance(payload, dict):
                return False, "study_summary_not_dict"
            required_keys = ["titulo", "resumo_curto", "topicos_principais", "checklist_de_estudo"]
            for key in required_keys:
                if key not in payload:
                    return False, f"study_summary_missing_{key}"
            return True, "ok"
        return False, "task_not_supported"

    def _provider_error_kind(self) -> str:
        provider = getattr(self, "provider", None)
        return str(getattr(provider, "last_error_kind", "") or "").strip().lower()

    def _should_abort_retry(self) -> bool:
        """Evita repeticao de chamadas quando erro e terminal para a sessao."""
        return self._provider_error_kind() in {"quota_hard", "quota_soft", "auth", "dependency"}

    _METADATA_PATTERNS = [
        r"\bautor(?:a)?\b",
        r"\belaborador(?:a)?\b",
        r"\bcoordenador(?:a)?\b",
        r"\bedi[cç][aã]o\b",
        r"\bvers[aã]o\b",
        r"\bisbn\b",
        r"\bissn\b",
        r"\bsum[aá]rio\b",
        r"\bpref[aá]cio\b",
        r"\bapresenta[cç][aã]o\b",
        r"\bcapa\b",
        r"\bexpediente\b",
        r"\bguia de estudos?\b",
        r"\bconforme\s+apresentado\s+no\s+contexto\s+do\b",
        r"\bcurso\s+especial\s+de\s+habilita[cç][aã]o\b",
        r"\bpromo[cç][aã]o\s+a\s+sargentos\b",
        r"\bciaa-\d+/\d+\b",
        r"\b(?:ema|ciaa)\s*[-/]?\s*\d+(?:\s*[./-]\s*\d+)?\b",
        r"\b(objetivo|finalidade)\s+(central\s+)?d[ao]\s+(publica[cç][aã]o|guia|manual)\b",
        r"\b(introdu[cç][aã]o|pref[aá]cio|sum[aá]rio)\s+d[ao]\s+(publica[cç][aã]o|guia|manual)\b",
        r"\bse\s+classifica\b.*\b(publica[cç][aã]o|manual)\b",
    ]
    _METADATA_RE = re.compile("|".join(_METADATA_PATTERNS), re.IGNORECASE)

    def _is_metadata_noise_line(self, line: str) -> bool:
        txt = str(line or "").strip()
        if not txt:
            return False
        if self._METADATA_RE.search(txt.lower()):
            return True
        has_digits = any(ch.isdigit() for ch in txt)
        alpha_chars = [ch for ch in txt if ch.isalpha()]
        upper_ratio = (sum(1 for ch in alpha_chars if ch.isupper()) / max(1, len(alpha_chars)))
        if len(txt) <= 48 and has_digits and upper_ratio >= 0.55:
            return True
        return False

    def _strip_metadata_noise(self, raw_text: str) -> str:
        text = str(raw_text or "").strip()
        if not text:
            return ""
        kept: List[str] = []
        for ln in text.splitlines():
            if self._is_metadata_noise_line(ln):
                continue
            kept.append(ln.rstrip())
        cleaned = "\n".join(kept).strip()
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned

    def _fold_text(self, value: str) -> str:
        raw = str(value or "")
        normalized = unicodedata.normalize("NFKD", raw)
        without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return without_marks.lower()

    def _is_metadata_question(self, text: str) -> bool:
        t = str(text or "").strip()
        if not t:
            return False
        tf = self._fold_text(t)
        has_regex_metadata = bool(self._METADATA_RE.search(t.lower()))
        has_doc_structure = bool(
            re.search(r"\b(capitulo|secao|anexo)\s*\d+\b", tf)
            or re.search(r"\b(?:ema|ciaa)\s*[-/]?\s*\d+(?:\s*[./-]\s*\d+)?\b", tf)
        )
        has_editorial_terms = any(
            tok in tf
            for tok in (
                "manual",
                "publicacao",
                "guia",
                "sumario",
                "edicao",
                "versao",
                "classificacao",
                "codigo",
                "introducao",
                "prefacio",
            )
        )
        has_course_context = bool(
            re.search(r"\bconforme\s+apresentado\s+no\s+contexto\s+do\b", tf)
            or re.search(r"\bcurso\s+especial\s+de\s+habilitacao\b", tf)
            or re.search(r"\bpromocao\s+a\s+sargentos\b", tf)
        )
        has_compound_metadata = bool(
            re.search(r"\b(objetivo|finalidade)\s+(central\s+)?da?\s+(publicacao|guia|manual)\b", tf)
            or re.search(r"\b(introducao|prefacio|sumario)\s+da?\s+(publicacao|guia|manual)\b", tf)
            or re.search(r"\bde\s+acordo\s+com\s+o?\s*(ema|ciaa)\b", tf)
            or re.search(r"\bse\s+classifica\b.*\b(publicacao|manual)\b", tf)
            or has_course_context
        )
        if not (has_regex_metadata or has_doc_structure or has_editorial_terms or has_course_context):
            return False
        question_like = (
            "?" in t
            or t.rstrip().endswith(":")
            or tf.startswith("qual ")
            or tf.startswith("quem ")
            or tf.startswith("quando ")
            or tf.startswith("como ")
            or tf.startswith("o que ")
            or tf.startswith("por que ")
            or tf.startswith("o objetivo ")
            or tf.startswith("a finalidade ")
        )
        if has_doc_structure:
            return True
        if has_compound_metadata and question_like:
            return True
        if has_editorial_terms and question_like:
            return True
        if has_course_context and question_like:
            return True
        if has_regex_metadata and question_like:
            return True
        return False

    def _is_metadata_flashcard(self, card: Dict[str, str]) -> bool:
        frente = str(card.get("frente") or "").strip()
        verso = str(card.get("verso") or "").strip()
        if self._is_metadata_question(frente):
            return True
        combo = f"{frente}\n{verso}".strip()
        if not combo:
            return False
        cf = self._fold_text(combo)
        if re.search(r"\b(capitulo|secao|anexo)\s*\d+\b", cf):
            return True
        if re.search(r"\b(?:ema|ciaa)-?\d+(?:[./-]\d+)?\b", cf) and any(
            tok in cf for tok in ("manual", "publicacao", "guia", "classificacao", "codigo")
        ):
            return True
        editorial_hits = sum(
            1
            for tok in ("manual", "publicacao", "guia", "sumario", "edicao", "versao", "classificacao", "codigo")
            if tok in cf
        )
        if editorial_hits >= 2 and len(combo) <= 420:
            return True
        return False

    def _select_source_snippets(
        self,
        content: Optional[List[str]],
        topic: Optional[str] = None,
        max_items: int = 4,
        max_chars: int = 6000,
    ) -> str:
        blocos: List[str] = []
        for raw in (content or []):
            txt = self._strip_metadata_noise(raw)
            if txt:
                blocos.append(txt)
        if not blocos:
            return ""

        ordered = list(blocos)
        topic_txt = str(topic or "").strip().lower()
        if topic_txt:
            tokens = [t for t in re.split(r"\W+", topic_txt) if len(t) >= 3]
            if tokens:
                prioritized = [b for b in blocos if any(tok in b.lower() for tok in tokens)]
                if prioritized:
                    remainder = [b for b in blocos if b not in prioritized]
                    ordered = prioritized + remainder

        selected = ordered[: max(1, int(max_items or 1))]
        joined = "\n\n".join(selected)
        return joined[: max(300, int(max_chars or 6000))]

    def _build_quiz_context(self, content: Optional[List[str]], topic: Optional[str]) -> Optional[str]:
        contexto = ""
        if content:
            texto_base = self._select_source_snippets(content, topic=topic, max_items=4, max_chars=6000)
            contexto = f"Baseado no texto:\n{texto_base}\n"
            if topic:
                contexto += f"\nFoque no topico: {topic}."
        elif topic:
            contexto = f"Voce e um professor especialista. Gere questoes tecnicas sobre: '{topic}'."
        return contexto or None

    def _normalize_quiz_batch_payload(self, data: Any, limit: int) -> List[Dict]:
        itens = []
        if isinstance(data, list):
            itens = data
        elif isinstance(data, dict):
            for key in ("questoes", "questions", "itens", "items"):
                payload = data.get(key)
                if isinstance(payload, list):
                    itens = payload
                    break
            if not itens:
                itens = [data]
        result = []
        seen_questions = set()
        seen_stem_token_sets: List[set[str]] = []
        seen_semantic_token_sets: List[set[str]] = []
        answer_counts: Dict[str, int] = {}
        answer_stems: Dict[str, List[set[str]]] = {}
        concept_counts: Dict[str, int] = {}
        numeric_counts: Dict[str, int] = {}
        fact_counts: Dict[str, int] = {}
        template_counts: Dict[str, int] = {}
        topic_bucket_counts: Dict[str, int] = {}
        safe_limit = max(1, int(limit or 1))
        answer_repeat_limit = 1 if safe_limit <= 12 else (2 if safe_limit <= 20 else 3)
        near_duplicate_threshold = 0.68 if safe_limit <= 12 else (0.73 if safe_limit <= 20 else 0.78)
        semantic_duplicate_threshold = 0.56 if safe_limit <= 12 else (0.60 if safe_limit <= 20 else 0.64)
        concept_repeat_limit = 1 if safe_limit <= 10 else (2 if safe_limit <= 20 else max(2, int((safe_limit + 3) // 4)))
        numeric_repeat_limit = 1 if safe_limit <= 20 else 2
        fact_repeat_limit = 1 if safe_limit <= 20 else 2
        template_repeat_limit = 1 if safe_limit <= 12 else (2 if safe_limit <= 20 else 3)
        topic_bucket_repeat_limit = 2 if safe_limit <= 12 else (3 if safe_limit <= 20 else max(3, int((safe_limit + 2) // 4)))

        stopwords = {
            "qual", "quais", "como", "sobre", "acerca", "segundo", "desta", "deste",
            "esta", "este", "essa", "esse", "para", "com", "das", "dos", "uma", "um",
            "que", "onde", "quando", "porque", "por", "pela", "pelo", "nos", "nas",
            "entre", "apos", "antes", "manual", "guia", "publicacao", "capitulo",
            "responda", "assinale", "alternativa", "correta",
            "texto", "material", "documento", "amazonia", "azul", "brasil", "brasileiro",
            "importancia", "impacto", "economica", "economico", "estrategica", "estrategico",
            "afirma", "destaca", "acordo", "regiao",
        }

        def _canonical_token(token: str) -> str:
            tok = str(token or "").strip().lower()
            if not tok:
                return ""
            # Canonicaliza flexoes comuns do portugues para aproximar similaridade semantica.
            for old, new in (
                ("acoes", "acao"),
                ("icoes", "icao"),
                ("coes", "cao"),
                ("oes", "ao"),
                ("ais", "al"),
            ):
                if tok.endswith(old) and len(tok) > len(old) + 2:
                    tok = tok[: -len(old)] + new
                    break
            if tok.endswith("mente") and len(tok) > 8:
                tok = tok[:-5]
            if tok.endswith("s") and len(tok) > 5:
                tok = tok[:-1]
            return tok

        raw_topic_buckets: Dict[str, set[str]] = {
            "economia_comercio": {
                "economia", "economico", "comercio", "exportacao", "importacao", "balanca", "mercado", "logistica",
                "porto", "portuario", "cadeia", "fluxo", "movimentacao", "cabotagem", "receita",
            },
            "soberania_defesa": {
                "soberania", "defesa", "estrategia", "estrategico", "territorio", "fronteira", "militar",
                "seguranca", "patrulha", "marinha", "presenca", "nacional",
            },
            "ambiental_clima": {
                "ambiental", "ambiente", "biodiversidade", "ecossistema", "recife", "manguezal", "clima",
                "sustentavel", "sustentabilidade", "preservacao", "conservacao", "biologico",
            },
            "energia_recursos": {
                "energia", "energetico", "petroleo", "gas", "pre", "sal", "mineral", "minerio",
                "reserva", "exploracao", "extracao", "recurso",
            },
            "juridico_geopolitico": {
                "onu", "cnudm", "zee", "plataforma", "continental", "territorial", "juridico", "direito",
                "norma", "convencao", "reconhecimento", "equatorial",
            },
            "ciencia_sociedade": {
                "pesquisa", "oceanografia", "cientifico", "educacao", "sociedade", "mentalidade", "conscientizacao",
                "cultura", "futuro", "visao", "planejamento",
            },
        }
        topic_bucket_keywords = {
            bucket: {_canonical_token(tok) for tok in terms if _canonical_token(tok)}
            for bucket, terms in raw_topic_buckets.items()
        }

        stopword_roots = {_canonical_token(s) for s in stopwords}
        semantic_noise = stopword_roots | {
            "texto", "material", "documento", "questao", "pergunta", "alternativa",
            "correta", "amazonia", "azul", "brasil", "brasileiro", "regiao",
            "importancia", "impacto", "relevancia", "estrategico", "economico",
            "segundo", "acordo", "afirma", "destaca",
        }

        def _compact_text(value: Any) -> str:
            folded = self._fold_text(str(value or ""))
            folded = "".join(ch if ch.isalnum() else " " for ch in folded)
            return " ".join(folded.split())

        def _question_tokens(question: str) -> set[str]:
            base = _compact_text(question)
            tokens = []
            for tok in base.split():
                root = _canonical_token(tok)
                if len(root) >= 4 and root not in stopword_roots:
                    tokens.append(root)
            if len(tokens) >= 3:
                return set(tokens)
            return {_canonical_token(tok) for tok in base.split() if len(_canonical_token(tok)) >= 3}

        def _answer_signature(quiz: Dict[str, Any]) -> str:
            try:
                opcoes = quiz.get("opcoes") or []
                if not isinstance(opcoes, list) or not opcoes:
                    return ""
                idx = int(quiz.get("correta_index", 0) or 0)
                idx = max(0, min(idx, len(opcoes) - 1))
                ans = _compact_text(opcoes[idx])
                if not ans:
                    return ""
                parts = ans.split()
                if len(parts) >= 2 and parts[0] in {"a", "b", "c", "d"}:
                    ans = " ".join(parts[1:]).strip()
                return ans
            except Exception:
                return ""

        def _answer_tokens(quiz: Dict[str, Any]) -> set[str]:
            ans = _answer_signature(quiz)
            if not ans:
                return set()
            tokens = set()
            for tok in ans.split():
                root = _canonical_token(tok)
                if len(root) >= 4 and root not in stopword_roots:
                    tokens.add(root)
            return tokens

        def _is_near_duplicate(tokens: set[str]) -> bool:
            if len(tokens) < 4:
                return False
            for existing in seen_stem_token_sets:
                union = len(tokens | existing)
                if union == 0:
                    continue
                overlap = len(tokens & existing) / float(union)
                if overlap >= near_duplicate_threshold:
                    return True
            return False

        def _semantic_tokens(quiz: Dict[str, Any]) -> set[str]:
            combined = set(_question_tokens(str(quiz.get("pergunta") or ""))) | _answer_tokens(quiz)
            refined = {tok for tok in combined if len(tok) >= 4 and tok not in semantic_noise}
            return refined or combined

        def _is_semantic_duplicate(tokens: set[str]) -> bool:
            if len(tokens) < 4:
                return False
            for existing in seen_semantic_token_sets:
                union = len(tokens | existing)
                if union == 0:
                    continue
                overlap = len(tokens & existing) / float(union)
                if overlap >= semantic_duplicate_threshold:
                    return True
            return False

        def _concept_signature(tokens: set[str]) -> str:
            if not tokens:
                return ""
            noise = {
                "amazonia", "azul", "brasil", "brasileiro", "texto", "material",
                "documento", "questao", "pergunta", "importancia", "impacto",
                "economica", "economico", "estrategica", "estrategico", "regiao",
            }
            core = [tok for tok in tokens if tok not in noise and len(tok) >= 5]
            if len(core) < 2:
                core = [tok for tok in tokens if len(tok) >= 4]
            if not core:
                return ""
            selected = sorted(core, key=lambda t: (-len(t), t))[:3]
            return "|".join(sorted(selected))

        def _numeric_signature(quiz: Dict[str, Any]) -> str:
            try:
                question = str(quiz.get("pergunta") or "")
                options = quiz.get("opcoes") or []
                options_text = " ".join(str(opt or "") for opt in (options[:4] if isinstance(options, list) else []))
                base = _compact_text(f"{question} {options_text}")
                nums = re.findall(r"\b\d+(?:[\.,]\d+)?\b", base)
                if not nums:
                    return ""
                uniq = sorted(set(nums))
                return "|".join(uniq[:3])
            except Exception:
                return ""

        def _fact_signature(quiz: Dict[str, Any], semantic_tokens: set[str]) -> str:
            try:
                question = str(quiz.get("pergunta") or "")
                options = quiz.get("opcoes") or []
                answer = _answer_signature(quiz)
                options_text = " ".join(str(opt or "") for opt in (options[:4] if isinstance(options, list) else []))
                base = _compact_text(f"{question} {answer} {options_text}")
                nums = sorted(set(re.findall(r"\b\d+(?:[\.,]\d+)?\b", base)))
                anchors = [tok for tok in semantic_tokens if tok not in semantic_noise and len(tok) >= 5]
                if not nums and not anchors:
                    return ""
                anchor_top = sorted(anchors, key=lambda t: (-len(t), t))[:3]
                num_part = "|".join(nums[:2]) if nums else ""
                anchor_part = "|".join(sorted(anchor_top)) if anchor_top else ""
                if num_part and anchor_part:
                    return f"{num_part}::{anchor_part}"
                return num_part or anchor_part
            except Exception:
                return ""

        template_alias = {
            "relevancia": "importancia",
            "impact": "impacto",
            "efeito": "impacto",
            "funcao": "papel",
            "objetivo": "finalidade",
        }
        template_frame_terms = {
            "qual", "como", "porque", "por", "que", "sobre", "segundo", "acordo", "texto",
            "papel", "relacao", "importancia", "impacto", "finalidade", "definicao",
            "composicao", "visao", "cenario", "aplicacao", "consequencia", "causa",
        }

        def _template_signature(question: str) -> str:
            compact = _compact_text(question)
            if not compact:
                return ""
            roots = [_canonical_token(tok) for tok in compact.split()[:16] if _canonical_token(tok)]
            if not roots:
                return ""
            frame: List[str] = []
            for tok in roots:
                canon = template_alias.get(tok, tok)
                if canon in template_frame_terms:
                    if not frame or frame[-1] != canon:
                        frame.append(canon)
                if len(frame) >= 5:
                    break
            if len(frame) >= 3:
                return "|".join(frame[:4])
            core = [template_alias.get(tok, tok) for tok in roots if tok not in stopword_roots and len(tok) >= 4]
            if not core:
                core = [template_alias.get(tok, tok) for tok in roots[:3]]
            return "|".join(core[:3])

        def _topic_bucket_signature(quiz: Dict[str, Any], semantic_tokens: set[str]) -> str:
            tokens = set(semantic_tokens or set())
            assunto = _compact_text(quiz.get("assunto") or quiz.get("subtema") or quiz.get("tema") or "")
            if assunto:
                tokens |= {_canonical_token(tok) for tok in assunto.split() if _canonical_token(tok)}
            if not tokens:
                return ""
            buckets: List[str] = []
            for bucket, words in topic_bucket_keywords.items():
                if tokens & words:
                    buckets.append(bucket)
            if not buckets:
                return ""
            return "|".join(sorted(buckets)[:2])

        for item in itens:
            quiz = self._normalize_quiz(item if isinstance(item, dict) else {})
            if not quiz:
                continue
            key = _compact_text(quiz.get("pergunta", ""))
            if key and key in seen_questions:
                continue
            stem_tokens = _question_tokens(quiz.get("pergunta", ""))
            if stem_tokens and _is_near_duplicate(stem_tokens):
                continue
            semantic_tokens = _semantic_tokens(quiz)
            if semantic_tokens and _is_semantic_duplicate(semantic_tokens):
                continue
            answer_sig = _answer_signature(quiz)
            concept_sig = _concept_signature(set(stem_tokens) | _answer_tokens(quiz))
            numeric_sig = _numeric_signature(quiz)
            fact_sig = _fact_signature(quiz, semantic_tokens)
            template_sig = _template_signature(str(quiz.get("pergunta") or ""))
            topic_bucket_sig = _topic_bucket_signature(quiz, semantic_tokens)
            if answer_sig:
                if answer_counts.get(answer_sig, 0) >= answer_repeat_limit:
                    continue
                if stem_tokens:
                    for prev_tokens in answer_stems.get(answer_sig, []):
                        union = len(stem_tokens | prev_tokens)
                        if union == 0:
                            continue
                        overlap = len(stem_tokens & prev_tokens) / float(union)
                        if overlap >= 0.34:
                            stem_tokens = set()
                            break
                    if not stem_tokens:
                        continue
            if concept_sig and concept_counts.get(concept_sig, 0) >= concept_repeat_limit:
                continue
            if numeric_sig and numeric_counts.get(numeric_sig, 0) >= numeric_repeat_limit:
                continue
            if fact_sig and fact_counts.get(fact_sig, 0) >= fact_repeat_limit:
                continue
            if template_sig and template_counts.get(template_sig, 0) >= template_repeat_limit:
                continue
            if topic_bucket_sig and topic_bucket_counts.get(topic_bucket_sig, 0) >= topic_bucket_repeat_limit:
                continue
            if key:
                seen_questions.add(key)
            if stem_tokens:
                seen_stem_token_sets.append(stem_tokens)
            if semantic_tokens:
                seen_semantic_token_sets.append(semantic_tokens)
            if answer_sig:
                answer_counts[answer_sig] = answer_counts.get(answer_sig, 0) + 1
                if stem_tokens:
                    answer_stems.setdefault(answer_sig, []).append(set(stem_tokens))
            if concept_sig:
                concept_counts[concept_sig] = concept_counts.get(concept_sig, 0) + 1
            if numeric_sig:
                numeric_counts[numeric_sig] = numeric_counts.get(numeric_sig, 0) + 1
            if fact_sig:
                fact_counts[fact_sig] = fact_counts.get(fact_sig, 0) + 1
            if template_sig:
                template_counts[template_sig] = template_counts.get(template_sig, 0) + 1
            if topic_bucket_sig:
                topic_bucket_counts[topic_bucket_sig] = topic_bucket_counts.get(topic_bucket_sig, 0) + 1
            result.append(quiz)
            if len(result) >= safe_limit:
                break
        return result

    def generate_quiz_batch(
        self,
        content: Optional[List[str]] = None,
        topic: Optional[str] = None,
        difficulty: str = "Medio",
        quantity: int = 3,
        retries: int = 2,
        avoid_questions: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Gera varias questoes em uma unica chamada para reduzir latencia/custo.
        """
        quantidade = max(1, min(10, int(quantity or 1)))
        tentativas = max(1, int(retries or 1))
        contexto = self._build_quiz_context(content, topic)
        if not contexto:
            print("[AI] Sem conteudo ou topico")
            return []

        avoid_block = ""
        if isinstance(avoid_questions, list):
            itens_bloqueio: List[str] = []
            for q in avoid_questions:
                txt = " ".join(str(q or "").split()).strip()
                if txt:
                    itens_bloqueio.append(txt[:180])
                if len(itens_bloqueio) >= 20:
                    break
            if itens_bloqueio:
                avoid_block = "HISTORICO — nao recrie nem parafraseie estas perguntas:\n"
                avoid_block += "\n".join(f"- {item}" for item in itens_bloqueio)
                avoid_block += "\n"

        # Instrucao de profundidade por nivel
        _nivel_map = {
            "facil":         "FACIL: conceito central direto; distratores erram um detalhe concreto.",
            "medio":         "INTERMEDIARIO: exija relacao causa-efeito ou aplicacao do conceito; distratores invertem a logica.",
            "intermediario": "INTERMEDIARIO: exija relacao causa-efeito ou aplicacao do conceito; distratores invertem a logica.",
            "dificil":       "DIFICIL: questao-problema com raciocinio de multiplas etapas; distratores sao conclusoes parcialmente corretas.",
        }
        nivel_instrucao = _nivel_map.get(str(difficulty or "").lower(), _nivel_map["intermediario"])

        # Sequencia sugerida de correta_index para evitar vies posicional
        indices_seq = ", ".join(str(i % 4) for i in range(quantidade))

        prompt = f"""Voce e um elaborador senior de questoes para concursos publicos brasileiros de alto nivel (CESPE, FCC, VUNESP).

{contexto}
{avoid_block}
Nivel: {nivel_instrucao}
Gere EXATAMENTE {quantidade} questao(oes) novas.

REGRAS OBRIGATORIAS:
1. Use exclusivamente o conteudo do material acima. Nunca invente fatos externos.
2. Perguntas autonomas: proibido usar "segundo o texto", "conforme o trecho" ou similar.
3. Proibido decoreba ("O que e X?"). Exija raciocinio, comparacao ou aplicacao.
4. Ignore metadados do material (autor, ISBN, editora, edicao, datas, sumario, codigos de curso).
5. Cada distrator deve usar conceito real do material, mas aplicado no contexto errado.
6. Varie os valores de correta_index — sequencia sugerida: [{indices_seq}].
7. Se nao houver base suficiente no texto, retorne [].

LIMITES DE CARACTERES (ultrapassar causa descarte):
- "pergunta"   : max 280 chars
- cada "opcoes": max 90 chars, SEM prefixos "A)" "B)" etc.
- "explicacao" : max 190 chars

Retorne APENAS JSON valido, sem markdown, sem texto antes ou depois:
[
  {{
    "pergunta": "Enunciado tecnico e direto",
    "subtema": "Subtema curto",
    "opcoes": ["Opcao correta", "Distrator 1", "Distrator 2", "Distrator 3"],
    "correta_index": 0,
    "explicacao": "Razao objetiva da resposta correta."
  }}
]
"""

        for attempt in range(tentativas):
            try:
                text = self._call_provider_text(prompt, "quiz_batch")
                if not text:
                    if self._should_abort_retry():
                        break
                    continue

                data = self.provider.extract_json_list(text)
                if data is None:
                    data = self.provider.extract_json_object(text)

                normalizadas = self._normalize_quiz_batch_payload(data, quantidade)
                normalizadas = [q for q in normalizadas if not self._is_metadata_question(str(q.get("pergunta") or ""))]
                normalizadas = [q for q in normalizadas if self.validate_task_payload("quiz", q)[0]]
                if normalizadas:
                    print(f"[AI] [OK] {len(normalizadas)} questoes geradas em lote")
                    return normalizadas

                print(f"[AI] Tentativa {attempt + 1}: lote invalido")
            except Exception as e:
                print(f"[AI] Tentativa {attempt + 1} erro em lote: {e}")
                if self._should_abort_retry():
                    break

            if attempt < tentativas - 1:
                time.sleep(0.35)

        print("[AI] [ERRO] Falha ao gerar lote de questoes")
        return []
    
    def generate_quiz(
        self,
        content: Optional[List[str]] = None,
        topic: Optional[str] = None,
        difficulty: str = "Medio",
        retries: int = 2,
        avoid_questions: Optional[List[str]] = None,
    ) -> Optional[Dict]:
        """
        Gera uma questÃ£o de mÃºltipla escolha
        
        Args:
            content: Lista de textos (do PDF)
            topic: TÃ³pico especÃ­fico
            difficulty: Dificuldade
            retries: Tentativas
        
        Returns:
            Dict com pergunta, opÃ§Ãµes, resposta correta e explicaÃ§Ã£o
        """
        lote = self.generate_quiz_batch(
            content=content,
            topic=topic,
            difficulty=difficulty,
            quantity=1,
            retries=retries,
            avoid_questions=avoid_questions,
        )
        if lote:
            return lote[0]
        print("[AI] [ERRO] Falha ao gerar quiz apos todas as tentativas")
        return None

    def _normalize_flashcard(self, item: Dict) -> Optional[Dict]:
        if not isinstance(item, dict):
            return None
        frente = (
            item.get("frente")
            or item.get("front")
            or item.get("pergunta")
            or item.get("question")
            or item.get("titulo")
            or ""
        )
        verso = (
            item.get("verso")
            or item.get("back")
            or item.get("resposta")
            or item.get("answer")
            or item.get("explicacao")
            or ""
        )
        frente = str(frente).strip()
        verso = str(verso).strip()
        if not frente or not verso:
            return None
        return {"frente": frente, "verso": verso}

    def generate_flashcards(
        self,
        content: List[str],
        quantity: int = 5,
        retries: int = 2
    ) -> List[Dict]:
        """
        Gera flashcards
        
        Args:
            content: Textos do PDF
            quantity: Quantidade de flashcards
            retries: Tentativas
        
        Returns:
            Lista de dicts com 'frente' e 'verso'
        """
        if not content:
            return []

        quantidade = max(1, min(20, int(quantity or 5)))
        tentativas = max(1, int(retries or 1))
        texto_amostra = self._select_source_snippets(content, topic=None, max_items=4, max_chars=6000)

        prompt = f"""
Gere {quantidade} flashcards do texto abaixo.

REGRAS DE FOCO:
- Use estritamente o conteudo do texto abaixo.
- Nao invente topicos fora do material.
- Se o texto nao trouxer base suficiente, retorne [].
- Nao gere flashcards sobre metadados do documento (autor, elaborador, edicao, capa, codigo de guia).
- Nao gere flashcards sobre estrutura editorial (capitulo, secao, anexo, classificacao/publicacao/manual, codigos como EMA/CIAA).

IMPORTANTE: Responda APENAS com JSON vÃ¡lido, sem texto adicional.

Formato JSON obrigatÃ³rio:
[
  {{"frente": "Pergunta ou conceito...", "verso": "Resposta ou explicaÃ§Ã£o..."}},
  {{"frente": "...", "verso": "..."}}
]

Texto:
{texto_amostra}
"""

        for attempt in range(tentativas):
            try:
                text = self._call_provider_text(prompt, "flashcards")
                if not text:
                    if self._should_abort_retry():
                        break
                    continue

                data = self.provider.extract_json_list(text)
                if data is None:
                    data = self.provider.extract_json_object(text)
                    if isinstance(data, dict):
                        for key in ("flashcards", "cards", "itens", "items"):
                            maybe_list = data.get(key)
                            if isinstance(maybe_list, list):
                                data = maybe_list
                                break
                if isinstance(data, list) and len(data) > 0:
                    cards = []
                    seen = set()
                    for item in data:
                        card = self._normalize_flashcard(item if isinstance(item, dict) else {})
                        if not card:
                            continue
                        if self._is_metadata_flashcard(card):
                            continue
                        if not self.validate_task_payload("flashcard", card)[0]:
                            continue
                        key = card["frente"].lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        cards.append(card)
                        if len(cards) >= quantidade:
                            break
                    if cards:
                        print(f"[AI] [OK] {len(cards)} flashcards gerados")
                        return cards

                print(f"[AI] Tentativa {attempt + 1}: Lista JSON invalida")

            except Exception as e:
                print(f"[AI] Tentativa {attempt + 1} erro: {e}")

                if self._should_abort_retry():
                    break
            if attempt < tentativas - 1:
                time.sleep(0.35)

        print("[AI] [ERRO] Falha ao gerar flashcards")
        return []
    
    def generate_open_question(
        self,
        content: List[str],
        topic: Optional[str] = None,
        source_lock: bool = False,
        difficulty: str = "Médio",
        retries: int = 2
    ) -> Optional[Dict]:
        """
        Gera pergunta dissertativa
        
        Returns:
            Dict com 'pergunta' e 'resposta_esperada'
        """
        if not content:
            return None

        # Remove linhas de controle para nao poluir o contexto real.
        cleaned_blocks: List[str] = []
        for raw in (content or []):
            txt = str(raw or "").strip()
            if not txt:
                continue
            lower = txt.lower()
            if lower.startswith("instrucao de foco:") or lower.startswith("instrução de foco:"):
                continue
            if lower.startswith("tema central:"):
                continue
            cleaned_blocks.append(txt)

        texto_amostra = self._select_source_snippets(cleaned_blocks, topic=topic, max_items=5, max_chars=9000)
        if not texto_amostra:
            if source_lock:
                return None
            texto_amostra = self._select_source_snippets(content, topic=topic, max_items=3, max_chars=5000)
        if not texto_amostra:
            return None

        tema_hint = str(topic or "").strip()
        tema_bloco = f"\nTema declarado pelo usuario: {tema_hint}\n" if tema_hint else ""

        prompt = f"""
Crie 1 pergunta dissertativa de nível {difficulty}, em português brasileiro.

REGRAS:
- Use ortografia correta com acentuação e cedilha.
- Mantenha o texto natural e claro para estudantes brasileiros.
- Baseie-se no texto fornecido, sem inventar fatos fora da referência.
- Use o material anexado como fonte principal e obrigatória.
- Nao gere pergunta sobre metadados/estrutura editorial do documento (autor, edicao, capitulo, sumario, codigo de manual/publicacao).
- A pergunta deve cobrar conteudo conceitual do tema, nao informacoes administrativas do arquivo.

IMPORTANTE: Responda APENAS com JSON válido, sem texto adicional.

Formato JSON obrigatório:
{{
  "pergunta": "Pergunta dissertativa...",
  "resposta_esperada": "Resposta modelo esperada..."
}}
{tema_bloco}

Texto:
{texto_amostra}
"""
        
        tentativas = max(1, int(retries or 1))
        for attempt in range(tentativas):
            try:
                text = self._call_provider_text(prompt, "open_question")
                if not text:
                    if self._should_abort_retry():
                        break
                    continue
                
                data = self.provider.extract_json_object(text)
                if data and "pergunta" in data:
                    try:
                        data["pergunta"] = str(data.get("pergunta") or "").strip()
                        data["resposta_esperada"] = str(
                            data.get("resposta_esperada")
                            or data.get("gabarito")
                            or data.get("resposta")
                            or ""
                        ).strip()
                        if not data["pergunta"]:
                            raise ValueError("pergunta_vazia")
                    except Exception:
                        print(f"[AI] Tentativa {attempt + 1}: payload aberto invalido")
                        continue
                    print("[AI] [OK] Pergunta aberta gerada")
                    return data
                
                print(f"[AI] Tentativa {attempt + 1}: JSON invÃ¡lido")
                
            except Exception as e:
                print(f"[AI] Tentativa {attempt + 1} erro: {e}")
                if self._should_abort_retry():
                    break
            
            if attempt < tentativas - 1:
                time.sleep(0.35)
        
        print("[AI] [ERRO] Falha ao gerar pergunta aberta")
        return None

    _GRADE_STOPWORDS_PT = {
        "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas",
        "um", "uma", "uns", "umas", "por", "para", "com", "sem", "que", "se", "ao", "aos", "à", "às",
        "como", "sobre", "entre", "mais", "menos", "muito", "muita", "sua", "seu", "suas", "seus",
        "ser", "estar", "ter", "foi", "são", "sao", "é", "eh", "ou", "também", "tambem",
    }

    def _grade_tokens(self, text: str, max_items: int = 300) -> List[str]:
        folded = self._fold_text(str(text or ""))
        parts = re.split(r"[^a-z0-9]+", folded)
        out: List[str] = []
        for p in parts:
            tok = str(p or "").strip()
            if len(tok) < 3:
                continue
            if tok in self._GRADE_STOPWORDS_PT:
                continue
            out.append(tok)
            if len(out) >= max_items:
                break
        return out

    def _token_overlap_score(self, a: str, b: str) -> float:
        ta = set(self._grade_tokens(a))
        tb = set(self._grade_tokens(b))
        if not ta or not tb:
            return 0.0
        inter = len(ta.intersection(tb))
        base = min(len(ta), len(tb))
        if base <= 0:
            return 0.0
        return max(0.0, min(1.0, inter / float(base)))

    def _local_open_grade(self, question: str, student_answer: str, expected_answer: str) -> Dict[str, Any]:
        answer_txt = str(student_answer or "").strip()
        words = [w for w in re.split(r"\s+", answer_txt) if w]
        word_count = len(words)
        q_overlap = self._token_overlap_score(answer_txt, question)
        e_overlap = self._token_overlap_score(answer_txt, expected_answer)
        overall_overlap = (q_overlap * 0.45) + (e_overlap * 0.55)

        length_score = min(100.0, (word_count / 120.0) * 100.0)
        if word_count < 25:
            length_score = max(10.0, length_score * 0.55)
        paragraph_count = max(1, len([p for p in answer_txt.splitlines() if p.strip()]))
        sentence_parts = [s.strip() for s in re.split(r"[.!?;]+", answer_txt) if s.strip()]
        sentence_count = max(1, len(sentence_parts))
        punct_hits = sum(answer_txt.count(ch) for ch in (".", ",", ";", ":"))
        structure_score = min(100.0, 30.0 + (paragraph_count * 10.0) + (sentence_count * 4.0) + min(20.0, punct_hits * 1.5))

        avg_sentence_words = word_count / float(sentence_count or 1)
        clarity_penalty = 0.0
        if avg_sentence_words > 34:
            clarity_penalty += min(25.0, (avg_sentence_words - 34.0) * 1.2)
        if avg_sentence_words < 6:
            clarity_penalty += 10.0
        clarity_score = max(0.0, min(100.0, structure_score - clarity_penalty + 8.0))

        fundamentacao_score = max(0.0, min(100.0, (overall_overlap * 100.0) * 0.75 + (length_score * 0.25)))
        aderencia_score = max(0.0, min(100.0, overall_overlap * 100.0))
        estrutura_score = max(0.0, min(100.0, structure_score))
        clareza_score = max(0.0, min(100.0, clarity_score))

        weighted = (
            aderencia_score * 0.35
            + estrutura_score * 0.20
            + clareza_score * 0.20
            + fundamentacao_score * 0.25
        )
        nota_local = int(round(max(0.0, min(100.0, weighted))))
        return {
            "nota_local": nota_local,
            "criterios": {
                "aderencia": int(round(aderencia_score)),
                "estrutura": int(round(estrutura_score)),
                "clareza": int(round(clareza_score)),
                "fundamentacao": int(round(fundamentacao_score)),
            },
            "word_count": word_count,
        }

    def _normalize_open_grade_payload(
        self,
        data: Dict[str, Any],
        question: str,
        student_answer: str,
        expected_answer: str,
    ) -> Dict[str, Any]:
        local = self._local_open_grade(question, student_answer, expected_answer)
        nota_local = int(local.get("nota_local") or 0)
        try:
            ai_nota = int(data.get("nota", 0))
        except Exception:
            ai_nota = nota_local
        ai_nota = max(0, min(ai_nota, 100))

        # Reduz variacao extrema entre correcoes parecidas.
        delta = abs(ai_nota - nota_local)
        if delta > 30:
            nota_final = int(round((ai_nota * 0.35) + (nota_local * 0.65)))
        else:
            nota_final = int(round((ai_nota * 0.55) + (nota_local * 0.45)))
        nota_final = max(0, min(100, nota_final))

        criterios_ai = data.get("criterios") if isinstance(data.get("criterios"), dict) else {}
        criterios = {
            "aderencia": int(max(0, min(100, criterios_ai.get("aderencia", local["criterios"]["aderencia"])))),
            "estrutura": int(max(0, min(100, criterios_ai.get("estrutura", local["criterios"]["estrutura"])))),
            "clareza": int(max(0, min(100, criterios_ai.get("clareza", local["criterios"]["clareza"])))),
            "fundamentacao": int(max(0, min(100, criterios_ai.get("fundamentacao", local["criterios"]["fundamentacao"])))),
        }

        def _to_lines(value: Any, limit: int = 3) -> List[str]:
            if isinstance(value, list):
                lines = [str(x).strip() for x in value if str(x).strip()]
            else:
                raw = str(value or "")
                lines = [p.strip(" -•\t") for p in re.split(r"[\n;]+", raw) if p.strip(" -•\t")]
            return lines[: max(1, int(limit or 1))]

        feedback_txt = str(data.get("feedback") or "").strip()
        if not feedback_txt:
            feedback_txt = (
                "Resposta avaliada pelos criterios de aderencia, estrutura, clareza e fundamentacao. "
                "Revise pontos de melhoria para elevar a nota."
            )

        out = {
            "nota": nota_final,
            "correto": bool(nota_final >= 70),
            "feedback": feedback_txt,
            "criterios": criterios,
            "pontos_fortes": _to_lines(data.get("pontos_fortes"), limit=3),
            "pontos_melhorar": _to_lines(data.get("pontos_melhorar"), limit=3),
        }
        return out
    
    def grade_open_answer(
        self,
        question: str,
        student_answer: str,
        expected_answer: str,
        retries: int = 2
    ) -> Dict:
        """
        Corrige resposta dissertativa
        
        Returns:
            Dict com 'nota', 'correto' e 'feedback'
        """
        prompt = f"""
Avalie a resposta do aluno com base na pergunta e no contexto esperado.

Pergunta: {question}

Gabarito: {expected_answer}

Resposta do aluno: {student_answer}

REGRAS DE AVALIACAO:
- Nao exija copia literal do gabarito; aceite formulacoes proprias com sentido correto.
- Avalie pelos criterios: aderencia ao tema, estrutura, clareza e fundamentacao.
- Penalize fuga de tema, incoerencia ou resposta muito superficial.
- Evite notas extremas sem justificativa clara.

IMPORTANTE: Responda APENAS com JSON vÃ¡lido, sem texto adicional.

Formato JSON obrigatÃ³rio:
{{
  "nota": 85,
  "correto": true,
  "criterios": {{
    "aderencia": 80,
    "estrutura": 75,
    "clareza": 78,
    "fundamentacao": 72
  }},
  "pontos_fortes": ["...", "..."],
  "pontos_melhorar": ["...", "..."],
  "feedback": "Feedback detalhado sobre a resposta..."
}}

Nota de 0 a 100. Considere correto se nota >= 70.
"""
        
        tentativas = max(1, int(retries or 1))
        for attempt in range(tentativas):
            try:
                text = self._call_provider_text(prompt, "grade_open_answer")
                if not text:
                    if self._should_abort_retry():
                        break
                    continue
                
                data = self.provider.extract_json_object(text)
                if data and "nota" in data:
                    normalized = self._normalize_open_grade_payload(data, question, student_answer, expected_answer)
                    print(f"[AI] [OK] Resposta corrigida: {normalized.get('nota')}")
                    return normalized
                
                print(f"[AI] Tentativa {attempt + 1}: JSON invÃ¡lido")
                
            except Exception as e:
                print(f"[AI] Tentativa {attempt + 1} erro: {e}")
                if self._should_abort_retry():
                    break
            
            if attempt < tentativas - 1:
                time.sleep(0.35)
        
        print("[AI] âŒ Falha ao corrigir resposta")
        local = self._local_open_grade(question, student_answer, expected_answer)
        nota = int(local.get("nota_local") or 0)
        return {
            "nota": nota,
            "correto": bool(nota >= 70),
            "criterios": dict(local.get("criterios") or {}),
            "pontos_fortes": [],
            "pontos_melhorar": ["Refine a estrutura e aprofunde os argumentos com exemplos."],
            "feedback": "Correcao local aplicada por indisponibilidade temporaria da IA.",
        }

    def explain_simple(
        self,
        question: str,
        answer: str,
        retries: int = 2
    ) -> str:
        """
        Explica a questao de forma simples ("explain like I'm 5").
        """
        prompt = f"""
Voce e um professor experiente e didatico.
Explique o conceito por tras desta questao e por que a resposta e essa, de forma extremamente simples e direta.
Use analogias se possivel. Maximo de 3 paragrafos curtos.

Questao: {question}
Resposta Correta: {answer}

Explique para um estudante iniciante:
"""
        tentativas = max(1, int(retries or 1))
        for attempt in range(tentativas):
            try:
                text = self._call_provider_text(prompt, "explain_simple")
                if text:
                    return text.strip()
            except Exception as e:
                print(f"[AI] Tentativa {attempt + 1} erro: {e}")
                if self._should_abort_retry():
                    break
            if attempt < tentativas - 1:
                time.sleep(0.35)
        
        return "Nao foi possivel gerar uma explicacao simplificada no momento."

    def generate_study_plan(
        self,
        objetivo: str,
        data_prova: str,
        tempo_diario_min: int,
        topicos_prioritarios: Optional[List[str]] = None,
        retries: int = 2,
    ) -> List[Dict]:
        topicos = topicos_prioritarios or ["Geral"]
        prompt = f"""
Crie um plano de estudo de 7 dias em JSON.

Objetivo: {objetivo}
Data da prova: {data_prova}
Tempo diario (min): {tempo_diario_min}
Topicos prioritarios: {", ".join(topicos)}

Retorne APENAS JSON no formato:
[
  {{
    "dia": "Seg",
    "tema": "Tema principal",
    "atividade": "Questoes + revisao de erros",
    "duracao_min": 90,
    "prioridade": 1
  }}
]
"""
        tentativas = max(1, int(retries or 1))
        for attempt in range(tentativas):
            try:
                text = self._call_provider_text(prompt, "study_plan")
                if not text:
                    if self._should_abort_retry():
                        break
                    continue
                data = self.provider.extract_json_list(text)
                if isinstance(data, list) and data:
                    result = []
                    for item in data[:7]:
                        if not isinstance(item, dict):
                            continue
                        row = {
                            "dia": str(item.get("dia") or "Dia"),
                            "tema": str(item.get("tema") or "Geral"),
                            "atividade": str(item.get("atividade") or "Resolver questoes"),
                            "duracao_min": int(item.get("duracao_min") or tempo_diario_min),
                            "prioridade": int(item.get("prioridade") or 1),
                        }
                        if not self.validate_task_payload("study_plan_item", row)[0]:
                            continue
                        result.append(row)
                    if result:
                        return result
            except Exception:
                if self._should_abort_retry():
                    break
            if attempt < tentativas - 1:
                time.sleep(0.35)

        # Fallback deterministico
        dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
        fallback = []
        for i, d in enumerate(dias):
            tema = topicos[i % len(topicos)]
            fallback.append(
                {
                    "dia": d,
                    "tema": tema,
                    "atividade": "Questoes (60%) + flashcards (20%) + revisao de erros (20%)",
                    "duracao_min": tempo_diario_min,
                    "prioridade": 1 if i < 3 else 2,
                }
            )
        return fallback

    def generate_study_summary(
        self,
        content: List[str],
        topic: str = "",
        retries: int = 2,
    ) -> Dict:
        def _clean_text(value: Any, max_len: int = 280) -> str:
            text = re.sub(r"\s+", " ", str(value or "")).strip()
            if not text:
                return ""
            return text[:max_len]

        def _as_str_list(value: Any, max_items: int = 8, max_len: int = 180) -> List[str]:
            if not isinstance(value, list):
                return []
            out: List[str] = []
            seen = set()
            for item in value:
                text = _clean_text(item, max_len=max_len)
                if not text:
                    continue
                key = text.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(text)
                if len(out) >= max_items:
                    break
            return out

        def _as_definition_list(value: Any, max_items: int = 8) -> List[Dict]:
            if not isinstance(value, list):
                return []
            out: List[Dict] = []
            for item in value:
                if isinstance(item, dict):
                    termo = _clean_text(item.get("termo") or item.get("conceito") or item.get("titulo"), 90)
                    definicao = _clean_text(item.get("definicao") or item.get("descricao") or item.get("explicacao"), 240)
                else:
                    raw = _clean_text(item, 260)
                    if ":" in raw:
                        left, right = raw.split(":", 1)
                        termo = _clean_text(left, 90)
                        definicao = _clean_text(right, 240)
                    else:
                        termo = ""
                        definicao = raw
                if termo and definicao:
                    out.append({"termo": termo, "definicao": definicao})
                elif definicao:
                    out.append({"termo": "Conceito", "definicao": definicao})
                if len(out) >= max_items:
                    break
            return out

        def _normalize_dificuldade(value: Any) -> str:
            raw = _clean_text(value, 24).lower()
            if ("facil" in raw) or ("fácil" in raw) or ("easy" in raw):
                return "facil"
            if ("dificil" in raw) or ("difícil" in raw) or ("hard" in raw):
                return "dificil"
            return "medio"

        def _normalize_tags(value: Any, max_items: int = 6) -> List[str]:
            if isinstance(value, str):
                parts = [x.strip() for x in re.split(r"[;,|]", value) if x.strip()]
                return _as_str_list(parts, max_items=max_items, max_len=36)
            return _as_str_list(value, max_items=max_items, max_len=36)

        def _as_flashcard_suggestions(value: Any, max_items: int = 10) -> List[Dict]:
            if not isinstance(value, list):
                return []
            out: List[Dict] = []
            seen = set()
            for item in value:
                if isinstance(item, dict):
                    frente = _clean_text(item.get("frente") or item.get("front") or item.get("pergunta"), 140)
                    verso = _clean_text(item.get("verso") or item.get("back") or item.get("resposta"), 240)
                    tags = _normalize_tags(item.get("tags"))
                    dificuldade = _normalize_dificuldade(item.get("dificuldade"))
                else:
                    raw = _clean_text(item, 320)
                    if "->" in raw:
                        left, right = raw.split("->", 1)
                    elif ":" in raw:
                        left, right = raw.split(":", 1)
                    else:
                        left, right = raw, ""
                    frente = _clean_text(left, 140)
                    verso = _clean_text(right, 240)
                    tags = []
                    dificuldade = "medio"
                if not frente:
                    continue
                if not verso:
                    verso = "Explique o conceito com suas palavras."
                key = frente.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append({"frente": frente, "verso": verso, "tags": tags, "dificuldade": dificuldade})
                if len(out) >= max_items:
                    break
            return out

        def _as_question_suggestions(value: Any, max_items: int = 8) -> List[Dict]:
            if not isinstance(value, list):
                return []
            out: List[Dict] = []
            seen = set()
            for item in value:
                if isinstance(item, dict):
                    enunciado = _clean_text(item.get("enunciado") or item.get("pergunta") or item.get("question"), 220)
                    alternativas_raw = item.get("alternativas") or item.get("opcoes") or item.get("options") or []
                    if isinstance(alternativas_raw, str):
                        alternativas_raw = [x.strip() for x in re.split(r"\n|;", alternativas_raw) if x.strip()]
                    alternativas = _as_str_list(alternativas_raw, max_items=5, max_len=140)
                    if len(alternativas) < 2:
                        alternativas = [
                            "Alternativa A",
                            "Alternativa B",
                            "Alternativa C",
                            "Alternativa D",
                        ]
                    gabarito_raw = item.get("gabarito")
                    if gabarito_raw is None:
                        gabarito_raw = item.get("correta_index", item.get("indice_correto", 0))
                    if isinstance(gabarito_raw, str):
                        gr = gabarito_raw.strip().upper()
                        if gr in {"A", "B", "C", "D", "E"}:
                            gabarito = ["A", "B", "C", "D", "E"].index(gr)
                        else:
                            try:
                                gabarito = int(gr)
                            except Exception:
                                gabarito = 0
                    else:
                        try:
                            gabarito = int(gabarito_raw)
                        except Exception:
                            gabarito = 0
                    gabarito = max(0, min(gabarito, len(alternativas) - 1))
                    explicacao = _clean_text(item.get("explicacao") or item.get("resposta_curta") or item.get("feedback"), 240)
                    tags = _normalize_tags(item.get("tags"))
                    dificuldade = _normalize_dificuldade(item.get("dificuldade"))
                else:
                    raw = _clean_text(item, 320)
                    if "?" in raw:
                        enunciado = _clean_text(raw if raw.endswith("?") else raw.split("?")[0] + "?", 220)
                    else:
                        enunciado = _clean_text(raw, 220)
                    alternativas = [
                        "Alternativa A",
                        "Alternativa B",
                        "Alternativa C",
                        "Alternativa D",
                    ]
                    gabarito = 0
                    explicacao = ""
                    tags = []
                    dificuldade = "medio"
                if not enunciado:
                    continue
                key = enunciado.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    {
                        "enunciado": enunciado,
                        "alternativas": alternativas,
                        "gabarito": gabarito,
                        "explicacao": explicacao or "Use os pontos-chave do resumo para justificar a resposta correta.",
                        "tags": tags,
                        "dificuldade": dificuldade,
                    }
                )
                if len(out) >= max_items:
                    break
            return out

        def _normalize_summary_payload(data: Dict) -> Dict:
            titulo = _clean_text(data.get("titulo") or topic or "Resumo de estudo", 120)
            resumo_curto = _clean_text(data.get("resumo_curto") or data.get("resumo"), 520)
            resumo_estruturado = data.get("resumo_estruturado")
            if isinstance(resumo_estruturado, str):
                resumo_estruturado = [x.strip(" -") for x in resumo_estruturado.splitlines() if x.strip()]
            resumo_estruturado = _as_str_list(resumo_estruturado, max_items=10, max_len=220)
            topicos_principais = _as_str_list(data.get("topicos_principais") or data.get("topicos"), max_items=10, max_len=120)
            definicoes = _as_definition_list(data.get("definicoes"), max_items=8)
            exemplos = _as_str_list(data.get("exemplos"), max_items=8, max_len=220)
            pegadinhas = _as_str_list(data.get("pegadinhas"), max_items=8, max_len=220)
            checklist = _as_str_list(data.get("checklist_de_estudo"), max_items=10, max_len=180)
            sugestoes_flash = _as_flashcard_suggestions(data.get("sugestoes_flashcards"), max_items=10)
            sugestoes_q = _as_question_suggestions(data.get("sugestoes_questoes"), max_items=8)

            if not resumo_curto and resumo_estruturado:
                resumo_curto = " ".join(resumo_estruturado[:3])[:520]
            if not resumo_curto:
                resumo_curto = "Resumo indisponivel no momento."
            if not topicos_principais and definicoes:
                topicos_principais = [d.get("termo", "") for d in definicoes if d.get("termo")]
            if not topicos_principais:
                topicos_principais = ["Visao geral do material"]
            if not checklist:
                checklist = [
                    "Leia o resumo curto e marque duvidas",
                    "Resolva 5 questoes sobre os topicos principais",
                    "Revise os erros no mesmo dia",
                ]
            if not sugestoes_flash and topicos_principais:
                sugestoes_flash = [
                    {
                        "frente": f"O que e {topicos_principais[0]}?",
                        "verso": "Defina com suas palavras e cite um exemplo pratico.",
                        "tags": [topicos_principais[0]],
                        "dificuldade": "medio",
                    }
                ]
            if not sugestoes_q and topicos_principais:
                sugestoes_q = [
                    {
                        "enunciado": f"Qual alternativa melhor descreve {topicos_principais[0]}?",
                        "alternativas": [
                            "Definicao central do topico",
                            "Exemplo desconectado do tema",
                            "Opiniao sem relacao tecnica",
                            "Descricao incorreta do conceito",
                        ],
                        "gabarito": 0,
                        "explicacao": "A alternativa correta apresenta a definicao central do topico estudado.",
                        "tags": [topicos_principais[0]],
                        "dificuldade": "medio",
                    }
                ]

            return {
                "titulo": titulo,
                "resumo_curto": resumo_curto,
                "resumo_estruturado": resumo_estruturado,
                "topicos_principais": topicos_principais,
                "definicoes": definicoes,
                "exemplos": exemplos,
                "pegadinhas": pegadinhas,
                "checklist_de_estudo": checklist,
                "sugestoes_flashcards": sugestoes_flash,
                "sugestoes_questoes": sugestoes_q,
                # Compatibilidade com payload legado
                "resumo": resumo_curto,
                "topicos": topicos_principais,
            }

        if not content:
            return _normalize_summary_payload({})

        texto = "\n".join(content[:8])[:9000]
        prompt = f"""
Voce e um mentor de estudo para concursos e certificacoes tecnicas.
Gere um resumo acionavel em JSON.

Topico opcional: {topic}

Retorne APENAS JSON com este schema:
{{
  "titulo": "Titulo curto do material",
  "resumo_curto": "Resumo objetivo em ate 6 linhas",
  "resumo_estruturado": ["Item 1", "Item 2"],
  "topicos_principais": ["Topico 1", "Topico 2"],
  "definicoes": [{{"termo": "Termo", "definicao": "Definicao curta"}}],
  "exemplos": ["Exemplo pratico 1"],
  "pegadinhas": ["Erro comum 1"],
  "checklist_de_estudo": ["Acao 1", "Acao 2"],
  "sugestoes_flashcards": [{{"frente": "Pergunta", "verso": "Resposta", "tags": ["tag1"], "dificuldade": "medio"}}],
  "sugestoes_questoes": [{{"enunciado": "Pergunta objetiva", "alternativas": ["A", "B", "C", "D"], "gabarito": 0, "explicacao": "Motivo", "tags": ["tag1"], "dificuldade": "medio"}}]
}}

Material:
{texto}
"""
        tentativas = max(1, int(retries or 1))
        for attempt in range(tentativas):
            try:
                text = self._call_provider_text(prompt, "study_summary")
                if not text:
                    if self._should_abort_retry():
                        break
                    continue
                data = self.provider.extract_json_object(text)
                if isinstance(data, dict):
                    normalized = _normalize_summary_payload(data)
                    if normalized.get("resumo_curto") and self.validate_task_payload("study_summary", normalized)[0]:
                        return normalized
            except Exception:
                if self._should_abort_retry():
                    break
            if attempt < tentativas - 1:
                time.sleep(0.35)
        return _normalize_summary_payload({})


# ========== UTILIDADES ==========
def read_pdf(filepath: str) -> Optional[List[str]]:
    """LÃª PDF e retorna lista de textos"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        texts = []
        for page in reader.pages:
            text = page.extract_text()
            if text and len(text) > 50:
                texts.append(text)
        return texts if texts else None
    except Exception as e:
        print(f"[PDF] Erro ao ler PDF: {e}")
        return None


# ========== TESTES ==========
if __name__ == "__main__":
    # Teste com Gemini
    try:
        provider = create_ai_provider("gemini", "YOUR_API_KEY_HERE")
        service = AIService(provider)
        
        quiz = service.generate_quiz(topic="Python bÃ¡sico", difficulty="MÃ©dio")
        if quiz:
            print("\n===== QUIZ GERADO =====")
            print(json.dumps(quiz, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"Erro no teste: {e}")
