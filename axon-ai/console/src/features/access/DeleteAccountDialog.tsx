/** Apagar a conta de uma pessoa (013 US12, FR-039, FR-040; ADR-058, ADR-059). Irreversível: confirma pelo nome de
 * usuário. Depois, o relatório por parte da plataforma — completo, ou parcial com "Tentar de novo". Com a conta já em
 * apagamento, "Concluir apagamento" vai direto ao botão, sem pedir o nome de novo (013 R34). */

import { useState, type FormEvent } from "react";

import { deletionReportOf, isApiError } from "../../api/errors";
import { useDeleteUser } from "../../api/hooks/access";
import type { Account, DeletionReport } from "../../api/schemas";
import { countText, moduleText } from "../../i18n/pt-BR";
import { Badge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Dialog } from "../../ui/Dialog";
import { Field, TextInput } from "../../ui/Field";
import { Notice } from "../../ui/Notice";
import styles from "./Access.module.css";

function Counts({ counts }: { counts: Record<string, number> }) {
  const entries = Object.entries(counts).filter(([, value]) => value > 0);
  if (entries.length === 0) {
    return <p className={styles.reportCounts}>Nada a apagar.</p>;
  }
  return (
    <p className={styles.reportCounts}>{entries.map(([name, value]) => `${value} ${countText(name)}`).join(" · ")}</p>
  );
}

function Report({ report }: { report: DeletionReport }) {
  return (
    <ul className={styles.report} aria-label="O que foi feito em cada parte da plataforma">
      {report.complete ? (
        <li className={styles.reportPart}>
          <span className={styles.reportTitle}>{moduleText("identity")}</span>
          <Counts counts={report.identity} />
        </li>
      ) : null}
      {report.modules.map((part) => (
        <li key={part.name} className={styles.reportPart}>
          <span className={styles.reportTitle}>
            {moduleText(part.name)}
            {part.failed ? <Badge tone="bad">Falhou</Badge> : <Badge tone="ok">Concluído</Badge>}
          </span>
          {part.failed ? null : <Counts counts={part.counts} />}
          {part.warnings.map((warning) => (
            <p key={warning} className={styles.reportCounts}>
              Aviso: {warning}
            </p>
          ))}
        </li>
      ))}
    </ul>
  );
}

export function DeleteAccountDialog({ account, onClose }: { account: Account; onClose: () => void }) {
  const remove = useDeleteUser();
  const [typed, setTyped] = useState("");
  const resuming = account.deleting;
  const matches = resuming || typed.trim() === account.username;
  const partial = deletionReportOf(remove.error);
  const report = remove.data ?? partial;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (matches) {
      remove.mutate(account.username);
    }
  };
  const refused = remove.error && !partial ? remove.error : null;

  if (report) {
    return (
      <Dialog
        open
        onOpenChange={(next) => (next ? undefined : onClose())}
        title={
          report.complete
            ? `A conta ${account.username} foi apagada`
            : `O apagamento de ${account.username} não terminou`
        }
        description={
          report.complete
            ? "O nome de usuário está livre de novo."
            : "Uma parte da plataforma não respondeu. A conta fica em apagamento — não entra e não aparece como ativa — até concluir."
        }
      >
        <Report report={report} />
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
          {report.complete ? (
            <Button variant="primary" onClick={onClose}>
              Concluir
            </Button>
          ) : (
            <>
              <Button variant="ghost" onClick={onClose}>
                Deixar para depois
              </Button>
              <Button variant="danger" busy={remove.isPending} onClick={() => remove.mutate(account.username)}>
                Tentar de novo
              </Button>
            </>
          )}
        </div>
      </Dialog>
    );
  }

  return (
    <Dialog
      open
      onOpenChange={(next) => (next ? undefined : onClose())}
      title={resuming ? `Concluir o apagamento de ${account.username}` : `Apagar a conta de ${account.name}?`}
      description={
        resuming
          ? "Um apagamento anterior não terminou. Concluir repete o que faltou."
          : "Não dá para desfazer. O nome de usuário fica livre para uma conta nova."
      }
    >
      <form className={styles.form} onSubmit={submit} noValidate>
        {resuming ? null : (
          <>
            <div>
              <p className={styles.legend}>Será apagado</p>
              <ul className={styles.explain}>
                <li>a conta, as sessões e os grupos;</li>
                <li>as chaves de API, os Assistants e os servidores MCP pessoais;</li>
                <li>as conversas e as imagens delas.</li>
              </ul>
            </div>
            <div>
              <p className={styles.legend}>Fica, sem identificar a pessoa</p>
              <ul className={styles.explain}>
                <li>
                  a auditoria das ferramentas que alteram dados, os preços e os ajustes que ela fez — com o autor
                  trocado.
                </li>
              </ul>
            </div>
            <Field label="Digite o nome de usuário para confirmar" help={`Exatamente: ${account.username}`}>
              <TextInput mono value={typed} onChange={(event) => setTyped(event.target.value)} autoComplete="off" />
            </Field>
          </>
        )}
        {refused ? (
          <Notice tone="bad" title="A plataforma recusou" role="alert">
            {isApiError(refused) ? refused.message : "O apagamento falhou. Nada foi alterado."}
          </Notice>
        ) : null}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button variant="danger" type="submit" busy={remove.isPending} disabled={!matches}>
            {resuming ? "Concluir" : "Apagar"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
