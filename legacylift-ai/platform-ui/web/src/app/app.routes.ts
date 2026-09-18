import { Routes } from '@angular/router';

/**
 * Route shape follows the site hierarchy in
 * `docs/exec-plans/pending/reqs-review-ui-additional-info.md`: a project owns
 * systems, and every artifact page is scoped to one system.
 */
export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./pages/dashboard').then((m) => m.Dashboard),
    title: 'Projects — LegacyLift',
  },
  {
    path: 'knowledge/patterns',
    loadComponent: () => import('./pages/knowledge-patterns').then((m) => m.KnowledgePatterns),
    title: 'Requirement formats — LegacyLift',
  },
  {
    path: 'p/:projectId',
    loadComponent: () => import('./pages/project-shell').then((m) => m.ProjectShell),
    children: [
      { path: '', redirectTo: 'overview', pathMatch: 'full' },
      {
        path: 'overview',
        loadComponent: () => import('./pages/project-overview').then((m) => m.ProjectOverview),
      },
      {
        path: ':systemId/requirements',
        loadComponent: () =>
          import('./pages/requirements-list').then((m) => m.RequirementsList),
      },
      {
        path: ':systemId/requirements/:grId',
        loadComponent: () =>
          import('./pages/requirement-detail').then((m) => m.RequirementDetailPage),
      },
      {
        path: ':systemId/candidates',
        loadComponent: () => import('./pages/candidates').then((m) => m.Candidates),
      },
      {
        path: ':systemId/graph',
        loadComponent: () => import('./pages/graph').then((m) => m.Graph),
      },
      {
        path: ':systemId/map',
        loadComponent: () => import('./pages/map').then((m) => m.MapPage),
      },
      {
        path: ':systemId/assess',
        loadComponent: () => import('./pages/doc-page').then((m) => m.DocPage),
        data: { doc: 'ASSESSMENT.md', heading: 'Assessment' },
      },
      {
        path: ':systemId/preflight',
        loadComponent: () => import('./pages/doc-page').then((m) => m.DocPage),
        data: { doc: 'PREFLIGHT.md', heading: 'Preflight' },
      },
      {
        path: ':systemId/data',
        loadComponent: () => import('./pages/doc-page').then((m) => m.DocPage),
        data: { doc: 'DATA_OBJECTS.md', heading: 'Data objects' },
      },
      {
        path: ':systemId/rules-doc',
        loadComponent: () => import('./pages/doc-page').then((m) => m.DocPage),
        data: { doc: 'BUSINESS_RULES.md', heading: 'Business rules (document)' },
      },
      {
        path: ':systemId/recommendation',
        loadComponent: () => import('./pages/recommendation').then((m) => m.Recommendation),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
