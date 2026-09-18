import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { Api } from '../core/api';

@Component({
  selector: 'page-dashboard',
  imports: [RouterLink],
  template: `
    <div class="ll-page">
      <div class="head">
        <div>
          <h1>Projects</h1>
          <p class="ll-muted">
            Engagements analyzed with the LegacyLift skills. One project, one analysis
            output tree.
          </p>
        </div>
      </div>

      @if (projects(); as list) {
        @if (list.length === 0) {
          <div class="ll-card empty">
            <strong>No projects in the demo dataset.</strong>
            <p class="ll-muted">
              Build it with
              <code>python platform-ui/tools/prepare_data.py</code>.
            </p>
          </div>
        }
        <div class="ll-grid cards">
          @for (p of list; track p.projectId) {
            <a class="ll-card card" [routerLink]="['/p', p.projectId]">
              <div class="client ll-small">{{ p.client }}</div>
              <h2>{{ p.name }}</h2>
              <p class="ll-muted summary">{{ p.summary }}</p>
              <div class="stats">
                @for (s of p.systems; track s.systemId) {
                  <div class="stat">
                    <div class="ll-small ll-muted">{{ s.label }}</div>
                    <div class="value">
                      @if (s.hasRequirements) {
                        {{ s.requirementCount }}
                        <span class="unit">rules</span>
                      } @else {
                        <span class="unit none">no rules extracted</span>
                      }
                    </div>
                  </div>
                }
              </div>
              <div class="step ll-small">
                Last step run: <strong>{{ p.currentStep }}</strong>
              </div>
            </a>
          }
        </div>
      } @else {
        <div class="ll-card">Loading…</div>
      }
    </div>
  `,
  styles: `
    .head { margin-bottom: 18px; }
    .head p { margin: 0; }
    .cards { grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); }
    .card {
      display: block;
      color: inherit;
      text-decoration: none;
      transition: box-shadow 0.15s, transform 0.15s;
    }
    .card:hover {
      text-decoration: none;
      box-shadow: 0 2px 4px rgba(0, 30, 60, 0.08), 0 10px 26px rgba(0, 30, 60, 0.1);
      transform: translateY(-1px);
    }
    .client {
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--ll-green-dark);
      font-weight: 600;
    }
    .summary { margin: 6px 0 14px; }
    .stats { display: flex; gap: 22px; flex-wrap: wrap; }
    .stat .value { font-size: 22px; font-weight: 600; color: var(--ll-navy); }
    .unit { font-size: 12px; font-weight: 400; color: var(--ll-muted); }
    .unit.none { font-size: 12px; }
    .step { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--ll-line); color: var(--ll-muted); }
    .empty { margin-bottom: 16px; }
  `,
})
export class Dashboard {
  private readonly api = inject(Api);
  readonly projects = toSignal(this.api.projects());
}
