// Platform primitive absent from the test DOM; real browser provides it.
if(!globalThis.ResizeObserver)globalThis.ResizeObserver=class {observe(){}unobserve(){}disconnect(){}}
