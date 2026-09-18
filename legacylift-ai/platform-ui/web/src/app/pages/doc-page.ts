import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { combineLatest } from 'rxjs';
import { Api } from '../core/api';
import { MarkdownView } from '../shared/markdown-view';

/**
 * Renders one generated markdown document for a system. Which file to show
 * comes from the route's `data`, so ASSESSMENT, PREFLIGHT, DATA_OBJECTS and
 * BUSINESS_RULES all share this page.
 */
@Component({
  selector: 'page-doc',
  imports: [MarkdownView],
  template: `
    <div class="ll-page">
      <div class="head">
        <h1>{{ heading() }}</h1>
        <span class="ll-small ll-muted mono">{{ docName() }}</span>
      </div>

      @if (stale()) {
        <!-- BUSINESS_RULES.md and DATA_OBJECTS.md were never re-rendered into the
             current analysis tree; these copies predate the requirements store. -->
        <div class="warn">
          <strong>This document predates the requirements store.</strong>
          It was generated in an earlier run and has not been re-rendered since, so its
          counts and wording can disagree with the Requirements pages, which read the
          store directly.
        </div>
      }

      @if (error()) {
        <div class="ll-card">
          <strong>This document is not in the demo dataset.</strong>
          <p class="ll-muted">
            {{ docName() }} was not found for this system. Rebuild the dataset with
            <code>python platform-ui/tools/prepare_data.py</code> after the skill that
            produces it has run.
          </p>
        </div>
      } @else if (source()) {
        <div class="ll-card doc">
          <markdown-view [source]="source()!" />
        </div>
      } @else {
        <div class="ll-card">Loading document…</div>
      }
    </div>
  `,
  styles: `
    .head { display: flex; align-items: baseline; gap: 12px; margin-bottom: 12px; }
    .warn {
      border: 1px solid #f0dbb4;
      background: var(--ll-warn-bg);
      border-radius: var(--ll-radius);
      padding: 10px 14px;
      margin-bottom: 14px;
      max-width: 100ch;
      font-size: 13px;
    }
    .doc { max-width: 108ch; }
  `,
})
export class DocPage {
  private readonly api = inject(Api);
  private readonly route = inject(ActivatedRoute);

  readonly source = signal<string | null>(null);
  readonly error = signal(false);
  readonly docName = signal('');
  readonly heading = signal('');
  readonly stale = signal(false);

  constructor() {
    combineLatest([this.route.paramMap, this.route.data]).subscribe(([params, data]) => {
      const systemId = params.get('systemId') ?? '';
      const doc = (data['doc'] as string) ?? '';
      this.docName.set(doc);
      this.heading.set((data['heading'] as string) ?? doc);
      this.source.set(null);
      this.error.set(false);

      this.api.system(this.projectId(), systemId).subscribe((s) => {
        this.stale.set(s?.docs.some((d) => d.name === doc && d.stale) ?? false);
      });

      this.api.doc(systemId, doc).subscribe({
        next: (text) => this.source.set(text),
        error: () => this.error.set(true),
      });
    });
  }

  private projectId(): string {
    return this.route.parent?.snapshot.paramMap.get('projectId') ?? '';
  }
}
