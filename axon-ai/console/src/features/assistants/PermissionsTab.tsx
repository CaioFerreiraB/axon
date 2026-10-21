/** Aba "Permissões" (013 US10, FR-028 a FR-030; ADR-040): quem pode usar um Assistant de sistema — os esquemas aceitos
 * e as entradas de `allow` —, sobreposto como Modelos e MCP. A console só antecipa a forma e aponta pendências; quem
 * decide é a 003, que recusa o mesmo com o campo (013 R25). */

import { useId, useMemo, useState, type FormEvent } from "react";

import { useApiKeys } from "../../api/hooks/apiKeys";
import { useGroups } from "../../api/hooks/access";
import { useDiscardOverride, useSaveAuth } from "../../api/hooks/assistants";
import { SCHEMES, type AssistantView, type Scheme } from "../../api/schemas";
import { Badge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Checkbox } from "../../ui/Checkbox";
import { Field, TextInput } from "../../ui/Field";
import { Notice } from "../../ui/Notice";
import { Panel } from "../../ui/Panel";
import { Toggle } from "../../ui/Toggle";
import { useAssistantContext } from "./AssistantDetail";
import styles from "./Editor.module.css";
import { DiscardButton, overrideMeta, SaveError } from "./editorParts";
import p from "./Permissions.module.css";
import { overrideOf, sentence } from "./status";

const ANYONE = "*";
const ENTRY = /^(user|svc|group):\S+$/;

const SCHEME_TEXT: Record<Scheme, { name: string; help: string }> = {
  oidc: { name: "Login", help: "Pessoas que entram pelo chat, com usuário e senha ou Google." },
  api_key: { name: "Chave de API", help: "Sistemas que chamam a plataforma com uma chave." },
};

const KIND_TEXT: Record<string, string> = { svc: "Sistema", group: "Grupo", user: "Pessoa" };

type Draft = { schemes: Set<Scheme>; allow: string[] };

function draftOf(view: AssistantView): Draft {
  return { schemes: new Set(view.effective.auth.schemes), allow: [...view.effective.auth.allow] };
}

function changesOf(draft: Draft, base: Draft): number {
  const schemes = SCHEMES.filter((scheme) => draft.schemes.has(scheme) !== base.schemes.has(scheme)).length;
  const entries = new Set(
    [...draft.allow, ...base.allow].filter((entry) => draft.allow.includes(entry) !== base.allow.includes(entry)),
  ).size;
  return schemes + entries;
}

/** O que a API já lista: sistemas com chave ativa e grupos (008 FR-038). `null` enquanto carrega — sem marcas. */
function useKnown(): { systems: string[]; groups: string[] } | null {
  const apiKeys = useApiKeys();
  const groups = useGroups();
  return useMemo(() => {
    if (!apiKeys.data || !groups.data) {
      return null;
    }
    const systems = [
      ...new Set(
        apiKeys.data
          .filter((key) => key.revoked_at === null && key.subject.startsWith("svc:"))
          .map((key) => key.subject),
      ),
    ].sort();
    return { systems, groups: groups.data.map((group) => `group:${group.name}`).sort() };
  }, [apiKeys.data, groups.data]);
}

function marksOf(entry: string, draft: Draft, known: ReturnType<typeof useKnown>): string[] {
  const marks: string[] = [];
  if (known && entry.startsWith("svc:") && !known.systems.includes(entry)) {
    marks.push("Sem correspondência");
  }
  if (known && entry.startsWith("group:") && !known.groups.includes(entry)) {
    marks.push("Sem correspondência");
  }
  if (entry.startsWith("svc:") && !draft.schemes.has("api_key")) {
    marks.push("Não entra com os esquemas ligados");
  }
  return marks;
}

export default function PermissionsTab() {
  const { view, refetch } = useAssistantContext();
  const editable = view.overridable.includes("auth");
  const override = overrideOf(view, "auth");
  const isPublic = view.visibility === "public";
  const known = useKnown();
  const [draft, setDraft] = useState<Draft>(() => draftOf(view));
  const [baseVersion, setBaseVersion] = useState<number | null>(override?.version ?? null);
  const [adding, setAdding] = useState("");
  const [addError, setAddError] = useState<string | undefined>(undefined);
  const save = useSaveAuth(view.name);
  const discard = useDiscardOverride(view.name);
  const listId = useId();

  const changes = changesOf(draft, draftOf(view));
  const named = draft.allow.filter((entry) => entry !== ANYONE);
  const blocker =
    draft.schemes.size === 0
      ? "Ligue ao menos uma forma de entrada."
      : draft.allow.length === 0
        ? "Inclua ao menos uma entrada."
        : null;

  const setScheme = (scheme: Scheme, on: boolean) =>
    setDraft((current) => {
      const schemes = new Set(current.schemes);
      if (on) {
        schemes.add(scheme);
      } else {
        schemes.delete(scheme);
      }
      return { ...current, schemes };
    });
  const setAnyone = (on: boolean) =>
    setDraft((current) => ({
      ...current,
      allow: on
        ? [...current.allow.filter((entry) => entry !== ANYONE), ANYONE]
        : current.allow.filter((e) => e !== ANYONE),
    }));
  const remove = (entry: string) =>
    setDraft((current) => ({ ...current, allow: current.allow.filter((item) => item !== entry) }));
  const add = (event: FormEvent) => {
    event.preventDefault();
    const entry = adding.trim();
    if (!ENTRY.test(entry)) {
      setAddError("Use svc:<nome>, group:<nome> ou user:<nome>, sem espaço.");
      return;
    }
    if (draft.allow.includes(entry)) {
      setAddError("Essa entrada já está na lista.");
      return;
    }
    setDraft((current) => ({ ...current, allow: [...current.allow, entry] }));
    setAdding("");
    setAddError(undefined);
  };

  const onSave = () =>
    save.mutate(
      {
        schemes: SCHEMES.filter((scheme) => draft.schemes.has(scheme)).sort(),
        allow: draft.allow,
        version: baseVersion,
      },
      {
        onSuccess: (next) => {
          setDraft(draftOf(next));
          setBaseVersion(overrideOf(next, "auth")?.version ?? null);
        },
      },
    );

  return (
    <div className={styles.stack}>
      {!editable ? (
        <Notice tone="neutral" title="As permissões deste Assistant só mudam por novo deploy">
          O assistants.yaml não inclui auth em overrides. Para liberar a edição pela console, acrescente overrides:
          [auth] e faça o deploy.
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
      ) : null}

      <Panel
        title="Quem pode usar este Assistant"
        subtitle="Vale no chat e na API. Administrar o Assistant é do grupo de administração, qualquer que seja esta lista."
      >
        <div className={p.schemes}>
          {SCHEMES.map((scheme) => (
            <div key={scheme} className={p.scheme}>
              <Toggle
                checked={draft.schemes.has(scheme)}
                onChange={(on) => setScheme(scheme, on)}
                disabled={!editable}
                label={SCHEME_TEXT[scheme].name}
              />
              <span className={p.schemeText}>
                <span className={p.schemeName}>{SCHEME_TEXT[scheme].name}</span>
                <span className={p.schemeHelp}>{SCHEME_TEXT[scheme].help}</span>
              </span>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Entradas" subtitle="Sistemas, grupos e pessoas que podem usar o Assistant.">
        <div className={styles.stack}>
          {isPublic ? (
            <div>
              <Checkbox
                label="Qualquer pessoa autenticada (*)"
                checked={draft.allow.includes(ANYONE)}
                disabled={!editable}
                onChange={(event) => setAnyone(event.target.checked)}
              />
              <p className={p.note}>Libera o Assistant para toda pessoa que entra no chat e toda chave de API ativa.</p>
            </div>
          ) : (
            <p className={p.note}>
              Assistant privado: a plataforma não aceita qualquer pessoa autenticada; nomeie sistemas, grupos ou
              pessoas.
            </p>
          )}
          {named.length > 0 ? (
            <ul className={p.entries} aria-label="Quem pode usar">
              {named.map((entry) => {
                const kind = entry.split(":")[0] ?? "";
                return (
                  <li key={entry} className={p.entry}>
                    <span className={p.kind}>{KIND_TEXT[kind] ?? "Entrada"}</span>
                    <span className={p.value}>{entry}</span>
                    <span className={p.marks}>
                      {marksOf(entry, draft, known).map((mark) => (
                        <Badge key={mark} tone="warn">
                          {mark}
                        </Badge>
                      ))}
                    </span>
                    {editable ? (
                      <Button variant="ghost" size="sm" aria-label={`Remover ${entry}`} onClick={() => remove(entry)}>
                        Remover
                      </Button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          ) : (
            <ul className={p.entries} aria-label="Quem pode usar">
              <li className={p.entry}>
                <span className={p.note}>Nenhum sistema, grupo ou pessoa nomeado.</span>
              </li>
            </ul>
          )}
          {named.some((entry) => marksOf(entry, draft, known).includes("Sem correspondência")) ? (
            <p className={p.note}>
              Sem correspondência: nenhum sistema com chave ativa ou grupo tem esse nome. A entrada não dá acesso a
              ninguém; remova-a ou crie a chave ou o grupo.
            </p>
          ) : null}
          {editable ? (
            <form className={p.add} onSubmit={add} noValidate>
              <div className={p.addField}>
                <Field
                  label="Adicionar sistema, grupo ou pessoa"
                  error={addError}
                  help="Escolha um sistema ou grupo da lista, ou digite user:<nome>."
                >
                  <TextInput
                    mono
                    list={listId}
                    value={adding}
                    autoComplete="off"
                    placeholder="svc:… · group:… · user:…"
                    onChange={(event) => {
                      setAdding(event.target.value);
                      setAddError(undefined);
                    }}
                  />
                </Field>
                <datalist id={listId}>
                  {[...(known?.systems ?? []), ...(known?.groups ?? [])].map((option) => (
                    <option key={option} value={option} />
                  ))}
                </datalist>
              </div>
              <Button type="submit" icon="mais" className={p.addButton} disabled={!adding.trim()}>
                Adicionar
              </Button>
            </form>
          ) : null}
        </div>
      </Panel>

      <SaveError
        error={save.error ?? discard.error}
        onReload={() =>
          void refetch().then((fresh) => {
            const next = (fresh as { data?: AssistantView }).data;
            if (next) {
              setBaseVersion(overrideOf(next, "auth")?.version ?? null);
            }
            save.reset();
          })
        }
      />
      <div className={styles.footer}>
        <span className={styles.meta}>
          {editable
            ? overrideMeta(override, "Sem sobreposição de permissões: vale o YAML", changes)
            : "Valores do assistants.yaml deste deploy."}
        </span>
        {editable ? (
          <div className={styles.actions}>
            {changes > 0 ? (
              <Button variant="ghost" onClick={() => setDraft(draftOf(view))}>
                Desfazer alterações
              </Button>
            ) : override ? (
              <DiscardButton
                override={override}
                busy={discard.isPending}
                onConfirm={() =>
                  discard.mutate(
                    { section: "auth", version: override.version },
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
              disabled={changes === 0 || blocker !== null}
              busy={save.isPending}
              onClick={onSave}
            >
              Salvar sobreposição
            </Button>
          </div>
        ) : null}
      </div>
      {editable && blocker ? <p className={styles.hint}>{blocker}</p> : null}
    </div>
  );
}
