/**
 * Frontend sanitization utilities for XSS protection.
 */

/**
 * Escape HTML entities to prevent XSS in text contexts.
 */
export function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  };
  return text.replace(/[&<>"']/g, (char) => map[char]);
}

/**
 * Validate that a string is a valid base64-encoded image.
 */
export function isValidBase64Image(data: string): boolean {
  const pattern = /^data:image\/(png|jpeg|jpg|gif|webp);base64,[A-Za-z0-9+/=]+$/;
  return pattern.test(data);
}

/**
 * Sanitize a URL to prevent javascript: and malicious data: URLs.
 * Returns '#' for potentially dangerous URLs.
 */
export function sanitizeUrl(url: string): string {
  if (!url) return '#';

  const trimmed = url.trim().toLowerCase();

  // Block javascript: URLs
  if (trimmed.startsWith('javascript:')) {
    return '#';
  }

  // Block data: URLs except for images
  if (trimmed.startsWith('data:') && !trimmed.startsWith('data:image/')) {
    return '#';
  }

  // Block vbscript: URLs (IE legacy)
  if (trimmed.startsWith('vbscript:')) {
    return '#';
  }

  return url;
}

/**
 * Sanitize markdown content to remove potentially dangerous elements.
 */
export function sanitizeMarkdown(markdown: string): string {
  if (!markdown) return '';

  let clean = markdown;

  // Remove HTML comments (can hide malicious content)
  clean = clean.replace(/<!--[\s\S]*?-->/g, '');

  // Remove javascript: links in markdown format
  clean = clean.replace(/\[([^\]]*)\]\(javascript:[^)]*\)/gi, '[$1](#)');

  // Remove vbscript: links
  clean = clean.replace(/\[([^\]]*)\]\(vbscript:[^)]*\)/gi, '[$1](#)');

  // Remove data: links except for images
  clean = clean.replace(/\[([^\]]*)\]\(data:(?!image\/)[^)]*\)/gi, '[$1](#)');

  // Remove on* event handlers that might slip through in raw HTML
  clean = clean.replace(/\s+on\w+\s*=\s*["'][^"']*["']/gi, '');

  return clean;
}

/**
 * Truncate text to a maximum length with ellipsis.
 */
export function truncate(text: string, maxLength: number): string {
  if (!text || text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + '...';
}

/**
 * Check if a string looks like it might contain HTML.
 */
export function containsHtml(text: string): boolean {
  return /<[a-z][\s\S]*>/i.test(text);
}
