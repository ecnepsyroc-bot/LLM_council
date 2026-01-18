import { describe, it, expect } from 'vitest'
import { render, screen } from '../../test/utils'
import { ProgressTimeline, MiniProgressIndicator } from './ProgressTimeline'

describe('ProgressTimeline', () => {
  describe('default view', () => {
    it('renders all three stages', () => {
      render(
        <ProgressTimeline
          currentStage={0}
          stage1Complete={false}
          stage2Complete={false}
          stage3Complete={false}
        />
      )

      expect(screen.getByText('Responses')).toBeInTheDocument()
      expect(screen.getByText('Rankings')).toBeInTheDocument()
      expect(screen.getByText('Synthesis')).toBeInTheDocument()
    })

    it('shows pending state when no stage is active', () => {
      const { container } = render(
        <ProgressTimeline
          currentStage={0}
          stage1Complete={false}
          stage2Complete={false}
          stage3Complete={false}
        />
      )

      // All stages should be in pending state (gray colors)
      const stageLabels = container.querySelectorAll('.text-gray-500')
      expect(stageLabels.length).toBeGreaterThan(0)
    })

    it('shows active state for current stage', () => {
      render(
        <ProgressTimeline
          currentStage={1}
          stage1Complete={false}
          stage2Complete={false}
          stage3Complete={false}
        />
      )

      // Stage 1 should have active styling
      const responsesLabel = screen.getByText('Responses')
      expect(responsesLabel.className).toContain('text-blue')
    })

    it('shows complete state for finished stages', () => {
      render(
        <ProgressTimeline
          currentStage={2}
          stage1Complete={true}
          stage2Complete={false}
          stage3Complete={false}
        />
      )

      // Stage 1 should be complete, stage 2 active
      const responsesLabel = screen.getByText('Responses')
      const rankingsLabel = screen.getByText('Rankings')

      expect(responsesLabel.className).toContain('text-blue')
      expect(rankingsLabel.className).toContain('text-purple')
    })

    it('shows all stages complete when finished', () => {
      render(
        <ProgressTimeline
          currentStage={0}
          stage1Complete={true}
          stage2Complete={true}
          stage3Complete={true}
        />
      )

      // All stages should show completion
      expect(screen.getByText('Responses').className).toContain('text-blue')
      expect(screen.getByText('Rankings').className).toContain('text-purple')
      expect(screen.getByText('Synthesis').className).toContain('text-green')
    })
  })

  describe('compact view', () => {
    it('renders compact version when compact prop is true', () => {
      const { container } = render(
        <ProgressTimeline
          currentStage={1}
          stage1Complete={false}
          stage2Complete={false}
          stage3Complete={false}
          compact
        />
      )

      // Compact view doesn't show stage names, just icons
      expect(screen.queryByText('Responses')).not.toBeInTheDocument()

      // Should have the compact container class
      expect(container.querySelector('.flex.items-center.gap-1')).toBeInTheDocument()
    })

    it('shows title attributes in compact mode', () => {
      const { container } = render(
        <ProgressTimeline
          currentStage={1}
          stage1Complete={false}
          stage2Complete={false}
          stage3Complete={false}
          compact
        />
      )

      // Compact icons should have title attributes
      const icons = container.querySelectorAll('[title]')
      expect(icons.length).toBe(3)
    })
  })
})

describe('MiniProgressIndicator', () => {
  it('returns null when no activity', () => {
    const { container } = render(
      <MiniProgressIndicator
        currentStage={0}
        stage1Complete={false}
        stage2Complete={false}
        stage3Complete={false}
      />
    )

    expect(container.firstChild).toBeNull()
  })

  it('renders when stage 1 is active', () => {
    const { container } = render(
      <MiniProgressIndicator
        currentStage={1}
        stage1Complete={false}
        stage2Complete={false}
        stage3Complete={false}
      />
    )

    expect(container.firstChild).not.toBeNull()
    // Should have 3 dots
    const dots = container.querySelectorAll('.w-2.h-2.rounded-full')
    expect(dots.length).toBe(3)
  })

  it('renders when stages are complete', () => {
    const { container } = render(
      <MiniProgressIndicator
        currentStage={0}
        stage1Complete={true}
        stage2Complete={false}
        stage3Complete={false}
      />
    )

    expect(container.firstChild).not.toBeNull()
  })

  it('shows appropriate colors for different stages', () => {
    const { container } = render(
      <MiniProgressIndicator
        currentStage={2}
        stage1Complete={true}
        stage2Complete={false}
        stage3Complete={false}
      />
    )

    const dots = container.querySelectorAll('.w-2.h-2.rounded-full')
    expect(dots.length).toBe(3)

    // First dot should be complete (blue)
    expect(dots[0].className).toContain('bg-blue')

    // Second dot should be active (purple)
    expect(dots[1].className).toContain('bg-purple')

    // Third dot should be pending (gray)
    expect(dots[2].className).toContain('bg-gray')
  })

  it('shows title attributes on dots', () => {
    const { container } = render(
      <MiniProgressIndicator
        currentStage={1}
        stage1Complete={false}
        stage2Complete={false}
        stage3Complete={false}
      />
    )

    const dots = container.querySelectorAll('[title]')
    expect(dots.length).toBe(3)
    expect(dots[0].getAttribute('title')).toContain('Responses')
    expect(dots[1].getAttribute('title')).toContain('Rankings')
    expect(dots[2].getAttribute('title')).toContain('Synthesis')
  })
})
