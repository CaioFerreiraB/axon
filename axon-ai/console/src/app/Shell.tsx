import { Suspense, useState } from "react";
import { Outlet } from "react-router";

import { useMe } from "../api/hooks/me";
import { PageChromeSetter, PageTitleSuffix, type PageChrome } from "../ui/Page";
import { AppBar } from "./AppBar";
import { BottomNav } from "./BottomNav";
import { PageSkeleton } from "./PageSkeleton";
import styles from "./Shell.module.css";
import { Sidebar } from "./Sidebar";

/** A casca: barra lateral (trilho abaixo de 1100px) e, abaixo de 640px, cabeçalho de app e barra inferior no lugar
 * dela (013 FR-046, R38). */
export function Shell() {
  const name = useMe().data?.instance.name ?? "Axon";
  const [chrome, setChrome] = useState<PageChrome | null>(null);
  return (
    <PageTitleSuffix.Provider value={name}>
      <PageChromeSetter.Provider value={setChrome}>
        <div className={styles.shell}>
          <a href="#conteudo" className={styles.skip}>
            Ir para o conteúdo
          </a>
          <Sidebar />
          <div className={styles.column}>
            <AppBar chrome={chrome} />
            <main id="conteudo" className={styles.main} tabIndex={-1}>
              <Suspense fallback={<PageSkeleton />}>
                <Outlet />
              </Suspense>
            </main>
          </div>
          <BottomNav />
        </div>
      </PageChromeSetter.Provider>
    </PageTitleSuffix.Provider>
  );
}
