# Domain: DSP & Audio Processing

## Real-Time Constraints
- [ ] Audio callback must complete within buffer period
- [ ] No memory allocation in audio thread
- [ ] No blocking calls in audio path
- [ ] No logging/printf in real-time code
- [ ] Lock-free data structures for audio thread communication

## Numerical Stability
- [ ] Fixed-point vs floating-point choice documented
- [ ] Overflow/underflow handling defined
- [ ] Saturation arithmetic where appropriate
- [ ] Filter stability verified (pole locations)
- [ ] Denormal handling (flush to zero)

## Audio Quality
- [ ] Sample rate conversions use proper interpolation
- [ ] Anti-aliasing filters where needed
- [ ] Latency budget documented
- [ ] Click/pop prevention on parameter changes (smoothing)
- [ ] Proper gain staging (headroom management)

## DSP Patterns
- [ ] Circular buffers for delay lines
- [ ] SIMD optimization where applicable
- [ ] Lookup tables for expensive functions (sin, log)
- [ ] Double-buffering for DMA transfers

## Testing
- [ ] Unit tests with known input/output pairs
- [ ] Impulse response verification
- [ ] THD+N measurements for audio quality
- [ ] CPU load profiling under worst-case conditions
