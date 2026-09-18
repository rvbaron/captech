import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { forkJoin, map, of, switchMap } from 'rxjs';
import { Api } from '../core/api';

interface PatternDoc {
  id: string;
  ruleClass: 'behavioral' | 'definitional';
  template: string;
  meaning: string;
  example: string;
  carriesCondition: boolean;
}

/**
 * The ten sentence patterns, taken verbatim from the extractor's own
 * specification (`.claude/skills/code-modernization/commands/modernize-extract-rules.md`,
 * the SPEC-1 §S1.4 partition). Requirement pages link here by pattern, so the
 * anchors are the pattern identifiers.
 */
const PATTERNS: PatternDoc[] = [
  {
    id: 'B-COND',
    ruleClass: 'behavioral',
    template: '[Condition], [Subject] must [Action]',
    meaning: 'Something is required, but only when the stated condition holds.',
    example:
      'When the vendor number is absent, the Order Service must reject the purchase order.',
    carriesCondition: true,
  },
  {
    id: 'B-UNCOND',
    ruleClass: 'behavioral',
    template: '[Subject] must [Action]',
    meaning: 'Something is required always, with no qualifying condition.',
    example: 'A purchase order must record a vendor number.',
    carriesCondition: false,
  },
  {
    id: 'B-PROHIB',
    ruleClass: 'behavioral',
    template: '[Condition], [Subject] must not [Action]',
    meaning: 'Something is forbidden when the condition holds.',
    example:
      'When the vendor number is absent, the Order Service must not accept the purchase order.',
    carriesCondition: true,
  },
  {
    id: 'B-RESTRICT',
    ruleClass: 'behavioral',
    template: '[Subject] may [Action] only if [Condition]',
    meaning:
      'Permission is granted narrowly — the action is allowed in the stated case and no other.',
    example: 'A clerk may waive the late fee only if the account is in good standing.',
    carriesCondition: true,
  },
  {
    id: 'D-NEC',
    ruleClass: 'definitional',
    template: '[Subject] always [Action]',
    meaning:
      'A necessity — true by definition of the thing, so it cannot be violated, only mis-stated.',
    example: 'A rental always specifies exactly one car group.',
    carriesCondition: false,
  },
  {
    id: 'D-IMPOSS',
    ruleClass: 'definitional',
    template: '[Subject] never [Action]',
    meaning: 'An impossibility — the case cannot arise, by definition.',
    example: 'A cancelled rental never accrues mileage charges.',
    carriesCondition: false,
  },
  {
    id: 'D-RESTRICT',
    ruleClass: 'definitional',
    template: '[Subject] can [Action] only if [Condition]',
    meaning: 'A definitional limit on what is even possible, not a permission granted.',
    example: 'A rental can be extended only if its return has not been recorded.',
    carriesCondition: true,
  },
  {
    id: 'D-COMPUTE',
    ruleClass: 'definitional',
    template: '[Subject] is to be computed as [Formula]',
    meaning:
      'A derivation. One of three forms that do not follow the standard slot structure — the tail is a formula, not an action.',
    example:
      'The interest owed is to be computed as (old balance + purchases − payments) × interest rate / 10000.',
    carriesCondition: false,
  },
  {
    id: 'D-INFER',
    ruleClass: 'definitional',
    template: '[Subject] is to be considered [Value] if [Condition]',
    meaning: 'A classification: the condition decides which category something falls in.',
    example:
      'An inventory item is to be considered category 87 if its purchase cost is more than 1000.00.',
    carriesCondition: true,
  },
  {
    id: 'D-CONST',
    ruleClass: 'definitional',
    template: '[Subject] is to be fixed at [Value]',
    meaning: 'A constant. The value is stipulated rather than derived.',
    example: 'The grace period is to be fixed at 10 days.',
    carriesCondition: false,
  },
];

@Component({
  selector: 'page-knowledge-patterns',
  imports: [RouterLink],
  template: `
    <div class="ll-page">
      <h1>Requirement formats</h1>
      <p class="lede">
        Every extracted rule is written in one of ten sentence patterns, split into two
        classes. The class is the important distinction: a <strong>behavioral</strong>
        rule can be violated, so it can be enforced; a <strong>definitional</strong> rule
        is true by definition of the thing it describes, so there is nothing to enforce —
        which is why a definitional rule never carries an enforcement level.
      </p>

      <div class="ll-card keywords">
        <h3>The modal keywords</h3>
        <div class="kw-grid">
          <div>
            <div class="ll-small ll-muted">Behavioral</div>
            <code>must</code> · <code>must not</code> · <code>may … only</code>
          </div>
          <div>
            <div class="ll-small ll-muted">Definitional</div>
            <code>always</code> · <code>never</code> · <code>can … only</code>
          </div>
          <div>
            <div class="ll-small ll-muted">Definitional (special)</div>
            <code>is to be computed as</code> · <code>is to be considered</code> ·
            <code>is to be fixed at</code>
          </div>
        </div>
        <p class="ll-small ll-muted">
          Mixing classes — <em>“An order always must have a customer”</em> — is the
          commonest error and is rejected. <code>may</code>, <code>need not</code> and
          <code>sometimes</code> are advice, not rules: an observation whose only keyword
          is one of those carries no pattern at all.
        </p>
      </div>

      @for (cls of ['behavioral', 'definitional']; track cls) {
        <div class="ll-section-title">
          <h2>{{ cls === 'behavioral' ? 'Behavioral' : 'Definitional' }}</h2>
          <span class="count">
            {{ cls === 'behavioral' ? 'can be violated — enforceable' : 'true by definition — nothing to enforce' }}
          </span>
        </div>

        <div class="list">
          @for (p of byClass(cls); track p.id) {
            <div class="ll-card pat" [id]="p.id">
              <div class="pat-head">
                <span class="mono pid">{{ p.id }}</span>
                <span class="ll-badge" [class]="'ll-badge-' + p.ruleClass">{{ p.ruleClass }}</span>
                @if (p.carriesCondition) {
                  <span
                    class="ll-badge ll-badge-neutral"
                    title="A statement in this pattern must actually carry its condition"
                    >carries a condition</span
                  >
                }
                @if (counts()[p.id]; as n) {
                  <a
                    class="usage ll-small"
                    [routerLink]="usageLink(p.id)"
                    [queryParams]="{ pattern: p.id }"
                  >
                    {{ n }} in this corpus →
                  </a>
                }
              </div>
              <div class="template mono">{{ p.template }}</div>
              <p class="meaning">{{ p.meaning }}</p>
              <div class="example">
                <span class="ll-small ll-muted">Example</span>
                <div>{{ p.example }}</div>
              </div>
            </div>
          }
        </div>
      }

      <div class="ll-section-title"><h2>What else a statement must do</h2></div>
      <div class="ll-card rules">
        <ul>
          <li>
            Name a real business subject — <em>A station</em>, <em>A purchase order</em>,
            <em>The Order Service</em> — and never <code>the system</code>,
            <code>the application</code>, <code>the software</code> or
            <code>the program</code>.
          </li>
          <li>
            Carry <strong>one</strong> action. <code>and</code> may join conditions, never
            two actions; two actions means two rules.
          </li>
          <li>
            Use active voice, except the three <code>is to be …</code> definitional forms,
            which are required passives.
          </li>
          <li>Never <code>shall</code>, <code>shall not</code> or <code>will</code>.</li>
          <li>
            Prefer the business term over the program symbol. A surviving
            <code>CamelCase</code>, <code>snake_case</code> or exception name is a warning
            and belongs in implementation notes.
          </li>
        </ul>
        <p class="ll-small ll-muted">
          A violation of any of these is a validator finding against the statement, and an
          <code>ERROR</code> finding blocks approval until it clears.
        </p>
      </div>

      <div class="ll-card rules last">
        <h3>Statement and As built are two fields on purpose</h3>
        <p>
          <strong>As built</strong> describes what the code does today, in whatever words
          fit, and is never held to this notation. <strong>Statement</strong> is the
          normative requirement — what the business requires — and is. Each carries its own
          confidence, and collapsing them into one field is the thing this schema exists to
          prevent.
        </p>
        <p class="ll-small ll-muted">
          Rationale, fit criterion, enforcement level and intent confidence are never the
          extractor's to fill. They belong to a subject-matter expert, and their emptiness
          is review progress rather than a gap to close.
        </p>
      </div>
    </div>
  `,
  styles: `
    .lede { max-width: 88ch; }
    .keywords { max-width: 100ch; }
    .keywords h3 { margin-bottom: 8px; }
    .kw-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin-bottom: 10px; }
    .kw-grid code { background: #eef1f4; padding: 1px 6px; border-radius: 4px; }
    .keywords p { margin: 0; max-width: 88ch; }
    .list { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); }
    .pat { scroll-margin-top: 80px; }
    .pat:target { border-color: var(--ll-green); box-shadow: 0 0 0 3px rgba(81, 183, 73, 0.18); }
    .pat-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
    .pid { font-weight: 600; color: var(--ll-navy); font-size: 13px; }
    .usage { margin-left: auto; white-space: nowrap; }
    .template {
      background: #f7f9fb;
      border: 1px solid var(--ll-line);
      border-radius: 7px;
      padding: 7px 10px;
      color: var(--ll-navy-deep);
    }
    .meaning { margin: 8px 0; max-width: 74ch; }
    .example { border-left: 3px solid var(--ll-green); padding-left: 10px; }
    .rules { max-width: 100ch; }
    .rules ul { margin: 0 0 10px; padding-left: 20px; }
    .rules li { margin-bottom: 6px; max-width: 88ch; }
    .rules p { max-width: 88ch; }
    .last { margin-top: 12px; }
  `,
})
export class KnowledgePatterns {
  private readonly api = inject(Api);

  /** Live counts across every system that has requirements, for orientation. */
  readonly counts = toSignal(
    this.api.projects().pipe(
      switchMap((projects) => {
        const systems = projects.flatMap((p) =>
          p.systems
            .filter((s) => s.hasRequirements)
            .map((s) => ({ projectId: p.projectId, systemId: s.systemId })),
        );
        if (systems.length === 0) return of({} as Record<string, number>);
        return forkJoin(
          systems.map((s) =>
            this.api.stats(s.systemId).pipe(
              map((stats) => ({ ...s, byPattern: stats.byPattern ?? {} })),
            ),
          ),
        ).pipe(
          map((rows) => {
            const totals: Record<string, number> = {};
            for (const row of rows) {
              this.firstSystem.set(row);
              for (const [k, v] of Object.entries(row.byPattern)) {
                totals[k] = (totals[k] ?? 0) + v;
              }
            }
            return totals;
          }),
        );
      }),
    ),
    { initialValue: {} as Record<string, number> },
  );

  private readonly firstSystem = signal<{ projectId: string; systemId: string } | null>(
    null,
  );

  byClass(ruleClass: string): PatternDoc[] {
    return PATTERNS.filter((p) => p.ruleClass === ruleClass);
  }

  usageLink(pattern: string): unknown[] {
    const s = this.firstSystem();
    return s ? ['/p', s.projectId, s.systemId, 'requirements'] : ['/'];
  }
}
