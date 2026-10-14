"""Spec 012 — provedor de identidade da plataforma (ADR-030).

Contas, grupos, login por senha ou Google (só contas cadastradas) e emissão dos tokens OIDC que o Open WebUI repassa e
que a console usa. Outros módulos importam só `ai_core.identity.api` (seams `AccountAdmin`, `LoginSettings` e
`PublicKeySet`); o protocolo e as páginas são o adapter primário `adapters/http.py`, montado pela composition root.
"""
