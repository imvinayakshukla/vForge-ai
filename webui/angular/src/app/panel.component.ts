import { CommonModule } from '@angular/common';
import { Component, Input, OnChanges, inject, signal } from '@angular/core';

import {
  AgentInfo,
  ApiService,
  PromptInfo,
  SessionInfo,
  SkillInfo,
  ToolInfo,
} from './api.service';

export type PanelName =
  | 'Agents'
  | 'Tools'
  | 'Prompts'
  | 'Skills'
  | 'Sessions'
  | 'Logs'
  | 'Metrics'
  | 'Health'
  | 'Config';

/** Read-only data panels; each renders one console API endpoint. */
@Component({
  selector: 'vf-panel',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (error()) {
      <pre>{{ error() }}</pre>
    } @else {
      @switch (tab) {
        @case ('Agents') {
          @for (agent of agents(); track agent.name) {
            <div class="card">
              <h3>{{ agent.name }}</h3>
              <p class="muted">{{ agent.description || '(no description)' }}</p>
              <p class="muted">
                tools: {{ agent.tools.length ? agent.tools.join(', ') : '(none)' }}
                · max_iterations: {{ agent.max_iterations }}
              </p>
            </div>
          }
        }
        @case ('Tools') {
          @if (!tools().length) { <p class="muted">No tools bound.</p> }
          @for (tool of tools(); track tool.agent + tool.name) {
            <div class="card">
              <h3>{{ tool.name }} <span class="muted">({{ tool.agent }})</span></h3>
              <p class="muted">{{ tool.description }}</p>
              <pre>{{ tool.input_schema | json }}</pre>
            </div>
          }
        }
        @case ('Prompts') {
          @for (prompt of prompts(); track prompt.agent) {
            <div class="card">
              <h3>{{ prompt.agent }}</h3>
              <pre>{{ prompt.system_prompt }}</pre>
            </div>
          }
        }
        @case ('Skills') {
          @if (!skills().length) { <p class="muted">No skills configured.</p> }
          @for (skill of skills(); track skill.name) {
            <div class="card">
              <h3>{{ skill.name }}</h3>
              <p class="muted">used by: {{ skill.agents.join(', ') }}</p>
              <pre>{{ skill.content }}</pre>
            </div>
          }
        }
        @case ('Sessions') {
          @if (!sessions().length) { <p class="muted">No sessions yet.</p> } @else {
            <table>
              <tr><th>Agent</th><th>Session</th><th>Messages</th></tr>
              @for (session of sessions(); track session.agent + session.session_id) {
                <tr>
                  <td>{{ session.agent }}</td>
                  <td><code>{{ session.session_id }}</code></td>
                  <td>{{ session.messages }}</td>
                </tr>
              }
            </table>
          }
        }
        @case ('Logs') { <pre>{{ logs().join('\n') || '(empty)' }}</pre> }
        @default { <pre>{{ raw() | json }}</pre> }
      }
    }
  `,
})
export class PanelComponent implements OnChanges {
  private api = inject(ApiService);

  @Input({ required: true }) tab!: PanelName;

  readonly agents = signal<AgentInfo[]>([]);
  readonly tools = signal<ToolInfo[]>([]);
  readonly prompts = signal<PromptInfo[]>([]);
  readonly skills = signal<SkillInfo[]>([]);
  readonly sessions = signal<SessionInfo[]>([]);
  readonly logs = signal<string[]>([]);
  readonly raw = signal<unknown>(null);
  readonly error = signal<string | null>(null);

  ngOnChanges(): void {
    this.error.set(null);
    const fail = (err: unknown) => this.error.set(String((err as Error)?.message ?? err));
    switch (this.tab) {
      case 'Agents':
        this.api.agents().subscribe({ next: (v) => this.agents.set(v), error: fail });
        break;
      case 'Tools':
        this.api.tools().subscribe({ next: (v) => this.tools.set(v), error: fail });
        break;
      case 'Prompts':
        this.api.prompts().subscribe({ next: (v) => this.prompts.set(v), error: fail });
        break;
      case 'Skills':
        this.api.skills().subscribe({ next: (v) => this.skills.set(v), error: fail });
        break;
      case 'Sessions':
        this.api.sessions().subscribe({ next: (v) => this.sessions.set(v), error: fail });
        break;
      case 'Logs':
        this.api.logs().subscribe({ next: (v) => this.logs.set(v), error: fail });
        break;
      case 'Metrics':
        this.api.metrics().subscribe({ next: (v) => this.raw.set(v), error: fail });
        break;
      case 'Health':
        this.api.health().subscribe({ next: (v) => this.raw.set(v), error: fail });
        break;
      case 'Config':
        this.api.config().subscribe({ next: (v) => this.raw.set(v), error: fail });
        break;
    }
  }
}
