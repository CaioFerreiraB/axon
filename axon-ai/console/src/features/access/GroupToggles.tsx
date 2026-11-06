/** Os grupos de uma pessoa, um de cada vez e na hora (013 FR-041, R35; 008 FR-050): cada caixa põe ou tira só aquele
 * grupo, sem versão e sem reescrever a lista — a mudança de outro admin no mesmo instante fica. A recusa da plataforma
 * (último admin, grupo inexistente) volta a caixa e aparece ao lado dela. */

import { useState } from "react";

import { isApiError } from "../../api/errors";
import { useAddGroup, useRemoveGroup } from "../../api/hooks/access";
import type { Account, Group } from "../../api/schemas";
import { Checkbox } from "../../ui/Checkbox";
import styles from "./Access.module.css";

export function GroupToggles({ account, groups }: { account: Account; groups: Group[] }) {
  const add = useAddGroup();
  const remove = useRemoveGroup();
  const [current, setCurrent] = useState<string[]>([...account.groups]);
  const [busy, setBusy] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<{ group: string; message: string } | null>(null);

  const toggle = (group: string, on: boolean) => {
    setRefusal(null);
    setBusy(group);
    // A caixa muda na hora; se a plataforma recusa, volta ao que era (013 R35).
    const before = current;
    setCurrent(on ? [...before, group] : before.filter((name) => name !== group));
    const mutation = on ? add : remove;
    mutation.mutate(
      { username: account.username, group },
      {
        onSuccess: (updated) => setCurrent([...updated.groups]),
        onError: (error) => {
          setCurrent(before);
          setRefusal({ group, message: isApiError(error) ? error.message : "A mudança falhou. Nada foi alterado." });
        },
        onSettled: () => setBusy(null),
      },
    );
  };

  return (
    <fieldset className={styles.fieldset} aria-describedby="grupos-na-hora">
      <legend className={styles.legend}>Grupos</legend>
      <p id="grupos-na-hora" className={styles.help}>
        Cada grupo vale na hora, sem precisar salvar.
      </p>
      <div className={styles.groupPicker}>
        {groups.length === 0 ? <span className={styles.stateNote}>Nenhum grupo criado ainda.</span> : null}
        {groups.map((group) => (
          <span key={group.name} className={styles.groupToggle} aria-busy={busy === group.name}>
            <Checkbox
              label={group.name}
              checked={current.includes(group.name)}
              disabled={busy !== null}
              aria-describedby={refusal?.group === group.name ? `recusa-${group.name}` : undefined}
              onChange={(event) => toggle(group.name, event.target.checked)}
            />
            {refusal?.group === group.name ? (
              <span id={`recusa-${group.name}`} className={styles.fieldError} role="alert">
                {refusal.message}
              </span>
            ) : null}
          </span>
        ))}
      </div>
    </fieldset>
  );
}
