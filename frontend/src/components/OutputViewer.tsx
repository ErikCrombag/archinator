import { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { previewPlantuml } from '../api';
import type { OutputFormat } from '../types';

interface OutputViewerProps {
  format: OutputFormat;
  content: string;
}

let mermaidCounter = 0;

export function OutputViewer({ format, content }: OutputViewerProps) {
  const [copied, setCopied] = useState(false);
  const [svgContent, setSvgContent] = useState<string>('');
  const [renderError, setRenderError] = useState<string>('');
  const idRef = useRef<string>(`mermaid-${++mermaidCounter}`);

  // Mermaid: render client-side
  useEffect(() => {
    if (format !== 'mermaid') return;
    let cancelled = false;

    async function render() {
      try {
        const { svg } = await mermaid.render(idRef.current, content);
        if (!cancelled) {
          setSvgContent(svg);
          setRenderError('');
        }
      } catch (err) {
        if (!cancelled) {
          setRenderError(err instanceof Error ? err.message : String(err));
          setSvgContent('');
        }
      }
    }

    render();
    return () => { cancelled = true; };
  }, [format, content]);

  // PlantUML: proxy through backend → kroki.io (avoids browser CORS restriction)
  useEffect(() => {
    if (format !== 'plantuml' || !content) return;
    let cancelled = false;

    setSvgContent('');
    setRenderError('');

    previewPlantuml(content)
      .then(svg => { if (!cancelled) setSvgContent(svg); })
      .catch(err => { if (!cancelled) setRenderError(err instanceof Error ? err.message : String(err)); });

    return () => { cancelled = true; };
  }, [format, content]);

  function handleCopy() {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const languageLabel: Partial<Record<OutputFormat, string>> = {
    mermaid: 'mermaid',
    plantuml: 'plantuml',
    exchange_xml: 'xml',
    json: 'json',
  };

  return (
    <div className="space-y-4">
      {/* Code block */}
      <div className="relative">
        <div className="absolute right-2 top-2 z-10">
          <button
            onClick={handleCopy}
            className="rounded bg-gray-700 px-2 py-1 text-xs text-gray-300 hover:bg-gray-600 hover:text-gray-100 transition-colors"
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>
        <div className="mb-1 px-1 font-mono text-xs text-gray-500">
          {languageLabel[format] ?? format}
        </div>
        <pre className="max-h-96 overflow-auto rounded border border-gray-700 bg-gray-950 p-4 font-mono text-xs text-gray-200 leading-relaxed whitespace-pre">
          <code>{content}</code>
        </pre>
      </div>

      {/* Mermaid preview — rendered client-side */}
      {format === 'mermaid' && (
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-gray-400">
            Diagram Preview
          </div>
          {renderError ? (
            <div className="rounded border border-red-700 bg-red-950/40 p-3 font-mono text-xs text-red-300 whitespace-pre-wrap">
              Mermaid render error: {renderError}
            </div>
          ) : svgContent ? (
            <div
              className="overflow-auto rounded border border-gray-600 bg-white p-4"
              dangerouslySetInnerHTML={{ __html: svgContent }}
            />
          ) : (
            <div className="flex h-24 items-center justify-center rounded border border-gray-700 bg-gray-900 text-xs text-gray-500">
              Rendering diagram…
            </div>
          )}
        </div>
      )}

      {/* PlantUML preview — POST to kroki.io, render inline SVG */}
      {format === 'plantuml' && content && (
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-gray-400">
            Diagram Preview
          </div>
          {renderError ? (
            <div className="rounded border border-red-700 bg-red-950/40 p-3 font-mono text-xs text-red-300 whitespace-pre-wrap">
              PlantUML render error: {renderError}
            </div>
          ) : svgContent ? (
            <div
              className="overflow-auto rounded border border-gray-600 bg-white p-4"
              dangerouslySetInnerHTML={{ __html: svgContent }}
            />
          ) : (
            <div className="flex h-24 items-center justify-center rounded border border-gray-700 bg-gray-900 text-xs text-gray-500">
              Rendering diagram…
            </div>
          )}
        </div>
      )}
    </div>
  );
}
