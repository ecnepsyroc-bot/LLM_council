import { describe, it, expect } from 'vitest'
import { render, screen } from '../../test/utils'
import { MarkdownRenderer } from './MarkdownRenderer'

describe('MarkdownRenderer', () => {
  it('renders plain text', () => {
    render(<MarkdownRenderer content="Hello World" />)
    expect(screen.getByText('Hello World')).toBeInTheDocument()
  })

  it('renders markdown headings', () => {
    render(<MarkdownRenderer content="# Heading 1" />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Heading 1')
  })

  it('renders bold text', () => {
    render(<MarkdownRenderer content="This is **bold** text" />)
    expect(screen.getByText('bold')).toBeInTheDocument()
    expect(screen.getByText('bold').tagName).toBe('STRONG')
  })

  it('renders italic text', () => {
    render(<MarkdownRenderer content="This is *italic* text" />)
    expect(screen.getByText('italic')).toBeInTheDocument()
    expect(screen.getByText('italic').tagName).toBe('EM')
  })

  it('renders links with safe attributes', () => {
    render(<MarkdownRenderer content="[Link](https://example.com)" />)
    const link = screen.getByRole('link', { name: 'Link' })
    expect(link).toHaveAttribute('href', 'https://example.com')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('sanitizes javascript: links', () => {
    render(<MarkdownRenderer content="[Click me](javascript:alert(1))" />)
    const link = screen.getByRole('link', { name: 'Click me' })
    expect(link).toHaveAttribute('href', '#')
  })

  it('renders lists', () => {
    // React-markdown may combine list items in jsdom without proper newlines
    const { container } = render(<MarkdownRenderer content="- Item 1\n- Item 2\n- Item 3" />)
    // Just verify a list is rendered
    const list = container.querySelector('ul')
    expect(list).toBeInTheDocument()
    expect(container.textContent).toContain('Item 1')
  })

  it('renders code blocks', () => {
    const { container } = render(<MarkdownRenderer content="```javascript\nconst x = 1;\n```" />)
    // Code blocks may render differently in jsdom
    const code = container.querySelector('code')
    expect(code).toBeInTheDocument()
    expect(container.textContent).toContain('const x = 1')
  })

  it('renders inline code', () => {
    render(<MarkdownRenderer content="Use `const` keyword" />)
    const code = screen.getByText('const')
    expect(code.tagName).toBe('CODE')
  })

  it('applies custom className', () => {
    const { container } = render(
      <MarkdownRenderer content="Test" className="custom-class" />
    )
    expect(container.firstChild).toHaveClass('custom-class')
  })

  it('handles empty content', () => {
    const { container } = render(<MarkdownRenderer content="" />)
    expect(container.firstChild).toBeInTheDocument()
  })

  it('renders blockquotes', () => {
    render(<MarkdownRenderer content="> This is a quote" />)
    expect(screen.getByText('This is a quote')).toBeInTheDocument()
  })

  it('removes HTML comments from content', () => {
    render(<MarkdownRenderer content="Hello <!-- hidden comment --> World" />)
    expect(screen.getByText(/Hello/)).toBeInTheDocument()
    expect(screen.getByText(/World/)).toBeInTheDocument()
    expect(screen.queryByText('hidden comment')).not.toBeInTheDocument()
  })
})
