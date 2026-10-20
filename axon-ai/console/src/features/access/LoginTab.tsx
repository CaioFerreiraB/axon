/** Ajustes de login (013 FR-013): Google liga e desliga — desabilitado, com a explicação, sem cliente na instalação —
 * e o endereço de retorno a registrar no Google. Usuário e senha ficam sempre ligados. */

import { useState } from "react";

import { useLoginSettings, useSaveLoginSettings } from "../../api/hooks/access";
import { Badge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Field, TextInput } from "../../ui/Field";
import { GoogleMark, Icon } from "../../ui/icons";
import { Notice } from "../../ui/Notice";
import { LoadError, Skeleton } from "../../ui/States";
import { Toggle } from "../../ui/Toggle";
import styles from "./Access.module.css";

export default function LoginTab() {
  const settings = useLoginSettings();
  const save = useSaveLoginSettings();
  const [copied, setCopied] = useState(false);
  if (settings.isError) {
    return <LoadError what="os ajustes de login" error={settings.error} onRetry={() => void settings.refetch()} />;
  }
  if (settings.isPending) {
    return <Skeleton height={220} style={{ borderRadius: 8 }} />;
  }
  const view = settings.data;
  const installation = view.google_source === "installation";
  return (
    <>
      <section className={styles.panel} aria-labelledby="google-titulo">
        <div className={styles.panelHead}>
          <GoogleMark size={20} />
          <div className={styles.grow}>
            <div className={styles.panelTitleRow}>
              <h2 className={styles.panelTitle} id="google-titulo">
                Entrar com Google
              </h2>
              {view.google_enabled ? (
                <Badge tone="ok" dot>
                  Ligado
                </Badge>
              ) : (
                <Badge>Desligado</Badge>
              )}
              {installation ? <Badge icon="cadeado">Definido na instalação</Badge> : null}
            </div>
            <p className={styles.panelText}>
              Só entra quem já tem conta: o e-mail verificado pelo Google precisa ser o de uma conta ativa.
            </p>
          </div>
          <Toggle
            label="Entrar com Google"
            checked={view.google_enabled}
            disabled={!view.google_configured || installation || save.isPending}
            onChange={(enabled) => save.mutate({ google_enabled: enabled, version: view.version })}
          />
        </div>
        <div className={styles.panelBody}>
          {!view.google_configured ? (
            <Notice tone="neutral" title="Falta o cliente Google na instalação">
              Para ligar, a instalação precisa de AXON_GOOGLE_CLIENT_ID e AXON_GOOGLE_CLIENT_SECRET. Registre no Google
              o endereço de retorno abaixo e reinicie a plataforma.
            </Notice>
          ) : null}
          {save.error instanceof Error ? (
            <Notice tone="bad" title="Não foi possível mudar o login Google" role="alert">
              {save.error.message}
            </Notice>
          ) : null}
          <div className={styles.copyRow}>
            <Field label="Endereço de retorno para cadastrar no Google">
              <TextInput mono readOnly value={view.google_redirect_uri} onFocus={(event) => event.target.select()} />
            </Field>
            <Button
              icon={copied ? "confere" : "copiar"}
              onClick={() => void navigator.clipboard?.writeText(view.google_redirect_uri).then(() => setCopied(true))}
            >
              {copied ? "Copiado" : "Copiar"}
            </Button>
          </div>
          {view.google_configured ? (
            <div className={styles.twoFields}>
              <Field label="Cliente" installation>
                <TextInput mono readOnly value={view.google_client_id ?? ""} />
              </Field>
              <Field label="Domínio aceito" installation>
                <TextInput readOnly value={view.google_hosted_domain ?? "qualquer domínio"} />
              </Field>
            </div>
          ) : null}
        </div>
      </section>
      <section className={styles.panel} aria-labelledby="senha-titulo">
        <div className={styles.panelHead}>
          <Icon name="cadeado" />
          <div className={styles.grow}>
            <h2 className={styles.panelTitle} id="senha-titulo">
              Usuário ou e-mail e senha
            </h2>
            <p className={styles.panelText}>Sempre ligado. Bloqueio de 15 min depois de 5 falhas; sessão de 30 dias.</p>
          </div>
          <Badge>Sempre ligado</Badge>
        </div>
      </section>
    </>
  );
}
