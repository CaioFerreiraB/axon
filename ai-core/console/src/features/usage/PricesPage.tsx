/** Tabela de preços (013 FR-011): USD por milhão de tokens, com vigência. O custo é calculado na consulta: um preço
 * com data no passado recalcula o histórico. Modelos usados sem preço aparecem destacados. Provider que informa o
 * custo de cada chamada (o OpenRouter) não tem preço a cadastrar (ADR-036): fica fora do formulário. */

import { useMemo, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";

import { fieldError } from "../../api/errors";
import { useProviders } from "../../api/hooks/assistants";
import { useAddPrice, usePrices, useUnpriced, useUsage } from "../../api/hooks/usage";
import type { Price, Provider } from "../../api/schemas";
import { formatFullDay, formatInstantDay, formatInteger, formatPrice } from "../../i18n/format";
import { Badge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Field, Select, TextInput } from "../../ui/Field";
import { Notice } from "../../ui/Notice";
import { Page, PageHeader } from "../../ui/Page";
import { Panel } from "../../ui/Panel";
import { EmptyState, LoadError, Skeleton } from "../../ui/States";
import { Table, tableStyles as t } from "../../ui/Table";
import { defaultProvider, joinRef, optionLabel, splitRef, type ProviderOption } from "../assistants/modelRef";
import { addDays } from "./period";
import { reportsCost } from "./series";
import styles from "./PricesPage.module.css";

const DECIMAL = /^\d+([.,]\d+)?$/;

type Row = { price: Price; until: string | null };

function rowsOf(prices: Price[]): Row[] {
  const byModel = new Map<string, Price[]>();
  for (const price of prices) {
    const key = `${price.provider}/${price.model}`;
    byModel.set(key, [...(byModel.get(key) ?? []), price]);
  }
  const rows: Row[] = [];
  for (const list of byModel.values()) {
    const sorted = [...list].sort((a, b) => b.effective_from.localeCompare(a.effective_from));
    sorted.forEach((price, index) => {
      const newer = sorted[index - 1];
      rows.push({ price, until: newer ? addDays(newer.effective_from, -1) : null });
    });
  }
  return rows.sort((a, b) => {
    const order = (row: Row) => (row.price.state === "superseded" ? 1 : 0);
    return (
      `${a.price.provider}/${a.price.model}`.localeCompare(`${b.price.provider}/${b.price.model}`) ||
      order(a) - order(b) ||
      b.price.effective_from.localeCompare(a.price.effective_from)
    );
  });
}

function PriceForm({
  model,
  onDone,
  unpricedCalls,
}: {
  model: string;
  onDone: () => void;
  unpricedCalls: (m: string) => number;
}) {
  const add = useAddPrice();
  const providers = useProviders();
  const priceable: Provider[] | undefined = providers.data?.filter((option) => !option.reports_cost);
  const [draft, setDraft] = useState({ ...splitRef(model), input: "", output: "", from: "" });
  const [shapeError, setShapeError] = useState<Record<string, string>>({});
  const set = (field: keyof typeof draft) => (event: { target: { value: string } }) =>
    setDraft((current) => ({ ...current, [field]: event.target.value }));
  // Preço também vale para provider fora do ar: a lista tem todos os registrados que não informam o custo, os prontos
  // primeiro.
  const provider = draft.provider || defaultProvider(priceable);
  const options: ProviderOption[] = [...(priceable ?? [])].sort(
    (a, b) => Number(b.ready) - Number(a.ready) || a.name.localeCompare(b.name),
  );
  if (provider && !options.some((option) => option.name === provider)) {
    options.unshift({ name: provider, ready: providers.data === undefined, detail: null });
  }
  const ref = joinRef({ provider, model: draft.model });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (!provider) {
      errors.provider = "Escolha o provedor.";
    }
    if (!draft.model.trim()) {
      errors.model = "Informe o modelo, como openai/gpt-4.1-mini.";
    }
    for (const field of ["input", "output"] as const) {
      if (!DECIMAL.test(draft[field].trim())) {
        errors[field] = "Um número, como 0,40.";
      }
    }
    if (!draft.from) {
      errors.effective_from = "Escolha a data de início.";
    }
    setShapeError(errors);
    if (Object.keys(errors).length > 0) {
      return;
    }
    add.mutate(
      {
        provider,
        model: draft.model.trim(),
        input: draft.input.trim().replace(",", "."),
        output: draft.output.trim().replace(",", "."),
        effective_from: draft.from,
      },
      { onSuccess: onDone },
    );
  };

  const error = (field: string) => shapeError[field] ?? fieldError(add.error, field);
  const calls = unpricedCalls(ref);
  if (reportsCost(`${provider}/`, providers.data)) {
    return (
      <Notice
        tone="info"
        title={`${provider} informa o custo de cada chamada`}
        action={{ label: "Fechar", onClick: onDone }}
      >
        Não há preço a cadastrar para {joinRef(splitRef(model)) || provider}: o custo vem de cada chamada. As chamadas
        sem custo informado, como as anteriores a essa mudança, ficam como “não informado”.
      </Notice>
    );
  }
  return (
    <Panel title="Novo preço" labelledBy="novo-preco">
      <form onSubmit={submit} noValidate>
        <div className={styles.form}>
          <Field label="Provedor" error={error("provider")}>
            <Select mono value={provider} onChange={set("provider")}>
              {provider === "" ? <option value="">Nenhum provedor</option> : null}
              {options.map((option) => (
                <option key={option.name} value={option.name}>
                  {optionLabel(option)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Modelo" error={error("model")}>
            <TextInput mono value={draft.model} onChange={set("model")} placeholder="autor/modelo" autoComplete="off" />
          </Field>
          <Field label="Entrada (US$ / 1 M)" error={error("input")}>
            <TextInput inputMode="decimal" value={draft.input} onChange={set("input")} placeholder="0,00" />
          </Field>
          <Field label="Saída (US$ / 1 M)" error={error("output")}>
            <TextInput inputMode="decimal" value={draft.output} onChange={set("output")} placeholder="0,00" />
          </Field>
          <Field label="Vigente desde" error={error("effective_from")}>
            <TextInput type="date" value={draft.from} onChange={set("from")} />
          </Field>
          <div className={styles.formActions}>
            <Button variant="ghost" onClick={onDone}>
              Cancelar
            </Button>
            <Button variant="primary" type="submit" busy={add.isPending}>
              Salvar preço
            </Button>
          </div>
        </div>
        <p className={styles.formNote}>
          {calls > 0 ? `${ref} foi usado sem preço em ${formatInteger(calls)} chamadas. ` : ""}
          Uma data no passado recalcula o custo desde ela; preço zero tira o modelo de “sem preço”.
        </p>
      </form>
    </Panel>
  );
}

export default function PricesPage() {
  const [params, setParams] = useSearchParams();
  const prefill = params.get("modelo");
  const [open, setOpen] = useState(prefill !== null);
  const prices = usePrices();
  const providers = useProviders();
  const unpriced = useUnpriced({});
  const usage = useUsage({ by: "model", origin: "all" });
  const rows = useMemo(() => rowsOf(prices.data ?? []), [prices.data]);
  const pricedKeys = new Set(rows.map((row) => `${row.price.provider}/${row.price.model}`));
  const missing = (unpriced.data ?? []).filter((key) => !pricedKeys.has(key) && !reportsCost(key, providers.data));
  const callsOf = (model: string) => usage.data?.totals.find((row) => row.key === model && !row.priced)?.calls ?? 0;

  const close = () => {
    setOpen(false);
    if (prefill !== null) {
      const next = new URLSearchParams(params);
      next.delete("modelo");
      setParams(next, { replace: true });
    }
  };

  return (
    <Page>
      <PageHeader
        back={{ to: "/uso", label: "Uso e custo" }}
        title="Tabela de preços"
        subtitle="US$ por 1 milhão de tokens. O custo é calculado na consulta, pelo preço vigente em cada dia."
        actions={
          <Button variant="primary" icon="mais" disabled={open} onClick={() => setOpen(true)}>
            Novo preço
          </Button>
        }
      />
      {open ? <PriceForm model={prefill ?? missing[0] ?? ""} onDone={close} unpricedCalls={callsOf} /> : null}
      {prices.isError ? (
        <LoadError what="os preços" error={prices.error} onRetry={() => void prices.refetch()} />
      ) : prices.isPending ? (
        <Skeleton height={180} style={{ borderRadius: 8 }} />
      ) : rows.length === 0 && missing.length === 0 ? (
        <Panel>
          <EmptyState title="Nenhum preço cadastrado">
            Cadastre o preço de cada modelo para o dashboard calcular o custo. Sem preço, as chamadas contam, mas ficam
            fora do custo.
          </EmptyState>
        </Panel>
      ) : (
        <Table caption="Preços por modelo, com vigência">
          <thead>
            <tr>
              <th scope="col">Modelo</th>
              <th scope="col" className={t.num}>
                Entrada
              </th>
              <th scope="col" className={t.num}>
                Saída
              </th>
              <th scope="col">Vigência</th>
              <th scope="col">Cadastrado por</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ price, until }) => {
              const superseded = price.state === "superseded";
              return (
                <tr
                  key={`${price.provider}/${price.model}@${price.effective_from}`}
                  className={superseded ? t.muted : undefined}
                >
                  <th scope="row" className={t.mono} style={{ fontWeight: 400 }}>
                    {price.provider}/{price.model}
                  </th>
                  <td className={t.num}>{formatPrice(price.input)}</td>
                  <td className={t.num}>{formatPrice(price.output)}</td>
                  <td>
                    <span className={styles.vigencia}>
                      {superseded && until
                        ? `${formatInstantDay(`${price.effective_from}T12:00:00`)} a ${formatFullDay(until)}`
                        : price.state === "scheduled"
                          ? `a partir de ${formatFullDay(price.effective_from)}`
                          : `desde ${formatFullDay(price.effective_from)}`}
                      <Badge tone={superseded ? "neutral" : price.state === "scheduled" ? "accent" : "ok"}>
                        {superseded ? "Substituído" : price.state === "scheduled" ? "Agendado" : "Vigente"}
                      </Badge>
                    </span>
                  </td>
                  <td className={styles.by}>
                    {price.created_by.split(":").pop()} · {formatInstantDay(price.created_at)}
                  </td>
                </tr>
              );
            })}
            {missing.map((key) => (
              <tr key={key}>
                <th scope="row" className={t.mono} style={{ fontWeight: 400 }}>
                  {key}
                </th>
                <td className={t.num}>—</td>
                <td className={t.num}>—</td>
                <td>
                  <span className={styles.vigencia}>
                    — <Badge tone="warn">Sem preço</Badge>
                  </span>
                </td>
                <td className={styles.by}>—</td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Page>
  );
}
