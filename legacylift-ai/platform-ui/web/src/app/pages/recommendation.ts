import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

/**
 * The modernization brief has not been generated for either NNG system, so this
 * page says exactly that rather than showing something adjacent. An empty state
 * that names the step that would fill it is more useful in a demo than a page
 * of content nothing produced.
 */
@Component({
  selector: 'page-recommendation',
  imports: [RouterLink],
  template: `
    <div class="ll-page">
      <h1>Recommendation</h1>
      <div class="ll-card empty">
        <div class="glyph">—</div>
        <h2>No modernization brief yet</h2>
        <p>
          This page renders the phased plan produced by
          <code>/modernize-brief</code>. That step has not been run for this system, so
          there is nothing to show — and nothing here is inferred from the steps that
          have run.
        </p>
        <p class="ll-small ll-muted">
          The brief is the approved plan that transformation work executes against. It
          draws on the assessment, the topology and the reviewed requirements, which is
          why it comes last in the workflow.
        </p>
        <div class="links">
          <a routerLink="../assess">Assessment</a>
          <a routerLink="../map">Map</a>
          <a routerLink="../requirements">Requirements</a>
        </div>
      </div>
    </div>
  `,
  styles: `
    .empty { max-width: 74ch; text-align: center; padding: 40px 32px; }
    .glyph { font-size: 40px; color: #c9d3dc; line-height: 1; }
    .empty h2 { margin: 10px 0 8px; }
    .empty p { text-align: left; }
    .links { display: flex; gap: 18px; justify-content: center; margin-top: 18px; }
  `,
})
export class Recommendation {}
