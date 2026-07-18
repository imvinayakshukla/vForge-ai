import { CommonModule } from '@angular/common';
import { Component, Input, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from './api.service';

interface ChatMessage {
  kind: 'user' | 'agent' | 'err';
  text: string;
}

@Component({
  selector: 'vf-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="chat-log">
      @for (msg of messages(); track $index) {
        <div class="msg" [class.user]="msg.kind === 'user'"
             [class.agent]="msg.kind === 'agent'" [class.err]="msg.kind === 'err'">
          {{ msg.text }}
        </div>
      }
    </div>
    <form class="chat-form" (ngSubmit)="send()">
      <select [(ngModel)]="agent" name="agent">
        @for (name of agents; track name) {
          <option [value]="name">{{ name }}</option>
        }
      </select>
      <input type="text" name="message" [(ngModel)]="draft"
             placeholder="Ask your agent..." autocomplete="off" />
      <button class="primary" type="submit" [disabled]="busy()">Send</button>
    </form>
    <p class="muted session">Session: <code>{{ sessionId }}</code></p>
  `,
  styles: [
    `
      .chat-log { display: flex; flex-direction: column; gap: 8px;
                  min-height: 280px; max-height: 55vh; overflow-y: auto; margin-bottom: 12px; }
      .msg { padding: 10px 12px; border-radius: 10px; max-width: 80%; white-space: pre-wrap; }
      .msg.user { align-self: flex-end; background: #243b62; }
      .msg.agent { align-self: flex-start; background: var(--panel); border: 1px solid var(--border); }
      .msg.err { align-self: flex-start; background: #4a1f24; }
      .chat-form { display: flex; gap: 8px; }
      input[type='text'] { flex: 1; }
      .session { margin-top: 8px; }
    `,
  ],
})
export class ChatComponent {
  private api = inject(ApiService);

  @Input() agents: string[] = [];
  @Input({ required: false }) set defaultAgent(value: string | undefined) {
    if (value && !this.agent) this.agent = value;
  }

  agent = '';
  draft = '';
  readonly sessionId = 'ng-' + Math.random().toString(36).slice(2, 10);
  readonly messages = signal<ChatMessage[]>([]);
  readonly busy = signal(false);

  send(): void {
    const text = this.draft.trim();
    if (!text || this.busy()) return;
    this.messages.update((all) => [...all, { kind: 'user', text }]);
    this.draft = '';
    this.busy.set(true);
    this.api.chat(this.agent || this.agents[0], text, this.sessionId).subscribe({
      next: (res) => {
        this.messages.update((all) => [...all, { kind: 'agent', text: res.answer }]);
        this.busy.set(false);
      },
      error: (err) => {
        const detail = err?.error?.detail ?? err?.message ?? 'request failed';
        this.messages.update((all) => [...all, { kind: 'err', text: String(detail) }]);
        this.busy.set(false);
      },
    });
  }
}
