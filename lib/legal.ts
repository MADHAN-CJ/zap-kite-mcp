/**
 * Operator details used by the Terms of Service and Privacy Policy. Replace every
 * bracketed placeholder before launch; the pages render them verbatim.
 */
export const legal = {
  productName: "/markets",
  spokenName: "Slash Markets",
  companyName: "Certus Innovations Private Limited",
  companyType: "a private limited company incorporated in India",
  registeredAddress: "412 2nd, 3rd, and 4th Floors, Duru House, Juhu Tara Road (Next to JW Marriott), Juhu, Vile Parle West, Mumbai, Maharashtra 400049",
  supportEmail: "support@revise.network",
  privacyEmail: "support@revise.network",
  grievanceOfficer: "Mehul Parmar",
  grievanceEmail: "mehul@revise.network",
  governingCity: "Mumbai",
  marketingUrl: "https://slash.markets",
  appUrl: "https://app.slash.markets",
  openSourceUrl: "https://github.com/MADHAN-CJ/zap-kite-mcp",
  effectiveDate: "22 October 2026",
  lastUpdated: "22 October 2026",
} as const;

export const legalPlaceholders = Object.entries(legal)
  .filter(([, v]) => v.startsWith("["))
  .map(([k]) => k);
