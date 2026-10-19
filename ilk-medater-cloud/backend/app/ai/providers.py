"""Moteurs de génération : Ollama (local, sans Internet) et API cloud Anthropic (facultative, désactivée par défaut)."""
import json
import logging
import urllib.error
import urllib.request

from ..config import get_settings

log = logging.getLogger("ilk.ai")

FALLBACK_MODELS = {"claude-opus-5-5", "claude-fable-5-1", "claude-opus-5", "claude-sonnet-5-5"}


class ProviderUnavailable(Exception):
    pass


def ollama_available() -> bool:
    cfg = get_settings()
    if not cfg.ollama_url:
        return False
    try:
        with urllib.request.urlopen(cfg.ollama_url.rstrip("/") + "/api/tags", timeout=2) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def ollama_chat(system: str, prompt: str) -> str:
    cfg = get_settings()
    if not cfg.ollama_url:
        raise ProviderUnavailable("IA locale non configurée (OLLAMA_URL)")
    body = json.dumps({"model": cfg.ollama_model, "stream": False, "options": {"temperature": 0.1},
                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(cfg.ollama_url.rstrip("/") + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=cfg.ollama_timeout_s) as r:
            data = json.loads(r.read().decode())
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ProviderUnavailable(f"IA locale injoignable : {e}") from e
    return (data.get("message") or {}).get("content", "").strip()


def cloud_chat(system: str, prompt: str) -> str:
    """Appel à l'API Claude. N'est appelé qu'après contrôle des droits, du consentement et du masquage."""
    cfg = get_settings()
    if not cfg.cloud_configured:
        raise ProviderUnavailable("IA cloud non configurée")
    import anthropic

    client = anthropic.Anthropic(api_key=cfg.cloud_ai_api_key, timeout=120.0, max_retries=2)
    kwargs = {}
    if cfg.cloud_ai_model in FALLBACK_MODELS:
        kwargs = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    try:
        resp = client.beta.messages.create(
            model=cfg.cloud_ai_model, max_tokens=cfg.cloud_ai_max_tokens, system=system,
            messages=[{"role": "user", "content": prompt}], output_config={"effort": "medium"}, **kwargs)
    except anthropic.AuthenticationError as e:
        raise ProviderUnavailable("Clé API cloud refusée") from e
    except anthropic.RateLimitError as e:
        raise ProviderUnavailable("Quota de l'API cloud atteint, réessayer plus tard") from e
    except anthropic.APIStatusError as e:
        log.warning("Erreur API cloud %s", e.status_code)
        raise ProviderUnavailable(f"Erreur du fournisseur cloud ({e.status_code})") from e
    except anthropic.APIConnectionError as e:
        raise ProviderUnavailable("Fournisseur cloud injoignable") from e
    if resp.stop_reason == "refusal":
        raise ProviderUnavailable("Le fournisseur cloud a refusé de traiter la demande")
    return "".join(b.text for b in resp.content if b.type == "text").strip()
