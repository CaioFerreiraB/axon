import * as Switch from "@radix-ui/react-switch";

import styles from "./Toggle.module.css";

export function Toggle({
  checked,
  onChange,
  label,
  disabled = false,
  showLabel = false,
  describedBy,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
  showLabel?: boolean;
  describedBy?: string;
}) {
  const control = (
    <Switch.Root
      checked={checked}
      onCheckedChange={onChange}
      disabled={disabled}
      aria-label={showLabel ? undefined : label}
      aria-describedby={describedBy}
      className={styles.root}
    >
      <Switch.Thumb className={styles.thumb} />
    </Switch.Root>
  );
  if (!showLabel) {
    return control;
  }
  return (
    <label className={styles.row}>
      {label}
      {control}
    </label>
  );
}
