import React from 'react';

/**
 * Parses inline tokens:
 * - **bold** -> <strong>bold</strong>
 * - *italic* -> <em>italic</em>
 * - `code` -> <code className="inline-code">code</code>
 * Strips remaining unclosed asterisks so no stray * or ** is displayed.
 */
export function renderInlineMarkdown(text) {
  if (!text) return '';
  const parts = [];
  // Match **bold**, `code`, or *italic*
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let lastIndex = 0;
  let match;
  let keyIdx = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      // Clean any accidental stray asterisks in normal text
      const plain = text.substring(lastIndex, match.index).replace(/(?<!\w)\*+|\*+(?!\w)/g, '');
      if (plain) parts.push(plain);
    }
    const token = match[0];
    if (token.startsWith('**') && token.endsWith('**')) {
      const boldContent = token.slice(2, -2).trim();
      parts.push(<strong key={`b-${keyIdx++}`} className="md-bold">{boldContent}</strong>);
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(<code key={`c-${keyIdx++}`} className="inline-code">{token.slice(1, -1)}</code>);
    } else if (token.startsWith('*') && token.endsWith('*')) {
      const italicContent = token.slice(1, -1).trim();
      parts.push(<em key={`i-${keyIdx++}`} className="md-italic">{italicContent}</em>);
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    const remaining = text.substring(lastIndex).replace(/(?<!\w)\*+|\*+(?!\w)/g, '');
    if (remaining) parts.push(remaining);
  }

  return parts.length > 0 ? parts : text.replace(/(?<!\w)\*+|\*+(?!\w)/g, '');
}

/**
 * Reusable full Markdown renderer for both Chat messages and Artifacts
 */
export default function MarkdownRenderer({ content, className = '' }) {
  if (!content) return null;

  const lines = content.split('\n');
  const elements = [];
  let inCodeBlock = false;
  let codeBlockLines = [];
  let codeBlockLang = '';
  let currentList = [];
  let listType = null; // 'ul' | 'ol'
  let keyCounter = 0;

  const flushList = () => {
    if (currentList.length > 0) {
      if (listType === 'ol') {
        elements.push(
          <ol key={`ol-${keyCounter++}`} className="md-ol">
            {currentList.map((item, i) => (
              <li key={i} className="md-ol-item" value={item.number}>
                {renderInlineMarkdown(item.text)}
              </li>
            ))}
          </ol>
        );
      } else {
        elements.push(
          <ul key={`ul-${keyCounter++}`} className="md-ul">
            {currentList.map((item, i) => (
              <li key={i} className={item.isChecklist ? 'md-checklist-item' : 'md-ul-item'}>
                {item.isChecklist ? (
                  <label className="checkbox-label">
                    <input type="checkbox" checked={item.checked} readOnly />
                    <span>{renderInlineMarkdown(item.text)}</span>
                  </label>
                ) : (
                  renderInlineMarkdown(item.text)
                )}
              </li>
            ))}
          </ul>
        );
      }
      currentList = [];
      listType = null;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code blocks
    if (line.trim().startsWith('```')) {
      flushList();
      if (inCodeBlock) {
        elements.push(
          <div key={`codeblock-${keyCounter++}`} className="md-code-block-wrapper">
            {codeBlockLang && <div className="code-lang-tag">{codeBlockLang}</div>}
            <pre className="md-code-block">
              <code>{codeBlockLines.join('\n')}</code>
            </pre>
          </div>
        );
        inCodeBlock = false;
        codeBlockLines = [];
        codeBlockLang = '';
      } else {
        inCodeBlock = true;
        codeBlockLang = line.trim().slice(3).trim();
      }
      continue;
    }

    if (inCodeBlock) {
      codeBlockLines.push(line);
      continue;
    }

    // Horizontal Rule
    if (/^---+$|^\*\*\*+$/.test(line.trim())) {
      flushList();
      elements.push(<hr key={`hr-${keyCounter++}`} className="md-divider" />);
      continue;
    }

    // Headings
    if (line.startsWith('# ')) {
      flushList();
      elements.push(<h1 key={`h1-${keyCounter++}`} className="md-h1">{renderInlineMarkdown(line.slice(2))}</h1>);
      continue;
    }
    if (line.startsWith('## ')) {
      flushList();
      elements.push(<h2 key={`h2-${keyCounter++}`} className="md-h2">{renderInlineMarkdown(line.slice(3))}</h2>);
      continue;
    }
    if (line.startsWith('### ')) {
      flushList();
      elements.push(<h3 key={`h3-${keyCounter++}`} className="md-h3">{renderInlineMarkdown(line.slice(4))}</h3>);
      continue;
    }
    if (line.startsWith('#### ')) {
      flushList();
      elements.push(<h4 key={`h4-${keyCounter++}`} className="md-h4">{renderInlineMarkdown(line.slice(5))}</h4>);
      continue;
    }

    // Blockquote
    if (line.startsWith('> ')) {
      flushList();
      elements.push(
        <blockquote key={`bq-${keyCounter++}`} className="md-blockquote">
          {renderInlineMarkdown(line.slice(2))}
        </blockquote>
      );
      continue;
    }

    // Ordered list item (e.g. 1. **Title**: desc)
    const orderedMatch = line.match(/^(\d+)\.\s+(.*)$/);
    if (orderedMatch) {
      if (listType !== 'ol') {
        flushList();
        listType = 'ol';
      }
      currentList.push({
        number: parseInt(orderedMatch[1], 10),
        text: orderedMatch[2]
      });
      continue;
    }

    // Checklist items: - [ ] or - [x]
    const checklistMatch = line.match(/^[-*]\s+\[([ xX])\]\s+(.*)$/);
    if (checklistMatch) {
      if (listType !== 'ul') {
        flushList();
        listType = 'ul';
      }
      currentList.push({
        isChecklist: true,
        checked: checklistMatch[1].toLowerCase() === 'x',
        text: checklistMatch[2]
      });
      continue;
    }

    // Bullet items: - item or * item
    const bulletMatch = line.match(/^[-*]\s+(.*)$/);
    if (bulletMatch) {
      if (listType !== 'ul') {
        flushList();
        listType = 'ul';
      }
      currentList.push({
        isChecklist: false,
        text: bulletMatch[1]
      });
      continue;
    }

    // Empty lines flush lists
    if (!line.trim()) {
      flushList();
      continue;
    }

    // Standard paragraph
    flushList();
    elements.push(<p key={`p-${keyCounter++}`} className="md-p">{renderInlineMarkdown(line)}</p>);
  }

  flushList();

  return <div className={`markdown-render-flow ${className}`}>{elements}</div>;
}
