/** Cadastrar ou editar uma pessoa. No cadastro, a senha temporária aparece uma única vez, com "Copiar" — o único modal
 * da console, porque protege o foco de um segredo mostrado uma vez (013 R7, FR-013). Nada dela fica em cache. */

import { useState, type FormEvent } from "react";

import { fieldError, isApiError } from "../../api/errors";
import { useCreateUser, useResetPassword, useUpdateUser, type PersonDraft } from "../../api/hooks/access";
import type { Account, Group, Issued } from "../../api/schemas";
import { Button } from "../../ui/Button";
import { Checkbox } from "../../ui/Checkbox";
import { Dialog } from "../../ui/Dialog";
import { Field, TextInput } from "../../ui/Field";
import { Notice } from "../../ui/Notice";
import { Toggle } from "../../ui/Toggle";
import styles from "./Access.module.css";

function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] ?? name;
}

export function IssuedPassword({
  issued,
  onDone,
  onAnother,
}: {
  issued: Issued;
  onDone: () => void;
  onAnother?: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const account = issued.account;
  const password = issued.temporary_password;
  return (
    <>
      {password ? (
        <>
          <div className={styles.secretRow}>
            <div className={styles.grow}>
              <Field label="Senha temporária">
                <TextInput mono readOnly value={password} onFocus={(event) => event.target.select()} />
              </Field>
            </div>
            <Button
              icon={copied ? "confere" : "copiar"}
              onClick={() => {
                void navigator.clipboard?.writeText(password).then(() => setCopied(true));
              }}
            >
              {copied ? "Copiada" : "Copiar"}
            </Button>
          </div>
        </>
      ) : (
        <Notice tone="info" title="Entra só pelo Google">
          Sem senha: {firstName(account.name)} entra com o Google, pelo e-mail cadastrado.
        </Notice>
      )}
      <dl className={styles.facts}>
        <dt>Usuário</dt>
        <dd className="mono">{account.username}</dd>
        <dt>E-mail</dt>
        <dd>{account.email}</dd>
        <dt>Grupos</dt>
        <dd>{account.groups.join(", ") || "—"}</dd>
      </dl>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
        {onAnother ? (
          <Button variant="ghost" onClick={onAnother}>
            Cadastrar outra pessoa
          </Button>
        ) : null}
        <Button variant="primary" onClick={onDone}>
          Concluir
        </Button>
      </div>
    </>
  );
}

function GroupPicker({
  groups,
  value,
  onChange,
}: {
  groups: Group[];
  value: string[];
  onChange: (value: string[]) => void;
}) {
  return (
    <fieldset className={styles.fieldset}>
      <legend className={styles.legend}>Grupos</legend>
      <div className={styles.groupPicker}>
        {groups.length === 0 ? <span className={styles.stateNote}>Nenhum grupo criado ainda.</span> : null}
        {groups.map((group) => (
          <Checkbox
            key={group.name}
            label={group.name}
            checked={value.includes(group.name)}
            onChange={(event) =>
              onChange(event.target.checked ? [...value, group.name] : value.filter((name) => name !== group.name))
            }
          />
        ))}
      </div>
    </fieldset>
  );
}

export function CreatePersonDialog({ open, onClose, groups }: { open: boolean; onClose: () => void; groups: Group[] }) {
  const create = useCreateUser();
  const [issued, setIssued] = useState<Issued | null>(null);
  const empty: PersonDraft = { username: "", email: "", name: "", groups: [], google_only: false };
  const [draft, setDraft] = useState<PersonDraft>(empty);
  const close = () => {
    setIssued(null);
    setDraft(empty);
    create.reset();
    onClose();
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(draft, { onSuccess: (result) => setIssued(result) });
  };
  const error = (field: string) => fieldError(create.error, field);
  const general =
    create.error &&
    isApiError(create.error) &&
    !["username", "email", "name", "groups"].includes(create.error.param ?? "")
      ? create.error
      : null;
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => (next ? undefined : close())}
      title={issued ? `${issued.account.name} foi cadastrado` : "Cadastrar pessoa"}
      description={
        issued
          ? issued.temporary_password
            ? `Repasse a senha temporária por um canal seguro. Ela aparece só agora; no primeiro login, ${firstName(issued.account.name)} define a própria senha.`
            : undefined
          : "A pessoa entra no chat e, se estiver no grupo de administração, na console."
      }
    >
      {issued ? (
        <IssuedPassword
          issued={issued}
          onDone={close}
          onAnother={() => {
            setIssued(null);
            setDraft(empty);
            create.reset();
          }}
        />
      ) : (
        <form className={styles.form} onSubmit={submit} noValidate>
          <div className={styles.formRow}>
            <Field label="Nome" error={error("name")}>
              <TextInput
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                autoComplete="off"
              />
            </Field>
            <Field label="Usuário" error={error("username")} help="Não muda depois do cadastro.">
              <TextInput
                mono
                value={draft.username}
                onChange={(e) => setDraft({ ...draft, username: e.target.value })}
                autoComplete="off"
              />
            </Field>
          </div>
          <Field label="E-mail" error={error("email")}>
            <TextInput
              type="email"
              value={draft.email}
              onChange={(e) => setDraft({ ...draft, email: e.target.value })}
              autoComplete="off"
            />
          </Field>
          <GroupPicker
            groups={groups}
            value={draft.groups}
            onChange={(value) => setDraft({ ...draft, groups: value })}
          />
          <Toggle
            showLabel
            label="Entra só pelo Google (sem senha)"
            checked={draft.google_only}
            onChange={(checked) => setDraft({ ...draft, google_only: checked })}
          />
          {general ? (
            <Notice tone="bad" title="Não foi possível cadastrar" role="alert">
              {general.message}
            </Notice>
          ) : null}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button variant="ghost" onClick={close}>
              Cancelar
            </Button>
            <Button variant="primary" type="submit" busy={create.isPending}>
              Cadastrar
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  );
}

export function EditPersonDialog({
  account,
  onClose,
  groups,
}: {
  account: Account;
  onClose: () => void;
  groups: Group[];
}) {
  const update = useUpdateUser();
  const [draft, setDraft] = useState({ name: account.name, email: account.email, groups: [...account.groups] });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    update.mutate(
      {
        username: account.username,
        version: account.version,
        ...(draft.name !== account.name ? { name: draft.name } : {}),
        ...(draft.email !== account.email ? { email: draft.email } : {}),
        ...(draft.groups.slice().sort().join() !== [...account.groups].sort().join() ? { groups: draft.groups } : {}),
      },
      { onSuccess: onClose },
    );
  };
  const error = (field: string) => fieldError(update.error, field);
  const general =
    update.error && !(isApiError(update.error) && ["name", "email", "groups"].includes(update.error.param ?? ""))
      ? update.error
      : null;
  return (
    <Dialog open onOpenChange={(next) => (next ? undefined : onClose())} title={`Editar ${account.name}`}>
      <form className={styles.form} onSubmit={submit} noValidate>
        <Field label="Nome" error={error("name")}>
          <TextInput value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        </Field>
        <Field label="E-mail" error={error("email")}>
          <TextInput type="email" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} />
        </Field>
        <GroupPicker groups={groups} value={draft.groups} onChange={(value) => setDraft({ ...draft, groups: value })} />
        {error("groups") ? (
          <p className={styles.stateNote} role="alert">
            {error("groups")}
          </p>
        ) : null}
        {general ? (
          <Notice
            tone={isApiError(general) && general.isVersionConflict ? "warn" : "bad"}
            title="Não foi possível salvar"
            role="alert"
          >
            {isApiError(general) && general.isVersionConflict
              ? "Outra pessoa mudou esta conta depois que você abriu. Feche e abra de novo para ver a versão atual."
              : general.message}
          </Notice>
        ) : null}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button variant="primary" type="submit" busy={update.isPending}>
            Salvar
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

export function ResetPasswordDialog({ account, onClose }: { account: Account; onClose: () => void }) {
  const reset = useResetPassword();
  const [issued, setIssued] = useState<Issued | null>(null);
  return (
    <Dialog
      open
      onOpenChange={(next) => (next ? undefined : onClose())}
      title={issued ? "Senha temporária nova" : `Redefinir a senha de ${account.name}`}
      description={
        issued
          ? "Repasse por um canal seguro. Ela aparece só agora; a senha anterior deixou de valer."
          : "A senha atual deixa de valer e uma temporária é gerada. No próximo login, a pessoa define outra."
      }
    >
      {issued ? (
        <IssuedPassword issued={issued} onDone={onClose} />
      ) : (
        <>
          {reset.error instanceof Error ? (
            <Notice tone="bad" title="Não foi possível redefinir" role="alert">
              {reset.error.message}
            </Notice>
          ) : null}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
            <Button variant="ghost" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              busy={reset.isPending}
              onClick={() => reset.mutate(account.username, { onSuccess: setIssued })}
            >
              Gerar senha temporária
            </Button>
          </div>
        </>
      )}
    </Dialog>
  );
}
