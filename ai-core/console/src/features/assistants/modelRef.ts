/** Referência de modelo `provider/modelo` (006 `ModelRef.parse`): o provider vai até o primeiro `/`, e o modelo pode
 * conter outros (`openrouter/openai/gpt-4.1-mini`). Puro. */

import type { Provider } from "../../api/schemas";

export type RefParts = { provider: string; model: string };

export function splitRef(ref: string | undefined): RefParts {
  const text = ref?.trim() ?? "";
  const slash = text.indexOf("/");
  return slash < 0 ? { provider: "", model: text } : { provider: text.slice(0, slash), model: text.slice(slash + 1) };
}

/** A referência inteira, ou vazia quando falta o modelo ou o provider. */
export function joinRef({ provider, model }: RefParts): string {
  const name = model.trim();
  return provider && name ? `${provider}/${name}` : "";
}

export type ProviderOption = { name: string; ready: boolean; detail: string | null };

/** Os prontos, mais os que já estão em uso (`current`) mesmo sem estar prontos — a escolha nunca troca sozinha. */
export function providerOptions(providers: Provider[] | undefined, current: string[]): ProviderOption[] {
  const known = new Map((providers ?? []).map((p) => [p.name, p]));
  const names = new Set([...(providers ?? []).filter((p) => p.ready).map((p) => p.name), ...current.filter(Boolean)]);
  return [...names]
    .map((name) => known.get(name) ?? { name, ready: providers === undefined, detail: null })
    .sort((a, b) => Number(b.ready) - Number(a.ready) || a.name.localeCompare(b.name));
}

/** O provider de um campo sem escolha: o primeiro pronto. */
export function defaultProvider(providers: Provider[] | undefined): string {
  return (providers ?? []).find((p) => p.ready)?.name ?? "";
}

export function optionLabel(option: ProviderOption): string {
  return option.ready ? option.name : `${option.name} · indisponível`;
}
