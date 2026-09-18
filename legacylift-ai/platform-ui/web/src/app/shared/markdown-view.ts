import { Component, Input, OnChanges } from '@angular/core';
import { marked } from 'marked';
import { MermaidView } from './mermaid-view';

type Block =
  | { kind: 'html'; html: string }
  | { kind: 'mermaid'; code: string };

/**
 * Renders a generated markdown document.
 *
 * Fenced ```mermaid blocks are pulled out before parsing and re-inserted as
 * <mermaid-view> hosts, because the skills' documents carry their diagrams
 * inline and a document showing fence source instead of a diagram is not the
 * deliverable.
 */
@Component({
  selector: 'markdown-view',
  imports: [MermaidView],
  template: `
    <div class="ll-markdown">
      @for (b of blocks; track $index) {
        @if (b.kind === 'html') {
          <div [innerHTML]="b.html"></div>
        } @else {
          <mermaid-view [source]="b.code"></mermaid-view>
        }
      }
    </div>
  `,
})
export class MarkdownView implements OnChanges {
  @Input() source = '';
  blocks: Block[] = [];

  ngOnChanges(): void {
    this.blocks = this.source ? split(this.source) : [];
  }
}

const MERMAID_FENCE = /^```mermaid[^\n]*\n([\s\S]*?)^```[ \t]*$/gm;

function split(markdown: string): Block[] {
  const blocks: Block[] = [];
  let cursor = 0;
  for (const match of markdown.matchAll(MERMAID_FENCE)) {
    const at = match.index ?? 0;
    if (at > cursor) blocks.push(toHtml(markdown.slice(cursor, at)));
    blocks.push({ kind: 'mermaid', code: match[1] });
    cursor = at + match[0].length;
  }
  if (cursor < markdown.length) blocks.push(toHtml(markdown.slice(cursor)));
  return blocks;
}

function toHtml(md: string): Block {
  return { kind: 'html', html: marked.parse(md, { async: false, gfm: true }) as string };
}
