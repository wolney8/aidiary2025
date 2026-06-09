// Entry detail view with two-column layout
import {
  Component,
  ElementRef,
  HostListener,
  OnDestroy,
  OnInit,
  ViewChild,
  inject,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { ActivatedRoute, Router, RouterModule } from "@angular/router";
import { MatCardModule } from "@angular/material/card";
import { MatChipsModule } from "@angular/material/chips";
import { MatIconModule } from "@angular/material/icon";
import { MatButtonModule } from "@angular/material/button";
import { MatTooltipModule } from "@angular/material/tooltip";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { EntriesService } from "../../core/services/entries.service";
import { BackToTopComponent } from "../../shared/components/back-to-top/back-to-top.component";
import { formatReadableLongDate } from "../../shared/utils/date-display";

@Component({
  selector: "app-detail",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatCardModule,
    MatChipsModule,
    MatIconModule,
    MatButtonModule,
    MatTooltipModule,
    MatProgressSpinnerModule,
    BackToTopComponent,
  ],
  template: `
    <div class="detail-container" *ngIf="entry">
      <div class="analysis-warning" *ngIf="analysisWarningMessage" role="alert">
        {{ analysisWarningMessage }}
      </div>

      <div class="date-nav">
        <button mat-stroked-button type="button" (click)="goBack()">
          Back
        </button>
        <div class="date-heading">
          <h2>{{ getFriendlyDate() }}</h2>
          <p *ngIf="getFriendlyTime()">{{ getFriendlyTime() }}</p>
        </div>
        <div class="action-buttons">
          <button
            mat-raised-button
            color="primary"
            [routerLink]="['/entries', entry.id, 'edit']"
          >
            Edit Entry
          </button>
          <button mat-stroked-button color="warn" (click)="deleteEntry()">
            Delete
          </button>
        </div>
      </div>

      <section
        class="entry-image-band"
        [class.expanded]="isDreamImageExpanded"
        [class.prompt-editor-open]="isEditingDreamPrompt"
        [class.has-image]="!!getEntryImageUrl()"
        aria-label="Entry image"
      >
        <div
          #entryImageSurface
          class="entry-image-surface"
          [class.clickable]="canExpandDreamImage()"
          [class.expanded]="isDreamImageExpanded"
          [attr.role]="canExpandDreamImage() ? 'button' : null"
          [attr.tabindex]="canExpandDreamImage() ? 0 : null"
          [attr.aria-label]="
            canExpandDreamImage()
              ? isDreamImageExpanded
                ? 'Collapse entry image'
                : 'Expand entry image'
              : null
          "
          (click)="onDreamImageSurfaceClick($event)"
          (keydown.enter)="onDreamImageSurfaceClick($event)"
          (keydown.space)="onDreamImageSurfaceClick($event)"
        >
          <div
            class="entry-image-actions"
            [class.hidden]="isDreamImageExpanded"
            (click)="$event.stopPropagation()"
          >
            <input
              #dreamImageInput
              type="file"
              accept="image/png,image/jpeg,image/webp"
              class="dream-image-file-input"
              (change)="onDreamImageSelected($event)"
            />
            <button
              mat-raised-button
              color="primary"
              type="button"
              *ngIf="shouldShowDreamGenerateButton()"
              (click)="generateDreamImage()"
              [disabled]="isDreamImageBusy() || !canGenerateEntryImage()"
              [matTooltip]="getEntryImageGenerationTooltip()"
              [matTooltipShowDelay]="2500"
            >
              <mat-icon *ngIf="!isGeneratingDreamImage">{{
                getEntryImageUrl() ? "refresh" : "auto_awesome"
              }}</mat-icon>
              <mat-progress-spinner
                *ngIf="isGeneratingDreamImage"
                mode="indeterminate"
                diameter="18"
                strokeWidth="3"
              ></mat-progress-spinner>
              {{
                isGeneratingDreamImage
                  ? "Generating image…"
                  : getEntryImageUrl()
                    ? "Retry image"
                    : "Generate image"
              }}
            </button>
            <button
              mat-stroked-button
              type="button"
              (click)="triggerDreamImageUpload()"
              [disabled]="isDreamImageBusy()"
            >
              <mat-icon>{{ getEntryImageUrl() ? "upload" : "add_photo_alternate" }}</mat-icon>
              {{ getEntryImageUrl() ? "Replace image" : "Upload image" }}
            </button>
            <button
              mat-stroked-button
              type="button"
              (click)="toggleDreamPromptEditor()"
              [disabled]="isDreamImageBusy() || isSavingDreamPrompt"
            >
              <mat-icon>{{ isEditingDreamPrompt ? "close" : "edit" }}</mat-icon>
              {{ isEditingDreamPrompt ? "Close prompt" : "Edit prompt" }}
            </button>
            <button
              mat-stroked-button
              color="warn"
              class="danger-action"
              type="button"
              *ngIf="getEntryImageUrl()"
              (click)="deleteDreamImage()"
              [disabled]="isDreamImageBusy()"
            >
              <mat-icon>delete</mat-icon>
              Delete image
            </button>
          </div>
          <div class="entry-image-loading" *ngIf="isDreamImageBusy()">
            <mat-progress-spinner
              mode="indeterminate"
              diameter="56"
              strokeWidth="4"
            ></mat-progress-spinner>
            <span>{{ getDreamImageBusyLabel() }}</span>
          </div>
          <img
            *ngIf="getEntryImageUrl()"
            #entryImageElement
            [src]="getEntryImageUrl()!"
            alt="Entry image"
            class="entry-image"
            [style.object-position]="getDreamImageObjectPosition()"
            (load)="onEntryImageLoaded()"
          />
          <div
            class="entry-image-ai-badge"
            *ngIf="getEntryImageUrl() && isCurrentEntryAiImage()"
            [class.expanded]="isDreamImageExpanded"
          >
            <mat-icon>auto_awesome</mat-icon>
            <span *ngIf="isDreamImageExpanded">Generated by AI</span>
          </div>
          <div
            class="entry-image-adjuster"
            *ngIf="getEntryImageUrl() && isDreamImageExpanded"
            (click)="$event.stopPropagation()"
          >
            <button
              mat-mini-fab
              color="primary"
              type="button"
              aria-label="Adjust image position"
              (click)="toggleDreamImageAdjuster()"
            >
              <mat-icon>control_camera</mat-icon>
            </button>
            <div
              class="entry-image-adjuster-panel"
              *ngIf="isAdjustingDreamImagePosition"
            >
              <ng-container *ngIf="hasHorizontalDreamImageAdjustment">
                <label for="dream-image-position-x">Horizontal framing</label>
                <input
                  id="dream-image-position-x"
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  [(ngModel)]="dreamImagePositionX"
                  (ngModelChange)="onDreamImagePositionChange()"
                />
              </ng-container>
              <label for="dream-image-position-y">Vertical framing</label>
              <input
                id="dream-image-position-y"
                type="range"
                min="0"
                max="100"
                step="1"
                [(ngModel)]="dreamImagePositionY"
                (ngModelChange)="onDreamImagePositionChange()"
              />
            </div>
          </div>
          <div
            class="entry-image-download"
            *ngIf="getEntryImageUrl() && isDreamImageExpanded"
            (click)="$event.stopPropagation()"
          >
            <button
              mat-mini-fab
              color="primary"
              type="button"
              aria-label="Download full image"
              (click)="downloadEntryImage($event)"
            >
              <mat-icon>download</mat-icon>
            </button>
          </div>
          <div class="entry-image-placeholder" *ngIf="!getEntryImageUrl()">
            <mat-icon>image</mat-icon>
            <p>{{ getEntryImagePlaceholderMessage() }}</p>
          </div>
        </div>
        <div
          class="entry-image-prompt-editor"
          *ngIf="isEditingDreamPrompt"
          (click)="$event.stopPropagation()"
        >
          <label for="dream-image-prompt">Image prompt</label>
          <textarea
            id="dream-image-prompt"
            [(ngModel)]="dreamPromptDraft"
            rows="4"
            maxlength="1000"
            placeholder="Describe the dream scene you want the AI to render."
          ></textarea>
          <div class="entry-image-prompt-actions">
            <button
              mat-button
              class="entry-image-recycle-button"
              type="button"
              *ngIf="hasRecyclableDreamPrompt()"
              (click)="restoreRecycledDreamPrompt()"
              [disabled]="isSavingDreamPrompt"
              aria-label="Restore previous image prompt"
            >
              <mat-icon>recycling</mat-icon>
            </button>
            <button
              mat-button
              type="button"
              (click)="cancelDreamPromptEdit()"
              [disabled]="isSavingDreamPrompt"
            >
              Cancel
            </button>
            <button
              mat-raised-button
              color="primary"
              type="button"
              (click)="saveDreamPrompt()"
              [disabled]="!canSaveDreamPrompt() || isSavingDreamPrompt"
            >
              {{ isSavingDreamPrompt ? "Saving…" : "Save prompt" }}
            </button>
          </div>
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
              <p
                class="no-response"
                *ngIf="!entry.summary && !entry.interpretation"
              >
                No AI analysis was recorded for this entry.
              </p>
            </div>
            <div *ngIf="!isDream()">
              <p
                class="paragraph-block"
                *ngFor="let paragraph of getAIParagraphs()"
              >
                {{ paragraph }}
              </p>
              <p class="no-response" *ngIf="getAIParagraphs().length === 0">
                No AI response was recorded for this entry.
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
              [class.duplicate-tag-chip]="isDuplicateTag(tag)"
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
            class="expand-toggle ellipsis-toggle"
            *ngIf="shouldShowToggle(getPeopleArray())"
            (click)="showAllPeople = !showAllPeople"
            [attr.aria-label]="
              showAllPeople ? 'Show fewer people' : 'Show more people'
            "
          >
            {{ showAllPeople ? "Show less" : "..." }}
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
      </div>

      <app-back-to-top />
    </div>
  `,
  styles: [
    `
      .detail-container {
        max-width: 1200px;
        margin: 0 auto;
      }

      .date-nav {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
        align-items: center;
        gap: 1rem;
        margin-bottom: var(--spacing-md);
      }

      .analysis-warning {
        margin-bottom: var(--spacing-md);
        padding: var(--spacing-sm) var(--spacing-md);
        border: 1px solid #f59e0b;
        background: #fffbeb;
        color: #92400e;
        border-radius: var(--radius-md);
      }

      .date-heading {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.15rem;
      }

      .date-nav h2 {
        margin: 0;
        text-align: center;
        justify-self: center;
      }

      .date-heading p {
        margin: 0;
        color: var(--colour-text-secondary);
        font-size: 0.95rem;
      }

      .date-nav > button {
        justify-self: start;
        width: auto;
      }

      .action-buttons {
        display: flex;
        gap: 0.5rem;
        justify-self: end;
      }

      .entry-image-band {
        position: relative;
        margin-bottom: var(--spacing-md);
        border-radius: var(--radius-md);
        border: 1px solid var(--colour-border);
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
        overflow: visible;
      }

      .entry-image-band.expanded {
        box-shadow: 0 20px 48px rgba(15, 23, 42, 0.22);
      }

      .entry-image-surface {
        position: relative;
        height: 214px;
        overflow: hidden;
        border-radius: inherit;
        transition:
          height 260ms ease,
          background 260ms ease;
      }

      .entry-image-surface.clickable {
        cursor: zoom-in;
      }

      .entry-image-surface.expanded {
        height: 470px;
        background: #020617;
        cursor: zoom-out;
      }

      .entry-image-actions {
        position: absolute;
        top: 0.9rem;
        right: 0.9rem;
        display: flex;
        gap: 0.75rem;
        flex-wrap: wrap;
        justify-content: flex-end;
        z-index: 2;
        transition:
          opacity 180ms ease,
          transform 180ms ease;
      }

      .dream-image-file-input {
        display: none;
      }

      .entry-image-actions.hidden {
        opacity: 0;
        pointer-events: none;
        transform: translateY(-8px);
      }

      .entry-image-actions .mdc-button {
        color: #ffffff !important;
      }

      .entry-image-actions .mat-mdc-raised-button {
        box-shadow: 0 10px 22px rgba(15, 23, 42, 0.22);
      }

      .entry-image-actions .mat-mdc-outlined-button {
        border-color: rgba(255, 255, 255, 0.72) !important;
        background: rgba(15, 23, 42, 0.54) !important;
      }

      .entry-image-actions .mat-mdc-outlined-button.danger-action {
        border-color: rgba(248, 113, 113, 0.95) !important;
        background: rgba(127, 29, 29, 0.72) !important;
        color: #fee2e2 !important;
      }

      .entry-image-actions .mat-mdc-outlined-button.danger-action:hover {
        background: rgba(185, 28, 28, 0.9) !important;
        color: #ffffff !important;
      }

      .entry-image-actions .mat-icon,
      .entry-image-actions .mat-mdc-progress-spinner {
        color: inherit;
        --mdc-circular-progress-active-indicator-color: currentColor;
      }

      .entry-image-loading {
        position: absolute;
        inset: 0;
        z-index: 2;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.8rem;
        background: rgba(15, 23, 42, 0.42);
        color: #ffffff;
        pointer-events: none;
        backdrop-filter: blur(2px);
      }

      .entry-image-loading .mat-mdc-progress-spinner {
        --mdc-circular-progress-active-indicator-color: #ffffff;
      }

      .entry-image-loading span {
        font-weight: 600;
      }

      .entry-image-adjuster {
        position: absolute;
        left: 1rem;
        bottom: 1rem;
        z-index: 2;
        display: flex;
        align-items: flex-end;
        gap: 0.75rem;
      }

      .entry-image-adjuster-panel {
        min-width: 220px;
        padding: 0.75rem 0.85rem;
        border-radius: var(--radius-md);
        border: 1px solid rgba(255, 255, 255, 0.18);
        background: rgba(15, 23, 42, 0.82);
        color: #ffffff;
        backdrop-filter: blur(8px);
        box-shadow: 0 12px 32px rgba(15, 23, 42, 0.28);
      }

      .entry-image-ai-badge {
        position: absolute;
        right: 1rem;
        bottom: 1rem;
        z-index: 2;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.4rem 0.6rem;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.55);
        color: rgba(255, 255, 255, 0.88);
        backdrop-filter: blur(4px);
        font-size: 0.78rem;
        font-weight: 600;
        pointer-events: none;
      }

      .entry-image-ai-badge.expanded {
        bottom: 1rem;
      }

      .entry-image-ai-badge .mat-icon {
        font-size: 0.95rem;
        width: 0.95rem;
        height: 0.95rem;
      }

      .entry-image-download {
        position: absolute;
        right: 1rem;
        top: 1rem;
        z-index: 2;
      }

      .entry-image-adjuster-panel label {
        display: block;
        margin-bottom: 0.35rem;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        text-transform: uppercase;
      }

      .entry-image-adjuster-panel label + input[type="range"] {
        margin-bottom: 0.7rem;
      }

      .entry-image-adjuster-panel input[type="range"] {
        width: 100%;
      }

      .entry-image-prompt-editor {
        position: absolute;
        top: 4.2rem;
        right: 0.9rem;
        z-index: 2;
        width: min(360px, calc(100% - 1.8rem));
        padding: 0.9rem;
        border-radius: var(--radius-md);
        border: 1px solid rgba(255, 255, 255, 0.22);
        background: rgba(15, 23, 42, 0.92);
        color: #ffffff;
        backdrop-filter: blur(8px);
      }

      .entry-image-band.prompt-editor-open {
        margin-bottom: calc(var(--spacing-md) + 11rem);
      }

      .entry-image-prompt-editor label {
        display: block;
        margin-bottom: 0.45rem;
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        text-transform: uppercase;
      }

      .entry-image-prompt-editor textarea {
        box-sizing: border-box;
        width: 100%;
        resize: vertical;
        min-height: 5.5rem;
        border-radius: var(--radius-sm);
        border: 1px solid rgba(255, 255, 255, 0.18);
        background: rgba(255, 255, 255, 0.1);
        color: #ffffff;
        padding: 0.7rem 0.8rem;
        font: inherit;
      }

      .entry-image-prompt-editor textarea::placeholder {
        color: rgba(255, 255, 255, 0.72);
      }

      .entry-image-prompt-actions {
        display: flex;
        justify-content: flex-end;
        gap: 0.6rem;
        margin-top: 0.7rem;
      }

      .entry-image-prompt-actions .mdc-button {
        color: #ffffff !important;
      }

      .entry-image-prompt-actions .mat-mdc-button {
        background: rgba(255, 255, 255, 0.08) !important;
      }

      .entry-image-prompt-actions .entry-image-recycle-button {
        min-width: 40px;
        padding: 0 0.8rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
      }

      .entry-image {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
        transition:
          transform 260ms ease,
          filter 260ms ease;
      }

      .entry-image-surface.expanded .entry-image {
        object-fit: cover;
        filter: saturate(1.05);
      }

      .entry-image-placeholder {
        position: absolute;
        inset: 0;
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
          grid-template-columns: 1fr;
        }

        .date-nav h2 {
          text-align: center;
        }

        .action-buttons {
          justify-self: stretch;
          justify-content: flex-end;
        }

        .entry-image-surface.expanded {
          height: min(55vh, 420px);
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

      .duplicate-tag-chip {
        background-color: #fee2e2 !important;
        color: #991b1b !important;
      }

      .duplicate-tag-chip:hover {
        background-color: #dc2626 !important;
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

      .no-response {
        color: var(--colour-text-secondary);
        font-style: italic;
        margin: 0;
      }
    `,
  ],
})
export class DetailComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private entriesService = inject(EntriesService);
  @ViewChild("dreamImageInput") dreamImageInput?: ElementRef<HTMLInputElement>;
  @ViewChild("entryImageSurface") entryImageSurface?: ElementRef<HTMLDivElement>;
  @ViewChild("entryImageElement") entryImageElement?: ElementRef<HTMLImageElement>;

  private readonly collapsedItemsLimit = 8;

  entry: any;
  entryType: "daily" | "dream" = "daily";
  backQueryParams: Record<string, string | number> = {};
  analysisWarningMessage = "";
  isGeneratingDreamImage = false;
  isUploadingDreamImage = false;
  isDreamImageExpanded = false;
  isAdjustingDreamImagePosition = false;
  isEditingDreamPrompt = false;
  isSavingDreamPrompt = false;
  hasHorizontalDreamImageAdjustment = false;
  dreamImagePositionX = 50;
  dreamImagePositionY = 50;
  dreamPromptDraft = "";
  dreamPromptOverride = "";
  recycledDreamPrompt = "";
  private dreamImagePositionSaveHandle: ReturnType<typeof setTimeout> | null =
    null;

  showAllTags = false;
  showAllPeople = false;

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get("id"));
    this.captureBackQueryParams();
    this.captureAnalysisWarning();

    // Try loading as daily first, then dream if not found
    this.entriesService.getDailyEntry(id).subscribe({
      next: (entry) => {
        this.entry = entry;
        this.entryType = "daily";
        this.syncDreamImageUiFromEntry();
      },
      error: () => {
        this.entriesService.getDreamEntry(id).subscribe((entry) => {
          this.entry = entry;
          this.entryType = "dream";
          this.syncDreamImageUiFromEntry();
        });
      },
    });
  }

  ngOnDestroy(): void {
    this.cancelDreamImagePositionSave();
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

  deleteEntry(): void {
    const entryType = this.isDream() ? "dream" : "daily";
    const confirmed = confirm(
      `Are you sure you want to delete this ${entryType} entry? This action cannot be undone.`,
    );

    if (confirmed && this.entry) {
      const deleteObservable = this.isDream()
        ? this.entriesService.deleteDreamEntry(this.entry.id)
        : this.entriesService.deleteDailyEntry(this.entry.id);

      deleteObservable.subscribe({
        next: () => {
          this.router.navigate(["/entries"]);
        },
        error: (error) => {
          console.error("Failed to delete entry:", error);
          alert("Failed to delete entry. Please try again.");
        },
      });
    }
  }

  getFriendlyDate(): string {
    if (!this.entry?.entry_date) {
      return "Entry";
    }

    return formatReadableLongDate(this.entry.entry_date) || "Entry";
  }

  getFriendlyTime(): string {
    const rawValue =
      typeof this.entry?.entry_time === "string" ? this.entry.entry_time.trim() : "";
    const value = rawValue || (this.isDream() ? "08:00" : "19:00");
    if (!/^\d{2}:\d{2}$/.test(value)) {
      return "";
    }

    const [hoursText, minutesText] = value.split(":");
    const hours = Number(hoursText);
    const minutes = Number(minutesText);
    if (
      Number.isNaN(hours) ||
      Number.isNaN(minutes) ||
      hours < 0 ||
      hours > 23 ||
      minutes < 0 ||
      minutes > 59
    ) {
      return "";
    }

    return new Intl.DateTimeFormat("en-GB", {
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(2000, 0, 1, hours, minutes));
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
    const raw = this.entry?.image_url;
    if (!raw || typeof raw !== "string") {
      return null;
    }

    const value = raw.trim();
    return value.length > 0 ? value : null;
  }

  isCurrentEntryAiImage(): boolean {
    return (this.entry?.image_source || "").trim() === "ai";
  }

  hasDreamImagePrompt(): boolean {
    return this.getCurrentDreamPrompt().length > 0;
  }

  isUsingCustomDreamImage(): boolean {
    return !!this.getEntryImageUrl() && !this.hasDreamImagePrompt();
  }

  shouldShowDreamGenerateButton(): boolean {
    return !this.isUsingCustomDreamImage() || this.isGeneratingDreamImage;
  }

  canExpandDreamImage(): boolean {
    return !!this.getEntryImageUrl();
  }

  isDreamImageBusy(): boolean {
    return this.isGeneratingDreamImage || this.isUploadingDreamImage;
  }

  getDreamImageBusyLabel(): string {
    if (this.isUploadingDreamImage) {
      return "Uploading image…";
    }
    return "Generating image…";
  }

  onDreamImageSurfaceClick(event: Event): void {
    if (!this.canExpandDreamImage()) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    this.isDreamImageExpanded = !this.isDreamImageExpanded;
    if (!this.isDreamImageExpanded) {
      this.isAdjustingDreamImagePosition = false;
      return;
    }

    setTimeout(() => this.updateDreamImageAdjustmentAvailability());
  }

  toggleDreamImageAdjuster(): void {
    this.isAdjustingDreamImagePosition = !this.isAdjustingDreamImagePosition;
  }

  onEntryImageLoaded(): void {
    this.updateDreamImageAdjustmentAvailability();
  }

  onDreamImagePositionChange(): void {
    if (!this.entry?.id || !this.getEntryImageUrl()) {
      return;
    }

    this.cancelDreamImagePositionSave();

    this.dreamImagePositionSaveHandle = setTimeout(() => {
      this.dreamImagePositionSaveHandle = null;
      const imagePositionX = this.hasHorizontalDreamImageAdjustment
        ? this.clampDreamImagePosition(this.dreamImagePositionX)
        : 50;
      const imagePositionY = this.clampDreamImagePosition(
        this.dreamImagePositionY,
      );
      const request: { subscribe: (handlers: { error: (error: unknown) => void }) => unknown } = this.isDream()
        ? this.entriesService.updateDreamEntry(this.entry.id, {
            image_position_x: imagePositionX,
            image_position_y: imagePositionY,
          })
        : this.entriesService.updateDailyEntry(this.entry.id, {
            image_position_x: imagePositionX,
            image_position_y: imagePositionY,
          });
      request.subscribe({
        error: (error: unknown) => {
          console.error("Failed to persist entry image position:", error);
        },
      });
    }, 250);
  }

  canGenerateEntryImage(): boolean {
    if (this.hasDreamImagePrompt()) {
      return true;
    }

    return this.isDream() ? false : this.canDeriveDailyImagePrompt();
  }

  getEntryImageGenerationTooltip(): string {
    if (this.canGenerateEntryImage()) {
      return "";
    }

    return this.isDream()
      ? "Generate an AI analysis first so this entry has an image prompt."
      : "Generate and save an AI response first so this daily entry has enough context for an image prompt.";
  }

  getEntryImagePlaceholderMessage(): string {
    return this.isDream()
      ? "No image generated for this dream yet."
      : "No image added for this daily entry yet.";
  }

  private canDeriveDailyImagePrompt(): boolean {
    const userMessage =
      typeof this.entry?.user_message === "string"
        ? this.entry.user_message.trim()
        : "";
    const aiResponse =
      typeof this.entry?.ai_response === "string"
        ? this.entry.ai_response.trim()
        : "";
    return userMessage.length > 0 && aiResponse.length > 0;
  }

  private generateEntryImageRequest(promptOverride?: string) {
    return this.isDream()
      ? this.entriesService.generateDreamImage(this.entry.id, promptOverride)
      : this.entriesService.generateDailyImage(this.entry.id, promptOverride);
  }

  private uploadEntryImageRequest(file: File) {
    return this.isDream()
      ? this.entriesService.uploadDreamImage(this.entry.id, file)
      : this.entriesService.uploadDailyImage(this.entry.id, file);
  }

  private deleteEntryImageRequest() {
    return this.isDream()
      ? this.entriesService.deleteDreamImage(this.entry.id)
      : this.entriesService.deleteDailyImage(this.entry.id);
  }

  toggleDreamPromptEditor(): void {
    this.isEditingDreamPrompt = !this.isEditingDreamPrompt;
    this.dreamPromptDraft = this.getCurrentDreamPrompt();
  }

  cancelDreamPromptEdit(): void {
    this.isEditingDreamPrompt = false;
    this.dreamPromptDraft = this.getCurrentDreamPrompt();
  }

  canSaveDreamPrompt(): boolean {
    return this.dreamPromptDraft.trim().length > 0;
  }

  hasRecyclableDreamPrompt(): boolean {
    return this.recycledDreamPrompt.trim().length > 0;
  }

  restoreRecycledDreamPrompt(): void {
    if (!this.hasRecyclableDreamPrompt()) {
      return;
    }

    this.dreamPromptDraft = this.recycledDreamPrompt.trim();
  }

  saveDreamPrompt(): void {
    if (!this.entry?.id || !this.canSaveDreamPrompt()) {
      return;
    }

    const nextPrompt = this.dreamPromptDraft.trim();
    this.isSavingDreamPrompt = true;
    this.dreamPromptOverride = nextPrompt;
    this.generateEntryImageRequest(nextPrompt).subscribe({
      next: (result) => {
        this.entry = {
          ...this.entry,
          image_url: result.image_url,
          image_source: result.image_source ?? this.entry?.image_source ?? null,
          recycled_image_prompt: result.recycled_image_prompt ?? this.entry?.recycled_image_prompt ?? "",
          image_position_x: result.image_position_x ?? this.entry?.image_position_x ?? 50,
          image_position_y: result.image_position_y ?? this.entry?.image_position_y ?? 50,
        };
        this.syncDreamImageUiFromEntry();
        this.isGeneratingDreamImage = false;
        this.isSavingDreamPrompt = false;
        this.isEditingDreamPrompt = false;
      },
      error: (error) => {
        console.error("Failed to generate dream image from edited prompt:", error);
        this.isGeneratingDreamImage = false;
        this.isSavingDreamPrompt = false;
        alert("Failed to generate a new image from this prompt. Please try again.");
      },
    });
    this.isGeneratingDreamImage = true;
  }

  generateDreamImage(): void {
    if (!this.entry?.id || this.isDreamImageBusy()) {
      return;
    }

    this.isGeneratingDreamImage = true;
    this.cancelDreamImagePositionSave();
    const promptOverride = this.dreamPromptOverride.trim();
    this.generateEntryImageRequest(
      promptOverride.length > 0 ? promptOverride : undefined,
    ).subscribe({
      next: (result) => {
        this.entry = {
          ...this.entry,
          image_url: result.image_url,
          image_source: result.image_source ?? this.entry?.image_source ?? null,
          recycled_image_prompt: result.recycled_image_prompt ?? "",
          image_position_x: result.image_position_x ?? this.entry?.image_position_x ?? 50,
          image_position_y: result.image_position_y ?? this.entry?.image_position_y ?? 50,
        };
        if (!promptOverride.length) {
          this.entry = {
            ...this.entry,
            image_prompt: result.image_prompt,
          };
        }
        this.syncDreamImageUiFromEntry();
        this.isGeneratingDreamImage = false;
      },
      error: (error) => {
        console.error("Failed to generate dream image:", error);
        this.isGeneratingDreamImage = false;
        alert("Failed to generate dream image. Please try again.");
      },
    });
  }

  triggerDreamImageUpload(): void {
    if (this.isDreamImageBusy()) {
      return;
    }

    this.dreamImageInput?.nativeElement.click();
  }

  onDreamImageSelected(event: Event): void {
    if (!this.entry?.id) {
      return;
    }

    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    input.value = "";

    if (!file) {
      return;
    }

    this.cancelDreamImagePositionSave();
    this.isUploadingDreamImage = true;
    this.uploadEntryImageRequest(file).subscribe({
      next: (result) => {
        this.entry = {
          ...this.entry,
          image_prompt: result.image_prompt,
          image_url: result.image_url,
          image_source: result.image_source ?? this.entry?.image_source ?? null,
          recycled_image_prompt: result.recycled_image_prompt ?? "",
          image_position_x: result.image_position_x ?? this.entry?.image_position_x ?? 50,
          image_position_y: result.image_position_y ?? this.entry?.image_position_y ?? 50,
        };
        this.dreamPromptOverride = "";
        this.syncDreamImageUiFromEntry();
        this.isUploadingDreamImage = false;
      },
      error: (error) => {
        console.error("Failed to upload dream image:", error);
        this.isUploadingDreamImage = false;
        alert(this.extractDreamImageError(error, "Failed to upload image. Please try again."));
      },
    });
  }

  deleteDreamImage(): void {
    if (!this.entry?.id || this.isDreamImageBusy()) {
      return;
    }

    const confirmed = confirm(
      "Delete the current image? Your saved image prompt will be kept so you can generate again later.",
    );

    if (!confirmed) {
      return;
    }

    this.cancelDreamImagePositionSave();
    this.isUploadingDreamImage = true;
    this.deleteEntryImageRequest().subscribe({
      next: (result) => {
        this.entry = {
          ...this.entry,
          image_prompt: result.image_prompt,
          image_url: result.image_url,
          image_source: result.image_source ?? null,
          recycled_image_prompt: result.recycled_image_prompt ?? "",
          image_position_x: result.image_position_x ?? 50,
          image_position_y: result.image_position_y ?? 50,
        };
        this.dreamPromptOverride = "";
        this.isDreamImageExpanded = false;
        this.isAdjustingDreamImagePosition = false;
        this.syncDreamImageUiFromEntry();
        this.isUploadingDreamImage = false;
      },
      error: (error) => {
        console.error("Failed to delete dream image:", error);
        this.isUploadingDreamImage = false;
        alert(this.extractDreamImageError(error, "Failed to delete image. Please try again."));
      },
    });
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

  @HostListener("document:click", ["$event"])
  onDocumentClick(event: MouseEvent): void {
    if (!this.isDreamImageExpanded) {
      return;
    }

    const target = event.target as HTMLElement | null;
    if (target?.closest(".entry-image-band")) {
      return;
    }

    this.isDreamImageExpanded = false;
    this.isAdjustingDreamImagePosition = false;
  }

  @HostListener("window:resize")
  onWindowResize(): void {
    this.updateDreamImageAdjustmentAvailability();
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

  private getCurrentDreamPrompt(): string {
    if (this.dreamPromptOverride.trim().length > 0) {
      return this.dreamPromptOverride.trim();
    }

    return typeof this.entry?.image_prompt === "string"
      ? this.entry.image_prompt.trim()
      : "";
  }

  private getCurrentRecycledDreamPrompt(): string {
    return typeof this.entry?.recycled_image_prompt === "string"
      ? this.entry.recycled_image_prompt.trim()
      : "";
  }

  private syncDreamImageUiFromEntry(): void {
    this.dreamPromptDraft = this.getCurrentDreamPrompt();
    this.recycledDreamPrompt = this.getCurrentRecycledDreamPrompt();
    this.hasHorizontalDreamImageAdjustment = false;
    this.dreamImagePositionX = this.clampDreamImagePosition(
      Number(this.entry?.image_position_x ?? 50),
    );
    this.dreamImagePositionY = this.clampDreamImagePosition(
      Number(this.entry?.image_position_y ?? 50),
    );
  }

  private cancelDreamImagePositionSave(): void {
    if (this.dreamImagePositionSaveHandle) {
      clearTimeout(this.dreamImagePositionSaveHandle);
      this.dreamImagePositionSaveHandle = null;
    }
  }

  private extractDreamImageError(error: any, fallback: string): string {
    const message =
      typeof error?.error?.error === "string" ? error.error.error.trim() : "";
    return message || fallback;
  }

  async downloadEntryImage(event: Event): Promise<void> {
    event.preventDefault();
    event.stopPropagation();

    const imageUrl = this.getEntryImageUrl();
    if (!imageUrl) {
      return;
    }

    try {
      const response = await fetch(imageUrl);
      if (!response.ok) {
        throw new Error(`Download failed with status ${response.status}`);
      }

      let blob = await response.blob();
      if (this.isCurrentEntryAiImage()) {
        blob = await this.applyAiWatermarkToBlob(blob);
      }
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = this.getEntryImageDownloadFilename(blob.type);
      link.click();
      URL.revokeObjectURL(objectUrl);
    } catch (error) {
      console.error("Failed to download entry image:", error);
      window.open(imageUrl, "_blank", "noopener");
    }
  }

  getDreamImageObjectPosition(): string {
    const x = this.hasHorizontalDreamImageAdjustment
      ? this.clampDreamImagePosition(this.dreamImagePositionX)
      : 50;
    const y = this.clampDreamImagePosition(this.dreamImagePositionY);
    return `${x}% ${y}%`;
  }

  private clampDreamImagePosition(value: number): number {
    if (Number.isNaN(value)) {
      return 50;
    }

    return Math.min(100, Math.max(0, value));
  }

  private updateDreamImageAdjustmentAvailability(): void {
    const surface = this.entryImageSurface?.nativeElement;
    const image = this.entryImageElement?.nativeElement;

    if (
      !surface ||
      !image ||
      !image.naturalWidth ||
      !image.naturalHeight ||
      !surface.clientWidth ||
      !surface.clientHeight
    ) {
      this.hasHorizontalDreamImageAdjustment = false;
      return;
    }

    const imageAspect = image.naturalWidth / image.naturalHeight;
    const surfaceAspect = surface.clientWidth / surface.clientHeight;
    this.hasHorizontalDreamImageAdjustment = imageAspect > surfaceAspect + 0.01;

    if (!this.hasHorizontalDreamImageAdjustment) {
      this.dreamImagePositionX = 50;
    }
  }

  private getEntryImageDownloadFilename(mimeType: string): string {
    const entryKind = this.isDream() ? "dream" : "daily";
    const entryId = this.entry?.id ?? "entry";
    const entryDate =
      typeof this.entry?.entry_date === "string"
        ? this.entry.entry_date
        : "image";

    if (mimeType === "image/png") {
      return `${entryKind}-${entryId}-${entryDate}.png`;
    }

    if (mimeType === "image/webp") {
      return `${entryKind}-${entryId}-${entryDate}.webp`;
    }

    return `${entryKind}-${entryId}-${entryDate}.jpg`;
  }

  private async applyAiWatermarkToBlob(blob: Blob): Promise<Blob> {
    const imageUrl = URL.createObjectURL(blob);

    try {
      const image = await this.loadImageForWatermark(imageUrl);
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth || image.width;
      canvas.height = image.naturalHeight || image.height;

      const context = canvas.getContext("2d");
      if (!context) {
        return blob;
      }

      context.drawImage(image, 0, 0, canvas.width, canvas.height);

      const watermarkText = "✨ Generated by AI";
      const fontSize = Math.max(18, Math.round(canvas.width * 0.022));
      context.font = `600 ${fontSize}px sans-serif`;
      const paddingX = Math.round(fontSize * 0.75);
      const paddingY = Math.round(fontSize * 0.5);
      const textWidth = context.measureText(watermarkText).width;
      const badgeWidth = textWidth + paddingX * 2;
      const badgeHeight = fontSize + paddingY * 2;
      const x = canvas.width - badgeWidth - Math.round(fontSize * 0.8);
      const y = canvas.height - badgeHeight - Math.round(fontSize * 0.8);

      context.fillStyle = "rgba(15, 23, 42, 0.55)";
      this.drawRoundedRect(context, x, y, badgeWidth, badgeHeight, badgeHeight / 2);
      context.fill();

      context.fillStyle = "rgba(255, 255, 255, 0.9)";
      context.textBaseline = "middle";
      context.fillText(
        watermarkText,
        x + paddingX,
        y + badgeHeight / 2,
      );

      return await new Promise<Blob>((resolve) => {
        canvas.toBlob(
          (result) => resolve(result ?? blob),
          blob.type || "image/png",
          0.92,
        );
      });
    } finally {
      URL.revokeObjectURL(imageUrl);
    }
  }

  private loadImageForWatermark(sourceUrl: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error("Failed to load image for watermarking"));
      image.src = sourceUrl;
    });
  }

  private drawRoundedRect(
    context: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    radius: number,
  ): void {
    const safeRadius = Math.min(radius, width / 2, height / 2);
    context.beginPath();
    context.moveTo(x + safeRadius, y);
    context.lineTo(x + width - safeRadius, y);
    context.quadraticCurveTo(x + width, y, x + width, y + safeRadius);
    context.lineTo(x + width, y + height - safeRadius);
    context.quadraticCurveTo(x + width, y + height, x + width - safeRadius, y + height);
    context.lineTo(x + safeRadius, y + height);
    context.quadraticCurveTo(x, y + height, x, y + height - safeRadius);
    context.lineTo(x, y + safeRadius);
    context.quadraticCurveTo(x, y, x + safeRadius, y);
    context.closePath();
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

  isDuplicateTag(tag: string): boolean {
    return tag.trim() === "*Duplicate*";
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

  private captureBackQueryParams(): void {
    const sourceParams = this.route.snapshot.queryParams;

    ["type", "month", "year", "search"].forEach((key) => {
      if (sourceParams[key] !== undefined && sourceParams[key] !== null) {
        this.backQueryParams[key] = sourceParams[key];
      }
    });
  }

  private captureAnalysisWarning(): void {
    const warningCode =
      this.route.snapshot.queryParamMap.get("analysisWarning");

    if (warningCode === "ai-rate-limit") {
      this.analysisWarningMessage =
        "Your entry was saved, but AI analysis is currently rate-limited. Please try analysing again later.";
      return;
    }

    if (warningCode === "ai-save-failed") {
      this.analysisWarningMessage =
        "Your entry was saved, but the AI response could not be attached to it. Please try analysing again.";
      return;
    }

    this.analysisWarningMessage = "";
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
