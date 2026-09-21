"""API HTTP: superfícies pública e privada, compatibilidade com o formato OpenAI (spec 008).

Este módulo **não tem `api.py`**: o seam que ele expõe é a própria superfície HTTP, consumida por clientes externos.
O que ele exige de outros módulos — autenticação, resolução de grant, identificador de requisição e relógio — está em
`ports.py`, para que a 003 chegue na Fase 2 como troca de adapter, sem mexer em rota nenhuma.
"""
