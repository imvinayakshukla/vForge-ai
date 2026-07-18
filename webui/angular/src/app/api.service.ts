import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

export interface Health {
  status: string;
  app: string;
  version: string;
  uptime_seconds: number;
  agents: string[];
}

export interface AgentInfo {
  name: string;
  description: string;
  tools: string[];
  max_iterations: number;
}

export interface ToolInfo {
  agent: string;
  name: string;
  description: string;
  input_schema: unknown;
}

export interface PromptInfo {
  agent: string;
  system_prompt: string;
}

export interface SkillInfo {
  name: string;
  agents: string[];
  content: string;
}

export interface SessionInfo {
  agent: string;
  session_id: string;
  messages: number;
}

export interface ChatResponse {
  agent: string;
  session_id: string;
  answer: string;
}

/** Thin client over the VForge console API — the same endpoints the
 *  built-in console uses, so this UI is a drop-in replacement. */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);

  health(): Observable<Health> {
    return this.http.get<Health>('/health');
  }

  agents(): Observable<AgentInfo[]> {
    return this.http.get<AgentInfo[]>('/api/agents');
  }

  chat(agent: string, message: string, sessionId: string): Observable<ChatResponse> {
    return this.http.post<ChatResponse>('/api/chat', {
      agent,
      message,
      session_id: sessionId,
    });
  }

  tools(): Observable<ToolInfo[]> {
    return this.http.get<ToolInfo[]>('/api/tools');
  }

  prompts(): Observable<PromptInfo[]> {
    return this.http.get<PromptInfo[]>('/api/prompts');
  }

  skills(): Observable<SkillInfo[]> {
    return this.http.get<SkillInfo[]>('/api/skills');
  }

  sessions(): Observable<SessionInfo[]> {
    return this.http.get<SessionInfo[]>('/api/sessions');
  }

  logs(): Observable<string[]> {
    return this.http.get<string[]>('/api/logs');
  }

  metrics(): Observable<unknown> {
    return this.http.get<unknown>('/api/metrics');
  }

  config(): Observable<unknown> {
    return this.http.get<unknown>('/api/config');
  }
}
