import Link from "next/link";
import { Wordmark } from "@/components/brand";
import { legal } from "@/lib/legal";

export function SiteFooter({ compact = false }: { readonly compact?: boolean }) {
  return (
    <footer
      className={
        compact
          ? "flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-muted-foreground text-sm"
          : "mt-6 flex flex-col gap-4 border-t pt-6 text-muted-foreground text-sm sm:flex-row sm:items-center sm:justify-between"
      }
    >
      {compact ? null : (
        <p className="m-0">
          <Wordmark className="text-foreground" /> is read-only. It can never trade.
        </p>
      )}
      <nav aria-label="Legal" className="flex flex-wrap gap-x-4 gap-y-1">
        <Link className="hover:text-foreground hover:underline" href="/terms">
          Terms
        </Link>
        <Link className="hover:text-foreground hover:underline" href="/privacy">
          Privacy
        </Link>
        <a className="hover:text-foreground hover:underline" href={legal.marketingUrl}>
          slash.markets
        </a>
      </nav>
    </footer>
  );
}
