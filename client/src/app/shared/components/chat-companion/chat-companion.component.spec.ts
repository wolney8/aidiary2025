import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NavigationEnd, Router } from "@angular/router";
import { provideNoopAnimations } from "@angular/platform-browser/animations";
import { Subject, of } from "rxjs";
import { AppDialogService } from "../../../core/services/app-dialog.service";
import { AuthService } from "../../../core/services/auth.service";
import { ChatService } from "../../../core/services/chat.service";
import { ChatCompanionComponent } from "./chat-companion.component";

describe("ChatCompanionComponent", () => {
  let fixture: ComponentFixture<ChatCompanionComponent>;
  let component: ChatCompanionComponent;
  let stream: Subject<string>;
  let chatService: {
    getOrCreateConversationId: jasmine.Spy;
    resetConversationId: jasmine.Spy;
    getHistory: jasmine.Spy;
    getContextStatus: jasmine.Spy;
    getStats: jasmine.Spy;
    sendMessage: jasmine.Spy;
    clearConversation: jasmine.Spy;
  };
  let dialogService: { confirm: jasmine.Spy };
  let routerEvents: Subject<NavigationEnd>;
  let router: { navigate: jasmine.Spy; url: string; events: Subject<NavigationEnd> };

  beforeEach(async () => {
    sessionStorage.clear();
    stream = new Subject<string>();
    routerEvents = new Subject<NavigationEnd>();
    chatService = {
      getOrCreateConversationId: jasmine
        .createSpy("getOrCreateConversationId")
        .and.returnValue("conversation-1"),
      resetConversationId: jasmine
        .createSpy("resetConversationId")
        .and.returnValue("conversation-2"),
      getHistory: jasmine.createSpy("getHistory").and.returnValue(of([])),
      getContextStatus: jasmine.createSpy("getContextStatus").and.returnValue(
        of({
          history_enabled: true,
          sources: [
            { key: "daily", label: "Diary entries", count: 2, enabled: true },
          ],
        }),
      ),
      getStats: jasmine.createSpy("getStats").and.returnValue(
        of({
          conversation_id: "conversation-1",
          message_count: 0,
          user_message_count: 0,
          assistant_message_count: 0,
          token_count: 0,
          started_at: null,
          last_message_at: null,
          active_seconds: 0,
          conversation_count: 0,
          limits: {
            max_message_length: 2000,
            max_messages_per_conversation: 100,
            model_history_limit: 20,
            history_response_limit: 50,
            daily_token_budget: 8000,
            monthly_chat: {
              used: 0,
              limit: 10,
              remaining: 10,
              unlimited: false,
            },
          },
        }),
      ),
      sendMessage: jasmine.createSpy("sendMessage").and.returnValue(stream),
      clearConversation: jasmine
        .createSpy("clearConversation")
        .and.returnValue(of(void 0)),
    };
    dialogService = {
      confirm: jasmine.createSpy("confirm").and.resolveTo(true),
    };
    router = {
      navigate: jasmine.createSpy("navigate").and.resolveTo(true),
      url: "/entries",
      events: routerEvents,
    };

    await TestBed.configureTestingModule({
      imports: [ChatCompanionComponent],
      providers: [
        provideNoopAnimations(),
        { provide: ChatService, useValue: chatService },
        { provide: AppDialogService, useValue: dialogService },
        { provide: Router, useValue: router },
        {
          provide: AuthService,
          useValue: {
            getCurrentUser: () => ({
              id: 1,
              username: "tester",
              chatgpt_daily_diary_coachname: "Sage",
            }),
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatCompanionComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("opens an accessible panel and loads history", () => {
    component.open();
    fixture.detectChanges();

    const panel = fixture.nativeElement.querySelector(
      '[data-testid="chat-panel"]',
    );
    expect(panel).not.toBeNull();
    expect(panel.getAttribute("aria-label")).toBe("Chat with Sage");
    expect(chatService.getHistory).toHaveBeenCalledWith("conversation-1");
    expect(chatService.getContextStatus).toHaveBeenCalled();
    expect(chatService.getStats).toHaveBeenCalledWith("conversation-1");
    expect(component.contextSummary()).toBe("May reference 1 source");
  });

  it("offers a stale conversation choice and can start a new chat", () => {
    chatService.getHistory.and.returnValue(
      of([
        {
          conversation_id: "conversation-1",
          role: "user",
          content: "Old message",
          created_at: "2026-01-01T10:00:00.000Z",
        },
      ]),
    );

    component.open();
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    expect(host.querySelector('[data-testid="chat-session-choice"]')).not.toBeNull();

    component.startNewChat();
    fixture.detectChanges();

    expect(chatService.resetConversationId).toHaveBeenCalled();
    expect(component.messages()).toEqual([]);
    expect(component.showSessionChoice()).toBeFalse();
  });

  it("expands context source details without exposing diary values", () => {
    component.open();
    component.toggleContextDrawer();
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    const drawer = host.querySelector('[data-testid="chat-context-drawer"]');
    expect(drawer).not.toBeNull();
    expect(drawer?.textContent).toContain("Diary entries");
    expect(drawer?.textContent).toContain("Available");
    expect(drawer?.textContent).not.toContain("Diary entries (2)");
  });

  it("keeps a visible close control and closes back to the launcher", () => {
    component.open();
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    const closeButton = host.querySelector<HTMLButtonElement>(
      '[data-testid="chat-close-button"]',
    );
    expect(closeButton).not.toBeNull();

    closeButton?.click();
    fixture.detectChanges();

    expect(component.isOpen()).toBeFalse();
    expect(host.querySelector('[data-testid="chat-open-button"]')).not.toBeNull();
  });

  it("exposes stable hooks for the trigger and primary chat controls", () => {
    const host = fixture.nativeElement as HTMLElement;
    expect(host.querySelector('[data-testid="chat-open-button"]')).not.toBeNull();

    component.open();
    fixture.detectChanges();

    expect(host.querySelector('[data-testid="chat-close-button"]')).not.toBeNull();
    component.messages.set([
      { conversation_id: "conversation-1", role: "user", content: "Hello" },
    ]);
    fixture.detectChanges();
    expect(host.querySelector('[data-testid="chat-session-button"]')).not.toBeNull();
    expect(host.querySelector('[data-testid="chat-message-thread"]')).not.toBeNull();
    expect(host.querySelector('[data-testid="chat-message-input"]')).not.toBeNull();
    expect(host.querySelector('[data-testid="chat-send-button"]')).not.toBeNull();
  });

  it("shows typing until the first streamed chunk arrives", () => {
    component.open();
    component.draft = "How have I been feeling?";
    component.send();

    expect(component.isStreaming()).toBeTrue();
    expect(component.showTypingIndicator()).toBeTrue();
    expect(chatService.sendMessage).toHaveBeenCalledWith(
      "conversation-1",
      "How have I been feeling?",
    );

    stream.next("You seem more settled.");

    expect(component.showTypingIndicator()).toBeFalse();
    expect(component.messages().at(-1)?.content).toBe("You seem more settled.");

    stream.complete();
    expect(component.isStreaming()).toBeFalse();
  });

  it("uses the app confirmation flow before clearing conversation", async () => {
    component.messages.set([
      {
        conversation_id: "conversation-1",
        role: "user",
        content: "Hello",
      },
    ]);

    await component.clearConversation();

    expect(dialogService.confirm).toHaveBeenCalled();
    expect(chatService.clearConversation).toHaveBeenCalledWith("conversation-1");
    expect(component.messages()).toEqual([]);
    expect(chatService.resetConversationId).toHaveBeenCalled();
  });

  it("creates a daily entry draft from the current chat", () => {
    component.isOpen.set(true);
    component.messages.set([
      {
        conversation_id: "conversation-1",
        role: "user",
        content: "I felt more settled today.",
        created_at: "2026-06-01T10:00:00.000Z",
      },
      {
        conversation_id: "conversation-1",
        role: "assistant",
        content: "That sounds like a useful reflection to keep.",
        created_at: "2026-06-01T10:01:00.000Z",
      },
    ]);

    component.createEntryDraft();

    const stored = sessionStorage.getItem("openmynd_chat_entry_draft");
    expect(stored).toContain("Chat reflection");
    expect(stored).toContain("useful reflection");
    expect(router.navigate).toHaveBeenCalledWith(["/entries/create"], {
      queryParams: { type: "daily", source: "chat" },
    });
    expect(component.isOpen()).toBeFalse();
  });

  it("shows diary route starter chips and sends the selected prompt", () => {
    component.open();
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    expect(host.querySelector('[data-testid="chat-starter-chips"]')).not.toBeNull();
    expect(host.textContent).toContain("What patterns stand out?");

    host.querySelector<HTMLButtonElement>(".chat-starter-chip")?.click();

    expect(chatService.sendMessage).toHaveBeenCalledWith(
      "conversation-1",
      "What patterns stand out across my recent diary and dream entries?",
    );
  });

  it("updates starter chips for thought-record routes", () => {
    component.open();
    router.url = "/cbt";
    routerEvents.next(new NavigationEnd(1, "/cbt", "/cbt"));
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    expect(host.textContent).toContain("What's a Thought Record?");
    expect(host.textContent).toContain("How do I fill this out?");
  });

  it("updates starter chips for important-day routes", () => {
    component.open();
    router.url = "/important-days";
    routerEvents.next(
      new NavigationEnd(1, "/important-days", "/important-days"),
    );
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    expect(host.textContent).toContain("Create my first important day");
    expect(host.textContent).toContain("What should I track?");
  });
});
