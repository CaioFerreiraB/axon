"""Providers de LLM e modelo por papel (spec 006).

Consumidores importam `axon_ai.llm.api` — o seam Model Router, que resolve papel → (provider, modelo) a partir de uma
Model Policy e devolve um cliente já ligado ao modelo. Providers concretos são adapters; só a composition root
(spec 011) os instancia.
"""
