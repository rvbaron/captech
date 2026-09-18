import { SlicePipe } from '@angular/common';
import { Component, Input, OnChanges, computed, inject, signal } from '@angular/core';
import hljs from 'highlight.js/lib/common';
import { Api } from '../core/api';
import { Citation, Snippet } from '../core/models';

interface Line {
  no: number;
  html: string;
  cited: boolean;
}

/**
 * Shows the cited lines of a citation with syntax highlighting.
 *
 * Only the cited range plus a little context was ever copied out of the client
 * codebase (see `tools/prepare_data.py`), so this can never browse the wider
 * source tree — which is the point.
 */
@Component({
  selector: 'code-snippet',
  imports: [SlicePipe],
  template: `
    @if (loading()) {
      <div class="ll-small ll-muted pad">Loading source…</div>
    } @else if (!snippet()?.available) {
      <div class="missing ll-small">
        The cited file was not readable when the demo dataset was built, so the
        source is unavailable here.
        <div class="mono">{{ citation.relativePath }}:{{ citation.startLine }}</div>
      </div>
    } @else {
      <div class="head">
        <span class="mono path">{{ citation.relativePath }}</span>
        <span class="ll-badge ll-badge-neutral">
          lines {{ citation.startLine }}–{{ citation.endLine }}
        </span>
        <span class="ll-badge" [class]="resolutionClass()">
          {{ citation.anchorResolution }}
        </span>
        @if (citation.verifiedAt) {
          <span class="ll-small ll-muted">verified {{ citation.verifiedAt | slice: 0:10 }}</span>
        }
      </div>
      <pre class="code"><code>@for (l of lines(); track l.no) {<span
          class="line" [class.cited]="l.cited"><span class="no">{{ l.no }}</span><span
          class="src" [innerHTML]="l.html"></span></span>}</code></pre>
      @if (citation.contentHash) {
        <div class="ll-small ll-muted mono foot">{{ citation.contentHash }}</div>
      }
    }
  `,
  styles: `
    .pad { padding: 10px 12px; }
    .head {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      padding: 8px 10px;
      border: 1px solid var(--ll-line);
      border-bottom: none;
      border-radius: var(--ll-radius) var(--ll-radius) 0 0;
      background: #f7f9fb;
    }
    .path { word-break: break-all; font-weight: 600; color: var(--ll-navy); }
    .code {
      margin: 0;
      background: #0e1b28;
      color: #e6edf3;
      border-radius: 0 0 var(--ll-radius) var(--ll-radius);
      padding: 10px 0;
      overflow-x: auto;
      max-height: 460px;
      overflow-y: auto;
      font-size: 12.5px;
      line-height: 1.5;
    }
    .line { display: block; white-space: pre; }
    .line.cited { background: rgba(81, 183, 73, 0.16); box-shadow: inset 3px 0 0 var(--ll-green); }
    .no {
      display: inline-block;
      width: 52px;
      padding-right: 12px;
      text-align: right;
      color: #5c7189;
      user-select: none;
    }
    .missing {
      border: 1px dashed var(--ll-line);
      border-radius: var(--ll-radius);
      padding: 10px 12px;
      color: var(--ll-muted);
    }
    .foot { padding: 4px 2px 0; }
  `,
})
export class CodeSnippet implements OnChanges {
  private readonly api = inject(Api);

  @Input({ required: true }) systemId!: string;
  @Input({ required: true }) citation!: Citation;

  readonly snippet = signal<Snippet | null>(null);
  readonly loading = signal(true);

  readonly lines = computed<Line[]>(() => {
    const s = this.snippet();
    if (!s?.lines) return [];
    const first = s.firstLine ?? s.startLine;
    const language = s.language && hljs.getLanguage(s.language) ? s.language : undefined;
    // Highlighting the block as a whole keeps multi-line constructs (comments,
    // strings) correct; `ignoreIllegals` stops a partial slice from bailing out.
    const body = s.lines.join('\n');
    const marked = language
      ? hljs.highlight(body, { language, ignoreIllegals: true }).value
      : escapeHtml(body);
    return splitHighlighted(marked).map((html, i) => ({
      no: first + i,
      html: html === '' ? ' ' : html,
      cited: first + i >= s.startLine && first + i <= s.endLine,
    }));
  });

  ngOnChanges(): void {
    this.loading.set(true);
    this.snippet.set(null);
    this.api.snippet(this.systemId, this.citation.citationId).subscribe({
      next: (s) => {
        this.snippet.set(s);
        this.loading.set(false);
      },
      error: () => {
        this.snippet.set(null);
        this.loading.set(false);
      },
    });
  }

  resolutionClass(): string {
    return this.citation.anchorResolution === 'unresolved'
      ? 'll-badge-warn'
      : 'll-badge-ok';
  }
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]!);
}

/**
 * highlight.js emits one HTML string with newlines inside spans. Splitting on
 * newlines would tear those spans, so each line re-opens the spans still on the
 * stack and closes them at the line end.
 */
function splitHighlighted(html: string): string[] {
  const out: string[] = [];
  const stack: string[] = [];
  let line = '';
  const tag = /<\/?span[^>]*>/g;
  let at = 0;

  const pushText = (text: string) => {
    const parts = text.split('\n');
    parts.forEach((part, i) => {
      line += part;
      if (i < parts.length - 1) {
        out.push(line + '</span>'.repeat(stack.length));
        line = stack.join('');
      }
    });
  };

  let m: RegExpExecArray | null;
  while ((m = tag.exec(html)) !== null) {
    pushText(html.slice(at, m.index));
    if (m[0].startsWith('</')) stack.pop();
    else stack.push(m[0]);
    line += m[0];
    at = m.index + m[0].length;
  }
  pushText(html.slice(at));
  out.push(line);
  return out;
}
