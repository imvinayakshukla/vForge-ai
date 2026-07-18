import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';

import { ApiService } from './api.service';
import { ChatComponent } from './chat.component';
import { PanelComponent, PanelName } from './panel.component';

const TABS = [
  'Chat',
  'Agents',
  'Tools',
  'Prompts',
  'Skills',
  'Sessions',
  'Logs',
  'Metrics',
  'Health',
  'Config',
] as const;

type Tab = (typeof TABS)[number];

@Component({
  selector: 'vf-root',
  standalone: true,
  imports: [CommonModule, ChatComponent, PanelComponent],
  template: `
    <header>
      <h1>⚒️ VForge</h1>
      <span class="app muted">{{ appName() }}</span>
      <span class="muted status">{{ status() }}</span>
    </header>
    <nav>
      @for (tab of tabs; track tab) {
        <button [class.active]="tab === selected()" (click)="selected.set(tab)">
          {{ tab }}
        </button>
      }
    </nav>
    <main>
      @if (selected() === 'Chat') {
        <vf-chat [agents]="agentNames()" [defaultAgent]="agentNames()[0]" />
      } @else {
        <vf-panel [tab]="panelTab()" />
      }
    </main>
  `,
  styles: [
    `
      header { display: flex; align-items: center; gap: 12px;
               padding: 12px 20px; border-bottom: 1px solid var(--border); }
      header h1 { font-size: 16px; }
      .status { margin-left: auto; }
      nav { display: flex; gap: 4px; padding: 8px 16px;
            border-bottom: 1px solid var(--border); flex-wrap: wrap; }
      nav button { background: none; border: 1px solid transparent; color: var(--muted);
                   padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px; }
      nav button.active { color: var(--text); border-color: var(--border); background: var(--panel); }
      main { padding: 16px 20px; max-width: 1100px; margin: 0 auto; }
    `,
  ],
})
export class AppComponent implements OnInit {
  private api = inject(ApiService);

  readonly tabs = TABS;
  readonly selected = signal<Tab>('Chat');
  readonly appName = signal('');
  readonly status = signal('');
  readonly agentNames = signal<string[]>([]);

  ngOnInit(): void {
    this.api.health().subscribe({
      next: (health) => {
        this.appName.set(health.app);
        this.status.set('● ' + health.status);
        this.agentNames.set(health.agents);
      },
      error: () => this.status.set('○ unreachable'),
    });
  }

  panelTab(): PanelName {
    return this.selected() as PanelName;
  }
}
