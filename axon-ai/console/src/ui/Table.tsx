import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
  type TableHTMLAttributes,
} from "react";

import styles from "./Table.module.css";

/** O texto de cada coluna do cabeçalho, pela posição (com `colSpan`), para os rótulos da lista do celular. */
function headerLabels(table: HTMLTableElement): string[] {
  const labels: string[] = [];
  const row = table.tHead?.rows[0];
  for (const cell of Array.from(row?.cells ?? [])) {
    const text = (cell.textContent ?? "").replace(/\s+/g, " ").trim();
    for (let span = 0; span < cell.colSpan; span++) {
      labels.push(text);
    }
  }
  return labels;
}

/** Abaixo de 640px, a tabela vira lista de linhas (013 FR-048, R39): cada célula do corpo e do rodapé ganha o rótulo
 * da coluna em `data-label`, que o CSS mostra antes do valor. Linhas que chegam depois também ganham. */
function useCellLabels(table: RefObject<HTMLTableElement | null>) {
  useLayoutEffect(() => {
    const element = table.current;
    if (!element) {
      return;
    }
    const label = () => {
      const labels = headerLabels(element);
      // Com `display: block` (a lista do celular), o Safari tira a semântica de tabela: os papéis explícitos a mantêm.
      for (const node of Array.from(element.querySelectorAll<HTMLElement>("thead, tbody, tfoot, tr, th, td"))) {
        const role =
          node.tagName === "TR"
            ? "row"
            : node.tagName === "TD"
              ? "cell"
              : node.tagName === "TH"
                ? node.getAttribute("scope") === "row"
                  ? "rowheader"
                  : "columnheader"
                : "rowgroup";
        if (node.getAttribute("role") !== role) {
          node.setAttribute("role", role);
        }
      }
      if (element.getAttribute("role") !== "table") {
        element.setAttribute("role", "table");
      }
      for (const section of [...Array.from(element.tBodies), element.tFoot]) {
        for (const row of Array.from(section?.rows ?? [])) {
          let column = 0;
          for (const cell of Array.from(row.cells)) {
            const text = labels[column] ?? "";
            if (cell.dataset.label !== text) {
              cell.dataset.label = text;
            }
            column += cell.colSpan;
          }
        }
      }
    };
    label();
    if (typeof MutationObserver === "undefined") {
      return;
    }
    const observer = new MutationObserver(label);
    observer.observe(element, { childList: true, subtree: true, characterData: true });
    // Os papéis e rótulos postos aqui mudam atributos, não a lista de filhos: o observador não se realimenta.
    return () => observer.disconnect();
  }, [table]);
}

/** Tabela no contêiner que rola na horizontal em telas estreitas. Quando rola, o contêiner vira uma região rotulada
 * que recebe foco, para a rolagem também ser possível pelo teclado (WCAG 2.1.1). No celular, vira lista de linhas,
 * a menos que `stack` seja falso. */
export function Table({
  caption,
  children,
  stack = true,
  ...rest
}: TableHTMLAttributes<HTMLTableElement> & { caption: string; children: ReactNode; stack?: boolean }) {
  const wrap = useRef<HTMLDivElement>(null);
  const table = useRef<HTMLTableElement>(null);
  useCellLabels(table);
  const [scrolls, setScrolls] = useState(false);
  useEffect(() => {
    const element = wrap.current;
    if (!element || typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver(() => setScrolls(element.scrollWidth > element.clientWidth + 1));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return (
    <div
      ref={wrap}
      className={stack ? `${styles.wrap} ${styles.stack}` : styles.wrap}
      {...(scrolls ? { tabIndex: 0, role: "region", "aria-label": caption } : {})}
    >
      <table ref={table} className={styles.table} {...rest}>
        <caption className="visually-hidden">{caption}</caption>
        {children}
      </table>
    </div>
  );
}

export const tableStyles = styles;
