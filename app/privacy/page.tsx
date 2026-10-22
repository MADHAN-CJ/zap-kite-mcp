import { MarketsLabel } from "@/components/brand";
import { legal } from "@/lib/legal";
import { LegalPage, type LegalSection, legalMetadata } from "../_components/legal-page";

export const metadata = legalMetadata(
  "Privacy Policy",
  "What /markets collects, why, where it is stored, who it is shared with, and the rights you have over it.",
);

const P = ({ children }: { readonly children: string }) => (
  <span className="placeholder">{children}</span>
);

const sections: readonly LegalSection[] = [
  {
    id: "scope",
    title: "Who this policy covers",
    body: (
      <>
        <p>
          This policy explains how <P>{legal.companyName}</P> (“we”, “us”) handles personal data
          when you use <MarketsLabel /> (the “Service”): the website at {legal.marketingUrl}, the
          account application at {legal.appUrl}, the connector used by AI assistants, and the emails
          we send. It is written to meet the Digital Personal Data Protection Act, 2023 and the
          Information Technology Act, 2000. We are the data fiduciary for the data described here.
        </p>
        <p>
          The policy does not cover Zerodha, Anthropic, OpenAI or any other company whose products
          you use alongside the Service. Their own policies apply to what they collect.
        </p>
      </>
    ),
  },
  {
    id: "data",
    title: "What we collect",
    body: (
      <>
        <h3>Account</h3>
        <ul>
          <li>Your email address, and the date you created the account.</li>
          <li>
            A one-way hash of each sign-in code we send you, with its expiry and the time it was
            used. We never store the code itself.
          </li>
        </ul>
        <h3>Zerodha connection</h3>
        <ul>
          <li>
            Your Zerodha client ID and the display name Zerodha returns, the time you connected, and
            when the session is expected to end.
          </li>
          <li>
            The Kite Connect session token Zerodha issues for your account, stored encrypted
            (AES-256-GCM). It is decrypted only inside our server at the moment a request is made to
            Zerodha on your behalf. We never receive your Zerodha password, PIN, two-factor code,
            bank details or PAN.
          </li>
        </ul>
        <h3>Use of the Service through an AI assistant</h3>
        <ul>
          <li>
            The programs your AI assistant sends to run. We keep each one on the server for up to 24
            hours so failures can be diagnosed, then delete it. We do not store the data those
            programs fetch from Zerodha, nor what they print, beyond returning it to the assistant.
          </li>
          <li>
            Files a program chooses to save in your private workspace on our server, until you
            delete them or your account is deleted.
          </li>
          <li>
            The connector registration your AI assistant creates (its name and redirect addresses)
            and one-way hashes of the access and refresh tokens we issue to it.
          </li>
        </ul>
        <h3>Watchers</h3>
        <ul>
          <li>
            Each watcher’s symbol, description, the program that evaluates it, its schedule and
            market, the latest value it reported, and the history of alerts it raised.
          </li>
        </ul>
        <h3>Technical</h3>
        <ul>
          <li>
            Server logs with the IP address, request path, timestamp and user agent of requests to
            the Service, kept for up to 30 days for security and troubleshooting.
          </li>
          <li>
            Email delivery metadata (address, subject, delivery status) held by our email provider.
          </li>
        </ul>
        <p>
          We use no advertising trackers and no third-party analytics on the account application.
          The application keeps your sign-in session in your browser’s local storage; it does not
          set tracking cookies.
        </p>
      </>
    ),
  },
  {
    id: "purpose",
    title: "Why we use it and on what basis",
    body: (
      <>
        <div className="legal-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Purpose</th>
                <th>Data</th>
                <th>Basis</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Signing you in and securing your account</td>
                <td>Email, sign-in code hashes, server logs</td>
                <td>Performance of our agreement with you; legitimate security interest</td>
              </tr>
              <tr>
                <td>Reading your Zerodha account and market data for you</td>
                <td>Zerodha client ID, encrypted session token</td>
                <td>Your consent, given when you log in to Zerodha through the Service</td>
              </tr>
              <tr>
                <td>Running the programs your AI assistant sends</td>
                <td>Programs, workspace files, connector tokens</td>
                <td>Performance of our agreement with you</td>
              </tr>
              <tr>
                <td>Checking watchers and emailing alerts</td>
                <td>Watcher definitions and results, email address</td>
                <td>Your consent, given when you ask the assistant to create a watcher</td>
              </tr>
              <tr>
                <td>Telling you when your Zerodha session has ended</td>
                <td>Email address, connection status</td>
                <td>Performance of our agreement with you</td>
              </tr>
              <tr>
                <td>Preventing abuse and keeping the Service available</td>
                <td>Server logs, request counts</td>
                <td>Legitimate interest; legal obligation</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>We do not sell personal data and we do not use it for advertising.</p>
      </>
    ),
  },
  {
    id: "sharing",
    title: "Who we share it with",
    body: (
      <>
        <ul>
          <li>
            <strong>Zerodha Broking Limited.</strong> Every read request made on your behalf is sent
            to Zerodha’s Kite Connect interface with your session token. Zerodha sees that the
            Service is accessing your account.
          </li>
          <li>
            <strong>Your AI Provider (for example Anthropic or OpenAI).</strong> Whatever a program
            prints is returned to the AI assistant you connected and becomes part of your
            conversation with that provider. This can include positions, holdings, funds, order
            history and market data. We do not control how your AI Provider stores or uses it;
            review its policy and settings.
          </li>
          <li>
            <strong>Service providers that host and operate the Service</strong>, acting on our
            instructions under contract: Neon (database hosting, Singapore), Vercel (website and
            account application hosting, United States), DigitalOcean (connector and watcher
            servers, Bangalore, India), and Resend (email delivery, United States).
          </li>
          <li>
            <strong>Authorities and others when required</strong> to comply with law, a court order
            or a regulator’s request, to enforce our Terms, or to protect the rights, property or
            safety of users, the public or us.
          </li>
          <li>
            <strong>A successor</strong> if the Service is merged, acquired or sold, with notice to
            you before your data becomes subject to a different policy.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "transfers",
    title: "Where your data is stored",
    body: (
      <p>
        Account, connection and watcher records are stored in a database in Singapore. The connector
        and watcher servers that run programs and hold the encrypted session token in memory are in
        Bangalore, India. The website and account application are served from the United States and
        from edge locations near you. Emails are sent from the United States. By using the Service
        you consent to this processing outside India, which we carry out under contracts that
        require our providers to protect your data.
      </p>
    ),
  },
  {
    id: "retention",
    title: "How long we keep it",
    body: (
      <div className="legal-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Data</th>
              <th>Retention</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Account (email)</td>
              <td>Until you ask us to delete your account, or 12 months after your last sign-in</td>
            </tr>
            <tr>
              <td>Sign-in code hashes</td>
              <td>Deleted within 7 days of expiry</td>
            </tr>
            <tr>
              <td>Zerodha session token</td>
              <td>
                Replaced on each login; erased when you disconnect, when Zerodha reports the session
                ended, or when your account is deleted
              </td>
            </tr>
            <tr>
              <td>Programs sent by your AI assistant</td>
              <td>Up to 24 hours</td>
            </tr>
            <tr>
              <td>Workspace files</td>
              <td>Until you delete them or your account is deleted</td>
            </tr>
            <tr>
              <td>Connector tokens</td>
              <td>
                Access tokens 1 hour, refresh tokens 30 days; records purged a day after expiry
              </td>
            </tr>
            <tr>
              <td>Watchers and alert history</td>
              <td>
                Until you cancel the watcher and we purge finished watchers, or account deletion
              </td>
            </tr>
            <tr>
              <td>Server logs</td>
              <td>Up to 30 days</td>
            </tr>
          </tbody>
        </table>
      </div>
    ),
  },
  {
    id: "security",
    title: "How we protect it",
    body: (
      <ul>
        <li>All traffic to the Service is encrypted in transit (TLS).</li>
        <li>
          Zerodha session tokens are encrypted at rest with AES-256-GCM under a key held only on our
          servers; sign-in codes and connector tokens are stored as one-way hashes.
        </li>
        <li>
          Programs run in a separate process with no access to your Zerodha token, other users’ data
          or our configuration; they reach Zerodha only through a gateway that enforces read-only
          access and rate limits.
        </li>
        <li>
          Servers are hardened (least-privilege service accounts, restricted filesystem, firewalled
          ports) and access to production data is limited to the people who operate the Service.
        </li>
        <li>
          The Service is open source, so its handling of your data can be inspected at{" "}
          {legal.openSourceUrl}.
        </li>
      </ul>
    ),
  },
  {
    id: "rights",
    title: "Your rights and choices",
    body: (
      <>
        <p>Under the Digital Personal Data Protection Act, 2023 you may:</p>
        <ul>
          <li>ask for a summary of the personal data we hold about you and how it is used;</li>
          <li>ask us to correct or update it;</li>
          <li>
            ask us to erase it, subject to any record we must keep by law, by asking us to delete
            your account;
          </li>
          <li>withdraw consent at any time, with effect for the future;</li>
          <li>nominate a person to exercise these rights on your behalf if you cannot;</li>
          <li>
            complain to us through the Grievance Officer below and, if unresolved, to the Data
            Protection Board of India.
          </li>
        </ul>
        <p>You can act on most of these yourself:</p>
        <ul>
          <li>
            <strong>Stop Zerodha access:</strong> choose Disconnect on your account page. The stored
            token is erased immediately.
          </li>
          <li>
            <strong>Stop watchers:</strong> pause or cancel them on your account page.
          </li>
          <li>
            <strong>Stop the AI connector:</strong> remove the connector in your AI assistant’s
            settings; its tokens expire and are purged.
          </li>
          <li>
            <strong>Delete your account:</strong> email <P>{legal.privacyEmail}</P> from your
            account email. We delete your account, connection, watchers and workspace within 30 days
            and confirm by email.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "children",
    title: "Children",
    body: (
      <p>
        The Service is for adults who hold a trading account. We do not knowingly collect data from
        anyone under 18. If you believe a minor has created an account, contact us and we will
        delete it.
      </p>
    ),
  },
  {
    id: "changes",
    title: "Changes to this policy",
    body: (
      <p>
        We may update this policy as the Service changes. The “last updated” date above shows the
        current version. For material changes we will notify you by email or on the account page
        before they take effect.
      </p>
    ),
  },
  {
    id: "contact",
    title: "Contact and grievance officer",
    body: (
      <>
        <p>
          Privacy questions and requests: <P>{legal.privacyEmail}</P>
        </p>
        <p>
          Grievance Officer under the Information Technology Act, 2000 and the Digital Personal Data
          Protection Act, 2023:
        </p>
        <p>
          <P>{legal.grievanceOfficer}</P>
          <br />
          <P>{legal.companyName}</P>, <P>{legal.registeredAddress}</P>
          <br />
          <P>{legal.grievanceEmail}</P>
        </p>
        <p>We acknowledge grievances within 24 hours and aim to resolve them within 15 days.</p>
      </>
    ),
  },
];

export default function PrivacyPage() {
  return (
    <LegalPage
      intro={
        <>
          <p>
            In short: we keep your email, an encrypted Zerodha session token, and the watchers your
            AI sets up. Programs your AI sends are kept for a day; what they print goes back to your
            AI, not into our database. We never see your Zerodha password. We do not sell data or
            run ads. You can disconnect, cancel watchers or delete your account whenever you like.
          </p>
          <p>The full policy below is what actually applies.</p>
        </>
      }
      sections={sections}
      title="Privacy Policy"
    />
  );
}
