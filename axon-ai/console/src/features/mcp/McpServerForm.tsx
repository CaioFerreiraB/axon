/** Cadastrar ou editar um servidor MCP global (013 FR-014). Credencial só por referência: o valor fica na instalação,
 * em `AXON_MCP_SECRET_<REF>`, e nunca passa pela console. */

import { useState, type FormEvent } from "react";

import { fieldError, isApiError } from "../../api/errors";
import { useCreateMcp, useUpdateMcp, type McpDraft } from "../../api/hooks/mcp";
import type { McpServer } from "../../api/schemas";
import { Button } from "../../ui/Button";
import { Field, Select, TextInput } from "../../ui/Field";
import { Notice } from "../../ui/Notice";
import { Panel } from "../../ui/Panel";
import { Toggle } from "../../ui/Toggle";
import styles from "./McpServersPage.module.css";

const list = (text: string) =>
  text
    .split(/[\s,]+/)
    .map((item) => item.trim())
    .filter(Boolean);

export function McpServerForm({ server, onDone }: { server?: McpServer; onDone: () => void }) {
  const create = useCreateMcp();
  const update = useUpdateMcp();
  const mutation = server ? update : create;
  const [draft, setDraft] = useState({
    alias: server?.alias ?? "",
    transport: (server?.transport === "sse" ? "sse" : "http") as "http" | "sse",
    endpoint: server?.endpoint ?? "",
    description: server?.description ?? "",
    credential: server?.auth.credential ?? "",
    userAccess: server?.user_access ?? false,
    allowed: (server?.policy?.allowed_tools ?? []).join(", "),
    write: (server?.policy?.write_tools ?? []).join(", "),
  });
  const set = (field: keyof typeof draft) => (event: { target: { value: string } }) =>
    setDraft((current) => ({ ...current, [field]: event.target.value }));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const body: McpDraft = {
      alias: draft.alias.trim(),
      transport: draft.transport,
      endpoint: draft.endpoint.trim(),
      user_access: draft.userAccess,
      policy: { allowed_tools: list(draft.allowed), write_tools: list(draft.write) },
      ...(draft.description.trim() ? { description: draft.description.trim() } : {}),
      ...(server?.auth.type === "delegated"
        ? { auth: { type: "delegated" as const } }
        : draft.credential.trim()
          ? { auth: { type: "bearer" as const, credential: draft.credential.trim() } }
          : { auth: { type: "none" as const } }),
    };
    mutation.mutate(body, { onSuccess: onDone });
  };
  const error = (field: string) => fieldError(mutation.error, field);
  const shown = ["alias", "transport", "endpoint", "description", "auth", "policy"];
  const placed =
    isApiError(mutation.error) &&
    mutation.error.param !== null &&
    shown.includes(mutation.error.param.split(".")[0] ?? "") &&
    !(server?.auth.type === "delegated" && mutation.error.param.startsWith("auth"));
  const unplaced = mutation.error && !placed ? mutation.error : null;

  return (
    <Panel title={server ? `Editar ${server.alias}` : "Novo servidor"} labelledBy="form-servidor">
      <form onSubmit={submit} className={styles.form} noValidate>
        <Field label="Alias" error={error("alias")} help="Nome curto, usado como namespace das tools: alias.tool">
          <TextInput
            mono
            value={draft.alias}
            onChange={set("alias")}
            disabled={server !== undefined}
            autoComplete="off"
          />
        </Field>
        <Field label="Transporte" error={error("transport")}>
          <Select value={draft.transport} onChange={set("transport")}>
            <option value="http">http</option>
            <option value="sse">sse</option>
          </Select>
        </Field>
        <div className={styles.wide}>
          <Field
            label="Endereço"
            error={error("endpoint")}
            help="https; endereços internos só pelo mcp.yaml da instalação."
          >
            <TextInput
              mono
              value={draft.endpoint}
              onChange={set("endpoint")}
              placeholder="https://"
              autoComplete="off"
            />
          </Field>
        </div>
        <Field label="Descrição" error={error("description")}>
          <TextInput value={draft.description} onChange={set("description")} />
        </Field>
        {server?.auth.type === "delegated" ? (
          <Notice tone="neutral" title="Autenticação delegada">
            Autorização temporária fornecida por execução. Este formulário preserva o modo delegado.
          </Notice>
        ) : (
          <Field
            label="Credencial (referência)"
            error={error("auth")}
            help="O nome da referência, não o valor: a instalação define AXON_MCP_SECRET_<REF>."
          >
            <TextInput
              mono
              value={draft.credential}
              onChange={set("credential")}
              placeholder="sem credencial"
              autoComplete="off"
            />
          </Field>
        )}
        <Field
          label="Tools permitidas"
          error={error("policy")}
          help="Separadas por vírgula. A allowlist é obrigatória."
        >
          <TextInput mono value={draft.allowed} onChange={set("allowed")} autoComplete="off" />
        </Field>
        <Field label="Tools de escrita" help="Separadas por vírgula; auditadas antes de executar.">
          <TextInput mono value={draft.write} onChange={set("write")} autoComplete="off" />
        </Field>
        <div className={styles.wide}>
          <Toggle
            showLabel
            label="Usuários podem ligar este servidor aos próprios Assistants"
            checked={draft.userAccess}
            onChange={(checked) => setDraft((current) => ({ ...current, userAccess: checked }))}
          />
        </div>
        {unplaced ? (
          <div className={styles.wide}>
            <Notice tone="bad" title="Não foi possível salvar" role="alert">
              {unplaced instanceof Error ? unplaced.message : "A gravação falhou."}
            </Notice>
          </div>
        ) : null}
        <div className={styles.formActions}>
          <Button variant="ghost" onClick={onDone}>
            Cancelar
          </Button>
          <Button variant="primary" type="submit" busy={mutation.isPending}>
            {server ? "Salvar servidor" : "Cadastrar servidor"}
          </Button>
        </div>
      </form>
    </Panel>
  );
}

/** Um servidor do arquivo do operador, como o mcp.yaml o define: só leitura, e a credencial só pelo nome. */
export function McpServerDetails({ server, onClose }: { server: McpServer; onClose: () => void }) {
  const policy = server.policy;
  const tools = (names: string[] | undefined) => (names && names.length > 0 ? names.join(", ") : "—");
  return (
    <Panel
      title={`${server.alias} · mcp.yaml`}
      subtitle="Definido no arquivo do operador. Só muda por novo deploy."
      labelledBy="detalhe-servidor"
      aside={
        <Button variant="ghost" size="sm" onClick={onClose}>
          Fechar
        </Button>
      }
    >
      <dl className={styles.details}>
        <dt>Transporte</dt>
        <dd>{server.transport ?? "—"}</dd>
        <dt>{server.command ? "Comando" : "Endereço"}</dt>
        <dd className={styles.detailsMono}>{server.endpoint ?? server.command ?? "—"}</dd>
        {server.description ? (
          <>
            <dt>Descrição</dt>
            <dd>{server.description}</dd>
          </>
        ) : null}
        <dt>Credencial (referência)</dt>
        <dd className={server.auth.credential ? styles.detailsMono : undefined}>
          {server.auth.type === "delegated"
            ? "Delegada por execução; sem credencial estática"
            : (server.auth.credential ?? "Sem credencial")}
        </dd>
        <dt>Tools permitidas</dt>
        <dd className={styles.detailsMono}>{tools(policy?.allowed_tools)}</dd>
        <dt>Tools de escrita</dt>
        <dd className={styles.detailsMono}>{tools(policy?.write_tools)}</dd>
        <dt>Usuários podem ligar</dt>
        <dd>{server.user_access ? "Sim" : "Não"}</dd>
      </dl>
    </Panel>
  );
}
