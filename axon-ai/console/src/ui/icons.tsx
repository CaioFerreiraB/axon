/** Os ícones do desenho aprovado no Penpot: 16 px, traço 1,5, pontas arredondadas, `currentColor` (013 R4). */

import type { SVGProps } from "react";

const PATHS = {
  uso: <path d="M2 13.5h12M4 11V8M8 11V3.5M12 11V6" />,
  assistente: (
    <>
      <rect x="2.75" y="5" width="10.5" height="8" rx="2" />
      <path d="M8 2.5V5M6 9.25v.5M10 9.25v.5" />
    </>
  ),
  mcp: <path d="M6 2v3M10 2v3M4 5h8v2.5a4 4 0 0 1-8 0V5ZM8 11.5v2.5" />,
  observabilidade: <path d="M1.5 8.5h3l2-5 3 9 2-4h3" />,
  acesso: (
    <>
      <circle cx="5.5" cy="10.5" r="3" />
      <path d="M7.6 8.4 13.5 2.5M11.25 4.75l1.75 1.75" />
    </>
  ),
  cadeado: (
    <>
      <rect x="3.25" y="7" width="9.5" height="7" rx="1.5" />
      <path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" />
    </>
  ),
  seta: <path d="M4.5 6.25 8 9.75l3.5-3.5" />,
  confere: <path d="m3.5 8.5 3 3 6-7" />,
  sol: (
    <>
      <circle cx="8" cy="8" r="2.75" />
      <path d="M8 1.5v1.25M8 13.25v1.25M1.5 8h1.25M13.25 8h1.25M3.4 3.4l.9.9M11.7 11.7l.9.9M3.4 12.6l.9-.9M11.7 4.3l.9-.9" />
    </>
  ),
  lua: <path d="M13 9.6A5.5 5.5 0 1 1 6.4 3a4.4 4.4 0 0 0 6.6 6.6Z" />,
  sistema: (
    <>
      <rect x="2" y="3" width="12" height="8" rx="1.5" />
      <path d="M5.5 13.5h5M8 11v2.5" />
    </>
  ),
  copiar: (
    <>
      <rect x="5.5" y="5.5" width="8" height="8" rx="1.5" />
      <path d="M10.5 3.5v-.25A1.25 1.25 0 0 0 9.25 2h-6A1.25 1.25 0 0 0 2 3.25v6A1.25 1.25 0 0 0 3.25 10.5h.25" />
    </>
  ),
  mais: <path d="M8 3v10M3 8h10" />,
  busca: (
    <>
      <circle cx="7" cy="7" r="4.25" />
      <path d="m10.25 10.25 3.25 3.25" />
    </>
  ),
  alerta: <path d="M8 2.25 14.25 13H1.75L8 2.25ZM8 6.5v3M8 11.4v.1" />,
  info: (
    <>
      <circle cx="8" cy="8" r="6" />
      <path d="M8 7.25v3.75M8 5v.1" />
    </>
  ),
  esquerda: <path d="M9.75 4 5.75 8l4 4" />,
  direita: <path d="m6.25 4 4 4-4 4" />,
  externo: <path d="M9 2.5h4.5V7M13.5 2.5 7.5 8.5M11.5 9.5v3a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1h3" />,
  sair: <path d="M6 13.5H3.5a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1H6M10.5 11l3-3-3-3M13.5 8H6" />,
  fechar: <path d="m4 4 8 8M12 4l-8 8" />,
  mais_acoes: <path d="M3.5 8h.1M8 8h.1M12.5 8h.1" />,
  pessoa: (
    <>
      <circle cx="8" cy="5.5" r="2.75" />
      <path d="M2.75 13.75c.8-2.3 2.9-3.5 5.25-3.5s4.45 1.2 5.25 3.5" />
    </>
  ),
  atualizar: <path d="M13.5 8A5.5 5.5 0 1 1 11.9 4.1M13.5 2.5v3h-3" />,
} as const;

export type IconName = keyof typeof PATHS;

type IconProps = Omit<SVGProps<SVGSVGElement>, "name"> & { name: IconName; size?: number; label?: string };

export function Icon({ name, size = 16, label, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={label ? undefined : true}
      role={label ? "img" : undefined}
      aria-label={label}
      focusable="false"
      {...rest}
    >
      {PATHS[name]}
    </svg>
  );
}

/** O "G" oficial do Google, só no lugar do login (013 R4). */
export function GoogleMark({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path
        fill="#4285F4"
        d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.26 21.3 7.31 24 12 24z"
      />
      <path
        fill="#FBBC05"
        d="M5.27 14.29c-.25-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29V6.62H1.29C.47 8.24 0 10.06 0 12s.47 3.76 1.29 5.38l3.98-3.09z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.62l3.98 3.09C6.22 6.86 8.87 4.75 12 4.75z"
      />
    </svg>
  );
}
