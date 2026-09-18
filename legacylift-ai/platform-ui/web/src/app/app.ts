import { Component } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink],
  template: `
    <header class="bar">
      <a routerLink="/" class="brand">
        <img src="/brand/logo.svg" alt="LegacyLift" class="logo" />
        <span class="divider"></span>
        <span class="product">Requirements Review</span>
      </a>
      <nav class="links">
        <a routerLink="/">Projects</a>
        <a routerLink="/knowledge/patterns">Requirement formats</a>
      </nav>
      <span class="mode" title="Milestone 1 of the review UI is read-only by design.">
        read-only preview
      </span>
    </header>
    <router-outlet />
  `,
  styles: `
    .bar {
      display: flex;
      align-items: center;
      gap: 18px;
      padding: 0 24px;
      height: 58px;
      background: var(--ll-navy);
      color: #fff;
      box-shadow: 0 1px 0 rgba(0, 0, 0, 0.1);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
      color: #fff;
      text-decoration: none;
    }
    .brand:hover { text-decoration: none; }
    .logo { height: 20px; filter: brightness(0) invert(1); }
    .divider { width: 1px; height: 22px; background: rgba(255, 255, 255, 0.3); }
    .product { font-weight: 500; letter-spacing: 0.02em; font-size: 14px; color: rgba(255, 255, 255, 0.92); }
    .links { display: flex; gap: 18px; margin-left: 12px; }
    .links a {
      color: rgba(255, 255, 255, 0.85);
      font-size: 13px;
      text-decoration: none;
      padding: 4px 0;
      border-bottom: 2px solid transparent;
    }
    .links a:hover { color: #fff; border-bottom-color: var(--ll-green); text-decoration: none; }
    .mode {
      margin-left: auto;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: #cfe6cd;
      border: 1px solid rgba(207, 230, 205, 0.4);
      border-radius: 999px;
      padding: 2px 10px;
    }
  `,
})
export class App {}
