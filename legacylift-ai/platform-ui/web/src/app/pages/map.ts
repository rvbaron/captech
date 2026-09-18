import { DecimalPipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Api } from '../core/api';
import { DomainsPayload } from '../core/models';
import { MermaidView } from '../shared/mermaid-view';

/**
 * The domain map: the architecture diagram plus the domain tagging that
 * everything downstream is bucketed by. `excluded` is a reserved value, not a
 * domain, so it is reported separately rather than ranked among the others.
 */
@Component({
  selector: 'page-map',
  imports: [MermaidView, DecimalPipe],
  template: `
    <div class="ll-page">
      <h1>Map</h1>
      <p class="ll-muted lede">
        How the system is put together, and how its files are bucketed into business
        domains. Domains come from the assess step and are the axis the requirements are
        grouped along.
      </p>

      <div class="ll-section-title">
        <h2>Architecture</h2>
        <span class="count">ARCHITECTURE.mmd</span>
      </div>
      @if (architecture()) {
        <mermaid-view [source]="architecture()!" />
      } @else {
        <div class="ll-card">Loading diagram…</div>
      }

      @if (domains(); as d) {
        <div class="ll-section-title">
          <h2>Domains</h2>
          <span class="count">
            {{ (d.definition.domains ?? []).length }} domains ·
            {{ taggedFiles(d) | number }} files tagged
          </span>
        </div>

        <div class="ll-card ll-card-flush">
          <table class="dom">
            <thead>
              <tr>
                <th>Domain</th>
                <th class="num">Files</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              @for (dom of d.definition.domains ?? []; track dom.domain_id) {
                <tr>
                  <td>
                    <div class="dname">{{ dom.name }}</div>
                    <div class="mono ll-small ll-muted">{{ dom.domain_id }}</div>
                  </td>
                  <td class="num">
                    {{ files(d, dom.domain_id) | number }}
                    <div class="minibar">
                      <span [style.width.%]="pct(d, dom.domain_id)"></span>
                    </div>
                  </td>
                  <td class="desc ll-small">{{ dom.description }}</td>
                </tr>
              }
            </tbody>
          </table>
        </div>

        <div class="ll-grid notes">
          @if (d.fileCounts['excluded']) {
            <div class="ll-card">
              <h3>Excluded by design</h3>
              <p class="ll-small">
                {{ files(d, 'excluded') | number }} files are tagged
                <code>excluded</code> — generated code, vendored libraries and build
                output named by <code>exclude_globs</code>. They are dropped from the
                coverage denominator rather than counted as untagged gaps.
              </p>
            </div>
          }
          @if (d.fileCounts['unassigned']) {
            <div class="ll-card">
              <h3>Unassigned</h3>
              <p class="ll-small">
                {{ files(d, 'unassigned') | number }} files matched no domain glob.
                That is an accepted gap, not a failure.
              </p>
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: `
    .lede { max-width: 84ch; margin-top: 0; }
    .dom { width: 100%; border-collapse: collapse; }
    .dom th {
      text-align: left;
      padding: 9px 14px;
      background: #f7f9fb;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--ll-muted);
      border-bottom: 1px solid var(--ll-line);
    }
    .dom td { padding: 10px 14px; border-bottom: 1px solid var(--ll-line); vertical-align: top; }
    .dom tr:last-child td { border-bottom: none; }
    .num { width: 110px; text-align: right; font-variant-numeric: tabular-nums; }
    .dname { font-weight: 600; color: var(--ll-navy); }
    .desc { color: var(--ll-muted); max-width: 70ch; }
    .minibar { height: 5px; background: #eceff2; border-radius: 3px; margin-top: 4px; overflow: hidden; }
    .minibar span { display: block; height: 100%; background: var(--ll-green); }
    .notes { margin-top: 16px; }
    .notes p { margin: 4px 0 0; }
  `,
})
export class MapPage {
  private readonly api = inject(Api);
  private readonly route = inject(ActivatedRoute);

  readonly architecture = signal<string | null>(null);
  readonly domains = signal<DomainsPayload | null>(null);

  constructor() {
    this.route.paramMap.subscribe((p) => {
      const systemId = p.get('systemId') ?? '';
      this.architecture.set(null);
      this.domains.set(null);
      this.api.diagram(systemId, 'ARCHITECTURE.mmd').subscribe({
        next: (t) => this.architecture.set(t),
        error: () => this.architecture.set(null),
      });
      this.api.domains(systemId).subscribe({
        next: (d) => this.domains.set(d),
        error: () => this.domains.set(null),
      });
    });
  }

  /** A domain with no tagged files is absent from the map, not zero. */
  files(d: DomainsPayload, domainId: string): number {
    return d.fileCounts[domainId] ?? 0;
  }

  taggedFiles(d: DomainsPayload): number {
    return Object.values(d.fileCounts).reduce((sum, n) => sum + n, 0);
  }

  pct(d: DomainsPayload, domainId: string): number {
    const counts = (d.definition.domains ?? []).map((x) => this.files(d, x.domain_id));
    const max = Math.max(1, ...counts);
    return (this.files(d, domainId) / max) * 100;
  }
}
