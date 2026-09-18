import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
  ActivatedRoute,
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive,
  RouterOutlet,
} from '@angular/router';
import { filter, map, startWith, switchMap } from 'rxjs';
import { Api } from '../core/api';
import { SystemSummary } from '../core/models';

interface NavItem {
  label: string;
  path: string[];
  note?: string;
  disabled?: boolean;
}

/**
 * Project chrome: the system switcher and the left-hand nav. Which system is
 * selected comes from the child route when the child has one, so deep links
 * stay honest; the first system is the fallback for project-level pages.
 */
@Component({
  selector: 'page-project-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    @if (project(); as p) {
      <div class="wrap">
        <aside class="side">
          <a class="back ll-small" routerLink="/">← All projects</a>
          <div class="title">{{ p.name }}</div>
          <div class="client ll-small">{{ p.client }}</div>

          <a
            class="nav-item top"
            [routerLink]="['/p', p.projectId, 'overview']"
            routerLinkActive="active"
            >Overview</a
          >

          <div class="switch">
            <div class="switch-label ll-small">System</div>
            @for (s of p.systems; track s.systemId) {
              <button
                class="sys"
                [class.on]="s.systemId === activeSystemId()"
                (click)="selectSystem(s.systemId)"
              >
                <span class="sys-label">{{ s.label }}</span>
                <span class="ll-small ll-muted">{{ s.kind }}</span>
              </button>
            }
          </div>

          <nav class="nav">
            @for (group of groups(); track group.title) {
              <div class="group-title ll-small">{{ group.title }}</div>
              @for (item of group.items; track item.label) {
                @if (item.disabled) {
                  <span class="nav-item off" [title]="item.note ?? ''">
                    {{ item.label }}
                    <span class="ll-small">not run</span>
                  </span>
                } @else {
                  <a class="nav-item" [routerLink]="item.path" routerLinkActive="active">
                    {{ item.label }}
                    @if (item.note) {
                      <span class="ll-small count">{{ item.note }}</span>
                    }
                  </a>
                }
              }
            }
          </nav>
        </aside>

        <main class="main">
          <router-outlet />
        </main>
      </div>
    } @else {
      <div class="ll-page">Loading project…</div>
    }
  `,
  styles: `
    .wrap { display: grid; grid-template-columns: 258px 1fr; min-height: calc(100vh - 58px); }
    .side {
      background: #fff;
      border-right: 1px solid var(--ll-line);
      padding: 18px 14px 40px;
    }
    .back { display: block; color: var(--ll-muted); margin-bottom: 14px; }
    .title { font-weight: 600; color: var(--ll-navy-deep); line-height: 1.3; }
    .client { color: var(--ll-muted); margin-bottom: 14px; }
    .switch { margin: 14px 0 8px; }
    .switch-label {
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--ll-muted);
      margin-bottom: 6px;
    }
    .sys {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      width: 100%;
      text-align: left;
      background: #f7f9fb;
      border: 1px solid var(--ll-line);
      border-radius: 8px;
      padding: 7px 10px;
      margin-bottom: 6px;
      cursor: pointer;
      font: inherit;
    }
    .sys:hover { border-color: #b9cbdc; }
    .sys.on { background: #eaf1f7; border-color: var(--ll-navy); }
    .sys.on .sys-label { color: var(--ll-navy); font-weight: 600; }
    .group-title {
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--ll-muted);
      margin: 16px 0 6px;
    }
    .nav-item {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 7px;
      color: var(--ll-ink);
      text-decoration: none;
      border-left: 3px solid transparent;
    }
    .nav-item.top { margin-bottom: 2px; }
    .nav-item:hover { background: #f4f7fa; text-decoration: none; }
    .nav-item.active {
      background: #eaf1f7;
      color: var(--ll-navy);
      font-weight: 600;
      border-left-color: var(--ll-green);
    }
    .nav-item.off { color: #9aa7b4; cursor: default; }
    .count { color: var(--ll-muted); font-weight: 400; }
    .main { min-width: 0; }
  `,
})
export class ProjectShell {
  private readonly api = inject(Api);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  private readonly projectId = toSignal(
    this.route.paramMap.pipe(map((p) => p.get('projectId') ?? '')),
    { initialValue: '' },
  );

  readonly project = toSignal(
    this.route.paramMap.pipe(
      switchMap((p) => this.api.project(p.get('projectId') ?? '')),
    ),
  );

  /** Set when the user clicks the switcher; the route wins when it names one. */
  private readonly chosen = signal<string | null>(null);

  private readonly routeSystemId = toSignal(
    this.router.events.pipe(
      filter((e) => e instanceof NavigationEnd),
      startWith(null),
      map(() => systemFromUrl(this.router.url)),
    ),
    { initialValue: systemFromUrl(this.router.url) },
  );

  readonly activeSystemId = computed(() => {
    const fromRoute = this.routeSystemId();
    if (fromRoute) return fromRoute;
    const picked = this.chosen();
    if (picked) return picked;
    return this.project()?.systems[0]?.systemId ?? '';
  });

  readonly activeSystem = computed<SystemSummary | undefined>(() =>
    this.project()?.systems.find((s) => s.systemId === this.activeSystemId()),
  );

  readonly groups = computed(() => {
    const p = this.project();
    const s = this.activeSystem();
    if (!p || !s) return [];
    const base = ['/p', p.projectId, s.systemId];
    const doc = (name: string) => s.docs.some((d) => d.name === name);

    const requirements: NavItem[] = s.hasRequirements
      ? [
          {
            label: 'Requirements',
            path: [...base, 'requirements'],
            note: String(s.requirementCount),
          },
          { label: 'Review queue', path: [...base, 'candidates'] },
        ]
      : [
          {
            label: 'Requirements',
            path: [],
            disabled: true,
            note: 'extract-rules has not been run against this system',
          },
        ];

    return [
      { title: 'Requirements', items: requirements },
      {
        title: 'Analysis',
        items: [
          doc('PREFLIGHT.md')
            ? { label: 'Preflight', path: [...base, 'preflight'] }
            : { label: 'Preflight', path: [], disabled: true },
          doc('ASSESSMENT.md')
            ? { label: 'Assessment', path: [...base, 'assess'] }
            : { label: 'Assessment', path: [], disabled: true },
          { label: 'Map', path: [...base, 'map'] },
          { label: 'Graph', path: [...base, 'graph'] },
        ],
      },
      {
        title: 'Documents',
        items: [
          doc('DATA_OBJECTS.md')
            ? { label: 'Data objects', path: [...base, 'data'] }
            : { label: 'Data objects', path: [], disabled: true },
          doc('BUSINESS_RULES.md')
            ? { label: 'Business rules', path: [...base, 'rules-doc'] }
            : { label: 'Business rules', path: [], disabled: true },
          { label: 'Recommendation', path: [...base, 'recommendation'] },
        ],
      },
    ];
  });

  selectSystem(systemId: string): void {
    this.chosen.set(systemId);
    const onSystemPage = this.routeSystemId();
    if (!onSystemPage) return;
    // Swap the system segment in place so the equivalent page opens for the
    // other system, falling back to overview where that page does not exist.
    const target = this.project()?.systems.find((s) => s.systemId === systemId);
    const tail = tailAfterSystem(this.router.url);
    if (target && tail === 'requirements' && !target.hasRequirements) {
      void this.router.navigate(['/p', this.projectId(), 'overview']);
      return;
    }
    void this.router.navigate(['/p', this.projectId(), systemId, tail || 'requirements']);
  }
}

/**
 * Read the system from the URL rather than by walking the activated-route tree.
 * The child route is not yet activated while this component is being
 * constructed, so its snapshot is undefined at that moment.
 */
function systemFromUrl(url: string): string {
  const parts = segments(url);
  return parts.length >= 3 ? parts[2] : '';
}

function tailAfterSystem(url: string): string {
  // /p/<project>/<system>/<page>[/...]
  const parts = segments(url);
  return parts.length >= 4 ? parts[3] : '';
}

function segments(url: string): string[] {
  return url.split(/[?#]/)[0].split('/').filter(Boolean).map(decodeURIComponent);
}
