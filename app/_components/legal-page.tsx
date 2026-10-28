import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { BrandHeader } from "@/components/brand";
import { legal } from "@/lib/legal";
import { SiteFooter } from "./site-footer";

export interface LegalSection {
  id: string;
  title: string;
  body: ReactNode;
}

export function legalMetadata(title: string, description: string): Metadata {
  return { title: `${title} · ${legal.productName}`, description, robots: { index: true } };
}

export function LegalPage({
  title,
  intro,
  sections,
}: {
  readonly title: string;
  readonly intro: ReactNode;
  readonly sections: readonly LegalSection[];
}) {
  return (
    <main className="min-h-dvh bg-background text-foreground">
      <div className="mx-auto flex max-w-3xl flex-col gap-8 px-5 pt-3 pb-16">
        <header className="glass sticky top-3 z-10 flex items-center gap-3 rounded-full border px-4 py-2">
          <Link aria-label={`${legal.productName} account`} className="min-w-0 flex-1" href="/">
            <BrandHeader />
          </Link>
          <nav aria-label="Legal pages" className="flex gap-4 text-sm">
            <Link className="text-muted-foreground hover:text-foreground" href="/terms">
              Terms
            </Link>
            <Link className="text-muted-foreground hover:text-foreground" href="/privacy">
              Privacy
            </Link>
            <Link className="text-muted-foreground hover:text-foreground" href="/support">
              Support
            </Link>
          </nav>
        </header>

        <article className="legal">
          <h1>{title}</h1>
          <p className="legal-meta">
            Effective {legal.effectiveDate} · Last updated {legal.lastUpdated}
          </p>
          <div className="legal-intro">{intro}</div>
          <nav aria-label="Contents" className="legal-toc">
            <ol>
              {sections.map((s, i) => (
                <li key={s.id}>
                  <a href={`#${s.id}`}>
                    {i + 1}. {s.title}
                  </a>
                </li>
              ))}
            </ol>
          </nav>
          {sections.map((s, i) => (
            <section aria-labelledby={`${s.id}-title`} id={s.id} key={s.id}>
              <h2 id={`${s.id}-title`}>
                {i + 1}. {s.title}
              </h2>
              {s.body}
            </section>
          ))}
        </article>

        <SiteFooter />
      </div>
    </main>
  );
}
