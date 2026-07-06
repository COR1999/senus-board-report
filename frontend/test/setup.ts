import '@testing-library/jest-dom'

// jsdom doesn't implement these; Radix UI's Select (and other popover-based
// primitives) call them internally, throwing without a stub. No-ops are
// sufficient since tests don't assert on actual scroll position/pointer capture.
if (typeof window !== 'undefined') {
  window.HTMLElement.prototype.scrollIntoView ??= () => {}
  window.HTMLElement.prototype.hasPointerCapture ??= () => false
  window.HTMLElement.prototype.releasePointerCapture ??= () => {}
}