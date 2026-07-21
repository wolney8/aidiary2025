import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { environment } from "../../../environments/environment";
import { AuthService } from "./auth.service";
import { ChatService } from "./chat.service";

describe("ChatService", () => {
  let service: ChatService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: AuthService,
          useValue: { getToken: () => "test-token" },
        },
      ],
    });
    service = TestBed.inject(ChatService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpTesting.verify());

  it("maps history API messages to chat models", () => {
    let result: unknown;
    service.getHistory("conversation-1").subscribe((messages) => (result = messages));

    const request = httpTesting.expectOne(
      `${environment.apiBaseUrl}/chat/history?conversation_id=conversation-1`,
    );
    request.flush({
      conversation_id: "conversation-1",
      messages: [
        {
          role: "assistant",
          message: "Welcome back",
          created_at: "2026-07-21T10:00:00Z",
          token_count: 3,
        },
      ],
    });

    expect(result).toEqual([
      {
        conversation_id: "conversation-1",
        role: "assistant",
        content: "Welcome back",
        created_at: "2026-07-21T10:00:00Z",
        token_count: 3,
      },
    ]);
  });

  it("clears a conversation through the API", () => {
    service.clearConversation("conversation-1").subscribe();

    const request = httpTesting.expectOne(
      `${environment.apiBaseUrl}/chat/conversation?conversation_id=conversation-1`,
    );
    expect(request.request.method).toBe("DELETE");
    request.flush(null);
  });

  it("creates and reuses a local conversation UUID", () => {
    const conversationId = service.getOrCreateConversationId();

    expect(conversationId).toMatch(/^[0-9a-f-]{36}$/);
    expect(service.getOrCreateConversationId()).toBe(conversationId);
  });

  it("emits chunks from an authenticated SSE response", (done) => {
    const encoder = new TextEncoder();
    const responseBody = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode('data: {"chunk":"Hello ","done":false}\n\n'),
        );
        controller.enqueue(
          encoder.encode(
            'data: {"chunk":"there","done":false}\n\ndata: {"chunk":"","done":true,"token_count":3}\n\n',
          ),
        );
        controller.close();
      },
    });
    const fetchSpy = spyOn(window, "fetch").and.resolveTo(
      new Response(responseBody, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );
    const chunks: string[] = [];

    service.sendMessage("conversation-1", "Hi").subscribe({
      next: (chunk) => chunks.push(chunk),
      complete: () => {
        expect(chunks).toEqual(["Hello ", "there"]);
        const init = fetchSpy.calls.mostRecent().args[1] as RequestInit;
        expect(init.method).toBe("POST");
        expect((init.headers as Record<string, string>)["Authorization"]).toBe(
          "Bearer test-token",
        );
        const body = JSON.parse(String(init.body)) as { request_id: string };
        expect(body.request_id).toMatch(/^[0-9a-f-]{36}$/);
        done();
      },
      error: done.fail,
    });
  });

  it("retries one pre-stream network failure with the same request id", (done) => {
    const encoder = new TextEncoder();
    const responseBody = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'data: {"chunk":"Recovered","done":false}\n\ndata: {"chunk":"","done":true}\n\n',
          ),
        );
        controller.close();
      },
    });
    const fetchSpy = spyOn(window, "fetch").and.returnValues(
      Promise.reject(new TypeError("Network unavailable")),
      Promise.resolve(
        new Response(responseBody, {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        }),
      ),
    );

    service.sendMessage("conversation-1", "Hi").subscribe({
      next: (chunk) => expect(chunk).toBe("Recovered"),
      complete: () => {
        expect(fetchSpy).toHaveBeenCalledTimes(2);
        const firstBody = JSON.parse(
          String((fetchSpy.calls.argsFor(0)[1] as RequestInit).body),
        ) as { request_id: string };
        const secondBody = JSON.parse(
          String((fetchSpy.calls.argsFor(1)[1] as RequestInit).body),
        ) as { request_id: string };
        expect(secondBody.request_id).toBe(firstBody.request_id);
        done();
      },
      error: done.fail,
    });
  });

  it("does not retry after an assistant chunk has been emitted", (done) => {
    const encoder = new TextEncoder();
    const responseBody = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'data: {"chunk":"Partial reply","done":false}\n\n' +
              'data: {"chunk":"","done":true,"error":"Stream failed","error_code":"provider_unavailable"}\n\n',
          ),
        );
        controller.close();
      },
    });
    const fetchSpy = spyOn(window, "fetch").and.resolveTo(
      new Response(responseBody, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );
    const chunks: string[] = [];

    service.sendMessage("conversation-1", "Hi").subscribe({
      next: (chunk) => chunks.push(chunk),
      complete: () => done.fail("Expected the partial stream to fail"),
      error: (error: Error) => {
        expect(chunks).toEqual(["Partial reply"]);
        expect(error.message).toBe("Stream failed");
        expect(fetchSpy).toHaveBeenCalledTimes(1);
        done();
      },
    });
  });
});
