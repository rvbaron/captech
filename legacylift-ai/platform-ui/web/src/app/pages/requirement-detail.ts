import { Component, computed, inject, signal } from '@angular/core';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Api } from '../core/api';
import { CandidateLink, Finding, RequirementDetail } from '../core/models';
import { CodeSnippet } from '../shared/code-snippet';
import { StatementView } from '../shared/statement-view';

/** The eight fields a human may write, per the store plan's Step 8. */
const SME_FIELDS: { key: keyof RequirementDetail; label: string; note: string }[] = [
  {
    key: 'rationale',
    label: 'Rationale',
    note: 'Why the business needs this. The extractor is forbidden to write it.',
  },
  {
    key: 'fitCriterion',
    label: 'Fit criterion',
    note: 'How compliance is measured. Extractor-forbidden.',
  },
  {
    key: 'enforcementLevel',
    label: 'Enforcement level',
    note: 'strict / deferred / pre-authorized / post-justified / override / guideline. Extractor-forbidden.',
  },
  {
    key: 'confidenceIntent',
    label: 'Confidence in intent',
    note: 'How sure the reviewer is that the normative statement is right.',
  },
  {
    key: 'disposition',
    label: 'Disposition',
    note: 'captured / not_applicable / unreachable / delegated.',
  },
  { key: 'owner', label: 'Owner', note: 'Who is accountable for this requirement.' },
  { key: 'reviewedBy', label: 'Reviewed by', note: 'Set only by a state transition.' },
  { key: 'reviewNote', label: 'Review note', note: '' },
];

@Component({
  selector: 'page-requirement-detail',
  imports: [
    RouterLink,
    MatTabsModule,
    MatTooltipModule,
    StatementView,
    CodeSnippet,
  ],
  template: `
    @if (gr(); as r) {
      <div class="ll-page">
        <a class="back ll-small" routerLink=".." queryParamsHandling="preserve">
          ← All requirements
        </a>

        <div class="head">
          <div class="head-main">
            <h1>{{ r.name || r.grId }}</h1>
            <div class="mono ll-small ll-muted">{{ r.grId }}</div>
          </div>
          <div class="head-badges">
            <span class="ll-badge" [class]="'ll-badge-' + (r.priority || 'neutral').toLowerCase()">{{
              r.priority
            }}</span>
            <span class="ll-badge ll-badge-neutral">{{ r.state }}</span>
            @if (r.errorCount) {
              <span class="ll-badge ll-badge-error">{{ r.errorCount }} ERROR</span>
            }
            @if (r.warnCount) {
              <span class="ll-badge ll-badge-warn">{{ r.warnCount }} WARN</span>
            }
            @if (r.notEvaluatedCount) {
              <span class="ll-badge ll-badge-neutral"
                >{{ r.notEvaluatedCount }} not run</span
              >
            }
          </div>
        </div>

        <!-- Approvability is the store's judgement, not this page's. Milestone 1
             has no write path, so the gate is *previewed* and nothing more. -->
        <div class="gate" [class.blocked]="r.errorCount > 0">
          @if (r.errorCount > 0) {
            <strong>Cannot be approved yet.</strong>
            {{ r.errorCount }} ERROR finding{{ r.errorCount > 1 ? 's' : '' }} must clear
            first. The gate lives in the store's <code>set_state</code>, which would refuse
            this transition.
          } @else {
            <strong>No blocking findings.</strong>
            Nothing would stop <code>set_state</code> from approving this rule — but
            approval needs a named reviewer, and this preview has no write path.
          }
          @if (r.notEvaluatedCount) {
            <div class="ll-small gate-note">
              {{ r.notEvaluatedCount }} check{{ r.notEvaluatedCount > 1 ? 's' : '' }}
              could not be run on this statement. Those do not block approval — the gate
              counts only <code>evaluated</code> findings — but they mean part of the
              validation is unverified rather than passed.
            </div>
          }
        </div>

        <div class="cols">
          <div class="col-main">
            <div class="ll-card">
              <div class="field-head">
                <h2>Statement</h2>
                <span class="ll-small ll-muted">normative — what the business requires</span>
              </div>
              <div class="statement">
                <statement-view [statement]="r.statement" [findings]="spannedFindings()" />
              </div>

              @if (r.edited) {
                <div class="edited">
                  <div class="ll-small">
                    <strong>A human has edited this statement.</strong>
                    The store's only definition of that is
                    <code>statement != statement_extracted</code>.
                  </div>
                  <div class="ll-small extracted">
                    <span class="ll-muted">Extractor's wording:</span>
                    {{ r.statementExtracted }}
                  </div>
                </div>
              } @else {
                <div class="ll-small ll-muted unedited">
                  Unedited — identical to <code>statement_extracted</code>.
                </div>
              }

              @if (spannedFindings().length || statementWide().length) {
                <div class="findings">
                  <h3>Validator findings</h3>
                  @if (spannedFindings().length) {
                    <div class="ll-small ll-muted hint">
                      {{ spannedFindings().length }} finding(s) point at specific words —
                      highlighted above. Hover a highlight for the message.
                    </div>
                  }
                  @for (f of r.findings; track f.findingId + f.span) {
                    <div
                      class="finding"
                      [class.err]="f.severity === 'ERROR' && f.evaluated"
                      [class.notrun]="!f.evaluated"
                    >
                      <span
                        class="ll-badge"
                        [class]="severityClass(f)"
                        [matTooltip]="
                          f.evaluated
                            ? ''
                            : 'This check could not run — it needs a template that this statement does not supply. Not a violation, and it does not block approval.'
                        "
                      >
                        {{ f.evaluated ? f.severity : 'NOT RUN' }}
                      </span>
                      <span class="mono fid">{{ f.findingId }}</span>
                      <span class="msg">{{ f.message }}</span>
                      @if (f.spanStart !== null) {
                        <span class="ll-small ll-muted span">chars {{ f.span }}</span>
                      }
                    </div>
                  }
                </div>
              } @else {
                <div class="ll-small ll-muted unedited">
                  No findings — this statement passed every check.
                </div>
              }
            </div>

            @if (r.asBuilt) {
              <div class="ll-card spaced">
                <div class="field-head">
                  <h2>As built</h2>
                  <span class="ll-small ll-muted">descriptive — what the code does</span>
                </div>
                <p class="body">{{ r.asBuilt }}</p>
                <div class="ll-small ll-muted">
                  Extraction confidence: <strong>{{ r.confidenceExtraction }}</strong>
                </div>
              </div>
            }

            <mat-tab-group class="tabs spaced" animationDuration="0ms">
              <mat-tab [label]="'Evidence (' + r.citations.length + ')'">
                <div class="tab-body">
                  @for (c of r.citations; track c.citationId) {
                    <div class="cite">
                      <code-snippet [systemId]="systemId()" [citation]="c" />
                    </div>
                  }
                  @if (r.citations.length === 0) {
                    <p class="ll-muted">No citations recorded.</p>
                  }
                </div>
              </mat-tab>

              <mat-tab [label]="'Scenarios (' + r.scenarios.length + ')'">
                <div class="tab-body">
                  @for (s of r.scenarios; track s.ordinal) {
                    <div class="gwt">
                      <div><span class="kw">Given</span> {{ s.given }}</div>
                      <div><span class="kw">When</span> {{ s.when }}</div>
                      <div><span class="kw">Then</span> {{ s.then }}</div>
                      @if (s.and) {
                        <div><span class="kw">And</span> {{ s.and }}</div>
                      }
                      <div class="ll-small ll-muted">{{ s.provenance }}</div>
                    </div>
                  }
                  @if (r.scenarios.length === 0) {
                    <p class="ll-muted">No scenario attached.</p>
                  }
                </div>
              </mat-tab>

              <mat-tab [label]="'Edge cases (' + r.edgeCases.length + ')'">
                <div class="tab-body">
                  <ul class="edge">
                    @for (e of r.edgeCases; track e.ordinal) {
                      <li>{{ e.text }}</li>
                    }
                  </ul>
                  @if (r.edgeCases.length === 0) {
                    <p class="ll-muted">None recorded.</p>
                  }
                </div>
              </mat-tab>

              <mat-tab [label]="'Merge candidates (' + r.candidates.length + ')'">
                <div class="tab-body">
                  @if (r.candidates.length === 0) {
                    <p class="ll-muted">
                      This rule is not paired with any near-duplicate or drift candidate.
                    </p>
                  }
                  @for (c of r.candidates; track c.otherGrId) {
                    <div class="cand" [class.drift]="c.reason === 'drift'">
                      <div class="cand-head">
                        <span class="ll-badge" [class]="reasonClass(c)">{{ c.reason }}</span>
                        <span class="ll-badge ll-badge-neutral">{{ c.resolution }}</span>
                        @if (c.similarity !== null) {
                          <span class="ll-small ll-muted"
                            >similarity {{ c.similarity!.toFixed(3) }}</span
                          >
                        }
                        <span class="ll-small ll-muted">{{ explain(c) }}</span>
                      </div>
                      <a class="cand-name" [routerLink]="['..', c.otherGrId]">{{
                        c.otherName || c.otherGrId
                      }}</a>
                      <div class="ll-small">{{ c.otherStatement }}</div>
                    </div>
                  }
                </div>
              </mat-tab>

              <mat-tab label="Implementation">
                <div class="tab-body">
                  @for (f of implementationFields(); track f.label) {
                    @if (f.value) {
                      <div class="kv">
                        <div class="k ll-small">{{ f.label }}</div>
                        <div class="v">{{ f.value }}</div>
                      </div>
                    }
                  }
                  @if (r.structuredBody) {
                    <div class="kv">
                      <div class="k ll-small">
                        Structured body <span class="ll-muted">({{ r.structuredBodyType }})</span>
                      </div>
                      <pre class="v code">{{ prettyBody() }}</pre>
                    </div>
                  }
                </div>
              </mat-tab>
            </mat-tab-group>
          </div>

          <aside class="col-side">
            <div class="ll-card">
              <h3>Classification</h3>
              <dl class="kvs">
                <dt>Domain</dt>
                <dd>{{ r.subject }}</dd>
                <dt>Rule class</dt>
                <dd>
                  @if (r.ruleClass) {
                    <span class="ll-badge" [class]="'ll-badge-' + r.ruleClass">{{
                      r.ruleClass
                    }}</span>
                  }
                </dd>
                <dt>Pattern</dt>
                <dd>
                  <a class="mono" routerLink="/knowledge/patterns" [fragment]="r.pattern || ''">{{
                    r.pattern
                  }}</a>
                </dd>
                <dt>Category</dt>
                <dd>{{ r.category }}</dd>
                <dt>Modality</dt>
                <dd>
                  {{ r.modality }}
                  @if (!r.modalityConfirmed) {
                    <span class="ll-small ll-muted">(unconfirmed)</span>
                  }
                </dd>
                <dt>Extraction confidence</dt>
                <dd>{{ r.confidenceExtraction }}</dd>
              </dl>
            </div>

            @if (r.smeQuestion || r.suspectedDefect) {
              <div class="ll-card spaced flags">
                @if (r.smeQuestion) {
                  <div class="flag warn">
                    <div class="ll-small label">Question for an SME</div>
                    <div>{{ r.smeQuestion }}</div>
                  </div>
                }
                @if (r.suspectedDefect) {
                  <div class="flag err">
                    <div class="ll-small label">Suspected defect in the legacy behaviour</div>
                    <div>{{ r.suspectedDefect }}</div>
                  </div>
                }
              </div>
            }

            @if (r.assumptions) {
              <div class="ll-card spaced">
                <h3>Assumptions</h3>
                <p class="body ll-small">{{ r.assumptions }}</p>
              </div>
            }

            <div class="ll-card spaced">
              <h3>SME review</h3>
              <div class="ll-small ll-muted sme-note">
                These are the fields a reviewer owns. Editing arrives in a later
                milestone; the values below are what the store holds today.
              </div>
              <dl class="kvs">
                @for (f of smeFields(); track f.label) {
                  <dt [matTooltip]="f.note">{{ f.label }}</dt>
                  <dd [class.unset]="!f.value">{{ f.value || 'not set by SME' }}</dd>
                }
              </dl>
            </div>

            <div class="ll-card spaced">
              <h3>Provenance</h3>
              <dl class="kvs">
                <dt>First seen in run</dt>
                <dd class="mono ll-small">{{ r.firstSeenRunId }}</dd>
                <dt>Seen in runs</dt>
                <dd class="ll-small">{{ r.runs.length }}</dd>
                <dt>Created</dt>
                <dd class="ll-small">{{ r.createdAt }}</dd>
                <dt>Updated</dt>
                <dd class="ll-small">{{ r.updatedAt }}</dd>
                <dt>Dedupe key</dt>
                <dd class="mono ll-small">{{ r.dedupeKey }}</dd>
                <dt>Anchor-only key</dt>
                <dd class="mono ll-small">{{ r.dedupeKeyAnchorOnly }}</dd>
              </dl>
            </div>
          </aside>
        </div>
      </div>
    } @else if (error()) {
      <div class="ll-page">
        <div class="ll-card">
          <strong>That requirement is not in this store.</strong>
          <p class="ll-muted">{{ error() }}</p>
          <a routerLink="..">Back to the list</a>
        </div>
      </div>
    } @else {
      <div class="ll-page"><div class="ll-card">Loading…</div></div>
    }
  `,
  styles: `
    .back { display: inline-block; color: var(--ll-muted); margin-bottom: 10px; }
    .head { display: flex; align-items: flex-start; gap: 20px; flex-wrap: wrap; }
    .head-main h1 { margin-bottom: 2px; max-width: 70ch; }
    .head-badges { display: flex; gap: 6px; flex-wrap: wrap; margin-left: auto; padding-top: 4px; }

    .gate {
      margin: 14px 0 18px;
      padding: 10px 14px;
      border-radius: var(--ll-radius);
      border: 1px solid #c6e6c2;
      background: #f4faf3;
      font-size: 13px;
    }
    .gate.blocked { border-color: #f3c2bd; background: var(--ll-error-bg); }

    .cols { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 18px; align-items: start; }
    @media (max-width: 1100px) {
      .cols { grid-template-columns: 1fr; }
    }
    .spaced { margin-top: 16px; }
    .field-head { display: flex; align-items: baseline; gap: 10px; }
    .field-head h2 { margin: 0 0 6px; }
    .statement { font-size: 15.5px; max-width: 82ch; }
    .body { max-width: 82ch; }

    .edited {
      margin-top: 12px;
      padding: 10px 12px;
      border-left: 3px solid var(--ll-green);
      background: #f6faf5;
      border-radius: 0 8px 8px 0;
    }
    .extracted { margin-top: 6px; }
    .unedited { margin-top: 10px; }

    .findings { margin-top: 16px; border-top: 1px solid var(--ll-line); padding-top: 12px; }
    .findings h3 { margin-bottom: 6px; }
    .hint { margin-bottom: 8px; }
    .finding {
      display: grid;
      grid-template-columns: 62px 88px 1fr auto;
      gap: 10px;
      align-items: baseline;
      padding: 6px 0;
      border-bottom: 1px dashed var(--ll-line);
      font-size: 13px;
    }
    .finding:last-child { border-bottom: none; }
    .fid { color: var(--ll-navy); font-weight: 600; }
    .finding.notrun { color: var(--ll-muted); }
    .gate-note { margin-top: 6px; color: var(--ll-muted); }
    .span { white-space: nowrap; }

    .tabs { background: transparent; }
    .tab-body { padding: 16px 2px 4px; }
    .cite { margin-bottom: 16px; }
    .gwt { border-left: 3px solid var(--ll-line); padding: 4px 0 4px 12px; margin-bottom: 14px; }
    .kw { display: inline-block; width: 52px; font-weight: 600; color: var(--ll-navy); }
    .edge { margin: 0; padding-left: 20px; }
    .edge li { margin-bottom: 6px; }

    .cand {
      border: 1px solid var(--ll-line);
      border-radius: var(--ll-radius);
      padding: 10px 12px;
      margin-bottom: 10px;
    }
    .cand.drift { border-left: 3px solid var(--ll-warn); }
    .cand-head { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 4px; }
    .cand-name { font-weight: 600; }

    .kv { margin-bottom: 14px; }
    .kv .k { color: var(--ll-muted); text-transform: uppercase; letter-spacing: 0.05em; }
    .kv .v { max-width: 92ch; }
    .kv .code {
      background: #0e1b28;
      color: #e6edf3;
      padding: 10px 12px;
      border-radius: 8px;
      overflow-x: auto;
      font-size: 12px;
    }

    .kvs { display: grid; grid-template-columns: minmax(104px, auto) 1fr; gap: 5px 12px; margin: 0; }
    .kvs dt { color: var(--ll-muted); font-size: 12px; }
    .kvs dd { margin: 0; word-break: break-word; }
    .kvs dd.unset { color: #9aa7b4; font-style: italic; }
    .sme-note { margin-bottom: 10px; }

    .flags .flag { padding: 8px 10px; border-radius: 8px; margin-bottom: 8px; }
    .flags .flag:last-child { margin-bottom: 0; }
    .flag .label { font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 2px; }
    .flag.warn { background: var(--ll-warn-bg); }
    .flag.err { background: var(--ll-error-bg); }
  `,
})
export class RequirementDetailPage {
  private readonly api = inject(Api);
  private readonly route = inject(ActivatedRoute);

  readonly systemId = signal('');
  readonly gr = signal<RequirementDetail | null>(null);
  readonly error = signal<string | null>(null);

  readonly spannedFindings = computed(
    () => this.gr()?.findings.filter((f) => f.spanStart !== null && f.evaluated) ?? [],
  );
  readonly statementWide = computed(
    () => this.gr()?.findings.filter((f) => f.spanStart === null) ?? [],
  );

  readonly smeFields = computed(() => {
    const r = this.gr();
    if (!r) return [];
    return SME_FIELDS.map((f) => ({
      label: f.label,
      note: f.note,
      value: (r[f.key] as string | null) ?? '',
    }));
  });

  readonly implementationFields = computed(() => {
    const r = this.gr();
    if (!r) return [];
    return [
      { label: 'Implementation notes', value: r.implementationNotes },
      { label: 'Parameters', value: r.parameters },
      { label: 'Assumptions (extractor)', value: r.assumptionsExtracted },
      { label: 'Derived from', value: r.derivedFrom },
      { label: 'Superseded by', value: r.supersededBy },
      { label: 'Subject provenance', value: r.subjectProvenance },
    ];
  });

  constructor() {
    this.route.paramMap.subscribe((p) => {
      const systemId = p.get('systemId') ?? '';
      const grId = p.get('grId') ?? '';
      this.systemId.set(systemId);
      this.gr.set(null);
      this.error.set(null);
      this.api.requirement(systemId, grId).subscribe({
        next: (r) => this.gr.set(r),
        error: (e) => this.error.set(e?.error?.error ?? e?.message ?? 'not found'),
      });
    });
  }

  severityClass(f: Finding): string {
    if (!f.evaluated) return 'll-badge-neutral';
    return f.severity === 'ERROR' ? 'll-badge-error' : 'll-badge-warn';
  }

  prettyBody(): string {
    const raw = this.gr()?.structuredBody;
    if (!raw) return '';
    try {
      return JSON.stringify(JSON.parse(raw), null, 2);
    } catch {
      return raw;
    }
  }

  reasonClass(c: CandidateLink): string {
    return c.reason === 'drift' ? 'll-badge-warn' : 'll-badge-neutral';
  }

  explain(c: CandidateLink): string {
    switch (c.reason) {
      case 'drift':
        return 'same rule recognised by its anchors, but the cited code changed';
      case 'range_overlap':
        return 'cites overlapping lines';
      default:
        return 'semantically similar wording';
    }
  }
}
