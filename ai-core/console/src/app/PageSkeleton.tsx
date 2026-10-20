import { Page } from "../ui/Page";
import { Skeleton } from "../ui/States";

/** Enquanto a tela sob demanda carrega: a forma do cabeçalho e de um painel. */
export function PageSkeleton() {
  return (
    <Page>
      <div aria-busy="true" aria-label="Carregando">
        <Skeleton width={180} height={26} />
        <Skeleton width={320} height={14} style={{ marginTop: 10 }} />
        <Skeleton height={220} style={{ marginTop: 28, borderRadius: 8 }} />
      </div>
    </Page>
  );
}
