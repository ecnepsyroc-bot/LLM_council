import { describe, it, expect } from 'vitest'
import {
  escapeHtml,
  isValidBase64Image,
  sanitizeUrl,
  sanitizeMarkdown,
  truncate,
  containsHtml,
} from './sanitize'

describe('escapeHtml', () => {
  it('escapes HTML special characters', () => {
    expect(escapeHtml('<script>alert("xss")</script>')).toBe(
      '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'
    )
  })

  it('escapes ampersands', () => {
    expect(escapeHtml('Tom & Jerry')).toBe('Tom &amp; Jerry')
  })

  it('escapes single quotes', () => {
    expect(escapeHtml("it's")).toBe('it&#039;s')
  })

  it('handles empty string', () => {
    expect(escapeHtml('')).toBe('')
  })

  it('leaves safe text unchanged', () => {
    expect(escapeHtml('Hello World')).toBe('Hello World')
  })
})

describe('isValidBase64Image', () => {
  it('accepts valid PNG base64', () => {
    expect(isValidBase64Image('data:image/png;base64,iVBORw0KGgo=')).toBe(true)
  })

  it('accepts valid JPEG base64', () => {
    expect(isValidBase64Image('data:image/jpeg;base64,/9j/4AAQSkZJRg==')).toBe(true)
  })

  it('accepts valid GIF base64', () => {
    expect(isValidBase64Image('data:image/gif;base64,R0lGODlh')).toBe(true)
  })

  it('rejects non-image data URLs', () => {
    expect(isValidBase64Image('data:text/html;base64,PHNjcmlwdD4=')).toBe(false)
  })

  it('rejects malformed data URLs', () => {
    expect(isValidBase64Image('data:image/png;notbase64,abc')).toBe(false)
  })

  it('rejects regular URLs', () => {
    expect(isValidBase64Image('https://example.com/image.png')).toBe(false)
  })
})

describe('sanitizeUrl', () => {
  it('allows safe HTTP URLs', () => {
    expect(sanitizeUrl('https://example.com')).toBe('https://example.com')
  })

  it('blocks javascript: URLs', () => {
    expect(sanitizeUrl('javascript:alert(1)')).toBe('#')
  })

  it('blocks javascript: URLs with case variations', () => {
    expect(sanitizeUrl('JAVASCRIPT:alert(1)')).toBe('#')
    expect(sanitizeUrl('JavaScript:alert(1)')).toBe('#')
  })

  it('blocks vbscript: URLs', () => {
    expect(sanitizeUrl('vbscript:msgbox(1)')).toBe('#')
  })

  it('blocks non-image data: URLs', () => {
    expect(sanitizeUrl('data:text/html,<script>alert(1)</script>')).toBe('#')
  })

  it('allows image data: URLs', () => {
    expect(sanitizeUrl('data:image/png;base64,abc')).toBe('data:image/png;base64,abc')
  })

  it('returns # for empty URL', () => {
    expect(sanitizeUrl('')).toBe('#')
  })

  it('handles URLs with whitespace', () => {
    expect(sanitizeUrl('  javascript:alert(1)  ')).toBe('#')
  })
})

describe('sanitizeMarkdown', () => {
  it('removes HTML comments', () => {
    expect(sanitizeMarkdown('Hello <!-- hidden --> World')).toBe('Hello  World')
  })

  it('removes javascript: links in markdown', () => {
    const result = sanitizeMarkdown('[Click me](javascript:alert(1))')
    // Should replace the malicious URL with #
    expect(result).toContain('[Click me](#)')
  })

  it('removes vbscript: links', () => {
    const result = sanitizeMarkdown('[Click](vbscript:msgbox(1))')
    // Should replace the malicious URL with #
    expect(result).toContain('[Click](#)')
  })

  it('removes non-image data: links', () => {
    const result = sanitizeMarkdown('[Link](data:text/plain,hello)')
    // Should replace non-image data URLs with #
    expect(result).toContain('[Link](#)')
  })

  it('preserves image data: links', () => {
    const md = '[Image](data:image/png;base64,abc)'
    expect(sanitizeMarkdown(md)).toBe(md)
  })

  it('removes event handlers', () => {
    expect(sanitizeMarkdown('<div onclick="alert(1)">text</div>')).toBe('<div>text</div>')
  })

  it('handles empty input', () => {
    expect(sanitizeMarkdown('')).toBe('')
  })

  it('preserves safe markdown', () => {
    const md = '# Hello\n\n**Bold** and *italic*'
    expect(sanitizeMarkdown(md)).toBe(md)
  })
})

describe('truncate', () => {
  it('truncates long text with ellipsis', () => {
    expect(truncate('Hello World', 8)).toBe('Hello...')
  })

  it('leaves short text unchanged', () => {
    expect(truncate('Hi', 10)).toBe('Hi')
  })

  it('handles exact length', () => {
    expect(truncate('Hello', 5)).toBe('Hello')
  })

  it('handles empty string', () => {
    expect(truncate('', 10)).toBe('')
  })
})

describe('containsHtml', () => {
  it('detects HTML tags', () => {
    expect(containsHtml('<div>text</div>')).toBe(true)
  })

  it('detects script tags', () => {
    expect(containsHtml('<script>alert(1)</script>')).toBe(true)
  })

  it('returns false for plain text', () => {
    expect(containsHtml('Hello World')).toBe(false)
  })

  it('returns false for markdown', () => {
    expect(containsHtml('**bold** and *italic*')).toBe(false)
  })

  it('handles angle brackets in text', () => {
    expect(containsHtml('1 < 2 and 3 > 2')).toBe(false)
  })
})
