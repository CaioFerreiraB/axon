/** A marca Axon (ADR-038; 013 research R15, R16): símbolo, wordmark e lockup dos arquivos do `brand-kit`, cada um nas
 * duas versões — para fundo claro e para fundo escuro —, e o CSS mostra a do tema em vigor, inclusive o escolhido na
 * console. Imagens, e não SVG embutido: o degradê e a máscara não repetem ids entre instâncias. */

import lockupDark from "../../brand/axon-lockup-dark.svg";
import lockupLight from "../../brand/axon-lockup-light.svg";
import symbolLight from "../../brand/axon-symbol-light.svg";
import symbolDark from "../../brand/axon-symbol.svg";
import wordmarkDark from "../../brand/axon-wordmark-dark.svg";
import wordmarkLight from "../../brand/axon-wordmark-light.svg";
import styles from "./Mark.module.css";

/** Largura sobre altura de cada arquivo (`viewBox`). */
const LOCKUP_RATIO = 435 / 132;
const WORDMARK_RATIO = 252.12 / 62.78;

function Themed({
  light,
  dark,
  height,
  ratio,
  alt,
  className,
}: {
  light: string;
  dark: string;
  height: number;
  ratio: number;
  alt: string;
  className?: string;
}) {
  const width = Math.round(height * ratio);
  return (
    <span className={className ? `${styles.mark} ${className}` : styles.mark}>
      <img className={styles.onLight} src={light} alt={alt} width={width} height={height} />
      <img className={styles.onDark} src={dark} alt={alt} width={width} height={height} />
    </span>
  );
}

export function AxonSymbol({ size, alt = "", className }: { size: number; alt?: string; className?: string }) {
  return <Themed light={symbolLight} dark={symbolDark} height={size} ratio={1} alt={alt} className={className} />;
}

/** `height` é a altura do arquivo; a altura de x do wordmark é 58,3/62,78 dela. */
export function AxonWordmark({ height }: { height: number }) {
  return <Themed light={wordmarkLight} dark={wordmarkDark} height={height} ratio={WORDMARK_RATIO} alt="Axon" />;
}

export function AxonLockup({ height }: { height: number }) {
  return <Themed light={lockupLight} dark={lockupDark} height={height} ratio={LOCKUP_RATIO} alt="Axon" />;
}
