// types/index.ts

export interface SearchResult {
  doc_id: string;
  chunk_text: string;
  score: number;
  book_title?: string;
  author?: string;
  chapter?: string;
  section?: string;
  page?: number;
  metadata?: Record<string, any>;
}

export interface SearchResponse {
  success: boolean;
  results: SearchResult[];
  total_found: number;
  search_time_ms: number;
  message?: string;
}

export interface BookInfo {
  doc_id: string;
  title: string;
  author?: string;
  isbn?: string;
  publisher?: string;
  publication_year?: number;
  category?: string;
  language?: string;
  description?: string;
  chunk_count?: number;
  page_count?: number;
}

export interface BooksResponse {
  success: boolean;
  data: BookInfo[];
  total: number;
  message?: string;
}

export interface UploadResponse {
  success: boolean;
  message: string;
  doc_id?: string;
}
