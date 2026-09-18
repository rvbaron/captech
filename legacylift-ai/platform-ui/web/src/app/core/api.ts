import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map, of, shareReplay } from 'rxjs';
import {
  CandidatePair,
  DomainsPayload,
  Project,
  RequirementDetail,
  RequirementPage,
  Snippet,
  Stats,
  SystemSummary,
} from './models';

export interface RequirementFilters {
  search?: string;
  priority?: string[];
  category?: string[];
  ruleClass?: string[];
  pattern?: string[];
  subject?: string[];
  severity?: string;
  smeQuestion?: boolean;
  suspectedDefect?: boolean;
  candidate?: boolean;
  edited?: boolean;
  sort?: string;
  page?: number;
  pageSize?: number;
}

@Injectable({ providedIn: 'root' })
export class Api {
  private readonly http = inject(HttpClient);
  private projects$?: Observable<Project[]>;
  private readonly snippets = new Map<string, Observable<Snippet>>();

  /** The catalog is static for a session, so it is fetched once and shared. */
  projects(): Observable<Project[]> {
    this.projects$ ??= this.http
      .get<{ projects: Project[] }>('/api/projects')
      .pipe(map((r) => r.projects ?? []), shareReplay(1));
    return this.projects$;
  }

  project(projectId: string): Observable<Project | undefined> {
    return this.projects().pipe(map((ps) => ps.find((p) => p.projectId === projectId)));
  }

  system(projectId: string, systemId: string): Observable<SystemSummary | undefined> {
    return this.project(projectId).pipe(
      map((p) => p?.systems.find((s) => s.systemId === systemId)),
    );
  }

  stats(systemId: string): Observable<Stats> {
    return this.http.get<Stats>(`/api/systems/${systemId}/stats`);
  }

  requirements(systemId: string, f: RequirementFilters): Observable<RequirementPage> {
    let params = new HttpParams();
    const many = (key: string, values?: string[]) => {
      if (values?.length) params = params.set(key, values.join(','));
    };
    if (f.search) params = params.set('search', f.search);
    many('priority', f.priority);
    many('category', f.category);
    many('ruleClass', f.ruleClass);
    many('pattern', f.pattern);
    many('subject', f.subject);
    if (f.severity) params = params.set('severity', f.severity);
    if (f.smeQuestion) params = params.set('smeQuestion', 'true');
    if (f.suspectedDefect) params = params.set('suspectedDefect', 'true');
    if (f.candidate) params = params.set('candidate', 'true');
    if (f.edited) params = params.set('edited', 'true');
    params = params
      .set('sort', f.sort ?? 'priority')
      .set('page', String(f.page ?? 1))
      .set('pageSize', String(f.pageSize ?? 25));
    return this.http.get<RequirementPage>(`/api/systems/${systemId}/requirements`, { params });
  }

  requirement(systemId: string, grId: string): Observable<RequirementDetail> {
    return this.http.get<RequirementDetail>(
      `/api/systems/${systemId}/requirements/${encodeURIComponent(grId)}`,
    );
  }

  candidates(systemId: string, reason?: string): Observable<CandidatePair[]> {
    const params = reason ? new HttpParams().set('reason', reason) : undefined;
    return this.http.get<CandidatePair[]>(`/api/systems/${systemId}/candidates`, { params });
  }

  /** Cited source slices are immutable for a session; cache per citation. */
  snippet(systemId: string, citationId: number): Observable<Snippet> {
    const key = `${systemId}#${citationId}`;
    let cached = this.snippets.get(key);
    if (!cached) {
      cached = this.http
        .get<Snippet>(`/api/systems/${systemId}/citations/${citationId}/snippet`)
        .pipe(shareReplay(1));
      this.snippets.set(key, cached);
    }
    return cached;
  }

  doc(systemId: string, name: string): Observable<string> {
    return this.http.get(`/api/systems/${systemId}/docs/${encodeURIComponent(name)}`, {
      responseType: 'text',
    });
  }

  diagram(systemId: string, name: string): Observable<string> {
    return this.http.get(`/api/systems/${systemId}/diagrams/${encodeURIComponent(name)}`, {
      responseType: 'text',
    });
  }

  domains(systemId: string): Observable<DomainsPayload> {
    return this.http.get<DomainsPayload>(`/api/systems/${systemId}/domains`);
  }

  topologyUrl(systemId: string): string {
    return `/api/systems/${systemId}/topology`;
  }

  /** Nothing yet produces a modernization brief for these systems. */
  recommendation(): Observable<null> {
    return of(null);
  }
}
