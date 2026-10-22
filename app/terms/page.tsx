import { MarketsLabel } from "@/components/brand";
import { legal } from "@/lib/legal";
import { LegalPage, type LegalSection, legalMetadata } from "../_components/legal-page";

export const metadata = legalMetadata(
  "Terms of Service",
  "The terms that govern your use of /markets: a read-only market data and alerting service for Claude and ChatGPT.",
);

const P = ({ children }: { readonly children: string }) => (
  <span className="placeholder">{children}</span>
);

const sections: readonly LegalSection[] = [
  {
    id: "about",
    title: "Who we are and what these terms cover",
    body: (
      <>
        <p>
          <MarketsLabel /> (the “Service”) is operated by <P>{legal.companyName}</P>,{" "}
          <P>{legal.companyType}</P>, with its registered office at <P>{legal.registeredAddress}</P>{" "}
          (“we”, “us”, “our”). The Service consists of the website at {legal.marketingUrl}, the
          account application at {legal.appUrl}, the connector that AI assistants such as Claude and
          ChatGPT use to reach it, the Python library those assistants write against, and the
          watcher alerts we send by email.
        </p>
        <p>
          These Terms of Service (“Terms”) are a legally binding agreement between you and us. By
          creating an account, connecting the Service to an AI assistant, or using the Service in
          any other way, you accept these Terms and our <a href="/privacy">Privacy Policy</a>. If
          you do not agree, do not use the Service.
        </p>
      </>
    ),
  },
  {
    id: "eligibility",
    title: "Eligibility",
    body: (
      <>
        <p>To use the Service you must:</p>
        <ul>
          <li>be at least 18 years old and able to enter into a binding contract;</li>
          <li>
            hold a trading account with Zerodha Broking Limited (“Zerodha”) that you are entitled to
            access through Zerodha’s Kite Connect interface;
          </li>
          <li>use the Service only for your own account and not on behalf of anyone else;</li>
          <li>not be barred from using the Service under any applicable law or regulation.</li>
        </ul>
        <p>
          The Service currently supports Indian markets only. We may add or remove markets, brokers
          and AI assistants at any time.
        </p>
      </>
    ),
  },
  {
    id: "account",
    title: "Your account",
    body: (
      <>
        <p>
          You sign in with your email address and a one-time code we send to it. You are responsible
          for keeping access to that email address secure and for everything that happens under your
          account. Tell us at <P>{legal.supportEmail}</P> as soon as you suspect unauthorised use.
        </p>
        <p>
          You may hold one account per email address. We may suspend or close accounts that breach
          these Terms, that are used fraudulently, or that have been inactive for more than twelve
          months.
        </p>
      </>
    ),
  },
  {
    id: "zerodha",
    title: "Connecting your Zerodha account",
    body: (
      <>
        <p>
          You connect Zerodha by logging in on Zerodha’s own website through Kite Connect. Zerodha
          then issues the Service a session token for your account. We never see your Zerodha
          password, PIN or two-factor code. We store the session token encrypted and use it solely
          to make read requests on your behalf. You can end the connection at any time from your
          account page, and Zerodha ends every session during its daily reset.
        </p>
        <p>
          Your use of Zerodha and Kite Connect is governed by Zerodha’s own terms and policies.
          Market data obtained through Zerodha is provided for your personal use. You must not
          redistribute, resell or publish that data, or use the Service to build a competing data
          feed, except as Zerodha and the relevant exchanges permit.
        </p>
        <p>
          <strong>The Service is read-only.</strong> It contains no facility to place, modify or
          cancel orders, transfer funds, or change any setting of your Zerodha account, and it does
          not authorise your AI assistant to do so. You remain solely responsible for every order
          you place through any channel.
        </p>
      </>
    ),
  },
  {
    id: "ai",
    title: "Using the Service through an AI assistant",
    body: (
      <>
        <p>
          The Service works inside AI assistants you already use, such as Claude by Anthropic and
          ChatGPT by OpenAI (“AI Providers”). When you connect the Service to an AI assistant, the
          assistant writes small programs that run on our servers against your data and returns only
          what those programs print. You should understand that:
        </p>
        <ul>
          <li>
            the AI assistant decides what to request and what to show you; its answers may be wrong,
            incomplete or out of date, and you must check them before relying on them;
          </li>
          <li>
            whatever the assistant prints is transmitted to and processed by your AI Provider under
            that provider’s own terms and privacy policy, which we do not control;
          </li>
          <li>
            you must not use the assistant or the Service to circumvent rate limits, access other
            people’s data, or run programs for any purpose other than analysing markets and your own
            account;
          </li>
          <li>
            you are responsible for the AI Provider account you use and for any fees it charges.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "watchers",
    title: "Watchers and alerts",
    body: (
      <>
        <p>
          Watchers are conditions your AI assistant sets up on your instruction. The Service checks
          them on a schedule during market hours and emails you when a condition becomes true.
          Alerts are informational. We do not guarantee that a check will run at any particular
          time, that an alert will be delivered or delivered promptly, or that a condition will be
          detected before the market moves. Watchers pause automatically when your Zerodha session
          ends and expire after the period shown on your account page. You can pause, resume or
          cancel them there at any time.
        </p>
      </>
    ),
  },
  {
    id: "advice",
    title: "No investment advice",
    body: (
      <>
        <p>
          The Service provides market data, calculations and tools for information and research
          only. Nothing in the Service, in an alert, or in an answer produced with the Service is
          investment advice, a research report, a recommendation, or an offer or solicitation to
          buy, sell or hold any security, derivative, commodity or currency. We are not a stock
          broker, investment adviser or research analyst registered with the Securities and Exchange
          Board of India (SEBI), and we do not manage money or execute trades.
        </p>
        <p>
          Trading and investing involve substantial risk, including the loss of all capital
          invested, and derivatives carry additional risk. You alone decide whether to trade and
          bear the consequences. For advice suited to your circumstances consult a SEBI-registered
          investment adviser.
        </p>
      </>
    ),
  },
  {
    id: "acceptable-use",
    title: "Acceptable use",
    body: (
      <>
        <p>You agree not to:</p>
        <ul>
          <li>share your sign-in codes, session or connector credentials with anyone;</li>
          <li>
            access or attempt to access another person’s account, data or watchers, or probe, scan
            or test the Service’s security without our written permission;
          </li>
          <li>
            send programs that attempt to escape the execution sandbox, mine cryptocurrency, attack
            other systems, or consume resources beyond the documented limits;
          </li>
          <li>
            use the Service to redistribute market data, to operate a service for others, or to
            build a product that competes with the Service, except as the open-source licence in
            section 10 allows;
          </li>
          <li>
            use the Service for market manipulation, insider dealing or any activity that violates
            securities law, exchange rules or Zerodha’s terms;
          </li>
          <li>interfere with the Service or with other users’ use of it.</li>
        </ul>
        <p>
          We apply fair-use limits on the number of requests, scripts and watchers per account.
          Current limits are shown in the connector’s documentation and may change.
        </p>
      </>
    ),
  },
  {
    id: "fees",
    title: "Fees",
    body: (
      <>
        <p>
          The Service is currently offered free of charge while it is in early access. We may
          introduce paid plans in future. If we do, we will publish the prices in advance, and
          continued use after the effective date will be subject to them. Charges from Zerodha, the
          exchanges or your AI Provider are separate and are your responsibility.
        </p>
      </>
    ),
  },
  {
    id: "ip",
    title: "Intellectual property and open source",
    body: (
      <>
        <p>
          The Service’s software is published under the MIT licence at {legal.openSourceUrl}. The
          licence covers the code only. The <MarketsLabel /> name, logomark, wordmark, artwork,
          website copy and brand assets are our property or our licensors’ and are not licensed to
          you except to identify the Service. You must not use them in a way that suggests we
          endorse you or your products.
        </p>
        <p>
          You keep all rights in the instructions, programs and watcher definitions you create. You
          grant us a licence to store and run them to the extent needed to provide the Service to
          you.
        </p>
      </>
    ),
  },
  {
    id: "availability",
    title: "Availability and changes",
    body: (
      <>
        <p>
          The Service is in early access. It may be interrupted, rate-limited, changed or withdrawn
          without notice, including because of maintenance, outages at Zerodha, the exchanges, our
          hosting providers or your AI Provider, or regulatory requirements. We will make reasonable
          efforts to announce planned downtime and material changes on the account page or by email.
        </p>
      </>
    ),
  },
  {
    id: "disclaimer",
    title: "Disclaimer of warranties",
    body: (
      <>
        <p>
          To the fullest extent permitted by law, the Service is provided “as is” and “as available”
          without warranties of any kind, express or implied, including warranties of
          merchantability, fitness for a particular purpose, accuracy, timeliness and
          non-infringement. Market data may be delayed, incomplete or incorrect. Computed values
          such as implied volatility, option greeks, indicators and P&amp;L are estimates and may
          differ from figures shown by Zerodha or the exchanges.
        </p>
      </>
    ),
  },
  {
    id: "liability",
    title: "Limitation of liability",
    body: (
      <>
        <p>
          To the fullest extent permitted by law, we and our directors, employees and suppliers are
          not liable for any trading or investment loss, loss of profit, revenue, data or goodwill,
          or any indirect, incidental, special, consequential or punitive loss arising out of or in
          connection with the Service or these Terms, however caused and under any theory of
          liability, even if we were advised of the possibility of such loss.
        </p>
        <p>
          Our total liability to you for all claims arising out of or relating to the Service in any
          twelve-month period will not exceed the greater of the fees you paid us in that period and
          ₹1,000.
        </p>
        <p>Nothing in these Terms limits liability that cannot be limited under applicable law.</p>
      </>
    ),
  },
  {
    id: "indemnity",
    title: "Indemnity",
    body: (
      <p>
        You will indemnify and hold us harmless from any claim, loss, liability and expense
        (including reasonable legal fees) arising from your breach of these Terms, your misuse of
        the Service, or your violation of any law or of the rights of a third party.
      </p>
    ),
  },
  {
    id: "termination",
    title: "Termination",
    body: (
      <>
        <p>
          You may stop using the Service at any time by disconnecting Zerodha, removing the
          connector from your AI assistant, and asking us at <P>{legal.supportEmail}</P> to delete
          your account. We may suspend or terminate your access immediately if you breach these
          Terms, if required by law or by Zerodha, or if we discontinue the Service. Sections 7 and
          10 to 16 survive termination.
        </p>
      </>
    ),
  },
  {
    id: "changes",
    title: "Changes to these Terms",
    body: (
      <p>
        We may update these Terms. For material changes we will give at least 15 days’ notice by
        email or on the account page before they take effect. The “last updated” date above shows
        the current version. Your continued use after the effective date is acceptance of the
        updated Terms.
      </p>
    ),
  },
  {
    id: "law",
    title: "Governing law and disputes",
    body: (
      <>
        <p>
          These Terms are governed by the laws of India. Subject to any mandatory consumer
          protection law, the courts at <P>{legal.governingCity}</P> have exclusive jurisdiction
          over any dispute arising out of or relating to the Service or these Terms. Before starting
          proceedings, you agree to contact us at <P>{legal.supportEmail}</P> and give us 30 days to
          resolve the matter.
        </p>
      </>
    ),
  },
  {
    id: "grievance",
    title: "Grievance officer and contact",
    body: (
      <>
        <p>
          In accordance with the Information Technology Act, 2000 and the rules made under it, our
          Grievance Officer is:
        </p>
        <p>
          <P>{legal.grievanceOfficer}</P>
          <br />
          <P>{legal.companyName}</P>, <P>{legal.registeredAddress}</P>
          <br />
          <P>{legal.grievanceEmail}</P>
        </p>
        <p>
          We acknowledge complaints within 24 hours and aim to resolve them within 15 days. For
          general questions write to <P>{legal.supportEmail}</P>.
        </p>
        <p>
          These Terms, together with the Privacy Policy, are the entire agreement between you and us
          about the Service. If any provision is held unenforceable, the rest remains in effect. Our
          failure to enforce a provision is not a waiver of it. You may not assign these Terms; we
          may assign them to a successor of the Service.
        </p>
      </>
    ),
  },
];

export default function TermsPage() {
  return (
    <LegalPage
      intro={
        <>
          <p>
            In short: <MarketsLabel /> lets an AI assistant you already use read your Zerodha
            account and Indian market data, and emails you when a condition you set becomes true. It
            is read-only and can never trade. It is a research tool, not investment advice. You
            decide what to do with what it shows you.
          </p>
          <p>The full terms below are what actually applies.</p>
        </>
      }
      sections={sections}
      title="Terms of Service"
    />
  );
}
