import { MarketsLabel } from "@/components/brand";
import { legal } from "@/lib/legal";
import { LegalPage, type LegalSection, legalMetadata } from "../_components/legal-page";

export const metadata = legalMetadata(
  "Support",
  "How to reach the /markets team, what to include, and where the policies live.",
);

const sections: readonly LegalSection[] = [
  {
    id: "contact",
    title: "Contact us",
    body: (
      <>
        <p>
          Email <a href={`mailto:${legal.supportEmail}`}>{legal.supportEmail}</a> from the address
          you signed in with. We reply within two business days (Indian business hours, Monday to
          Friday).
        </p>
        <p>
          Privacy requests, including account deletion, go to{" "}
          <a href={`mailto:${legal.privacyEmail}`}>{legal.privacyEmail}</a>. Our grievance officer
          under India&apos;s IT rules is {legal.grievanceOfficer} (
          <a href={`mailto:${legal.grievanceEmail}`}>{legal.grievanceEmail}</a>).
        </p>
      </>
    ),
  },
  {
    id: "include",
    title: "What to include",
    body: (
      <ul>
        <li>
          The email address of your <MarketsLabel /> account.
        </li>
        <li>
          Which AI assistant you use (Claude or ChatGPT) and roughly when the problem happened (date
          and time, IST).
        </li>
        <li>
          What you asked and what came back. Never send your Zerodha password, TOTP or any one-time
          code; we will never ask for them.
        </li>
      </ul>
    ),
  },
  {
    id: "common",
    title: "Common questions",
    body: (
      <>
        <p>
          <strong>&ldquo;The session has expired&rdquo;:</strong> Zerodha ends every Kite session
          during its overnight reset. Open the account page at {legal.appUrl}, log in to Zerodha
          again, and your watchers resume by themselves.
        </p>
        <p>
          <strong>Watchers:</strong> your assistant creates them; pausing, resuming and cancelling
          happens on the account page. The first check is a baseline and never alerts.
        </p>
        <p>
          <strong>Trading:</strong> <MarketsLabel /> is read-only and can never place, modify or
          cancel orders. Trade in Kite.
        </p>
      </>
    ),
  },
  {
    id: "policies",
    title: "Policies and source",
    body: (
      <p>
        <a href="/terms">Terms of Service</a> · <a href="/privacy">Privacy Policy</a> · the server
        is open source at <a href={legal.openSourceUrl}>{legal.openSourceUrl}</a>.
      </p>
    ),
  },
];

export default function SupportPage() {
  return (
    <LegalPage
      intro={
        <p>
          Help with your <MarketsLabel /> account, the Zerodha connection, watchers, or the
          connector in Claude and ChatGPT.
        </p>
      }
      sections={sections}
      title="Support"
    />
  );
}
