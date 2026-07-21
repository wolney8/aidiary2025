import { ComponentFixture, TestBed } from "@angular/core/testing";
import { MAT_DIALOG_DATA, MatDialogRef } from "@angular/material/dialog";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { EntryImageGalleryComponent } from "./entry-image-gallery.component";

describe("EntryImageGalleryComponent", () => {
  let fixture: ComponentFixture<EntryImageGalleryComponent>;
  let component: EntryImageGalleryComponent;
  let dialogRef: jasmine.SpyObj<MatDialogRef<EntryImageGalleryComponent>>;

  const images = [
    {
      id: 11,
      asset_role: "attachment",
      original_filename: "first-photo.jpg",
      mime_type: "image/jpeg",
      file_size_bytes: 1024,
      sort_order: 0,
      created_at: "2026-07-21T10:00:00Z",
      url: "/media/first-photo.jpg",
      is_image: true,
    },
    {
      id: 12,
      asset_role: "attachment",
      original_filename: "second-photo.jpg",
      mime_type: "image/jpeg",
      file_size_bytes: 2048,
      sort_order: 1,
      created_at: "2026-07-21T10:01:00Z",
      url: "/media/second-photo.jpg",
      is_image: true,
    },
  ];

  beforeEach(async () => {
    dialogRef = jasmine.createSpyObj("MatDialogRef", ["close"]);

    await TestBed.configureTestingModule({
      imports: [EntryImageGalleryComponent, NoopAnimationsModule],
      providers: [
        { provide: MAT_DIALOG_DATA, useValue: { images, initialImageId: 12 } },
        { provide: MatDialogRef, useValue: dialogRef },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(EntryImageGalleryComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("opens on the selected image", () => {
    expect(component.currentIndex).toBe(1);
    expect(component.currentImage.original_filename).toBe("second-photo.jpg");
  });

  it("cycles through images with gallery controls", () => {
    component.showNext();
    expect(component.currentIndex).toBe(0);

    component.showPrevious();
    expect(component.currentIndex).toBe(1);
  });

  it("supports arrow-key navigation and closes explicitly", () => {
    component.handleKeydown(new KeyboardEvent("keydown", { key: "ArrowLeft" }));
    expect(component.currentIndex).toBe(0);

    component.close();
    expect(dialogRef.close).toHaveBeenCalled();
  });
});
