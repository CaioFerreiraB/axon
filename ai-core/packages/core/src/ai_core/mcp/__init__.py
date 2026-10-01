"""Registry e cliente MCP (spec 007).

Servidores MCP por alias — globais e de usuário —, com política por servidor e só a **referência** da credencial; e o
cliente entregue a uma execução, que conhece apenas os aliases do grant e só conecta a destinos que passam pela
política de rede. Os seams estão em `api.py`.

`stdio` executa um comando no host do core: existe só no arquivo do operador, nunca pela API (ADR-003).
"""
