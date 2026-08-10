import { ComponentFixture, TestBed } from "@angular/core/testing";
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
    sendMessage: jasmine.Spy;
    clearConversation: jasmine.Spy;
  };
  let dialogService: { confirm: jasmine.Spy };

  beforeEach(async () => {
    stream = new Subject<string>();
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
      sendMessage: jasmine.createSpy("sendMessage").and.returnValue(stream),
      clearConversation: jasmine
        .createSpy("clearConversation")
        .and.returnValue(of(void 0)),
    };
    dialogService = {
      confirm: jasmine.createSpy("confirm").and.resolveTo(true),
    };

    await TestBed.configureTestingModule({
      imports: [ChatCompanionComponent],
      providers: [
        provideNoopAnimations(),
        { provide: ChatService, useValue: chatService },
        { provide: AppDialogService, useValue: dialogService },
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
    expect(component.contextSummary()).toBe("May use: Diary entries (2)");
  });

  it("exposes stable hooks for the trigger and primary chat controls", () => {
    const host = fixture.nativeElement as HTMLElement;
    expect(host.querySelector('[data-testid="chat-open-button"]')).not.toBeNull();

    component.open();
    fixture.detectChanges();

    expect(host.querySelector('[data-testid="chat-close-button"]')).not.toBeNull();
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
});
