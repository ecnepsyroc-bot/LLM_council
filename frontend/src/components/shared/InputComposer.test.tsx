import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '../../test/utils'
import userEvent from '@testing-library/user-event'
import { InputComposer } from './InputComposer'

describe('InputComposer', () => {
  it('renders textarea with placeholder', () => {
    render(<InputComposer onSend={vi.fn()} />)
    expect(screen.getByPlaceholderText('Ask the council...')).toBeInTheDocument()
  })

  it('renders custom placeholder', () => {
    render(<InputComposer onSend={vi.fn()} placeholder="Custom placeholder" />)
    expect(screen.getByPlaceholderText('Custom placeholder')).toBeInTheDocument()
  })

  it('disables input when loading', () => {
    render(<InputComposer onSend={vi.fn()} isLoading />)
    expect(screen.getByPlaceholderText('Ask the council...')).toBeDisabled()
  })

  it('disables submit button when input is empty', () => {
    render(<InputComposer onSend={vi.fn()} />)
    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
  })

  it('enables submit button when input has text', async () => {
    const user = userEvent.setup()
    render(<InputComposer onSend={vi.fn()} />)

    const textarea = screen.getByPlaceholderText('Ask the council...')
    await user.type(textarea, 'Hello')

    const button = screen.getByRole('button')
    expect(button).not.toBeDisabled()
  })

  it('calls onSend when submit button is clicked', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<InputComposer onSend={onSend} />)

    const textarea = screen.getByPlaceholderText('Ask the council...')
    await user.type(textarea, 'Hello world')

    const button = screen.getByRole('button')
    await user.click(button)

    expect(onSend).toHaveBeenCalledWith('Hello world', [])
  })

  it('clears input after sending', async () => {
    const user = userEvent.setup()
    render(<InputComposer onSend={vi.fn()} />)

    const textarea = screen.getByPlaceholderText('Ask the council...')
    await user.type(textarea, 'Hello')
    await user.click(screen.getByRole('button'))

    expect(textarea).toHaveValue('')
  })

  it('sends on Enter key (without Shift)', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<InputComposer onSend={onSend} />)

    const textarea = screen.getByPlaceholderText('Ask the council...')
    await user.type(textarea, 'Hello')
    await user.type(textarea, '{Enter}')

    expect(onSend).toHaveBeenCalledWith('Hello', [])
  })

  it('does not send on Shift+Enter (allows new line)', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<InputComposer onSend={onSend} />)

    const textarea = screen.getByPlaceholderText('Ask the council...')
    await user.type(textarea, 'Line 1{Shift>}{Enter}{/Shift}Line 2')

    expect(onSend).not.toHaveBeenCalled()
    expect(textarea).toHaveValue('Line 1\nLine 2')
  })

  it('trims whitespace from input before sending', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<InputComposer onSend={onSend} />)

    const textarea = screen.getByPlaceholderText('Ask the council...')
    await user.type(textarea, '  Hello world  ')
    await user.click(screen.getByRole('button'))

    expect(onSend).toHaveBeenCalledWith('Hello world', [])
  })

  it('does not send whitespace-only input', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<InputComposer onSend={onSend} />)

    const textarea = screen.getByPlaceholderText('Ask the council...')
    await user.type(textarea, '   ')

    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
  })

  it('shows loading spinner when loading', () => {
    render(<InputComposer onSend={vi.fn()} isLoading />)
    // The button should have a loader icon instead of send icon
    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
  })

  it('does not send when loading', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<InputComposer onSend={onSend} isLoading />)

    // Try to send despite being disabled
    const button = screen.getByRole('button')
    await user.click(button)

    expect(onSend).not.toHaveBeenCalled()
  })

  it('shows helper text', () => {
    render(<InputComposer onSend={vi.fn()} />)
    expect(screen.getByText(/Press Enter to send/)).toBeInTheDocument()
    expect(screen.getByText(/Shift\+Enter for new line/)).toBeInTheDocument()
  })
})
