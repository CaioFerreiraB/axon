/** Observabilidade (013 US5, FR-012): o Langfuse — endereço, chaves (a secreta só de escrita), envio e "Testar
 * conexão" — e a captura opcional de prompt e resposta. O que a instalação define aparece somente leitura. */

import { useState } from "react";

import { fieldError, isApiError } from "../../api/errors";
import { useObservability, useSaveCapture, useSaveLangfuse, useTestLangfuse } from "../../api/hooks/observability";
import type { Observability } from "../../api/schemas";
import { formatAgo, plural } from "../../i18n/format";
import { Badge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Field, TextInput } from "../../ui/Field";
import { Notice } from "../../ui/Notice";
import { Page, PageHeader } from "../../ui/Page";
import { LoadError, Skeleton } from "../../ui/States";
import { Toggle } from "../../ui/Toggle";
import { CaptureConsent } from "./CaptureConsent";
import styles from "./ObservabilityPage.module.css";

function LangfuseStatus({ view }: { view: Observability }) {
  const health = view.health.find((item) => item.name === "langfuse");
  if (!view.langfuse.enabled || !health || health.state === "off") {
    return <Badge>Desligado</Badge>;
  }
  return health.state === "ok" ? (
    <Badge tone="ok" dot>
      Conectado
    </Badge>
  ) : (
    <Badge tone="bad" dot>
      Com falha
    </Badge>
  );
}

function summary(view: Observability): string {
  const health = view.health.find((item) => item.name === "langfuse");
  const installation = view.langfuse.sources.host === "installation";
  if (installation) {
    return "Configurado na instalação: endereço e chaves são somente leitura.";
  }
  if (!view.langfuse.enabled || !health || health.state === "off") {
    return "Envio desligado. Informe endereço e chaves, teste e ligue o envio.";
  }
  const sent = health.last_sent_at ? `Último envio ${formatAgo(health.last_sent_at)}` : "Nenhum envio ainda";
  const dropped = `${plural(health.dropped_24h, "descarte", "descartes")} nas últimas 24 h`;
  return [sent, dropped, health.last_error].filter(Boolean).join(" · ");
}

function LangfusePanel({ view }: { view: Observability }) {
  const save = useSaveLangfuse();
  const toggle = useSaveLangfuse();
  const test = useTestLangfuse();
  const sources = view.langfuse.sources;
  const fromInstallation = (field: keyof typeof sources) => sources[field] === "installation";
  const [draft, setDraft] = useState({
    host: view.langfuse.host ?? "",
    publicKey: view.langfuse.public_key ?? "",
    secret: "",
  });

  const changed =
    draft.host.trim() !== (view.langfuse.host ?? "") ||
    draft.publicKey.trim() !== (view.langfuse.public_key ?? "") ||
    draft.secret !== "";
  const onSave = () =>
    save.mutate(
      {
        version: view.version,
        ...(draft.host.trim() !== (view.langfuse.host ?? "") ? { host: draft.host.trim() } : {}),
        ...(draft.publicKey.trim() !== (view.langfuse.public_key ?? "") ? { public_key: draft.publicKey.trim() } : {}),
        ...(draft.secret ? { secret_key: draft.secret } : {}),
      },
      {
        onSuccess: (next) =>
          setDraft({ host: next.langfuse.host ?? "", publicKey: next.langfuse.public_key ?? "", secret: "" }),
      },
    );
  const onTest = () =>
    test.mutate({
      ...(draft.host.trim() && !fromInstallation("host") ? { host: draft.host.trim() } : {}),
      ...(draft.publicKey.trim() && !fromInstallation("public_key") ? { public_key: draft.publicKey.trim() } : {}),
      ...(draft.secret ? { secret_key: draft.secret } : {}),
    });

  const secretError = fieldError(save.error, "secret_key");
  const otherError =
    save.error && !secretError && !fieldError(save.error, "host") && !fieldError(save.error, "public_key")
      ? save.error
      : null;
  return (
    <section className={styles.panel} aria-labelledby="langfuse-titulo">
      <div className={styles.head}>
        <div>
          <div className={styles.titleRow}>
            <h2 className={styles.title} id="langfuse-titulo">
              Langfuse
            </h2>
            <LangfuseStatus view={view} />
          </div>
          <p className={styles.subtitle}>{summary(view)}</p>
        </div>
        <Toggle
          showLabel
          label="Enviar traces"
          checked={view.langfuse.enabled}
          disabled={fromInstallation("enabled") || toggle.isPending}
          onChange={(enabled) => toggle.mutate({ enabled, version: view.version })}
        />
      </div>
      <div className={styles.body}>
        <div className={styles.grid}>
          <Field label="Endereço" installation={fromInstallation("host")} error={fieldError(save.error, "host")}>
            <TextInput
              value={draft.host}
              readOnly={fromInstallation("host")}
              placeholder="https://cloud.langfuse.com"
              onChange={(event) => setDraft((current) => ({ ...current, host: event.target.value }))}
              autoComplete="off"
            />
          </Field>
          <Field
            label="Chave pública"
            installation={fromInstallation("public_key")}
            error={fieldError(save.error, "public_key")}
          >
            <TextInput
              mono
              value={draft.publicKey}
              readOnly={fromInstallation("public_key")}
              placeholder="pk-lf-…"
              onChange={(event) => setDraft((current) => ({ ...current, publicKey: event.target.value }))}
              autoComplete="off"
            />
          </Field>
          <Field
            label="Chave secreta"
            installation={fromInstallation("secret_key")}
            error={secretError}
            help={fromInstallation("secret_key") ? undefined : "Só de escrita: o valor salvo nunca volta para a tela."}
          >
            <TextInput
              type="password"
              value={fromInstallation("secret_key") ? "" : draft.secret}
              readOnly={fromInstallation("secret_key")}
              placeholder={
                fromInstallation("secret_key")
                  ? "Definida na instalação"
                  : view.langfuse.secret_set
                    ? "Definida · digite para trocar"
                    : "Não definida"
              }
              onChange={(event) => setDraft((current) => ({ ...current, secret: event.target.value }))}
              autoComplete="new-password"
            />
          </Field>
        </div>
        {otherError ? (
          <Notice
            tone={isApiError(otherError) && otherError.isVersionConflict ? "warn" : "bad"}
            title="Não foi possível salvar"
            role="alert"
          >
            {otherError instanceof Error ? otherError.message : "A gravação falhou."}
          </Notice>
        ) : null}
        {toggle.error instanceof Error ? (
          <Notice tone="bad" title="Não foi possível mudar o envio" role="alert">
            {toggle.error.message}
          </Notice>
        ) : null}
        <div className={styles.row}>
          <Button icon="atualizar" busy={test.isPending} onClick={onTest}>
            Testar conexão
          </Button>
          <span aria-live="polite">
            {test.data ? (
              <Badge tone={test.data.ok ? "ok" : "bad"} dot>
                {test.data.ok ? `As credenciais foram aceitas · ${test.data.detail}` : test.data.detail}
              </Badge>
            ) : test.error instanceof Error ? (
              <Badge tone="bad" dot>
                {test.error.message}
              </Badge>
            ) : null}
          </span>
          <span className={styles.spacer} />
          {fromInstallation("host") ? null : (
            <Button variant="primary" disabled={!changed} busy={save.isPending} onClick={onSave}>
              Salvar
            </Button>
          )}
        </div>
      </div>
    </section>
  );
}

function CapturePanel({ view }: { view: Observability }) {
  const save = useSaveCapture();
  const [asking, setAsking] = useState(false);
  const fromInstallation = view.capture_source === "installation";
  return (
    <section className={styles.panel} aria-labelledby="captura-titulo">
      <div className={styles.head}>
        <div>
          <div className={styles.titleRow}>
            <h2 className={styles.title} id="captura-titulo">
              Capturar prompt e resposta
            </h2>
            {fromInstallation ? <Badge icon="cadeado">Definido na instalação</Badge> : null}
          </div>
          <p className={styles.subtitle}>
            Manda ao Langfuse o texto de cada chamada de modelo. Desligado por padrão; o trace da plataforma nunca
            guarda texto.
          </p>
        </div>
        <Toggle
          label="Capturar prompt e resposta"
          checked={view.capture_content || asking}
          disabled={fromInstallation || save.isPending}
          onChange={(checked) => {
            if (checked) {
              setAsking(true);
            } else if (asking) {
              setAsking(false);
            } else {
              save.mutate({ enabled: false, version: view.version });
            }
          }}
        />
      </div>
      {asking || save.error ? (
        <div className={styles.body}>
          {asking ? (
            <CaptureConsent
              busy={save.isPending}
              onCancel={() => setAsking(false)}
              onConfirm={() =>
                save.mutate(
                  { enabled: true, acknowledged: true, version: view.version },
                  { onSuccess: () => setAsking(false) },
                )
              }
            />
          ) : null}
          {save.error instanceof Error ? (
            <Notice tone="bad" title="Não foi possível mudar a captura" role="alert">
              {save.error.message}
            </Notice>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export default function ObservabilityPage() {
  const observability = useObservability();
  return (
    <Page>
      <PageHeader
        title="Observabilidade"
        subtitle="Envio de traces ao Langfuse. Metadados sempre; texto de prompt e resposta só com a captura ligada."
      />
      {observability.isError ? (
        <LoadError what="a observabilidade" error={observability.error} onRetry={() => void observability.refetch()} />
      ) : observability.isPending ? (
        <Skeleton height={260} style={{ borderRadius: 8 }} />
      ) : (
        <>
          <LangfusePanel view={observability.data} />
          <CapturePanel view={observability.data} />
        </>
      )}
    </Page>
  );
}
