import { useEffect, useRef, useState, type ReactNode, type TableHTMLAttributes } from "react";

import styles from "./Table.module.css";

/** Tabela no contêiner que rola na horizontal em telas estreitas. Quando rola, o contêiner vira uma região rotulada
 * que recebe foco, para a rolagem também ser possível pelo teclado (WCAG 2.1.1). */
export function Table({
  caption,
  children,
  ...rest
}: TableHTMLAttributes<HTMLTableElement> & { caption: string; children: ReactNode }) {
  const wrap = useRef<HTMLDivElement>(null);
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
      className={styles.wrap}
      {...(scrolls ? { tabIndex: 0, role: "region", "aria-label": caption } : {})}
    >
      <table className={styles.table} {...rest}>
        <caption className="visually-hidden">{caption}</caption>
        {children}
      </table>
    </div>
  );
}

export const tableStyles = styles;
