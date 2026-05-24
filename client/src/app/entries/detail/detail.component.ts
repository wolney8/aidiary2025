// Entry detail view with two-column layout
import { Component, OnInit, inject } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, Router, RouterModule } from "@angular/router";
import { MatCardModule } from "@angular/material/card";
import { MatChipsModule } from "@angular/material/chips";
import { MatIconModule } from "@angular/material/icon";
import { MatButtonModule } from "@angular/material/button";
import { EntriesService } from "../../core/services/entries.service";

@Component({
  selector: "app-detail",
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatCardModule,
    MatChipsModule,
    MatIconModule,
    MatButtonModule,
  ],
  template: `
    <div class="detail-container" *ngIf="entry">
      <div class="date-nav">
        <button mat-stroked-button type="button" (click)="goBack()">
          Back
        </button>
        <h2>{{ getFriendlyDate() }}</h2>
        <button
          mat-raised-button
          color="primary"
          [routerLink]="['/entries', entry.id, 'edit']"
        >
          Edit Entry
        </button>
      </div>

      <section class="entry-image-band" aria-label="Entry image">
        <img
          *ngIf="getEntryImageUrl()"
          [src]="getEntryImageUrl()!"
          alt="Entry image"
          class="entry-image"
        />
        <div class="entry-image-placeholder" *ngIf="!getEntryImageUrl()">
          <mat-icon>image</mat-icon>
          <p>No image uploaded for this entry yet.</p>
        </div>
      </section>

      <div class="detail-columns">
        <mat-card>
          <mat-card-header>
            <mat-card-title>{{ getTitle() }}</mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <div *ngIf="isDream()">
              <div class="section" *ngIf="entry.plot">
                <h4>Plot:</h4>
                <p
                  class="paragraph-block"
                  *ngFor="let paragraph of toParagraphs(entry.plot)"
                >
                  {{ paragraph }}
                </p>
              </div>
              <div class="section" *ngIf="entry.cast">
                <h4>Cast:</h4>
                <p
                  class="paragraph-block"
                  *ngFor="let paragraph of toParagraphs(entry.cast)"
                >
                  {{ paragraph }}
                </p>
              </div>
              <div class="section" *ngIf="entry.location">
                <h4>Location:</h4>
                <p
                  class="paragraph-block"
                  *ngFor="let paragraph of toParagraphs(entry.location)"
                >
                  {{ paragraph }}
                </p>
              </div>
              <div class="section" *ngIf="entry.period">
                <h4>Period:</h4>
                <p
                  class="paragraph-block"
                  *ngFor="let paragraph of toParagraphs(entry.period)"
                >
                  {{ paragraph }}
                </p>
              </div>
              <div class="section" *ngIf="entry.emotion">
                <h4>Emotion:</h4>
                <p
                  class="paragraph-block"
                  *ngFor="let paragraph of toParagraphs(entry.emotion)"
                >
                  {{ paragraph }}
                </p>
              </div>
              <div class="section" *ngIf="entry.symbols_and_imagery">
                <h4>Symbols and Imagery:</h4>
                <p
                  class="paragraph-block"
                  *ngFor="
                    let paragraph of toParagraphs(entry.symbols_and_imagery)
                  "
                >
                  {{ paragraph }}
                </p>
              </div>
              <div class="section" *ngIf="entry.insight">
                <h4>Insight:</h4>
                <p
                  class="paragraph-block"
                  *ngFor="let paragraph of toParagraphs(entry.insight)"
                >
                  {{ paragraph }}
                </p>
              </div>
              <div class="section" *ngIf="entry.action">
                <h4>Action:</h4>
                <p
                  class="paragraph-block"
                  *ngFor="let paragraph of toParagraphs(entry.action)"
                >
                  {{ paragraph }}
                </p>
              </div>
              <div class="section" *ngIf="entry.other">
                <h4>Other:</h4>
                <p
                  class="paragraph-block"
                  *ngFor="let paragraph of toParagraphs(entry.other)"
                >
                  {{ paragraph }}
                </p>
              </div>
            </div>
            <div *ngIf="!isDream()">
              <p
                class="paragraph-block"
                *ngFor="let paragraph of getUserParagraphs()"
              >
                {{ paragraph }}
              </p>
            </div>
          </mat-card-content>
        </mat-card>

        <mat-card>
          <mat-card-header>
            <mat-card-title>AI Response</mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <div *ngIf="isDream()">
              <div class="section" *ngIf="entry.summary">
                <h4>Summary:</h4>
                <p
                  class="paragraph-block"
                  *ngFor="let paragraph of toParagraphs(entry.summary)"
                >
                  {{ paragraph }}
                </p>
              </div>
              <div class="section" *ngIf="entry.interpretation">
                <h4>Interpretation:</h4>
                <p
                  class="paragraph-block"
                  *ngFor="let paragraph of toParagraphs(entry.interpretation)"
                >
                  {{ paragraph }}
                </p>
              </div>
            </div>
            <div *ngIf="!isDream()">
              <p
                class="paragraph-block"
                *ngFor="let paragraph of getAIParagraphs()"
              >
                {{ paragraph }}
              </p>
            </div>
          </mat-card-content>
        </mat-card>
      </div>

      <div class="metadata-bar">
        <div class="metadata-section">
          <h4>My Tags:</h4>
          <mat-chip-listbox>
            <mat-chip-option
              *ngFor="let tag of getVisibleItems(getTags(), showAllTags)"
              (click)="searchForTag(tag)"
              [class.clickable-chip]="true"
            >
              {{ tag }}
            </mat-chip-option>
          </mat-chip-listbox>
          <button
            mat-button
            type="button"
            class="expand-toggle ellipsis-toggle"
            *ngIf="shouldShowToggle(getTags())"
            (click)="showAllTags = !showAllTags"
            [attr.aria-label]="
              showAllTags ? 'Show fewer tags' : 'Show more tags'
            "
          >
            {{ showAllTags ? "Show less" : "..." }}
          </button>
        </div>

        <div class="metadata-section">
          <h4>Keywords:</h4>
          <mat-chip-listbox>
            <mat-chip-option
              *ngFor="
                let tag of getVisibleItems(getTagsArray(), showAllKeywords)
              "
              (click)="searchForTag(tag)"
              [class.clickable-chip]="true"
            >
              {{ tag }}
            </mat-chip-option>
          </mat-chip-listbox>
          <button
            mat-button
            type="button"
            class="expand-toggle"
            *ngIf="shouldShowToggle(getTagsArray())"
            (click)="showAllKeywords = !showAllKeywords"
          >
            {{ showAllKeywords ? "Show less" : "Show more" }}
          </button>
        </div>

        <div class="metadata-section" *ngIf="getPeopleArray().length > 0">
          <h4>People:</h4>
          <mat-chip-listbox>
            <mat-chip-option
              *ngFor="
                let person of getVisibleItems(getPeopleArray(), showAllPeople)
              "
              (click)="searchForPerson(person)"
              [class.clickable-chip]="true"
            >
              <mat-icon>person</mat-icon>
              {{ person }}
            </mat-chip-option>
          </mat-chip-listbox>
          <button
            mat-button
            type="button"
            class="expand-toggle"
            *ngIf="shouldShowToggle(getPeopleArray())"
            (click)="showAllPeople = !showAllPeople"
          >
            {{ showAllPeople ? "Show less" : "Show more" }}
          </button>
        </div>

        <div class="metadata-section" *ngIf="getPlacesArray().length > 0">
          <h4>Places:</h4>
          <mat-chip-listbox>
            <mat-chip-option
              *ngFor="let place of getPlacesArray()"
              (click)="searchForPlace(place)"
              [class.clickable-chip]="true"
            >
              <mat-icon>place</mat-icon>
              {{ place }}
            </mat-chip-option>
          </mat-chip-listbox>
        </div>

        <div class="metadata-section" *ngIf="isDream()">
          <h4>Image Generated with prompt:</h4>
          <p
            class="paragraph-block"
            *ngFor="let paragraph of toParagraphs(entry.image_prompt)"
          >
            {{ paragraph }}
          </p>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      .detail-container {
        max-width: 1200px;
        margin: 0 auto;
      }

      .date-nav {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: var(--spacing-md);
      }

      .date-nav h2 {
        margin: 0;
        text-align: center;
        flex: 1;
      }

      .entry-image-band {
        margin-bottom: var(--spacing-md);
        border-radius: var(--radius-md);
        border: 1px solid var(--colour-border);
        background: var(--colour-surface);
        overflow: hidden;
      }

      .entry-image {
        width: 100%;
        max-height: 320px;
        object-fit: cover;
        display: block;
      }

      .entry-image-placeholder {
        min-height: 180px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-direction: column;
        gap: 0.5rem;
        color: var(--colour-text-secondary);
        background: var(--colour-surface-muted);
      }

      .entry-image-placeholder mat-icon {
        font-size: 2rem;
        width: 2rem;
        height: 2rem;
      }

      .entry-image-placeholder p {
        margin: 0;
      }

      .section {
        margin-bottom: var(--spacing-md);
      }

      .section h4 {
        margin: 0 0 var(--spacing-xs) 0;
        font-weight: 500;
      }

      .paragraph-block {
        margin: 0 0 0.75rem 0;
        line-height: 1.55;
      }

      .detail-columns {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: var(--spacing-md);
        margin-bottom: var(--spacing-md);
      }

      @media (max-width: 768px) {
        .detail-columns {
          grid-template-columns: 1fr;
        }

        .date-nav {
          flex-direction: column;
          align-items: stretch;
        }

        .date-nav h2 {
          text-align: left;
        }
      }

      .metadata-bar {
        background: var(--colour-surface-muted);
        padding: var(--spacing-md);
        border-radius: var(--radius-md);
        border: 1px solid var(--colour-border);
      }

      .metadata-section {
        margin-bottom: var(--spacing-md);
      }

      .metadata-section h4 {
        margin-bottom: var(--spacing-sm);
        color: var(--colour-text-primary);
        font-weight: 600;
      }

      .metadata-section mat-chip-listbox {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
      }

      .clickable-chip {
        cursor: pointer;
        transition: all 0.2s ease;
        background-color: #dbeafe !important;
        color: var(--colour-text-primary) !important;
      }

      .clickable-chip:hover {
        background-color: var(--colour-primary) !important;
        color: #ffffff !important;
      }

      .clickable-chip mat-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
        margin-right: 4px;
      }

      .expand-toggle {
        margin-top: 0.35rem;
      }

      .ellipsis-toggle {
        min-width: 2.25rem;
        padding: 0 0.5rem;
        border-radius: var(--radius-pill);
        font-weight: 600;
      }
    `,
  ],
})
export class DetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private entriesService = inject(EntriesService);

  private readonly collapsedItemsLimit = 8;

  entry: any;
  entryType: "daily" | "dream" = "daily";
  backQueryParams: Record<string, string | number> = {};

  showAllTags = false;
  showAllKeywords = false;
  showAllPeople = false;

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get("id"));
    this.captureBackQueryParams();

    // Try loading as daily first, then dream if not found
    this.entriesService.getDailyEntry(id).subscribe({
      next: (entry) => {
        this.entry = entry;
        this.entryType = "daily";
      },
      error: () => {
        this.entriesService.getDreamEntry(id).subscribe((entry) => {
          this.entry = entry;
          this.entryType = "dream";
        });
      },
    });
  }

  goBack(): void {
    if (Object.keys(this.backQueryParams).length > 0) {
      this.router.navigate(["/entries"], {
        queryParams: this.backQueryParams,
      });
      return;
    }

    this.router.navigate(["/entries"]);
  }

  getFriendlyDate(): string {
    if (!this.entry?.entry_date) {
      return "Entry";
    }

    const date = new Date(this.entry.entry_date);
    const day = date.getDate();
    const month = date.toLocaleString("en-GB", { month: "long" });
    const year = date.getFullYear();

    return `${day}${this.getOrdinalSuffix(day)} of ${month} ${year}`;
  }

  getTitle(): string {
    if (!this.entry) {
      return "Entry";
    }

    if (this.entry.title?.trim()) {
      return this.entry.title.trim();
    }

    return `Entry for ${this.getFriendlyDate()}`;
  }

  getEntryImageUrl(): string | null {
    if (!this.isDream()) {
      return null;
    }

    const raw = this.entry?.image_url;
    if (!raw || typeof raw !== "string") {
      return null;
    }

    const value = raw.trim();
    return value.length > 0 ? value : null;
  }

  getUserParagraphs(): string[] {
    const content = this.getUserContent();
    const paragraphs = this.toParagraphs(content);

    // Fallback for older entries that were stored as one long block.
    if (paragraphs.length <= 1 && content.trim().length > 180) {
      return this.toSentenceParagraphs(content);
    }

    return paragraphs;
  }

  getAIParagraphs(): string[] {
    return this.toParagraphs(this.getAIContent());
  }

  getUserContent(): string {
    if (!this.entry) {
      return "";
    }

    if (this.isDream()) {
      return this.entry.plot || "";
    }

    if (this.entry.title) {
      return this.entry.user_message || "";
    }

    return this.splitDailyMessage(this.entry.user_message || "")[1];
  }

  getAIContent(): string {
    return this.isDream()
      ? this.entry.interpretation || ""
      : this.entry.ai_response || "";
  }

  toParagraphs(text?: string): string[] {
    if (!text) {
      return [];
    }

    return text
      .split(/\r?\n+/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0);
  }

  private toSentenceParagraphs(text: string): string[] {
    const sentences = text
      .replace(/\s+/g, " ")
      .trim()
      .split(/(?<=[.!?])\s+/)
      .map((sentence) => sentence.trim())
      .filter((sentence) => sentence.length > 0);

    if (sentences.length <= 1) {
      return [text.trim()];
    }

    const chunks: string[] = [];
    for (let i = 0; i < sentences.length; i += 2) {
      chunks.push(sentences.slice(i, i + 2).join(" "));
    }

    return chunks;
  }

  getVisibleItems(items: string[], expanded: boolean): string[] {
    if (expanded || items.length <= this.collapsedItemsLimit) {
      return items;
    }

    return items.slice(0, this.collapsedItemsLimit);
  }

  shouldShowToggle(items: string[]): boolean {
    return items.length > this.collapsedItemsLimit;
  }

  getTags(): string[] {
    return this.entry?.tags
      ? this.entry.tags
          .split(",")
          .map((item: string) => item.trim())
          .filter((item: string) => item.length > 0)
      : [];
  }

  getTagsArray(): string[] {
    return this.getTags();
  }

  getPeopleArray(): string[] {
    const peopleStr = this.isDream()
      ? this.entry?.dream_people_names
      : this.entry?.daily_people_names;

    return peopleStr
      ? peopleStr
          .split(",")
          .map((person: string) => person.trim())
          .filter((person: string) => person.length > 0)
          .filter((person: string) => this.isLikelyPersonName(person))
      : [];
  }

  getPlacesArray(): string[] {
    const placesStr = this.isDream()
      ? this.entry?.dream_places
      : this.entry?.daily_places;

    return placesStr
      ? placesStr
          .split(",")
          .map((place: string) => place.trim())
          .filter((place: string) => place.length > 0)
      : [];
  }

  searchForTag(tag: string): void {
    this.router.navigate(["/entries"], { queryParams: { search: tag } });
  }

  searchForPerson(person: string): void {
    this.router.navigate(["/entries"], { queryParams: { search: person } });
  }

  searchForPlace(place: string): void {
    this.router.navigate(["/entries"], { queryParams: { search: place } });
  }

  isDream(): boolean {
    return this.entryType === "dream";
  }

  private isLikelyPersonName(value: string): boolean {
    const candidate = value.trim();
    if (!candidate) {
      return false;
    }

    const blocked = new Set([
      "hopefully",
      "maybe",
      "someone",
      "somebody",
      "everyone",
      "everybody",
      "nobody",
      "anyone",
      "anybody",
      "person",
      "people",
      "friend",
      "friends",
      "unknown",
      "none",
      "na",
      "n/a",
    ]);

    const lower = candidate.toLowerCase();
    if (blocked.has(lower)) {
      return false;
    }

    // Keep typical person-name characters; drop obvious non-name tokens.
    return /^[A-Za-z][A-Za-z'\-\s]{1,49}$/.test(candidate);
  }

  private captureBackQueryParams(): void {
    const sourceParams = this.route.snapshot.queryParams;

    ["type", "month", "year", "search"].forEach((key) => {
      if (sourceParams[key] !== undefined && sourceParams[key] !== null) {
        this.backQueryParams[key] = sourceParams[key];
      }
    });
  }

  private getOrdinalSuffix(day: number): string {
    if (day >= 11 && day <= 13) {
      return "th";
    }

    const remainder = day % 10;
    if (remainder === 1) {
      return "st";
    }
    if (remainder === 2) {
      return "nd";
    }
    if (remainder === 3) {
      return "rd";
    }

    return "th";
  }

  private splitDailyMessage(message: string): [string, string] {
    if (!message) {
      return ["", ""];
    }

    const [title, ...rest] = message.split(/\n\n?/);
    if (rest.length === 0) {
      return ["", title];
    }

    return [title, rest.join("\n\n")];
  }
}
