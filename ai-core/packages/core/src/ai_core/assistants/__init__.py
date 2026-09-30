"""Assistants & Access (spec 003): a fronteira de isolamento da plataforma.

Autentica o Principal pelas duas superfícies, mantém o registro de Assistants — de sistema, do `assistants.yaml`, e de
usuário, do armazenamento — e resolve, para cada pedido, o Execution Grant: só o que o Assistant declara, com 404
idêntico para inexistente e não autorizado (princípio IV, ADR-002).

Os seams moram em `api.py`, que é tudo o que outro módulo pode importar daqui. A autenticação mora neste pacote, e não
num `ai_core/auth/` próprio (ADR-012).
"""
