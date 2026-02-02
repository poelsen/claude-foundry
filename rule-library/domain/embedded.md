# Domain: Embedded Systems

## Memory Safety
- [ ] Bounds checking on all array access
- [ ] No unbounded loops without timeout
- [ ] Stack usage analyzed (no deep recursion)
- [ ] Heap fragmentation considered (prefer static allocation)
- [ ] Buffer sizes explicitly defined and checked

## Resource Constraints
- [ ] RAM usage tracked and budgeted
- [ ] Flash/ROM usage monitored
- [ ] CPU cycles considered for real-time requirements
- [ ] Power consumption implications noted

## Reliability
- [ ] Watchdog timer integration
- [ ] Error recovery paths defined
- [ ] Graceful degradation on resource exhaustion
- [ ] No blocking calls in ISRs
- [ ] Interrupt latency considered

## Build & Debug
- [ ] Debug vs Release configs properly separated
- [ ] Debug interfaces disabled in production builds
- [ ] Assertions enabled in debug, compiled out in release
- [ ] Static analysis clean (no warnings)

## Hardware Interaction
- [ ] Volatile for hardware registers
- [ ] Memory barriers where needed
- [ ] Endianness handled explicitly
- [ ] Peripheral initialization order documented
