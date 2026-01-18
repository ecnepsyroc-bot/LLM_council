import ReactMarkdown from 'react-markdown';
import DOMPurify from 'dompurify';
import { CodeBlock } from './CodeBlock';
import { sanitizeMarkdown, sanitizeUrl } from '../../utils/sanitize';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  // Pre-sanitize markdown before rendering
  const sanitizedContent = sanitizeMarkdown(content);

  return (
    <div className={className}>
      <ReactMarkdown
        components={{
          code(props) {
            const { children, className: codeClassName, node, ...rest } = props;
            const match = /language-(\w+)/.exec(codeClassName || '');
            return match ? (
              <CodeBlock
                language={match[1]}
                value={String(children).replace(/\n$/, '')}
              />
            ) : (
              <code className={codeClassName} {...rest}>
                {children}
              </code>
            );
          },
          // Sanitize links to prevent javascript: URLs
          a({ href, children, ...props }) {
            const safeHref = sanitizeUrl(href || '');
            return (
              <a
                href={safeHref}
                target="_blank"
                rel="noopener noreferrer"
                {...props}
              >
                {children}
              </a>
            );
          },
          // Sanitize image sources
          img({ src, alt, ...props }) {
            if (!src) return null;
            // Use DOMPurify for additional sanitization
            const safeSrc = DOMPurify.sanitize(src);
            return (
              <img
                src={safeSrc}
                alt={alt || ''}
                loading="lazy"
                {...props}
              />
            );
          },
        }}
      >
        {sanitizedContent}
      </ReactMarkdown>
    </div>
  );
}
