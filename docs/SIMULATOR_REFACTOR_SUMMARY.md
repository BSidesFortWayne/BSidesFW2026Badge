# Simulator Refactor - Executive Summary

**Date:** January 6, 2026  
**Status:** Design Complete, Ready to Implement

---

## Problem Statement

The BSides FW 2025 Badge Simulator currently has critical issues:

1. **Crashes on startup** - KeyError: 'module' when processing commands
2. **Inconsistent code** - Multiple GUI files with overlapping functionality
3. **Mixed protocols** - Confusion between old (`module/parameters`) and new (`device/command`) JSON formats
4. **Poor error handling** - Silent failures and unclear error messages

**Impact:** Developers cannot reliably test badge apps, slowing development

---

## Solution Overview

We've created a **comprehensive design document** that establishes:

1. **Unified Architecture** - Single source of truth for all simulator components
2. **Clear Protocol Separation** - Binary for graphics, JSON for control
3. **Robust Error Handling** - No more silent crashes
4. **Performance Targets** - Sub-10ms rendering for smooth 60 FPS

---

## Documents Created

### 1. [SIMULATOR_DESIGN.md](./SIMULATOR_DESIGN.md)

**Purpose:** Complete architectural design specification

**Contents:**
- Architecture diagrams
- Protocol specifications (binary + JSON)
- Component responsibilities
- File organization
- Error handling patterns
- Performance targets
- Configuration schema
- Testing strategy

**Key Sections:**
- Protocol Design (pages 3-6)
- GUI Architecture (pages 7-9)
- Hardware Shim Pattern (pages 10-12)
- Error Handling (page 13)

### 2. [SIMULATOR_IMPLEMENTATION_PLAN.md](./SIMULATOR_IMPLEMENTATION_PLAN.md)

**Purpose:** Step-by-step implementation guide

**Contents:**
- 6 implementation phases
- Specific code changes for each file
- Validation steps after each change
- Test suite creation
- Rollback procedures
- Time estimates (12 hours total)

**Key Phases:**
1. Fix Critical Issues (JSON protocol, error handling)
2. Code Consolidation (merge duplicate GUI files)
3. Documentation Updates
4. Testing
5. Performance Validation
6. Real-World Testing

---

## Key Design Decisions

### 1. Protocol Standardization

**Decision:** Use `device/command` structure (not `module/parameters`)

**Rationale:**
- More consistent with industry standards
- Clearer separation of concerns
- Easier to extend

**Impact:** All JSON commands must be updated

### 2. Single GUI File

**Decision:** Consolidate `gui.py`, `gui_enhanced.py`, `gui_binary.py` → single `gui.py`

**Rationale:**
- Eliminates confusion about which file is authoritative
- Easier to maintain
- Clearer architecture

**Impact:** Must carefully merge functionality

### 3. Binary Protocol for Graphics

**Decision:** All high-throughput graphics operations use binary protocol

**Rationale:**
- 10-20x faster than JSON
- Essential for smooth animations
- Already implemented

**Impact:** No changes needed, already optimal

### 4. Backwards Compatibility

**Decision:** Support both old and new JSON formats during transition

**Rationale:**
- Minimize disruption
- Allow gradual migration
- Easy to test

**Impact:** Validation logic checks for both `device` and `module` keys

---

## Implementation Priority

### Phase 1: Critical (Do First) ✓

**Goal:** Stop crashes, enable development

**Tasks:**
1. Fix JSON protocol inconsistency (Step 1.1)
2. Add error handling to all command handlers (Step 1.1)
3. Update emulator.py with response validation (Step 1.2)
4. Update shim libraries (Step 1.3)

**Time:** 4 hours  
**Validation:** Simulator boots without errors

### Phase 2: Consolidation (Do Second) ✓

**Goal:** Clean up code structure

**Tasks:**
1. Identify duplicate files (Step 2.1)
2. Merge into single gui.py (Step 2.2)
3. Update imports in simulator.py (Step 2.3)

**Time:** 3 hours  
**Validation:** All badge apps work unchanged

### Phase 3: Testing & Documentation (Do Third) ✓

**Goal:** Ensure stability and maintainability

**Tasks:**
1. Create test suite (Step 4)
2. Run performance benchmarks (Step 5)
3. Update documentation (Step 3)
4. Real-world testing with badge apps (Step 6)

**Time:** 5 hours  
**Validation:** 100% test pass rate, performance targets met

---

## Success Criteria

### Must Have (Minimum Viable)

- [x] Design document complete
- [x] Implementation plan with step-by-step instructions
- [ ] Simulator boots without errors
- [ ] No KeyError crashes
- [ ] All existing badge apps work
- [ ] Performance: blit_buffer < 20ms

### Should Have (Target)

- [ ] Single GUI file (no duplication)
- [ ] Consistent JSON protocol
- [ ] Clear error messages in logs
- [ ] Performance: blit_buffer < 10ms
- [ ] LED rendering visible
- [ ] Test suite passing

### Nice to Have (Future)

- [ ] Hot reload on code changes
- [ ] Interactive debugger
- [ ] Recording/playback capability

---

## Risk Assessment

### High Risk ✗

**Risk:** Merging GUI files causes regression  
**Mitigation:** Validate after each step, keep backups, rollback plan ready

**Risk:** Protocol changes break existing apps  
**Mitigation:** Support both old and new formats, gradual migration

### Medium Risk ⚠

**Risk:** Performance regressions  
**Mitigation:** Benchmark before/after, optimize hot paths

**Risk:** Incomplete error handling  
**Mitigation:** Add tests for error cases, validate with real apps

### Low Risk ✓

**Risk:** Documentation out of date  
**Mitigation:** Update docs as part of implementation

---

## Timeline

| Week | Focus | Deliverables |
|------|-------|--------------|
| Week 1 | Phase 1: Critical Fixes | Stable simulator, no crashes |
| Week 1 | Phase 2: Consolidation | Single GUI file, clean structure |
| Week 2 | Phase 3: Testing | Test suite, performance validation |
| Week 2 | Documentation | Updated README, user guides |

**Total Time:** ~2 weeks (12 hours implementation + review/testing)

---

## Communication Plan

### Stakeholders

- **Badge App Developers** - Need stable simulator ASAP
- **Simulator Maintainers** - Need clear architecture
- **Documentation Team** - Need updated guides

### Updates

1. **Daily:** Status in team chat (#simulator channel)
2. **After Each Phase:** Demo + validation results
3. **Final:** Full walkthrough of new architecture

---

## Next Actions

### Immediate (Today)

1. ✅ Review design document
2. ✅ Review implementation plan
3. [ ] Get team approval
4. [ ] Create Git branch: `simulator-refactor`

### Tomorrow

1. [ ] Begin Phase 1, Step 1.1
2. [ ] Test after each change
3. [ ] Commit working increments

### End of Week

1. [ ] Complete Phase 1 & 2
2. [ ] Validate with all badge apps
3. [ ] Demo to team

---

## How to Get Started

```bash
# 1. Review the documents
cat docs/SIMULATOR_DESIGN.md
cat docs/SIMULATOR_IMPLEMENTATION_PLAN.md

# 2. Create working branch
git checkout -b simulator-refactor

# 3. Start with Step 1.1
# Edit simulator/gui.py - add error handling to handle_command()

# 4. Test after each change
uv run simulator/run.sh -v

# 5. Commit working increments
git add simulator/gui.py
git commit -m "Phase 1.1: Add JSON protocol error handling"
```

---

## Questions & Answers

**Q: Will this break existing badge apps?**  
A: No. We support both old and new JSON formats for backwards compatibility.

**Q: How long will this take?**  
A: ~12 hours of implementation + ~12 hours of testing = ~2 weeks part-time.

**Q: What if we find a critical bug?**  
A: Each step has validation. We can rollback to last working commit.

**Q: Do we need to update all shim libraries?**  
A: Only for response validation (Step 1.3). Most shims work as-is.

**Q: What about new features?**  
A: This is stabilization only. New features come after refactor is complete.

---

## References

- [SIMULATOR_DESIGN.md](./SIMULATOR_DESIGN.md) - Complete architecture
- [SIMULATOR_IMPLEMENTATION_PLAN.md](./SIMULATOR_IMPLEMENTATION_PLAN.md) - Step-by-step guide
- [SIMULATOR_ARCHITECTURE.md](./SIMULATOR_ARCHITECTURE.md) - Original architecture (outdated)
- [SIMULATOR_README.md](./SIMULATOR_README.md) - User guide

---

## Approval Sign-off

- [ ] Technical Lead - Design Review
- [ ] Project Manager - Timeline Approval
- [ ] QA Lead - Testing Strategy
- [ ] Badge App Team - Impact Assessment

**Approved by:** ___________________  
**Date:** ___________________

---

**Status: READY TO IMPLEMENT** 🚀

All design work is complete. Implementation can begin immediately.
