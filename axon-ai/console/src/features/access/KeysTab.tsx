/** Chaves de API dos sistemas (013 US9, FR-024 a FR-027; ADR-040): criar para `svc:<nome>`, ver a chave uma vez,
 * listar, revogar e rotacionar com confirmação na própria linha. Quem um sistema alcança se decide na aba
 * "Permissões" de cada Assistant, não aqui: a criação não concede grupos (clarificação de 2026-10-21). */

import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";

import { fieldError, isApiError } from "../../api/errors";
import { useApiKeys, useCreateKey, useRevokeKey, useRotateKey } from "../../api/hooks/apiKeys";
import type { ApiKey, IssuedKey } from "../../api/schemas";
import { formatInstant, formatInstantDay } from "../../i18n/format";
import { Badge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Field, TextInput } from "../../ui/Field";
import { Notice } from "../../ui/Notice";
import { Panel } from "../../ui/Panel";
import { EmptyState, LoadError, Skeleton } from "../../ui/States";
import { Table, tableStyles as t } from "../../ui/Table";
import styles from "./Access.module.css";
import { IssuedKeyDialog } from "./IssuedKeyDialog";

const SYSTEM_PREFIX = "svc:";

/** Ativas antes das revogadas; dentro de cada grupo, por sistema e rótulo (013 R24). */
function ordered(list: ApiKey[]): ApiKey[] {
  const rank = (key: ApiKey) => (key.revoked_at === null ? 0 : 1);
  return [...list].sort(
    (a, b) =>
      rank(a) - rank(b) ||
      a.subject.localeCompare(b.subject) ||
      (a.label ?? "").localeCompare(b.label ?? "") ||
      a.key_id.localeCompare(b.key_id),
  );
}

function CreateForm({ onIssued, onCancel }: { onIssued: (issued: IssuedKey) => void; onCancel: () => void }) {
  const create = useCreateKey();
  const [name, setName] = useState("");
  const [label, setLabel] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const draft = label.trim()
      ? { subject: `${SYSTEM_PREFIX}${name.trim()}`, label: label.trim() }
      : { subject: `${SYSTEM_PREFIX}${name.trim()}` };
    create.mutate(draft, {
      onSuccess: (issued) => {
        create.reset();
        onIssued(issued);
      },
    });
  };
  const general =
    isApiError(create.error) && !["subject", "label"].includes(create.error.param ?? "") ? create.error : null;
  return (
    <Panel
      title="Nova chave"
      subtitle="A chave sai com o subject svc:<nome>. Dê acesso a ela na aba Permissões de cada Assistant."
    >
      <form className={styles.form} onSubmit={submit} noValidate>
        <div className={styles.formRow}>
          <Field
            label="Nome do sistema"
            error={fieldError(create.error, "subject")}
            help="Minúsculas, números, ., _ e -, começando por letra ou número."
          >
            <TextInput mono value={name} onChange={(event) => setName(event.target.value)} autoComplete="off" />
          </Field>
          <Field
            label="Rótulo (opcional)"
            error={fieldError(create.error, "label")}
            help="Distingue chaves do mesmo sistema, como prod e homolog."
          >
            <TextInput value={label} onChange={(event) => setLabel(event.target.value)} autoComplete="off" />
          </Field>
        </div>
        {general ? (
          <Notice tone="bad" title="A plataforma recusou" role="alert">
            {general.message}
          </Notice>
        ) : null}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <Button variant="ghost" onClick={onCancel}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" busy={create.isPending} disabled={!name.trim()}>
            Gerar chave
          </Button>
        </div>
      </form>
    </Panel>
  );
}

type Asking = { keyId: string; action: "revoke" | "rotate" } | null;

function RowActions({
  apiKey,
  asking,
  setAsking,
  busy,
  onRevoke,
  onRotate,
}: {
  apiKey: ApiKey;
  asking: Asking;
  setAsking: (asking: Asking) => void;
  busy: boolean;
  onRevoke: () => void;
  onRotate: () => void;
}) {
  if (apiKey.revoked_at !== null) {
    return null;
  }
  if (asking?.keyId === apiKey.key_id) {
    const revoke = asking.action === "revoke";
    return (
      <span
        className={styles.confirm}
        role="group"
        aria-label={`Confirmar a ${revoke ? "revogação" : "rotação"} de ${apiKey.key_id}`}
      >
        {revoke ? "O sistema perde o acesso na hora." : "A chave atual deixa de valer na hora."}
        <Button variant="ghost" size="sm" onClick={() => setAsking(null)} autoFocus>
          Cancelar
        </Button>
        <Button variant="danger" size="sm" busy={busy} onClick={revoke ? onRevoke : onRotate}>
          {revoke ? "Revogar" : "Rotacionar"}
        </Button>
      </span>
    );
  }
  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        aria-label={`Rotacionar a chave ${apiKey.key_id}`}
        onClick={() => setAsking({ keyId: apiKey.key_id, action: "rotate" })}
      >
        Rotacionar
      </Button>
      <Button
        variant="ghost"
        size="sm"
        aria-label={`Revogar a chave ${apiKey.key_id}`}
        onClick={() => setAsking({ keyId: apiKey.key_id, action: "revoke" })}
      >
        Revogar
      </Button>
    </>
  );
}

export default function KeysTab() {
  const list = useApiKeys();
  const revoke = useRevokeKey();
  const rotate = useRotateKey();
  const [params, setParams] = useSearchParams();
  const creating = params.get("criar") === "1";
  const [asking, setAsking] = useState<Asking>(null);
  // A chave em claro vive só aqui, enquanto o diálogo está aberto (013 R23).
  const [issued, setIssued] = useState<{ key: IssuedKey; rotated: boolean } | null>(null);

  const closeForm = () =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("criar");
      return next;
    });
  const failure = revoke.error ?? rotate.error;

  return (
    <>
      {creating ? (
        <CreateForm
          onCancel={closeForm}
          onIssued={(key) => {
            closeForm();
            setIssued({ key, rotated: false });
          }}
        />
      ) : null}
      {failure ? (
        <Notice tone="bad" title="A plataforma recusou" role="alert">
          {isApiError(failure) ? failure.message : "A operação falhou. Nada foi alterado."}
        </Notice>
      ) : null}
      {list.isError ? (
        <LoadError what="as chaves" error={list.error} onRetry={() => void list.refetch()} />
      ) : list.isPending ? (
        <Skeleton height={160} style={{ borderRadius: 8 }} />
      ) : list.data.length === 0 ? (
        <Panel>
          <EmptyState title="Nenhuma chave">
            Sistemas entram na plataforma por chave de API. Crie uma para cada sistema e libere-a na aba Permissões dos
            Assistants que ele usa.
          </EmptyState>
        </Panel>
      ) : (
        <Table caption="Chaves de API">
          <thead>
            <tr>
              <th scope="col">Sistema</th>
              <th scope="col">Rótulo</th>
              <th scope="col">Identificador</th>
              <th scope="col">Grupos</th>
              <th scope="col">Criada</th>
              <th scope="col">Rotacionada</th>
              <th scope="col">Estado</th>
              <th scope="col">
                <span className="visually-hidden">Ações</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {ordered(list.data).map((apiKey) => (
              <tr key={apiKey.key_id}>
                <th scope="row" className={t.mono} style={{ fontWeight: 400 }}>
                  {apiKey.subject}
                </th>
                <td>{apiKey.label ?? "—"}</td>
                <td className={t.mono}>{apiKey.key_id}</td>
                <td>{apiKey.groups.join(", ") || "—"}</td>
                <td style={{ whiteSpace: "nowrap" }}>{formatInstantDay(apiKey.created_at)}</td>
                <td style={{ whiteSpace: "nowrap" }}>{apiKey.rotated_at ? formatInstant(apiKey.rotated_at) : "—"}</td>
                <td>
                  {apiKey.revoked_at === null ? (
                    <Badge tone="ok" dot>
                      Ativa
                    </Badge>
                  ) : (
                    <Badge>Revogada em {formatInstantDay(apiKey.revoked_at)}</Badge>
                  )}
                </td>
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  <RowActions
                    apiKey={apiKey}
                    asking={asking}
                    setAsking={(next) => {
                      revoke.reset();
                      rotate.reset();
                      setAsking(next);
                    }}
                    busy={revoke.isPending || rotate.isPending}
                    onRevoke={() => revoke.mutate(apiKey.key_id, { onSettled: () => setAsking(null) })}
                    onRotate={() =>
                      rotate.mutate(apiKey.key_id, {
                        onSuccess: (key) => {
                          rotate.reset();
                          setIssued({ key, rotated: true });
                        },
                        onSettled: () => setAsking(null),
                      })
                    }
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <IssuedKeyDialog
        issued={issued?.key ?? null}
        rotated={issued?.rotated ?? false}
        onClose={() => setIssued(null)}
      />
    </>
  );
}
