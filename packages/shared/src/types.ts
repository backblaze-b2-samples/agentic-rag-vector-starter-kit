export type FileStatus = "uploading" | "complete" | "error";

export interface FileMetadata {
  key: string;
  filename: string;
  folder: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
}

export interface FileMetadataDetail {
  filename: string;
  size_bytes: number;
  size_human: string;
  mime_type: string;
  extension: string;
  md5: string;
  sha256: string;
  uploaded_at: string;
  // Image-specific
  image_width: number | null;
  image_height: number | null;
  exif: Record<string, string> | null;
  // PDF-specific
  pdf_pages: number | null;
  pdf_author: string | null;
  pdf_title: string | null;
  // Audio/Video
  duration_seconds: number | null;
  codec: string | null;
  bitrate: number | null;
}

export interface FileUploadResponse {
  key: string;
  filename: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
  metadata: FileMetadataDetail | null;
}

export interface DailyUploadCount {
  date: string;
  uploads: number;
}

export interface UploadStats {
  total_files: number;
  total_size_bytes: number;
  total_size_human: string;
  uploads_today: number;
  total_downloads: number;
}

// --- Document processing types ---

export type DocumentStatus = "pending" | "processing" | "completed" | "failed";

export type DocumentClassification =
  | "policy"
  | "procedure"
  | "reference"
  | "tutorial"
  | "faq"
  | "troubleshooting"
  | "api_docs"
  | "general";

export interface DocumentChunk {
  chunk_id: string;
  doc_id: string;
  doc_title: string;
  section_path: string;
  text: string;
  summary: string;
  classification: DocumentClassification;
  chunk_index: number;
  total_chunks: number;
  source_filename: string;
  source_content_type: string;
  source_page: number | null;
  token_count: number;
  updated_at: string | null;
}

export interface ProcessingStatusResponse {
  doc_id: string;
  filename: string;
  status: DocumentStatus;
  chunk_count: number;
  classification: string;
  summary: string;
  error_message: string | null;
}

// --- Chat types ---

export type MessageRole = "user" | "assistant" | "system";

export interface Citation {
  index: number;
  doc_id: string;
  doc_title: string;
  section_path: string;
  source_filename: string;
  page: number | null;
  chunk_text: string;
  download_url: string | null;
}

export interface ChatMessage {
  role: MessageRole;
  content: string;
  citations: Citation[];
  timestamp: string | null;
}

export interface ChatRequest {
  message: string;
  conversation_id: string | null;
}

export interface ChatResponse {
  conversation_id: string;
  message: ChatMessage;
  retrieval_metadata: RetrievalInfo | null;
}

export interface RetrievalInfo {
  route: string;
  queries_generated: number;
  candidates_found: number;
  evidence_used: number;
  retrieval_loops: number;
  latency_ms: number;
}
