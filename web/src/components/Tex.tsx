import katex from "katex";
import "katex/dist/katex.min.css";

/** Typeset a LaTeX expression with KaTeX (HTML for display, MathML for screen readers). */
export function Tex({ children, block = false }: { children: string; block?: boolean }) {
  const html = katex.renderToString(children, {
    displayMode: block,
    fleqn: true, // block formulas align left, like the text around them
    throwOnError: false,
  });
  return <span className={block ? "block overflow-x-auto py-1" : undefined} dangerouslySetInnerHTML={{ __html: html }} />;
}
