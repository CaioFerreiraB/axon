# Contrato — política de rede (FR-009, US6, clarificação 2; research R5)

## A decisão

Função pura em `domain/network.py`:

```python
def admit(
    host: str,
    addresses: Sequence[IPAddress],
    *,
    scope: Scope,
    internal_hosts: frozenset[str],
    allowed_hosts: frozenset[str] | None,
) -> Admission
```

`Admission(allowed: bool, address: IPAddress | None, reason: str | None)` — o endereço a conectar quando permitido, o
motivo quando não. Ordem:

1. normaliza o host (minúsculas, sem ponto final);
2. `scope == "global"` e host (ou IP literal) em `internal_hosts` → permitido, primeiro endereço;
3. `localhost` ou terminado em `.localhost` → bloqueado;
4. `allowed_hosts` definida e o host não casa com nenhum padrão — nome exato, `*.domínio` (só subdomínios) ou IP literal
   exato → bloqueado ("fora da allowlist de hosts"), para global e para usuário;
5. nenhum endereço → bloqueado ("não resolveu");
6. cada endereço normalizado — IPv4 mapeado em IPv6, 6to4 e Teredo viram o IPv4 embutido — precisa ser `is_global`;
   **qualquer** endereço bloqueado bloqueia o destino, nomeando a classe (loopback, privado, link-local, …);
7. permitido, primeiro endereço.

## Onde é aplicada

No backend de rede do transporte `http`/`sse`, **a cada conexão TCP**: resolve pelo `DnsResolver`, chama `admit`, e
conecta no endereço devolvido — nunca deixa a biblioteca resolver de novo. TLS verifica o certificado contra o nome do
host. Proxies do ambiente desligados. O SDK só segue redirecionamento na mesma origem; a conexão nova passa pela mesma
decisão.

## Vetores (SC-002)

`unit/test_network.py` (a função) e `integration/test_ssrf.py` (pelo transporte real, com `DnsResolver` fixo). Todos
bloqueados para MCP de usuário, e para global fora de `internal_hosts`:

| Vetor | Exemplo |
|---|---|
| loopback IPv4 / IPv6 | `127.0.0.1`, `127.1.2.3`, `::1` |
| nome reservado | `localhost`, `api.localhost` |
| privadas | `10.0.0.5`, `172.16.0.1`, `192.168.1.1` |
| link-local / metadados | `169.254.169.254`, `fe80::1` |
| CGNAT | `100.64.0.1` |
| ULA (inclui metadados IPv6) | `fd00:ec2::254` |
| não especificado | `0.0.0.0`, `::` |
| IPv4 mapeado | `::ffff:127.0.0.1`, `::ffff:10.0.0.1` |
| 6to4 com IPv4 privado embutido | `2002:0a00:0001::` |
| decimal / octal na URL | `http://2130706433/`, `http://0177.0.0.1/` (a resolução devolve `127.0.0.1`) |
| DNS que resolve para privada | `interno.exemplo.test` → `10.0.0.7` |
| resposta mista | `misto.exemplo.test` → `[93.184.216.34, 10.0.0.7]` |
| rebinding | primeira resolução pública, segunda privada — a segunda conexão é bloqueada. Testado no backend de rede, com conector falso (`contract/test_guarded_backend.py`): com servidor local não há como a primeira resolução ser pública |
| redirecionamento | `302` para `http://127.0.0.1/` (o SDK não segue fora da origem) e para o mesmo host que passou a resolver para privada |

E as exceções e a allowlist de hosts de destino (US6 cen. 3–5):

| Caso | Resultado |
|---|---|
| global → host em `internal_hosts` resolvendo para `10.0.5.20` | permitido |
| usuário → o mesmo host | bloqueado |
| global registrado pela API → `169.254.169.254` fora de `internal_hosts` | bloqueado |
| público → `93.184.216.34` | permitido (escopo `user` e `global`) |
| `allowed_hosts = {"*.empresa.example"}` → `mcp.empresa.example` público | permitido (US6 cen. 5) |
| `allowed_hosts = {"*.empresa.example"}` → `empresa.example` ou `outro.example` | bloqueado, global e usuário (US6 cen. 5) |
| `allowed_hosts` definida → global para host em `internal_hosts` | permitido (a exceção interna vem antes) |

Propriedade (hypothesis): para todo IPv4/IPv6 com `is_global` falso, `admit(..., scope="user")` bloqueia.
