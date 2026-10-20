/** Usuários (013 FR-013): busca, estado, cadastro com senha temporária, edição, redefinir senha, desativar e
 * reativar, desfazer vínculo Google. Toda recusa (último admin, e-mail em uso) vem da API. */

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";

import { useGroups, useSetActive, useUnlinkGoogle, useUsers, type UsersParams } from "../../api/hooks/access";
import type { Account } from "../../api/schemas";
import { formatInstantDay, formatLastSeen, initials, plural } from "../../i18n/format";
import { Badge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { TextInput } from "../../ui/Field";
import { GoogleMark, Icon } from "../../ui/icons";
import { Notice } from "../../ui/Notice";
import { Panel } from "../../ui/Panel";
import { Segmented } from "../../ui/Segmented";
import { EmptyState, LoadError, Skeleton } from "../../ui/States";
import { Table, tableStyles as t } from "../../ui/Table";
import styles from "./Access.module.css";
import { CreatePersonDialog, EditPersonDialog, ResetPasswordDialog } from "./PersonDialog";

const STATES = [
  { value: "active", label: "Ativas" },
  { value: "disabled", label: "Desativadas" },
  { value: "all", label: "Todas" },
] as const;

type Action = { kind: "edit" | "password"; account: Account } | null;

function Menu({
  account,
  onAction,
}: {
  account: Account;
  onAction: (kind: "edit" | "password" | "toggle" | "unlink") => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) {
      return;
    }
    const close = (event: MouseEvent) => !ref.current?.contains(event.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  const pick = (kind: "edit" | "password" | "toggle" | "unlink") => {
    setOpen(false);
    onAction(kind);
  };
  return (
    <div className={styles.menu} ref={ref} onKeyDown={(event) => event.key === "Escape" && setOpen(false)}>
      <Button
        variant="ghost"
        size="sm"
        icon="mais_acoes"
        aria-label={`Ações de ${account.name}`}
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      />
      {open ? (
        <div className={styles.menuList}>
          <button type="button" className={styles.menuItem} autoFocus onClick={() => pick("edit")}>
            Editar
          </button>
          <button type="button" className={styles.menuItem} onClick={() => pick("password")} disabled={!account.active}>
            Redefinir senha
          </button>
          {account.google_linked ? (
            <button type="button" className={styles.menuItem} onClick={() => pick("unlink")}>
              Desfazer vínculo com o Google
            </button>
          ) : null}
          <button
            type="button"
            className={`${styles.menuItem} ${account.active ? styles.danger : ""}`}
            onClick={() => pick("toggle")}
          >
            {account.active ? "Desativar conta" : "Reativar conta"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

function StateCell({ account }: { account: Account }) {
  if (!account.active) {
    return (
      <>
        <Badge dot>Desativada</Badge>
        <span className={styles.stateNote}>
          {account.updated_by
            ? `Por ${account.updated_by.split(":").pop()} em ${formatInstantDay(account.updated_at)}`
            : null}
        </span>
      </>
    );
  }
  if (account.temporary_password) {
    return (
      <>
        <Badge tone="warn" dot>
          Senha temporária
        </Badge>
        <span className={styles.stateNote}>Troca no primeiro login</span>
      </>
    );
  }
  return (
    <Badge tone="ok" dot>
      Ativa
    </Badge>
  );
}

export default function UsersTab() {
  const [params, setParams] = useSearchParams();
  const state = (STATES.find((s) => s.value === params.get("estado"))?.value ?? "active") as UsersParams["state"];
  const query = params.get("q") ?? "";
  const [cursors, setCursors] = useState<string[]>([]);
  const users = useUsers({
    state,
    ...(query.trim() ? { query: query.trim() } : {}),
    ...(cursors.at(-1) ? { cursor: cursors.at(-1) } : {}),
  });
  const everyone = useUsers({ state: "all" });
  const groups = useGroups();
  const setActive = useSetActive();
  const unlink = useUnlinkGoogle();
  const [action, setAction] = useState<Action>(null);
  const [confirm, setConfirm] = useState<{ account: Account; kind: "toggle" | "unlink" } | null>(null);
  const creating = params.get("cadastrar") === "1";
  const protectedGroups = new Set((groups.data ?? []).filter((g) => g.protected).map((g) => g.name));

  const set = (key: string, value: string, fallback: string) => {
    const next = new URLSearchParams(params);
    if (value === fallback) {
      next.delete(key);
    } else {
      next.set(key, value);
    }
    setCursors([]);
    setParams(next, { replace: true });
  };
  const closeCreate = () => {
    const next = new URLSearchParams(params);
    next.delete("cadastrar");
    setParams(next, { replace: true });
  };

  const all = everyone.data?.data ?? [];
  const active = all.filter((a) => a.active).length;
  const disabled = all.length - active;
  const mutationError = setActive.error ?? unlink.error;

  return (
    <>
      <div className={styles.toolbar}>
        <div className={styles.search}>
          <Icon name="busca" className={styles.searchIcon} />
          <TextInput
            type="search"
            className={styles.searchInput}
            placeholder="Buscar por nome, usuário ou e-mail"
            aria-label="Buscar pessoa"
            value={query}
            onChange={(event) => set("q", event.target.value, "")}
          />
        </div>
        <Segmented
          label="Estado da conta"
          value={state}
          onChange={(value) => set("estado", value, "active")}
          options={STATES}
        />
        {everyone.data ? (
          <span className={styles.summary}>
            {plural(active, "conta ativa", "contas ativas")} · {plural(disabled, "desativada", "desativadas")}
          </span>
        ) : null}
      </div>
      {confirm ? (
        <Notice
          tone="warn"
          title={
            confirm.kind === "unlink"
              ? `Desfazer o vínculo de ${confirm.account.name} com o Google?`
              : confirm.account.active
                ? `Desativar a conta de ${confirm.account.name}?`
                : `Reativar a conta de ${confirm.account.name}?`
          }
          role="alert"
        >
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            {confirm.kind === "unlink"
              ? "O próximo login pelo Google com o mesmo e-mail cria o vínculo de novo."
              : confirm.account.active
                ? "A pessoa não entra mais; os acessos em andamento acabam em até 10 minutos."
                : "A pessoa volta a entrar com a senha ou o Google."}
            <Button variant="ghost" size="sm" onClick={() => setConfirm(null)} autoFocus>
              Cancelar
            </Button>
            <Button
              variant={confirm.kind === "toggle" && confirm.account.active ? "danger" : "primary"}
              size="sm"
              busy={setActive.isPending || unlink.isPending}
              onClick={() =>
                confirm.kind === "unlink"
                  ? unlink.mutate(confirm.account.username, { onSettled: () => setConfirm(null) })
                  : setActive.mutate(
                      { username: confirm.account.username, active: !confirm.account.active },
                      { onSettled: () => setConfirm(null) },
                    )
              }
            >
              Confirmar
            </Button>
          </span>
        </Notice>
      ) : null}
      {mutationError instanceof Error ? (
        <Notice tone="bad" title="A plataforma recusou" role="alert">
          {mutationError.message}
        </Notice>
      ) : null}
      {users.isError ? (
        <LoadError what="as contas" error={users.error} onRetry={() => void users.refetch()} />
      ) : users.isPending ? (
        <Skeleton height={260} style={{ borderRadius: 8 }} />
      ) : users.data.data.length === 0 ? (
        <Panel>
          <EmptyState
            title={
              query
                ? "Ninguém encontrado"
                : state === "disabled"
                  ? "Nenhuma conta desativada"
                  : "Só o admin inicial por enquanto"
            }
            action={
              query ? undefined : (
                <Button icon="mais" onClick={() => set("cadastrar", "1", "")}>
                  Cadastrar pessoa
                </Button>
              )
            }
          >
            {query ? "Nenhuma conta casa com a busca." : "Cadastre quem vai usar o chat ou administrar a plataforma."}
          </EmptyState>
        </Panel>
      ) : (
        <>
          <Table caption="Contas da plataforma">
            <thead>
              <tr>
                <th scope="col">Pessoa</th>
                <th scope="col">Grupos</th>
                <th scope="col">Login</th>
                <th scope="col">Estado</th>
                <th scope="col">Último acesso</th>
                <th scope="col">
                  <span className="visually-hidden">Ações</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {users.data.data.map((account) => (
                <tr key={account.id} className={account.active ? undefined : t.muted}>
                  <th scope="row" style={{ fontWeight: 400 }}>
                    <span className={styles.person}>
                      <span className={styles.avatar} aria-hidden="true">
                        {initials(account.name)}
                      </span>
                      <span>
                        <span className={styles.personName}>{account.name}</span>
                        <span className={styles.username}>{account.username}</span>
                        <span className={styles.email}>{account.email}</span>
                      </span>
                    </span>
                  </th>
                  <td>
                    <span className={styles.chips}>
                      {account.groups.map((group) => (
                        <Badge key={group} tone={protectedGroups.has(group) ? "accent" : "neutral"}>
                          {group}
                        </Badge>
                      ))}
                    </span>
                  </td>
                  <td>
                    <span className={styles.chips}>
                      {account.has_password ? <Badge>Senha</Badge> : null}
                      {account.google_linked ? (
                        <Badge>
                          <GoogleMark size={12} /> Google
                        </Badge>
                      ) : null}
                    </span>
                  </td>
                  <td>
                    <StateCell account={account} />
                  </td>
                  <td>{formatLastSeen(account.last_login_at)}</td>
                  <td className={t.chevron}>
                    <Menu
                      account={account}
                      onAction={(kind) =>
                        kind === "edit" || kind === "password"
                          ? setAction({ kind, account })
                          : setConfirm({ account, kind })
                      }
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
          {users.data.next_cursor || cursors.length > 0 ? (
            <div className={styles.pager}>
              <Button disabled={cursors.length === 0} onClick={() => setCursors((list) => list.slice(0, -1))}>
                Página anterior
              </Button>
              <Button
                disabled={!users.data.next_cursor}
                onClick={() =>
                  users.data.next_cursor && setCursors((list) => [...list, users.data.next_cursor as string])
                }
              >
                Próxima página
              </Button>
            </div>
          ) : null}
        </>
      )}
      <CreatePersonDialog open={creating} onClose={closeCreate} groups={groups.data ?? []} />
      {action?.kind === "edit" ? (
        <EditPersonDialog account={action.account} onClose={() => setAction(null)} groups={groups.data ?? []} />
      ) : null}
      {action?.kind === "password" ? (
        <ResetPasswordDialog account={action.account} onClose={() => setAction(null)} />
      ) : null}
    </>
  );
}
