import { DecimalPipe } from '@angular/common';
import { Component, computed, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Api, RequirementFilters } from '../core/api';
import { RequirementPage, Stats } from '../core/models';

const PATTERNS = [
  'B-COND', 'B-UNCOND', 'B-PROHIB', 'B-RESTRICT',
  'D-NEC', 'D-IMPOSS', 'D-RESTRICT', 'D-COMPUTE', 'D-INFER', 'D-CONST',
];

@Component({
  selector: 'page-requirements-list',
  imports: [
    RouterLink,
    FormsModule,
    DecimalPipe,
    MatTableModule,
    MatPaginatorModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatCheckboxModule,
    MatTooltipModule,
  ],
  template: `
    <div class="ll-page">
      <div class="top">
        <div>
          <h1>Requirements</h1>
          <p class="ll-muted">
            Every business rule the extractor mined from this system, as the store holds
            it. Read-only: nothing here writes back yet.
          </p>
        </div>
        <a class="queue" routerLink="../candidates">
          Review queue
          @if (stats(); as s) {
            <span class="ll-badge ll-badge-warn">{{ s.candidates.unresolved }}</span>
          }
        </a>
      </div>

      <div class="ll-card filters">
        <mat-form-field appearance="outline" class="search">
          <mat-label>Search statements, names, as-built text</mat-label>
          <input
            matInput
            [ngModel]="searchBox()"
            (ngModelChange)="onSearch($event)"
            placeholder="e.g. milepost truncate"
          />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Priority</mat-label>
          <mat-select multiple [ngModel]="priority()" (ngModelChange)="set('priority', $event)">
            @for (p of ['P0', 'P1', 'P2']; track p) {
              <mat-option [value]="p">{{ p }} ({{ facet('priority', p) }})</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Category</mat-label>
          <mat-select multiple [ngModel]="category()" (ngModelChange)="set('category', $event)">
            @for (c of categories(); track c) {
              <mat-option [value]="c">{{ c }} ({{ facet('category', c) }})</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Pattern</mat-label>
          <mat-select multiple [ngModel]="pattern()" (ngModelChange)="set('pattern', $event)">
            @for (p of patterns; track p) {
              <mat-option [value]="p">{{ p }} ({{ facet('pattern', p) }})</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline" class="wide">
          <mat-label>Domain</mat-label>
          <mat-select multiple [ngModel]="subject()" (ngModelChange)="set('subject', $event)">
            @for (s of subjects(); track s) {
              <mat-option [value]="s">{{ s }} ({{ facet('subject', s) }})</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Sort</mat-label>
          <mat-select [ngModel]="sort()" (ngModelChange)="set('sort', $event)">
            <mat-option value="priority">Priority, then errors</mat-option>
            <mat-option value="errors">Most blocking first</mat-option>
            <mat-option value="confidence">Weakest extraction first</mat-option>
            <mat-option value="name">Name</mat-option>
            <mat-option value="subject">Domain</mat-option>
            <mat-option value="id">Identifier</mat-option>
          </mat-select>
        </mat-form-field>

        <div class="toggles">
          <mat-checkbox
            [ngModel]="severityError()"
            (ngModelChange)="set('severity', $event ? 'ERROR' : '')"
            matTooltip="Rules with at least one evaluated ERROR finding — these cannot be approved until it clears"
            >Has ERROR</mat-checkbox
          >
          <mat-checkbox
            [ngModel]="smeQuestion()"
            (ngModelChange)="set('smeQuestion', $event)"
            matTooltip="The extractor raised a question for a subject-matter expert"
            >SME question</mat-checkbox
          >
          <mat-checkbox
            [ngModel]="suspectedDefect()"
            (ngModelChange)="set('suspectedDefect', $event)"
            matTooltip="The extractor suspects the legacy behaviour is a defect"
            >Suspected defect</mat-checkbox
          >
          <mat-checkbox
            [ngModel]="candidate()"
            (ngModelChange)="set('candidate', $event)"
            matTooltip="Part of an unresolved merge-candidate pair"
            >In review queue</mat-checkbox
          >
          @if (anyFilter()) {
            <button mat-button (click)="clear()">Clear filters</button>
          }
        </div>
      </div>

      @if (page(); as p) {
        <div class="result-line ll-small ll-muted">
          {{ p.total | number }} of {{ corpusTotal(p) | number }} rules
          @if (anyFilter()) {
            <span> match these filters</span>
          }
        </div>

        <div class="ll-card ll-card-flush">
          <table mat-table [dataSource]="p.rows" class="table">
            <ng-container matColumnDef="flags">
              <th mat-header-cell *matHeaderCellDef class="c-flags"></th>
              <td mat-cell *matCellDef="let r" class="c-flags">
                @if (r.errorCount) {
                  <span
                    class="ll-badge ll-badge-error"
                    [matTooltip]="r.errorCount + ' ERROR finding(s) block approval'"
                    >{{ r.errorCount }}E</span
                  >
                }
                @if (r.warnCount) {
                  <span class="ll-badge ll-badge-warn" [matTooltip]="r.warnCount + ' warning(s)'"
                    >{{ r.warnCount }}W</span
                  >
                }
                @if (r.notEvaluatedCount) {
                  <span
                    class="ll-badge ll-badge-neutral"
                    [matTooltip]="
                      r.notEvaluatedCount +
                      ' check(s) could not run on this rule — not a violation'
                    "
                    >{{ r.notEvaluatedCount }}?</span
                  >
                }
                @if (!r.errorCount && !r.warnCount && !r.notEvaluatedCount) {
                  <span class="ll-badge ll-badge-ok" matTooltip="No findings">clean</span>
                }
              </td>
            </ng-container>

            <ng-container matColumnDef="rule">
              <th mat-header-cell *matHeaderCellDef>Rule</th>
              <td mat-cell *matCellDef="let r">
                <a class="name" [routerLink]="[r.grId]">{{ r.name || r.grId }}</a>
                <div class="stmt">{{ r.statement }}</div>
                <div class="chips">
                  @if (r.hasSmeQuestion) {
                    <span class="ll-badge ll-badge-warn">SME question</span>
                  }
                  @if (r.hasSuspectedDefect) {
                    <span class="ll-badge ll-badge-error">suspected defect</span>
                  }
                  @if (r.edited) {
                    <span class="ll-badge ll-badge-ok">human edit</span>
                  }
                  @if (r.candidateCount) {
                    <span class="ll-badge ll-badge-neutral"
                      >{{ r.candidateCount }} candidate{{ r.candidateCount > 1 ? 's' : '' }}</span
                    >
                  }
                  @if (r.structuredBodyType) {
                    <span class="ll-badge ll-badge-neutral">{{ r.structuredBodyType }}</span>
                  }
                </div>
              </td>
            </ng-container>

            <ng-container matColumnDef="domain">
              <th mat-header-cell *matHeaderCellDef class="c-domain">Domain</th>
              <td mat-cell *matCellDef="let r" class="c-domain ll-small">{{ r.subject }}</td>
            </ng-container>

            <ng-container matColumnDef="class">
              <th mat-header-cell *matHeaderCellDef class="c-class">Class</th>
              <td mat-cell *matCellDef="let r" class="c-class">
                @if (r.ruleClass) {
                  <span class="ll-badge" [class]="'ll-badge-' + r.ruleClass">{{
                    r.ruleClass
                  }}</span>
                }
                <div class="ll-small mono pattern">{{ r.pattern }}</div>
              </td>
            </ng-container>

            <ng-container matColumnDef="meta">
              <th mat-header-cell *matHeaderCellDef class="c-meta">Priority</th>
              <td mat-cell *matCellDef="let r" class="c-meta">
                <span class="ll-badge" [class]="'ll-badge-' + (r.priority || 'neutral').toLowerCase()">{{
                  r.priority
                }}</span>
                <div class="ll-small ll-muted">{{ r.category }}</div>
                <div class="ll-small ll-muted" [matTooltip]="'confidence_extraction'">
                  {{ r.confidenceExtraction }}
                </div>
              </td>
            </ng-container>

            <ng-container matColumnDef="cites">
              <th mat-header-cell *matHeaderCellDef class="c-cites">Cites</th>
              <td mat-cell *matCellDef="let r" class="c-cites ll-small">{{ r.citationCount }}</td>
            </ng-container>

            <tr mat-header-row *matHeaderRowDef="columns"></tr>
            <tr mat-row *matRowDef="let row; columns: columns"></tr>
          </table>

          @if (p.rows.length === 0) {
            <div class="no-rows">
              Nothing matches these filters.
              <button mat-button (click)="clear()">Clear filters</button>
            </div>
          }

          <mat-paginator
            [length]="p.total"
            [pageSize]="p.pageSize"
            [pageIndex]="p.page - 1"
            [pageSizeOptions]="[10, 25, 50, 100]"
            (page)="onPage($event)"
          />
        </div>
      } @else {
        <div class="ll-card">Loading requirements…</div>
      }
    </div>
  `,
  styles: `
    .top { display: flex; align-items: flex-start; gap: 24px; margin-bottom: 14px; }
    .top p { margin: 0; max-width: 70ch; }
    .queue {
      margin-left: auto;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--ll-line);
      background: #fff;
      border-radius: 999px;
      padding: 7px 14px;
      white-space: nowrap;
      font-weight: 500;
    }
    .queue:hover { text-decoration: none; border-color: #b9cbdc; }

    .filters {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 14px;
      align-items: flex-start;
      margin-bottom: 12px;
    }
    .filters mat-form-field { width: 180px; }
    .filters .search { flex: 1 1 340px; min-width: 260px; }
    .filters .wide { width: 230px; }
    .toggles {
      display: flex;
      flex-wrap: wrap;
      gap: 4px 18px;
      align-items: center;
      flex-basis: 100%;
      padding-top: 2px;
    }
    .result-line { margin: 2px 0 8px; }

    .table { width: 100%; }
    .name { font-weight: 600; color: var(--ll-navy); }
    .stmt { margin: 2px 0 4px; max-width: 78ch; color: var(--ll-ink); }
    .chips { display: flex; flex-wrap: wrap; gap: 5px; }
    .c-flags { width: 92px; white-space: nowrap; }
    .c-flags .ll-badge { margin-right: 3px; }
    .c-domain { width: 150px; color: var(--ll-muted); }
    .c-class { width: 118px; }
    .c-meta { width: 108px; }
    .c-cites { width: 56px; text-align: right; }
    .pattern { color: var(--ll-muted); margin-top: 2px; }
    td.mat-mdc-cell { padding: 10px 12px; vertical-align: top; }
    th.mat-mdc-header-cell { padding: 8px 12px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ll-muted); }
    .no-rows { padding: 28px; text-align: center; color: var(--ll-muted); }
  `,
})
export class RequirementsList {
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  readonly route = inject(ActivatedRoute);
  readonly patterns = PATTERNS;
  readonly columns = ['flags', 'rule', 'domain', 'class', 'meta', 'cites'];

  private readonly systemId = signal('');
  readonly page = signal<RequirementPage | null>(null);
  readonly stats = signal<Stats | null>(null);

  /** Filter state lives in the URL so a filtered view is a shareable link. */
  private readonly params = signal<Record<string, string>>({});
  readonly searchBox = computed(() => this.params()['search'] ?? '');
  readonly priority = computed(() => csvList(this.params()['priority']));
  readonly category = computed(() => csvList(this.params()['category']));
  readonly pattern = computed(() => csvList(this.params()['pattern']));
  readonly subject = computed(() => csvList(this.params()['subject']));
  readonly sort = computed(() => this.params()['sort'] ?? 'priority');
  readonly severityError = computed(() => this.params()['severity'] === 'ERROR');
  readonly smeQuestion = computed(() => this.params()['smeQuestion'] === 'true');
  readonly suspectedDefect = computed(() => this.params()['suspectedDefect'] === 'true');
  readonly candidate = computed(() => this.params()['candidate'] === 'true');

  readonly categories = computed(() => this.facetKeys('category'));
  readonly subjects = computed(() => this.facetKeys('subject'));

  readonly anyFilter = computed(() => {
    const p = this.params();
    return Object.keys(p).some(
      (k) => !['sort', 'page', 'pageSize'].includes(k) && p[k],
    );
  });

  private searchTimer?: ReturnType<typeof setTimeout>;

  constructor() {
    this.route.paramMap.subscribe((p) => {
      const id = p.get('systemId') ?? '';
      if (id !== this.systemId()) {
        this.systemId.set(id);
        this.stats.set(null);
        this.api.stats(id).subscribe((s) => this.stats.set(s));
      }
    });

    this.route.queryParamMap.subscribe((q) => {
      const next: Record<string, string> = {};
      for (const key of q.keys) next[key] = q.get(key) ?? '';
      this.params.set(next);
    });

    effect(() => {
      const systemId = this.systemId();
      const p = this.params();
      if (!systemId) return;
      const filters: RequirementFilters = {
        search: p['search'] || undefined,
        priority: csv(p['priority']),
        category: csv(p['category']),
        pattern: csv(p['pattern']),
        subject: csv(p['subject']),
        ruleClass: csv(p['ruleClass']),
        severity: p['severity'] || undefined,
        smeQuestion: p['smeQuestion'] === 'true',
        suspectedDefect: p['suspectedDefect'] === 'true',
        candidate: p['candidate'] === 'true',
        edited: p['edited'] === 'true',
        sort: p['sort'] || 'priority',
        page: Number(p['page'] || 1),
        pageSize: Number(p['pageSize'] || 25),
      };
      this.api.requirements(systemId, filters).subscribe((res) => this.page.set(res));
    });
  }

  corpusTotal(p: RequirementPage): number {
    return this.stats()?.total ?? p.total;
  }

  facet(kind: string, value: string): number {
    const key = kind === 'ruleClass' ? 'rule_class' : kind;
    return this.stats() ? (this.facetMap(key)[value] ?? 0) : 0;
  }

  private facetMap(key: string): Record<string, number> {
    const s = this.stats();
    if (!s) return {};
    switch (key) {
      case 'priority': return s.byPriority;
      case 'category': return s.byCategory;
      case 'pattern': return s.byPattern;
      case 'subject': return s.bySubject;
      case 'rule_class': return s.byRuleClass;
      default: return {};
    }
  }

  private facetKeys(key: string): string[] {
    return Object.keys(this.facetMap(key)).filter((k) => k !== '(none)').sort();
  }

  onSearch(value: string): void {
    clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => this.set('search', value), 250);
  }

  set(key: string, value: string | string[] | boolean): void {
    const next = { ...this.params() };
    const flat = Array.isArray(value) ? value.join(',') : String(value ?? '');
    if (!flat || flat === 'false') delete next[key];
    else next[key] = flat;
    if (key !== 'page') delete next['page'];
    void this.router.navigate([], { relativeTo: this.route, queryParams: next });
  }

  onPage(e: PageEvent): void {
    const next = { ...this.params(), page: String(e.pageIndex + 1), pageSize: String(e.pageSize) };
    void this.router.navigate([], { relativeTo: this.route, queryParams: next });
  }

  clear(): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { sort: this.sort() },
    });
  }
}

/** For the API: absent rather than empty, so no filter is sent. */
function csv(value?: string): string[] | undefined {
  const list = csvList(value);
  return list.length ? list : undefined;
}

/** For `[ngModel]` on a multi-select, which wants an array. */
function csvList(value?: string): string[] {
  return value ? value.split(',').filter(Boolean) : [];
}
