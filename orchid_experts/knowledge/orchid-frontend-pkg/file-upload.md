<!-- Source: derived from orchid-frontend/AGENTS.md, orchid-website/src/content/packages/orchid-frontend.mdx, and codebase analysis -->

# File Upload

The frontend supports drag-and-drop file upload with multipart form data submission and optional vision model preview for images. Files are sent alongside messages using the multipart endpoint on the API.

## Drag-and-Drop

Files can be dragged directly into the chat input area:

```tsx
<ChatInput
  onDrop={handleFileDrop}
  acceptFileTypes={[".pdf", ".docx", ".xlsx", ".csv", ".txt", ".md", ".png", ".jpg", ".gif"]}
  maxFileSizeMB={20}
/>
```

### UX Flow

1. User drags a file onto the chat input area (drop zone highlights).
2. File preview appears: thumbnail for images, icon with file name for documents.
3. User can add multiple files or remove individual files.
4. User types a message and presses Enter or clicks Send.
5. Files are uploaded via multipart form data alongside the message.
6. Progress bar shows upload status if the file is large.
7. Message and file metadata appear in the chat.

## Multipart Upload

Files are sent together with the message using `FormData`:

```typescript
// src/app/actions.ts
"use server";

export async function sendMessage(chatId: string, message: string, files: File[]) {
  const formData = new FormData();
  formData.append("message", message);

  for (const file of files) {
    formData.append("files", file);  // Multiple files supported
  }

  const response = await fetch(`${API_URL}/chats/${chatId}/messages`, {
    method: "POST",
    body: formData,
    headers: { Authorization: `Bearer ${sessionToken}` },
  });
}
```

The API's `POST /chats/{chat_id}/messages` endpoint accepts `multipart/form-data`:
- `message` field — The user's text message.
- `file` or `files` field(s) — One or more file attachments.

## Vision Preview (Image Description)

For images, the frontend can optionally request a vision model description before sending. This gives the agent "sight" of image content:

```tsx
<ImagePreview
  file={imageFile}
  onRequestVision={async () => {
    const description = await getVisionDescription(imageFile);
    // Description is prepended to the message: "Image description: a chart showing..."
  }}
/>
```

The vision model is configured in `orchid.yml` under `upload.vision_model` (e.g., `ollama/minicpm-v`).

## File Type Support

| Type | Extensions | Preview | Max Recommended Size |
|------|-----------|---------|----------------------|
| PDF | `.pdf` | Icon + name | 20 MB |
| Word | `.docx` | Icon + name | 20 MB |
| Excel | `.xlsx` | Icon + name | 10 MB |
| CSV | `.csv` | Snippet (first 5 lines) | 5 MB |
| Markdown | `.md` | Snippet (first 500 chars) | 1 MB |
| Text | `.txt` | Snippet (first 500 chars) | 1 MB |
| PNG | `.png` | Thumbnail + vision | 10 MB |
| JPEG | `.jpg`, `.jpeg` | Thumbnail + vision | 10 MB |
| GIF | `.gif` | Thumbnail (no vision) | 5 MB |

## Size Limits and Validation

Size limits are configured in the API (`upload.max_size_mb` in `orchid.yml`). The frontend enforces the same limit locally for instant feedback:

```typescript
const MAX_SIZE_MB = 20;

function validateFile(file: File): string | null {
  if (file.size > MAX_SIZE_MB * 1024 * 1024) {
    return `File exceeds ${MAX_SIZE_MB}MB limit`;
  }
  const ext = file.name.split(".").pop()?.toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(`.${ext}`)) {
    return `Unsupported file type: .${ext}`;
  }
  return null;  // Valid
}
```

## Upload Progress

Large files show a progress bar during upload:

```tsx
<UploadProgress
  fileName="report.pdf"
  fileSize="15.2 MB"
  progress={65}
  onCancel={() => abortUpload()}
/>
```

The progress bar uses the `XMLHttpRequest` progress events (or `fetch` with a stream reader) to track upload percentage. Users can cancel an in-progress upload.

## File References in Messages

Uploaded files appear in the message as clickable references:

```tsx
<MessageBubble>
  <Content>What is in this annual report?</Content>
  <Attachments>
    <FileRef name="annual-report-2024.pdf" size="2.1 MB" />
  </Attachments>
</MessageBubble>
```

The agent receives the file content (extracted text) in its context. The original file bytes are stored and can be downloaded if configured.

## Error Handling

File upload errors are surfaced inline:

```tsx
{uploadError && (
  <UploadError
    fileName="report.pdf"
    error="File too large (25 MB exceeds 20 MB limit)"
    onRemove={() => removeFile("report.pdf")}
    onRetry={() => retryUpload("report.pdf")}
  />
)}
```

Common errors: file too large, unsupported type, network failure during upload, API rejection (413 Payload Too Large).
