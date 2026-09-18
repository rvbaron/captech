import {
  Component,
  ElementRef,
  Input,
  OnChanges,
  ViewChild,
  signal,
} from '@angular/core';
import mermaid from 'mermaid';

let initialized = false;
let seq = 0;

/**
 * Renders one mermaid source into inline SVG, themed to the brand palette.
 *
 * The generated diagrams are large (the NNG call graph is ~4 KB of source), so
 * the SVG is left at its natural size inside a scrolling frame rather than
 * squeezed to fit — a legible diagram you pan beats an illegible one that fits.
 */
@Component({
  selector: 'mermaid-view',
  template: `
    <figure class="wrap">
      @if (error()) {
        <div class="err">
          <strong>This diagram did not render.</strong>
          <div class="ll-small">{{ error() }}</div>
          <details>
            <summary class="ll-small">Show source</summary>
            <pre>{{ source }}</pre>
          </details>
        </div>
      }
      <div #host class="frame" [class.hidden]="error()"></div>
      @if (caption) {
        <figcaption class="ll-small ll-muted">{{ caption }}</figcaption>
      }
    </figure>
  `,
  styles: `
    .wrap { margin: 0; }
    .frame {
      overflow: auto;
      background: #fff;
      border: 1px solid var(--ll-line);
      border-radius: var(--ll-radius);
      padding: 14px;
      max-height: 78vh;
    }
    .frame.hidden { display: none; }
    .frame ::ng-deep svg { max-width: none; height: auto; }
    figcaption { margin-top: 6px; }
    .err {
      border: 1px solid #f3c2bd;
      background: var(--ll-error-bg);
      border-radius: var(--ll-radius);
      padding: 12px 14px;
    }
    .err pre { white-space: pre-wrap; max-height: 320px; overflow: auto; }
  `,
})
export class MermaidView implements OnChanges {
  @Input() source = '';
  @Input() caption?: string;

  @ViewChild('host', { static: true }) host!: ElementRef<HTMLDivElement>;
  readonly error = signal<string | null>(null);

  async ngOnChanges(): Promise<void> {
    if (!initialized) {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        theme: 'base',
        themeVariables: {
          fontFamily: 'Gibson, Montserrat, system-ui, sans-serif',
          primaryColor: '#e8eff5',
          primaryBorderColor: '#003865',
          primaryTextColor: '#00243f',
          lineColor: '#5c6b7a',
          secondaryColor: '#eaf7e8',
          tertiaryColor: '#f4f6f8',
          clusterBkg: '#f7f9fb',
          clusterBorder: '#dde3e9',
        },
        maxTextSize: 2_000_000,
        flowchart: { useMaxWidth: false, htmlLabels: true },
        sequence: { useMaxWidth: false },
      });
      initialized = true;
    }

    const el = this.host?.nativeElement;
    if (!el) return;
    if (!this.source?.trim()) {
      el.innerHTML = '';
      return;
    }

    this.error.set(null);
    try {
      const { svg } = await mermaid.render(`mmd-${++seq}`, this.source);
      el.innerHTML = svg;
    } catch (e) {
      el.innerHTML = '';
      this.error.set(e instanceof Error ? e.message : String(e));
    }
  }
}
