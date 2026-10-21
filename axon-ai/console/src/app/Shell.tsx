import { Suspense } from "react";
import { Outlet } from "react-router";

import { useMe } from "../api/hooks/me";
import { PageTitleSuffix } from "../ui/Page";
import { PageSkeleton } from "./PageSkeleton";
import styles from "./Shell.module.css";
import { Sidebar } from "./Sidebar";

export function Shell() {
  const name = useMe().data?.instance.name ?? "Axon";
  return (
    <PageTitleSuffix.Provider value={name}>
      <div className={styles.shell}>
        <a href="#conteudo" className={styles.skip}>
          Ir para o conteúdo
        </a>
        <Sidebar />
        <main id="conteudo" className={styles.main} tabIndex={-1}>
          <Suspense fallback={<PageSkeleton />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </PageTitleSuffix.Provider>
  );
}
