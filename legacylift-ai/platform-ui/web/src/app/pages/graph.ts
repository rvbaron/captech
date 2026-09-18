import { Component, inject, signal } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { MatTabsModule } from '@angular/material/tabs';
import { ActivatedRoute } from '@angular/router';
import { Api } from '../core/api';
import { MermaidView } from '../shared/mermaid-view';

interface Loaded {
  name: string;
  label: string;
  source: string | null;
}

const DIAGRAMS = [
  { name: 'call-graph.mmd', label: 'Call graph' },
  { name: 'critical-path.mmd', label: 'Critical path' },
  { name: 'data-lineage.mmd', label: 'Data lineage' },
];

/**
 * The call graphs the map step emits. The mermaid fragments render natively so they match
 * the rest of the app; the full TOPOLOGY.html the skill emits is offered in its
 * own frame, because it is the richer artifact and reproducing it would be a
 * second implementation of the same thing.
 */
@Component({
  selector: 'page-graph',
  imports: [MatTabsModule, MermaidView],
  template: `
    <div class="ll-page">
      <h1>Graph</h1>
      <p class="ll-muted lede">
        Dependency and data-flow topology produced by <code>/modernize-map</code>.
      </p>

      <mat-tab-group animationDuration="0ms">
        @for (d of diagrams(); track d.name) {
          <mat-tab [label]="d.label">
            <div class="tab-body">
              @if (d.source) {
                <mermaid-view [source]="d.source" [caption]="d.name" />
              } @else {
                <div class="ll-card">This diagram is not in the demo dataset.</div>
              }
            </div>
          </mat-tab>
        }
        <mat-tab label="Full topology">
          <div class="tab-body">
            <div class="ll-small ll-muted frame-note">
              The interactive topology page as the map skill generated it, shown in a
              frame — it carries its own styling.
            </div>
            @if (topologyUrl(); as url) {
              <iframe
                class="topology"
                [src]="url"
                title="Topology"
                sandbox="allow-scripts allow-same-origin"
              ></iframe>
            }
          </div>
        </mat-tab>
      </mat-tab-group>
    </div>
  `,
  styles: `
    .lede { max-width: 80ch; margin-top: 0; }
    .tab-body { padding: 16px 0 4px; }
    .frame-note { margin-bottom: 8px; }
    .topology {
      width: 100%;
      height: 78vh;
      border: 1px solid var(--ll-line);
      border-radius: var(--ll-radius);
      background: #fff;
    }
  `,
})
export class Graph {
  private readonly api = inject(Api);
  private readonly route = inject(ActivatedRoute);
  private readonly sanitizer = inject(DomSanitizer);

  readonly diagrams = signal<Loaded[]>(
    DIAGRAMS.map((d) => ({ ...d, source: null })),
  );
  readonly topologyUrl = signal<SafeResourceUrl | null>(null);

  constructor() {
    this.route.paramMap.subscribe((p) => {
      const systemId = p.get('systemId') ?? '';
      this.diagrams.set(DIAGRAMS.map((d) => ({ ...d, source: null })));
      this.topologyUrl.set(
        this.sanitizer.bypassSecurityTrustResourceUrl(this.api.topologyUrl(systemId)),
      );
      for (const d of DIAGRAMS) {
        this.api.diagram(systemId, d.name).subscribe({
          next: (text) =>
            this.diagrams.update((list) =>
              list.map((x) => (x.name === d.name ? { ...x, source: text } : x)),
            ),
          error: () => {},
        });
      }
    });
  }
}
