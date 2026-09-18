import { Component, Input, OnChanges, signal } from '@angular/core';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Finding } from '../core/models';

interface Piece {
  text: string;
  severity: 'ERROR' | 'WARN' | null;
  findings: Finding[];
}

/**
 * Renders a requirement's `statement` with its findings highlighted in place.
 *
 * A finding's `span` is a character range into this exact string. On the NNG
 * corpus 41 of 287 findings carry one; the rest are statement-wide and are
 * listed beside the statement instead of highlighted, which is why this
 * component only ever draws the ranges it was given.
 */
@Component({
  selector: 'statement-view',
  imports: [MatTooltipModule],
  template: `
    <span class="stmt">
      @for (p of pieces(); track $index) {
        @if (p.severity) {
          <span
            [class.ll-span-error]="p.severity === 'ERROR'"
            [class.ll-span-warn]="p.severity === 'WARN'"
            [matTooltip]="tip(p)"
            matTooltipClass="ll-finding-tip"
            >{{ p.text }}</span
          >
        } @else {
          <span>{{ p.text }}</span>
        }
      }
    </span>
  `,
  styles: `
    .stmt { line-height: 1.7; }
  `,
})
export class StatementView implements OnChanges {
  @Input() statement = '';
  @Input() findings: Finding[] = [];

  readonly pieces = signal<Piece[]>([]);

  ngOnChanges(): void {
    this.pieces.set(build(this.statement, this.findings ?? []));
  }

  tip(p: Piece): string {
    return p.findings.map((f) => `${f.findingId} — ${f.message}`).join('\n\n');
  }
}

function build(statement: string, findings: Finding[]): Piece[] {
  const spanned = findings.filter(
    (f) =>
      f.spanStart !== null &&
      f.spanEnd !== null &&
      f.spanEnd > f.spanStart &&
      f.spanStart >= 0 &&
      f.spanEnd <= statement.length,
  );
  if (spanned.length === 0) {
    return [{ text: statement, severity: null, findings: [] }];
  }

  // Cut at every span boundary, then label each cut by the findings covering
  // it. Overlapping spans therefore merge rather than fight, and ERROR wins the
  // colour where two findings share characters.
  const cuts = new Set<number>([0, statement.length]);
  for (const f of spanned) {
    cuts.add(f.spanStart!);
    cuts.add(f.spanEnd!);
  }
  const ordered = [...cuts].sort((a, b) => a - b);

  const pieces: Piece[] = [];
  for (let i = 0; i < ordered.length - 1; i++) {
    const from = ordered[i];
    const to = ordered[i + 1];
    if (to <= from) continue;
    const covering = spanned.filter((f) => f.spanStart! <= from && f.spanEnd! >= to);
    const severity = covering.some((f) => f.severity === 'ERROR')
      ? 'ERROR'
      : covering.length
        ? 'WARN'
        : null;
    pieces.push({
      text: statement.slice(from, to),
      severity: severity as Piece['severity'],
      findings: covering,
    });
  }
  return pieces;
}
