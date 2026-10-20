"""Bootstrap e composition root do núcleo (spec 011).

**Esta é a única spec autorizada a importar `service.py` e `adapters/` de outros módulos** (princípio XIII, ADR-012):
é ela que instancia os adapters de cada porta e injeta os seams. Nenhum outro módulo importa este — o import-linter
verifica os dois sentidos.

O ponto de entrada do processo é o comando `axon`; a plataforma montada é `wiring.platform()`.
"""
