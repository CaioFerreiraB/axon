"""Catálogo de capacidades e execução segura de tools (spec 004).

O elo 3 da cadeia de enforcement — o catálogo de uma execução é exatamente o que o Assistant declara, e o resto não
existe — e o ponto único de execução de tools, que despacha por tipo (ADR-005) com validação, prazo, corte, cerca,
auditoria de escrita e trace. Os seams estão em `api.py`.
"""
