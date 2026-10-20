/** Aba Modelos (013 US2, FR-006): para cada papel, o que o YAML define, a sobreposição e o valor efetivo. Só edita se
 * o YAML libera `models` em `overrides`; a allowlist e os papéis exigidos aparecem como referência, e toda recusa vem
 * da API junto ao papel (FR-001). A sobreposição escolhe o provider numa lista — só os prontos, mais o que o papel já
 * usa (ADR-035) — e digita o modelo sem o prefixo. */

import { useId, useMemo, useState } from "react";

import { fieldError, isApiError } from "../../api/errors";
import {
  useAssistants,
  useCheckModel,
  useDiscardOverride,
  useProviders,
  useSaveModels,
} from "../../api/hooks/assistants";
import { usePrices } from "../../api/hooks/usage";
import { isMcpPayload, ROLES, type AssistantView, type ModelCheck, type Provider } from "../../api/schemas";
import { formatInteger } from "../../i18n/format";
import { DEPLOY_ONLY, ROLE_TEXT } from "../../i18n/pt-BR";
import { Badge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Select, TextInput } from "../../ui/Field";
import { Icon } from "../../ui/icons";
import { Notice } from "../../ui/Notice";
import { Table, tableStyles as t } from "../../ui/Table";
import { useAssistantContext } from "./AssistantDetail";
import styles from "./Editor.module.css";
import { DiscardButton, overrideMeta, SaveError } from "./editorParts";
import { defaultProvider, joinRef, optionLabel, providerOptions, splitRef, type RefParts } from "./modelRef";
import { overrideOf, sentence } from "./status";

/** Por papel, o provider (vazio = o primeiro pronto) e o modelo sem o prefixo. */
type Draft = Record<string, RefParts>;

function draftOf(view: AssistantView): Draft {
  const override = overrideOf(view, "models");
  const stored: Record<string, string> =
    override?.state === "active" && override.payload && !isMcpPayload(override.payload) ? override.payload : {};
  return Object.fromEntries(ROLES.map((role) => [role, splitRef(stored[role] ?? view.yaml.models[role])]));
}

/** A referência do papel, com o provider padrão quando nenhum foi escolhido. */
function refOf(parts: RefParts | undefined, fallback: string): string {
  return parts ? joinRef({ provider: parts.provider || fallback, model: parts.model }) : "";
}

/** A sobreposição substitui a seção inteira (003 FR-018): vão todos os papéis preenchidos; o vazio fica sem modelo. */
function rolesOf(draft: Draft, fallback: string): Record<string, string> {
  return Object.fromEntries(
    ROLES.map((role) => [role, refOf(draft[role], fallback)] as const).filter(([, value]) => value !== ""),
  );
}

function useKnownModels(view: AssistantView): string[] {
  const assistants = useAssistants();
  const prices = usePrices();
  return useMemo(() => {
    const known = new Set<string>();
    for (const item of [view, ...(assistants.data ?? [])]) {
      Object.values(item.yaml.models).forEach((ref) => known.add(ref));
      Object.values(item.effective.models).forEach((ref) => known.add(ref));
    }
    (prices.data ?? []).forEach((price) => known.add(`${price.provider}/${price.model}`));
    return [...known].sort();
  }, [view, assistants.data, prices.data]);
}

function roleNote(role: string, view: AssistantView): string {
  if (view.required_roles.includes(role)) {
    return ROLE_TEXT[role] ?? "";
  }
  if (role === "rerank") {
    return "Opcional";
  }
  return `Não exigido pelo flow ${view.flow ?? ""}`.trim();
}

function CheckResult({ result, error }: { result?: ModelCheck | undefined; error: unknown }) {
  if (error) {
    return (
      <span className={`${styles.check} ${styles.checkBad}`}>
        {isApiError(error) ? error.message : "O teste falhou"}
      </span>
    );
  }
  if (!result) {
    return null;
  }
  return result.available ? (
    <span className={`${styles.check} ${styles.checkOk}`}>
      Disponível · respondeu em {formatInteger(result.latency_ms)} ms
    </span>
  ) : (
    <span className={`${styles.check} ${styles.checkBad}`}>Indisponível · {result.detail ?? "sem resposta"}</span>
  );
}

function RoleRow({
  role,
  view,
  value,
  onChange,
  editable,
  saveError,
  listId,
  known,
  providers,
}: {
  role: string;
  view: AssistantView;
  value: RefParts;
  onChange: (value: RefParts) => void;
  editable: boolean;
  saveError: unknown;
  listId: string;
  known: string[];
  providers: Provider[] | undefined;
}) {
  const check = useCheckModel(view.name);
  const yaml = view.yaml.models[role];
  const effective = view.effective.models[role];
  const override = overrideOf(view, "models");
  const overridden = override?.state === "active" && effective !== undefined && effective !== yaml;
  // A forma do corpo é conferida pela 008 (`roles.<papel>`); a regra, pela 003 (`models.<papel>`).
  const error = fieldError(saveError, `roles.${role}`) ?? fieldError(saveError, `models.${role}`);
  const required = view.required_roles.includes(role);
  const unusedByFlow = !required && role === "controller";
  const provider = value.provider || defaultProvider(providers);
  const options = providerOptions(providers, [provider, splitRef(yaml).provider, splitRef(effective).provider]);
  const chosen = options.find((option) => option.name === provider);
  const typed = joinRef({ provider, model: value.model });
  const target = typed || yaml || "";
  const modelsId = `${listId}-${role}-modelos`;
  const models = known.filter((ref) => ref.startsWith(`${provider}/`)).map((ref) => splitRef(ref).model);
  const hint =
    typed === "" && yaml
      ? "Vazio: o papel fica sem modelo na sobreposição"
      : typed !== "" && typed === yaml
        ? "Igual ao YAML"
        : typed === "" && role === "rerank"
          ? "Deixe vazio para seguir sem rerank"
          : typed === "" && unusedByFlow
            ? "Opcional neste flow"
            : null;
  return (
    <tr className={styles.cellTop}>
      <th scope="row" style={{ fontWeight: 400 }}>
        <span className={styles.roleName}>{role}</span>
        <span style={{ display: "block", marginTop: 4, color: "var(--texto-secundario)", fontSize: 13 }}>
          {roleNote(role, view)}
        </span>
        {/* Na tela estreita, a coluna "No YAML" some e o valor vem sob o papel. */}
        <span className={styles.yamlInline} title={yaml}>
          No YAML: <span className={styles.yamlValue}>{yaml ?? "—"}</span>
        </span>
      </th>
      <td className={`${styles.yaml} ${t.wideOnly}`} title={yaml}>
        {yaml ?? "—"}
      </td>
      <td>
        {editable ? (
          <div className={styles.overrideCell}>
            <div className={styles.inputRow}>
              <Select
                mono
                className={styles.providerSelect}
                value={provider}
                onChange={(event) => {
                  check.reset();
                  onChange({ ...value, provider: event.target.value });
                }}
                aria-label={`Provedor de ${role}`}
                title={chosen && !chosen.ready ? (chosen.detail ?? "Indisponível") : undefined}
              >
                {provider === "" ? <option value="">Nenhum provedor</option> : null}
                {options.map((option) => (
                  <option key={option.name} value={option.name}>
                    {optionLabel(option)}
                  </option>
                ))}
              </Select>
              <datalist id={modelsId}>
                {models.map((model) => (
                  <option key={model} value={model} />
                ))}
              </datalist>
              <TextInput
                mono
                list={modelsId}
                value={value.model}
                onChange={(event) => {
                  check.reset();
                  onChange({ ...value, model: event.target.value });
                }}
                placeholder={unusedByFlow || role === "rerank" ? "Sem modelo" : "autor/modelo"}
                aria-label={`Modelo de ${role}`}
                aria-invalid={error ? true : undefined}
                aria-describedby={`${listId}-${role}-ajuda`}
                autoComplete="off"
                spellCheck={false}
              />
              <Button
                icon="atualizar"
                aria-label={`Testar o modelo de ${role}`}
                title="Testar modelo"
                disabled={!target}
                busy={check.isPending}
                onClick={() => check.mutate({ role, model: target })}
              />
            </div>
            <div id={`${listId}-${role}-ajuda`} aria-live="polite">
              {error ? (
                <span className={styles.fieldError} role="alert">
                  {error}
                </span>
              ) : check.data || check.error ? (
                <CheckResult result={check.data} error={check.error} />
              ) : hint ? (
                <span className={styles.hint}>{hint}</span>
              ) : null}
            </div>
          </div>
        ) : (
          <span className={styles.locked}>
            <Icon name="cadeado" size={14} />
            {unusedByFlow && !yaml ? `O flow ${view.flow ?? ""} não usa ${role}` : DEPLOY_ONLY}
          </span>
        )}
      </td>
      <td>
        <div className={styles.effective}>
          <span className={styles.effectiveValue} title={effective}>
            {effective ?? "—"}
          </span>
          {effective ? overridden ? <Badge tone="accent">Sobreposto</Badge> : <Badge>Do YAML</Badge> : null}
        </div>
      </td>
    </tr>
  );
}

export default function ModelsTab() {
  const { view, refetch } = useAssistantContext();
  const editable = view.overridable.includes("models");
  const override = overrideOf(view, "models");
  const [draft, setDraft] = useState<Draft>(() => draftOf(view));
  const [baseVersion, setBaseVersion] = useState<number | null>(override?.version ?? null);
  const save = useSaveModels(view.name);
  const discard = useDiscardOverride(view.name);
  const providers = useProviders();
  const listId = useId();
  const known = useKnownModels(view);

  const fallback = defaultProvider(providers.data);
  const pristine = draftOf(view);
  const changes = ROLES.filter((role) => refOf(draft[role], fallback) !== refOf(pristine[role], fallback)).length;
  const roles = rolesOf(draft, fallback);
  const nothingToOverride = Object.keys(roles).length === 0;

  const onSave = () =>
    save.mutate(
      { roles, version: baseVersion },
      {
        onSuccess: (next) => {
          setDraft(draftOf(next));
          setBaseVersion(overrideOf(next, "models")?.version ?? null);
        },
      },
    );
  const onReload = async () => {
    const fresh = await refetch();
    // A versão nova vale para a próxima tentativa; o rascunho fica como está (FR-008).
    const next = (fresh as { data?: AssistantView }).data;
    if (next) {
      setBaseVersion(overrideOf(next, "models")?.version ?? null);
    }
    save.reset();
  };

  const onRole = (param: string | null) =>
    ROLES.some((role) => param === `roles.${role}` || param === `models.${role}`);
  const fieldless = save.error && !(isApiError(save.error) && onRole(save.error.param)) ? save.error : null;

  return (
    <div className={styles.stack}>
      {!editable ? (
        <Notice tone="neutral" title="Os modelos deste Assistant só mudam por novo deploy">
          O assistants.yaml não inclui models em overrides. Para liberar a troca pela console, acrescente overrides:
          [models] e faça o deploy.
        </Notice>
      ) : override?.state === "inactive" ? (
        <Notice
          tone="warn"
          title="Sobreposição inativa: o deploy mudou esta seção"
          action={{ label: "Ver a sobreposição guardada", to: "../historico" }}
        >
          {sentence(override.reason ?? "A sobreposição foi feita sobre outro YAML.")} Vale o que o deploy define até
          alguém gravar de novo.
        </Notice>
      ) : (
        <Notice
          tone="info"
          title={`O YAML libera a troca de modelos${view.overridable.includes("mcp") ? " e de MCP" : ""}`}
        >
          A allowlist continua do deploy: {view.allow.join(", ") || "nenhum padrão"}.
          {view.required_roles.length > 0
            ? ` Os papéis exigidos pelo flow ${view.flow ?? ""} são ${ROLES.filter((role) => view.required_roles.includes(role)).join(" e ")}.`
            : ""}
        </Notice>
      )}
      {editable && providers.data && !fallback ? (
        <Notice tone="warn" title="Nenhum provedor pronto">
          Defina a chave de um provedor remoto (AXON_OPENROUTER_API_KEY ou AXON_OPENAI_API_KEY) ou suba o Ollama em
          AXON_OLLAMA_BASE_URL. Os papéis que já têm modelo continuam mostrando o provedor deles.
        </Notice>
      ) : null}
      <Table caption={`Modelos por papel de ${view.name}`} style={{ tableLayout: "fixed" }}>
        <thead>
          <tr>
            <th scope="col" className={styles.colRole}>
              Papel
            </th>
            <th scope="col" className={`${styles.colYaml} ${t.wideOnly}`}>
              No YAML
            </th>
            <th scope="col">Sobreposição</th>
            <th scope="col" className={styles.colEffective}>
              Efetivo
            </th>
          </tr>
        </thead>
        <tbody>
          {ROLES.map((role) => (
            <RoleRow
              key={role}
              role={role}
              view={view}
              value={draft[role] ?? { provider: "", model: "" }}
              onChange={(value) => setDraft((current) => ({ ...current, [role]: value }))}
              editable={editable}
              saveError={save.error}
              listId={listId}
              known={known}
              providers={providers.data}
            />
          ))}
        </tbody>
      </Table>
      <SaveError error={fieldless ?? discard.error} onReload={() => void onReload()} />
      <div className={styles.footer}>
        <span className={styles.meta}>
          {editable
            ? overrideMeta(override, "Sem sobreposição de modelos: vale o YAML", changes)
            : "Valores do assistants.yaml deste deploy."}
        </span>
        {editable ? (
          <div className={styles.actions}>
            {override ? (
              <DiscardButton
                override={override}
                busy={discard.isPending}
                onConfirm={() =>
                  discard.mutate(
                    { section: "models", version: override.version },
                    {
                      onSuccess: (next) => {
                        setDraft(draftOf(next));
                        setBaseVersion(null);
                      },
                    },
                  )
                }
              />
            ) : null}
            <Button
              variant="primary"
              disabled={changes === 0 || nothingToOverride}
              busy={save.isPending}
              onClick={onSave}
            >
              Salvar sobreposição
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
