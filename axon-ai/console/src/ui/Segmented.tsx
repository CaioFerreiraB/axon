/** Escolha única entre poucas opções (período, agrupamento, filtro), com setas pelo teclado (Radix ToggleGroup). */

import * as ToggleGroup from "@radix-ui/react-toggle-group";
import type { ReactNode } from "react";

import styles from "./Segmented.module.css";
import { Icon, type IconName } from "./icons";

export type SegmentedOption<T extends string> = { value: T; label: ReactNode; icon?: IconName };

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  className,
}: {
  value: T;
  onChange: (value: T) => void;
  options: readonly SegmentedOption<T>[];
  label: string;
  className?: string;
}) {
  return (
    <ToggleGroup.Root
      type="single"
      value={value}
      onValueChange={(next) => {
        if (next) {
          onChange(next as T);
        }
      }}
      aria-label={label}
      className={className ? `${styles.group} ${className}` : styles.group}
    >
      {options.map((option) => (
        <ToggleGroup.Item
          key={option.value}
          value={option.value}
          className={option.icon ? `${styles.item} ${styles.iconItem}` : styles.item}
          aria-label={option.icon ? String(option.label) : undefined}
          title={option.icon ? String(option.label) : undefined}
        >
          {option.icon ? <Icon name={option.icon} size={14} /> : option.label}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}
