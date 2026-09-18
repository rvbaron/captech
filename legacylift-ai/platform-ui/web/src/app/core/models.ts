/** Shapes returned by the platform API. Field names mirror the store's columns
 *  (camelCased) so that a page can be read next to `knowledge.sqlite`. */

export interface SystemSummary {
  systemId: string;
  label: string;
  kind: 'application' | 'database' | string;
  hasRequirements: boolean;
  requirementCount: number;
  docs: { name: string; stale: boolean }[];
  diagrams: { name: string; label: string }[];
  topology: boolean;
  domains: boolean;
  snippetCount: number;
}

export interface Project {
  projectId: string;
  name: string;
  client: string;
  summary: string;
  currentStep: string;
  steps: string[];
  systems: SystemSummary[];
}

export interface RequirementRow {
  grId: string;
  name: string | null;
  subject: string | null;
  statement: string;
  priority: string | null;
  category: string | null;
  ruleClass: string | null;
  pattern: string | null;
  modality: string | null;
  confidenceExtraction: string | null;
  confidenceIntent: string | null;
  state: string;
  structuredBodyType: string | null;
  hasSmeQuestion: boolean;
  hasSuspectedDefect: boolean;
  edited: boolean;
  /** Only *evaluated* ERROR findings — the store's approval gate is
   *  `severity = 'ERROR' AND evaluated = 1`. */
  errorCount: number;
  warnCount: number;
  /** Checks that could not run (`evaluated = 0`). Never blocking. */
  notEvaluatedCount: number;
  citationCount: number;
  candidateCount: number;
}

export interface RequirementPage {
  hasRequirements: boolean;
  total: number;
  page: number;
  pageSize: number;
  rows: RequirementRow[];
  facets: Record<string, number>;
}

export interface Finding {
  findingId: string;
  severity: 'ERROR' | 'WARN';
  span: string;
  /** Character offset into `statement`, or null for a statement-wide check. */
  spanStart: number | null;
  spanEnd: number | null;
  message: string;
  evaluated: boolean;
}

export interface Citation {
  citationId: number;
  relativePath: string;
  startLine: number;
  endLine: number;
  anchorResolution: 'symbol' | 'file' | 'unresolved';
  contentHash: string | null;
  verifiedAt: string | null;
  provenance: 'extracted' | 'repaired' | 'human';
  anchorKey: string;
}

export interface Scenario {
  ordinal: number;
  given: string | null;
  when: string | null;
  then: string | null;
  and: string | null;
  provenance: 'extracted' | 'human';
}

export interface EdgeCase {
  ordinal: number;
  text: string;
  provenance: 'extracted' | 'human';
}

export interface CandidateLink {
  otherGrId: string;
  thisSide: 'existing' | 'incoming';
  reason: 'semantic' | 'range_overlap' | 'drift';
  resolution: 'merged' | 'distinct' | 'unresolved';
  similarity: number | null;
  runId: string | null;
  resolvedAt: string | null;
  otherName: string | null;
  otherStatement: string | null;
  otherPriority: string | null;
  otherSubject: string | null;
}

export interface CandidatePair {
  reason: 'semantic' | 'range_overlap' | 'drift';
  resolution: string;
  similarity: number | null;
  runId: string | null;
  existing: CandidateSide;
  incoming: CandidateSide;
}

export interface CandidateSide {
  grId: string;
  name: string | null;
  statement: string | null;
  priority: string | null;
  subject: string | null;
}

/** The full `gr` row plus its children. Extra columns arrive verbatim, so this
 *  is deliberately open — the detail page renders "everything the store holds". */
export interface RequirementDetail extends RequirementRow {
  statementExtracted: string;
  asBuilt: string | null;
  assumptions: string | null;
  assumptionsExtracted: string | null;
  rationale: string | null;
  fitCriterion: string | null;
  enforcementLevel: string | null;
  disposition: string | null;
  implementationNotes: string | null;
  parameters: string | null;
  structuredBody: string | null;
  smeQuestion: string | null;
  suspectedDefect: string | null;
  subjectProvenance: string | null;
  modalityExtracted: string;
  modalityConfirmed: number;
  dedupeKey: string;
  dedupeKeyAnchorOnly: string;
  owner: string | null;
  reviewedBy: string | null;
  reviewedAt: string | null;
  reviewNote: string | null;
  derivedFrom: string | null;
  supersededBy: string | null;
  firstSeenRunId: string | null;
  createdAt: string;
  updatedAt: string;
  extractorPayload: string;
  citations: Citation[];
  findings: Finding[];
  scenarios: Scenario[];
  edgeCases: EdgeCase[];
  candidates: CandidateLink[];
  runs: string[];
  [key: string]: unknown;
}

export interface Snippet {
  citationId: number;
  relativePath: string;
  startLine: number;
  endLine: number;
  firstLine?: number;
  language?: string;
  lines?: string[];
  available: boolean;
}

export interface Stats {
  total: number;
  byState: Record<string, number>;
  byPriority: Record<string, number>;
  byCategory: Record<string, number>;
  byRuleClass: Record<string, number>;
  byPattern: Record<string, number>;
  bySubject: Record<string, number>;
  byConfidenceExtraction: Record<string, number>;
  byStructuredBodyType: Record<string, number>;
  sme: {
    rationale: number;
    fitCriterion: number;
    enforcementLevel: number;
    edited: number;
    confidenceIntent: number;
    modalityConfirmed: number;
    reviewedBy: number;
    owner: number;
  };
  extraction: {
    smeQuestion: number;
    suspectedDefect: number;
    asBuilt: number;
    structuredBody: number;
  };
  findings: {
    error: number;
    warn: number;
    notEvaluated: number;
    rulesWithError: number;
    rulesNotEvaluated: number;
    rulesClean: number;
    byId: {
      findingId: string;
      severity: string;
      count: number;
      rules: number;
      evaluated: boolean;
    }[];
  };
  citations: {
    total: number;
    files: number;
    byResolution: Record<string, number>;
  };
  candidates: {
    unresolved: number;
    byReason: Record<string, number>;
  };
  scenarios: number;
  edgeCases: number;
  runs: RunInfo[];
  hasRequirements?: boolean;
}

export interface RunInfo {
  runId: string;
  system: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  roundsRun: number | null;
  roundCap: number | null;
  stopReason: string | null;
  rulesIn: number | null;
  rulesNew: number | null;
  rulesMerged: number | null;
  rulesCandidate: number | null;
  rulesRejected: number | null;
  notAccountedFor: number | null;
  finalRoundChunkCoveragePct: number | null;
  coverageSource: string | null;
}

export interface DomainDefinition {
  domain_id: string;
  name: string;
  description?: string;
  path_globs?: string[];
}

export interface DomainsPayload {
  definition: {
    schema_version?: number;
    assess_run_id?: string;
    domains?: DomainDefinition[];
    edges?: { from?: string; to?: string; [k: string]: unknown }[];
    exclude_globs?: string[];
    vendored_globs?: string[];
    own_identities?: string[];
  };
  /**
   * Files tagged per domain, from the store's `file_domains` mirror. A domain
   * defined in `domains.json` that matched no file is **absent** from this map
   * rather than present as zero, so every lookup needs a default — see
   * `MapPage.files()`.
   */
  fileCounts: Record<string, number>;
}
