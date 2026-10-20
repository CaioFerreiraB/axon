/** Grupos (013 FR-013): criar, apagar e definir membros. O grupo de administração aparece protegido, sem apagar. */

import { useState, type FormEvent } from "react";

import { fieldError } from "../../api/errors";
import { useCreateGroup, useDeleteGroup, useGroups, useSetMembers, useUsers } from "../../api/hooks/access";
import type { Group } from "../../api/schemas";
import { plural } from "../../i18n/format";
import { Badge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Checkbox } from "../../ui/Checkbox";
import { Field, TextInput } from "../../ui/Field";
import { Notice } from "../../ui/Notice";
import { Panel } from "../../ui/Panel";
import { EmptyState, LoadError, Skeleton } from "../../ui/States";
import { Table, tableStyles as t } from "../../ui/Table";
import styles from "./Access.module.css";

function Members({ group, onDone }: { group: Group; onDone: () => void }) {
  const users = useUsers({ state: "active" });
  const save = useSetMembers();
  const people = users.data?.data ?? [];
  const [chosen, setChosen] = useState<Set<string> | null>(null);
  const current = chosen ?? new Set(people.filter((p) => p.groups.includes(group.name)).map((p) => p.username));
  return (
    <Panel title={`Membros de ${group.name}`} subtitle="Contas ativas no grupo. Vale no próximo login de cada pessoa.">
      {users.isPending ? (
        <Skeleton height={80} />
      ) : (
        <div className={styles.members}>
          {people.map((person) => (
            <Checkbox
              key={person.username}
              label={`${person.name} (${person.username})`}
              checked={current.has(person.username)}
              onChange={(event) => {
                const next = new Set(current);
                if (event.target.checked) {
                  next.add(person.username);
                } else {
                  next.delete(person.username);
                }
                setChosen(next);
              }}
            />
          ))}
        </div>
      )}
      {save.error instanceof Error ? (
        <div style={{ marginTop: 16 }}>
          <Notice tone="bad" title="A plataforma recusou" role="alert">
            {save.error.message}
          </Notice>
        </div>
      ) : null}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
        <Button variant="ghost" onClick={onDone}>
          Cancelar
        </Button>
        <Button
          variant="primary"
          busy={save.isPending}
          disabled={chosen === null}
          onClick={() => save.mutate({ name: group.name, usernames: [...current].sort() }, { onSuccess: onDone })}
        >
          Salvar membros
        </Button>
      </div>
    </Panel>
  );
}

export default function GroupsTab() {
  const groups = useGroups();
  const create = useCreateGroup();
  const remove = useDeleteGroup();
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<Group | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(name.trim(), { onSuccess: () => setName("") });
  };
  return (
    <>
      <form onSubmit={submit} className={styles.inline} noValidate>
        <div style={{ width: 280 }}>
          <Field label="Novo grupo" error={fieldError(create.error, "name")} help="Letras minúsculas, números, - e _.">
            <TextInput mono value={name} onChange={(event) => setName(event.target.value)} autoComplete="off" />
          </Field>
        </div>
        <Button type="submit" icon="mais" busy={create.isPending} disabled={!name.trim()} style={{ marginBottom: 22 }}>
          Criar grupo
        </Button>
      </form>
      {removing ? (
        <Notice tone="warn" title={`Apagar o grupo ${removing}?`} role="alert">
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            As contas saem do grupo; Assistants com ACL por ele deixam de liberar essas pessoas.
            <Button variant="ghost" size="sm" onClick={() => setRemoving(null)} autoFocus>
              Cancelar
            </Button>
            <Button
              variant="danger"
              size="sm"
              busy={remove.isPending}
              onClick={() => remove.mutate(removing, { onSettled: () => setRemoving(null) })}
            >
              Apagar
            </Button>
          </span>
        </Notice>
      ) : null}
      {remove.error instanceof Error ? (
        <Notice tone="bad" title="A plataforma recusou" role="alert">
          {remove.error.message}
        </Notice>
      ) : null}
      {editing ? <Members group={editing} onDone={() => setEditing(null)} /> : null}
      {groups.isError ? (
        <LoadError what="os grupos" error={groups.error} onRetry={() => void groups.refetch()} />
      ) : groups.isPending ? (
        <Skeleton height={160} style={{ borderRadius: 8 }} />
      ) : groups.data.length === 0 ? (
        <Panel>
          <EmptyState title="Nenhum grupo">Grupos dão acesso aos Assistants privados e à console.</EmptyState>
        </Panel>
      ) : (
        <Table caption="Grupos da plataforma">
          <thead>
            <tr>
              <th scope="col">Grupo</th>
              <th scope="col">Membros</th>
              <th scope="col">
                <span className="visually-hidden">Ações</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {groups.data.map((group) => (
              <tr key={group.name}>
                <th scope="row" style={{ fontWeight: 400 }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
                    <span className={t.mono}>{group.name}</span>
                    {group.protected ? (
                      <Badge tone="accent" icon="cadeado">
                        Protegido
                      </Badge>
                    ) : null}
                  </span>
                </th>
                <td style={{ color: "var(--texto-secundario)" }}>
                  {plural(group.members, "conta ativa", "contas ativas")}
                </td>
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  <Button variant="ghost" size="sm" onClick={() => setEditing(group)}>
                    Membros
                  </Button>
                  {group.protected ? null : (
                    <Button variant="ghost" size="sm" onClick={() => setRemoving(group.name)}>
                      Apagar
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </>
  );
}
