import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '../../test/utils'
import { CodeBlock } from './CodeBlock'

// Mock clipboard API
const mockClipboard = {
  writeText: vi.fn().mockResolvedValue(undefined),
}
Object.assign(navigator, { clipboard: mockClipboard })

describe('CodeBlock', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders code content', () => {
    render(<CodeBlock language="javascript" value="const x = 1;" />)
    expect(screen.getByText('const x = 1;')).toBeInTheDocument()
  })

  it('displays language label', () => {
    render(<CodeBlock language="python" value="print('hello')" />)
    expect(screen.getByText('python')).toBeInTheDocument()
  })

  it('displays "text" for empty language', () => {
    render(<CodeBlock language="" value="some code" />)
    expect(screen.getByText('text')).toBeInTheDocument()
  })

  it('renders copy button', () => {
    render(<CodeBlock language="javascript" value="code" />)
    expect(screen.getByTitle('Copy code')).toBeInTheDocument()
  })

  it('copies code to clipboard when copy button clicked', async () => {
    const code = 'const hello = "world";'
    render(<CodeBlock language="javascript" value={code} />)

    const copyButton = screen.getByTitle('Copy code')
    fireEvent.click(copyButton)

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(code)
  })

  it('shows check icon after copying', async () => {
    render(<CodeBlock language="javascript" value="code" />)

    const copyButton = screen.getByTitle('Copy code')
    fireEvent.click(copyButton)

    // The check icon should appear after copying
    await waitFor(() => {
      expect(copyButton.querySelector('svg')).toBeInTheDocument()
    })
  })

  it('renders multiline code', () => {
    const multilineCode = `function test() {
  return 42;
}`
    render(<CodeBlock language="javascript" value={multilineCode} />)
    expect(screen.getByText(/function test/)).toBeInTheDocument()
    expect(screen.getByText(/return 42/)).toBeInTheDocument()
  })

  it('handles special characters in code', () => {
    const codeWithSpecialChars = '<div class="test">&nbsp;</div>'
    render(<CodeBlock language="html" value={codeWithSpecialChars} />)
    expect(screen.getByText(/<div class="test">/)).toBeInTheDocument()
  })
})
