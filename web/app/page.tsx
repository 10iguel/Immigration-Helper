import { ClearPathApp } from "./clearpath-app";
import styles from "./page.module.css";

export default function Home() {
  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <h1>ClearPath for Immigration</h1>
        <p className={styles.disclaimer}>
          Answers come only from the official I-130, I-131, I-485 and I-765 instructions. This is not legal advice.
          Confirm important details on uscis.gov or with an immigration attorney.
        </p>
      </header>
      <ClearPathApp />
    </main>
  );
}
