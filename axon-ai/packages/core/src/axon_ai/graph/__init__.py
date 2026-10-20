"""Motor de execução: flows do core (spec 005).

Consumidores importam `axon_ai.graph.api` — o seam Execution Engine (`run(grant, request)` → fluxo de eventos) e os
nomes de flow. O estado interno, os nomes dos nós e o framework de grafo são privados deste módulo e podem ser
reescritos sem tocar em nenhuma outra spec (ADR-011, SC-001).
"""
