import { Component, computed, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Api } from '../core/api';
import { CandidatePair } from '../core/models';

const REASONS: Record<string, { title: string; blurb: string }> = {
  drift: {
    title: 'Drift',
    blurb:
      'The same rule was recognised by its anchors, but the code it cites has changed ' +
      'since it was last verified. The question is whether the requirement still ' +
      'describes what the code now does — a different job from judging a duplicate.',
  },
  semantic: {
    title: 'Near-duplicate wording',
    blurb:
      'Two records say something similar. The merge deliberately under-merges and ' +
      'never auto-merges these, so a human decides whether they are one rule or two.',
  },
  range_overlap: {
    title: 'Overlapping citations',
    blurb:
      'Two records cite overlapping lines of the same file. They may be one rule seen ' +
      'twice, or two genuinely different rules implemented together.',
  },
};

/**
 * The unresolved merge-candidate queue. Read-only: resolving a pair writes
 * `gr_merge_candidate.resolution`, which Milestone 1 does not do — so this
 * screen presents the decision and stops short of taking it.
 */
@Component({
  selector: 'page-candidates',
  imports: [RouterLink, MatButtonModule],
  template: `
    <div class="ll-page">
      <h1>Review queue</h1>
      <p class="ll-muted lede">
        Pairs the merge surfaced but refused to merge on its own. Each one is a decision
        for a reviewer: the same rule, or two different rules.
      </p>

      <div class="tabs">
        <button
          class="tab"
          [class.on]="reason() === ''"
          (click)="setReason('')"
        >
          All <span class="n">{{ pairs().length }}</span>
        </button>
        @for (r of reasonKeys(); track r) {
          <button class="tab" [class.on]="reason() === r" (click)="setReason(r)">
            {{ REASONS[r].title }} <span class="n">{{ countFor(r) }}</span>
          </button>
        }
      </div>

      @if (reason(); as r) {
        <div class="ll-card blurb">{{ REASONS[r].blurb }}</div>
      }

      @if (visible().length === 0) {
        <div class="ll-card">Nothing unresolved in this category.</div>
      }

      @for (p of visible(); track p.existing.grId + p.incoming.grId) {
        <div class="pair ll-card">
          <div class="pair-head">
            <span class="ll-badge" [class]="p.reason === 'drift' ? 'll-badge-warn' : 'll-badge-neutral'">
              {{ REASONS[p.reason].title }}
            </span>
            @if (p.similarity !== null) {
              <span class="ll-small ll-muted">similarity {{ p.similarity!.toFixed(3) }}</span>
            }
            <span class="ll-small ll-muted mono">{{ p.runId }}</span>
            <span class="ll-small hint">
              Resolving a pair writes to the store — not in this read-only preview.
            </span>
          </div>
          <div class="sides">
            @for (side of [p.existing, p.incoming]; track side.grId; let first = $first) {
              <div class="side">
                <div class="ll-small ll-muted role">{{ first ? 'existing' : 'incoming' }}</div>
                <a class="side-name" [routerLink]="['..', 'requirements', side.grId]">{{
                  side.name || side.grId
                }}</a>
                <div class="ll-small stmt">{{ side.statement }}</div>
                <div class="side-meta ll-small ll-muted">
                  <span class="ll-badge" [class]="'ll-badge-' + (side.priority || 'neutral').toLowerCase()">{{
                    side.priority
                  }}</span>
                  {{ side.subject }}
                </div>
              </div>
            }
          </div>
        </div>
      }
    </div>
  `,
  styles: `
    .lede { max-width: 80ch; margin-top: 0; }
    .tabs { display: flex; gap: 8px; flex-wrap: wrap; margin: 16px 0 12px; }
    .tab {
      font: inherit;
      background: #fff;
      border: 1px solid var(--ll-line);
      border-radius: 999px;
      padding: 6px 14px;
      cursor: pointer;
    }
    .tab:hover { border-color: #b9cbdc; }
    .tab.on { background: var(--ll-navy); border-color: var(--ll-navy); color: #fff; }
    .tab .n { opacity: 0.7; margin-left: 4px; font-variant-numeric: tabular-nums; }
    .blurb { max-width: 92ch; margin-bottom: 14px; color: var(--ll-muted); }
    .pair { margin-bottom: 12px; }
    .pair-head { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
    .hint { margin-left: auto; color: #9aa7b4; }
    .sides { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    @media (max-width: 900px) {
      .sides { grid-template-columns: 1fr; }
    }
    .side { border-left: 3px solid var(--ll-line); padding-left: 12px; }
    .role { text-transform: uppercase; letter-spacing: 0.06em; }
    .side-name { font-weight: 600; }
    .stmt { margin: 4px 0 6px; }
    .side-meta { display: flex; gap: 8px; align-items: center; }
  `,
})
export class Candidates {
  private readonly api = inject(Api);
  private readonly route = inject(ActivatedRoute);
  readonly REASONS = REASONS;

  readonly pairs = signal<CandidatePair[]>([]);
  readonly reason = signal('');

  readonly reasonKeys = computed(() =>
    Object.keys(REASONS).filter((r) => this.countFor(r) > 0),
  );

  readonly visible = computed(() => {
    const r = this.reason();
    return r ? this.pairs().filter((p) => p.reason === r) : this.pairs();
  });

  constructor() {
    this.route.paramMap.subscribe((p) => {
      this.pairs.set([]);
      this.api
        .candidates(p.get('systemId') ?? '')
        .subscribe((rows) => this.pairs.set(rows));
    });
  }

  countFor(reason: string): number {
    return this.pairs().filter((p) => p.reason === reason).length;
  }

  setReason(reason: string): void {
    this.reason.set(reason);
  }
}
