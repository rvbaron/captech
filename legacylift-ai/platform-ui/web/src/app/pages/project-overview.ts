import { DecimalPipe } from '@angular/common';
import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Observable, forkJoin, map, of, switchMap } from 'rxjs';
import { Api } from '../core/api';
import { Project, Stats, SystemSummary } from '../core/models';

interface SystemWithStats {
  system: SystemSummary;
  stats: Stats | null;
}

@Component({
  selector: 'page-project-overview',
  imports: [RouterLink, DecimalPipe],
  template: `
    @if (project(); as p) {
      <div class="ll-page">
        <h1>{{ p.name }}</h1>
        <p class="ll-muted lede">{{ p.summary }}</p>

        <div class="ll-card">
          <div class="ll-small ll-muted track-label">Workflow</div>
          <ol class="track">
            @for (step of p.steps; track step; let i = $index) {
              <li
                [class.done]="i <= currentIndex()"
                [class.current]="i === currentIndex()"
              >
                <span class="dot"></span>
                <span class="name">{{ step }}</span>
              </li>
            }
          </ol>
          <div class="ll-small ll-muted">
            Steps through <strong>{{ p.currentStep }}</strong> have produced artifacts in
            this dataset. <em>brief</em> has not been run, so there is no recommendation
            to show yet.
          </div>
        </div>

        @for (row of systems(); track row.system.systemId) {
          <div class="ll-section-title">
            <h2>{{ row.system.label }}</h2>
            <span class="count">{{ row.system.systemId }}</span>
          </div>

          @if (row.stats?.total) {
            <div class="ll-grid tiles">
              <a
                class="ll-card tile"
                [routerLink]="['/p', p.projectId, row.system.systemId, 'requirements']"
              >
                <div class="tile-value">{{ row.stats!.total | number }}</div>
                <div class="tile-label">requirements extracted</div>
                <div class="ll-small ll-muted">all in state “draft”</div>
              </a>
              <a
                class="ll-card tile"
                [routerLink]="['/p', p.projectId, row.system.systemId, 'requirements']"
                [queryParams]="{ severity: 'ERROR' }"
              >
                <div class="tile-value err">{{ row.stats!.findings.rulesWithError | number }}</div>
                <div class="tile-label">blocked by an ERROR finding</div>
                <div class="ll-small ll-muted">
                  {{ row.stats!.findings.error }} errors,
                  {{ row.stats!.findings.warn }} warnings
                </div>
                <div class="ll-small ll-muted">
                  {{ row.stats!.findings.notEvaluated }} checks could not run
                </div>
              </a>
              <a
                class="ll-card tile"
                [routerLink]="['/p', p.projectId, row.system.systemId, 'candidates']"
              >
                <div class="tile-value">{{ row.stats!.candidates.unresolved | number }}</div>
                <div class="tile-label">unresolved merge candidates</div>
                <div class="ll-small ll-muted">{{ reasonSummary(row.stats!) }}</div>
              </a>
              <div class="ll-card tile static">
                <div class="tile-value">{{ reviewedPct(row.stats!) }}%</div>
                <div class="tile-label">SME review progress</div>
                <div class="meter" [title]="reviewTooltip(row.stats!)">
                  <span [style.width.%]="reviewedPct(row.stats!)"></span>
                </div>
                <div class="ll-small ll-muted">
                  {{ smeFilled(row.stats!) }} of {{ row.stats!.total * 3 | number }} SME-only
                  fields set
                </div>
              </div>
            </div>

            <div class="ll-grid two">
              <div class="ll-card">
                <h3>Priority</h3>
                @for (b of bars(row.stats!.byPriority, row.stats!.total); track b.key) {
                  <div class="bar-row">
                    <span class="bar-key">{{ b.key }}</span>
                    <span class="bar"><span [style.width.%]="b.pct"></span></span>
                    <span class="bar-val">{{ b.value }}</span>
                  </div>
                }
                <h3 class="spaced">Category</h3>
                @for (b of bars(row.stats!.byCategory, row.stats!.total); track b.key) {
                  <div class="bar-row">
                    <span class="bar-key">{{ b.key }}</span>
                    <span class="bar"><span [style.width.%]="b.pct"></span></span>
                    <span class="bar-val">{{ b.value }}</span>
                  </div>
                }
              </div>

              <div class="ll-card">
                <h3>Evidence</h3>
                <dl class="facts">
                  <dt>Citations</dt>
                  <dd>
                    {{ row.stats!.citations.total | number }} across
                    {{ row.stats!.citations.files | number }} files
                  </dd>
                  <dt>Given/When/Then</dt>
                  <dd>{{ row.stats!.scenarios | number }} scenarios</dd>
                  <dt>Edge cases</dt>
                  <dd>{{ row.stats!.edgeCases | number }}</dd>
                  <dt>As-built described</dt>
                  <dd>{{ row.stats!.extraction.asBuilt | number }}</dd>
                  <dt>Structured bodies</dt>
                  <dd>{{ row.stats!.extraction.structuredBody | number }}</dd>
                  <dt>SME questions raised</dt>
                  <dd>{{ row.stats!.extraction.smeQuestion | number }}</dd>
                  <dt>Suspected defects</dt>
                  <dd>{{ row.stats!.extraction.suspectedDefect | number }}</dd>
                </dl>
                <h3 class="spaced">Extraction runs</h3>
                @for (r of row.stats!.runs; track r.runId) {
                  <div class="run ll-small">
                    <span class="mono">{{ r.runId }}</span>
                    <span class="ll-muted">
                      {{ r.roundsRun }} rounds · in {{ r.rulesIn }} · new
                      {{ r.rulesNew }} · merged {{ r.rulesMerged }} · candidates
                      {{ r.rulesCandidate }}
                    </span>
                  </div>
                }
              </div>
            </div>
          } @else {
            <div class="ll-card none">
              <strong>No requirements for this system.</strong>
              <p class="ll-muted">
                Its knowledge store holds domain tagging only —
                <code>/modernize-extract-rules</code> has not been run against it. The
                assessment, preflight and topology artifacts are available in the left-hand
                nav.
              </p>
            </div>
          }
        }
      </div>
    }
  `,
  styles: `
    .lede { max-width: 76ch; margin-top: 0; }
    .track-label { text-transform: uppercase; letter-spacing: 0.06em; }
    .track {
      display: flex;
      flex-wrap: wrap;
      gap: 0;
      list-style: none;
      margin: 8px 0 12px;
      padding: 0;
      counter-reset: step;
    }
    .track li {
      display: flex;
      align-items: center;
      gap: 8px;
      padding-right: 26px;
      position: relative;
      color: #9aa7b4;
    }
    .track li::after {
      content: '';
      position: absolute;
      right: 9px;
      width: 8px;
      height: 1px;
      background: var(--ll-line);
    }
    .track li:last-child::after { display: none; }
    .track .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      border: 2px solid var(--ll-line);
      background: #fff;
    }
    .track li.done { color: var(--ll-ink); }
    .track li.done .dot { background: var(--ll-green); border-color: var(--ll-green); }
    .track li.current { color: var(--ll-navy); font-weight: 600; }
    .track li.current .dot { box-shadow: 0 0 0 3px rgba(81, 183, 73, 0.25); }

    .tiles { grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); }
    .tile { color: inherit; text-decoration: none; }
    .tile:not(.static):hover {
      text-decoration: none;
      border-color: #b9cbdc;
      box-shadow: 0 2px 4px rgba(0, 30, 60, 0.08), 0 10px 26px rgba(0, 30, 60, 0.1);
    }
    .tile-value { font-size: 30px; font-weight: 600; color: var(--ll-navy); line-height: 1.1; }
    .tile-value.err { color: var(--ll-error); }
    .tile-label { font-weight: 500; margin-bottom: 2px; }
    .meter {
      height: 7px;
      background: #eceff2;
      border-radius: 4px;
      overflow: hidden;
      margin: 6px 0;
    }
    .meter span { display: block; height: 100%; background: var(--ll-green); }

    .two { grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); margin-top: 16px; }
    h3 { margin-bottom: 8px; }
    h3.spaced { margin-top: 20px; }
    .bar-row { display: grid; grid-template-columns: 96px 1fr 44px; align-items: center; gap: 10px; margin-bottom: 5px; }
    .bar-key { font-size: 12px; color: var(--ll-muted); }
    .bar { background: #eceff2; height: 9px; border-radius: 4px; overflow: hidden; }
    .bar span { display: block; height: 100%; background: var(--ll-navy); opacity: 0.8; }
    .bar-val { font-size: 12px; text-align: right; font-variant-numeric: tabular-nums; }

    .facts { display: grid; grid-template-columns: minmax(150px, auto) 1fr; gap: 4px 16px; margin: 0; }
    .facts dt { color: var(--ll-muted); font-size: 12px; }
    .facts dd { margin: 0; }
    .run { padding: 3px 0; display: flex; gap: 10px; flex-wrap: wrap; }
    .none p { margin: 6px 0 0; max-width: 74ch; }
  `,
})
export class ProjectOverview {
  private readonly api = inject(Api);
  private readonly route = inject(ActivatedRoute);

  readonly project = toSignal(
    this.route.parent!.paramMap.pipe(
      switchMap((p) => this.api.project(p.get('projectId') ?? '')),
    ),
  );

  readonly systems = toSignal(
    this.route.parent!.paramMap.pipe(
      switchMap((p) => this.api.project(p.get('projectId') ?? '')),
      switchMap((proj: Project | undefined) => {
        if (!proj) return of([] as SystemWithStats[]);
        return forkJoin(
          proj.systems.map((system) => {
            // Typed explicitly: piping a union of two observable types resolves
            // to the wrong `pipe` overload and loses the element type.
            const source: Observable<Stats | null> = system.hasRequirements
              ? this.api.stats(system.systemId)
              : of(null);
            return source.pipe(map((stats) => ({ system, stats })));
          }),
        );
      }),
    ),
    { initialValue: [] as SystemWithStats[] },
  );

  readonly currentIndex = computed(() => {
    const p = this.project();
    return p ? p.steps.indexOf(p.currentStep) : -1;
  });

  bars(map: Record<string, number>, total: number) {
    return Object.entries(map)
      .sort((a, b) => b[1] - a[1])
      .map(([key, value]) => ({ key, value, pct: total ? (value / total) * 100 : 0 }));
  }

  /**
   * Review progress measured the way the store plan says to measure it: the
   * three extractor-forbidden fields, which are human by definition.
   */
  smeFilled(s: Stats): number {
    return s.sme.rationale + s.sme.fitCriterion + s.sme.enforcementLevel;
  }

  reviewedPct(s: Stats): number {
    const denom = s.total * 3;
    return denom ? Math.round((this.smeFilled(s) / denom) * 100) : 0;
  }

  reviewTooltip(s: Stats): string {
    return (
      `rationale ${s.sme.rationale}, fit_criterion ${s.sme.fitCriterion}, ` +
      `enforcement_level ${s.sme.enforcementLevel} — the three fields the ` +
      `extractor is forbidden to write. Edited statements: ${s.sme.edited}.`
    );
  }

  reasonSummary(s: Stats): string {
    return Object.entries(s.candidates.byReason)
      .map(([k, v]) => `${v} ${k.replace('_', ' ')}`)
      .join(' · ');
  }
}
