# Plan 007: Backup API and Simple Stage Logging

**Date:** 2025-11-01
**Status:** Planning
**Issue:** Need backup LLM API for reliability and simple logging to identify which pipeline stage fails

## Problem Description

### 1. Single Point of Failure - LLM API
Currently, OpenMetaMate relies on a single LLM API configuration. If the primary API fails due to:
- Billing issues (account runs out of credits)
- Rate limiting (quota exhausted)
- Service outages
- Network connectivity issues

...the entire extraction service becomes unavailable with no fallback mechanism.

### 2. Insufficient Logging
Current logging is minimal, making it difficult to identify which part of the pipeline fails:
- Can't tell if error comes from coding scheme parsing, PDF extraction, LLM calls, or post-processing
- No visibility into data transformation steps (e.g., LLM output → frontend format)
- No clear stage markers in logs
- Difficult to quickly diagnose production issues

**Impact:**
- Users experience complete service outages during API failures
- Engineers can't quickly identify which stage is failing (parsing? extraction? validation? formatting?)
- No visibility into data transformation failures

## Proposed Solution

### 1. Backup LLM API Configuration
Implement automatic failover to a backup LLM API using the same URL and model:

**Environment Variables (add to `.env`, `terraform.tfvars`, GitHub secrets):**
```bash
# Primary LLM API (existing)
LLM_API_KEY=sk-primary-...
LLM_API_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-2024-08-13

# Backup LLM API (new) - uses same URL and model, different key
BACKUP_LLM_API_KEY=sk-backup-...
```

**Note:** Backup API will use the same `LLM_API_URL` and `LLM_MODEL` as primary. Only the API key differs.

**Failover Logic:**
```
Primary API Call
    ↓
Success? → Return result ✅
    ↓
No → Check error type
    ↓
Is it a recoverable error (billing, rate limit, 5xx)?
    ↓
Yes → Try backup API
    ↓
Success? → Log fallback event, return result ✅
    ↓
No → Return error to user ❌
```

**Recoverable Errors (trigger failover):**
- HTTP 429: Rate limit exceeded
- HTTP 402: Payment required / Billing issue
- HTTP 500-599: Server errors
- OpenAI API error codes: `insufficient_quota`, `rate_limit_exceeded`
- Connection timeout errors

**Non-Recoverable Errors (don't trigger failover):**
- HTTP 400: Bad request (client error - same request will fail on backup)
- HTTP 401/403: Authentication error (indicates API key issue)
- Validation errors (malformed input)

### 2. Simple Stage-Based Logging

**Logging Strategy:**
- Add simple log messages at each pipeline stage
- Use emoji markers for easy visual scanning
- Log errors with stage information to identify where failures occur
- Backend-only logging (not exposed to users)
- Cover ALL processing steps including parsing, validation, and transformations

**Pipeline Stages (6 main stages):**
```
[STAGE 1/6] Request Validation → file upload validation, size checks
[STAGE 2/6] Coding Scheme Parsing → parse and validate JSON schema
[STAGE 3/6] PDF Text Extraction → extract text from PDF pages
[STAGE 4/6] LLM Extraction → AI analysis with primary/backup API
[STAGE 5/6] Output Post-Processing → validate and transform LLM output to frontend format
[STAGE 6/6] Response Complete → final validation and return
```

**Note:** STAGE 4 (LLM) may log multiple times if processing multiple chunks

**What to Log:**

#### A. Success Path
```python
# Stage 1: Request validation
logger.info(f"📥 [STAGE 1/6] Request received - file: {file_name} ({file_size_mb} MB)")
logger.info(f"✅ [STAGE 1/6] Request validation passed")

# Stage 2: Coding scheme parsing
logger.info(f"📋 [STAGE 2/6] Parsing coding scheme...")
# ... Parse JSON schema ...
logger.info(f"✅ [STAGE 2/6] Coding scheme parsed - {num_fields} fields")

# Stage 3: PDF text extraction
logger.info(f"📄 [STAGE 3/6] Starting PDF text extraction...")
# ... PDF processing ...
logger.info(f"✅ [STAGE 3/6] PDF extracted - {num_pages} pages, {text_length} chars")

# Stage 4: LLM extraction (may repeat for chunks)
logger.info(f"🤖 [STAGE 4/6] Starting LLM extraction (primary API) - chunk 1/{total_chunks}...")
# ... LLM processing ...
logger.info(f"✅ [STAGE 4/6] LLM extraction completed - chunk 1/{total_chunks} in {duration:.1f}s")

# Stage 5: Output post-processing
logger.info(f"🔧 [STAGE 5/6] Post-processing LLM output...")
# ... Validate and transform to frontend format ...
logger.info(f"✅ [STAGE 5/6] Output validated and transformed to frontend format")

# Stage 6: Response complete
logger.info(f"📦 [STAGE 6/6] Sending response...")
logger.info(f"✅ [STAGE 6/6] Request completed successfully")
```

#### B. Error Path
```python
# Coding scheme parsing error
logger.error(f"❌ [STAGE 2/6] Coding scheme parsing failed: {error_message}")

# PDF extraction error
logger.error(f"❌ [STAGE 3/6] PDF extraction failed: {error_message}")

# LLM API error with failover
logger.error(f"❌ [STAGE 4/6] Primary LLM API failed - chunk 1/{total_chunks}: {error_message}")
logger.info(f"🔄 [STAGE 4/6] Retrying with backup API...")
logger.info(f"✅ [STAGE 4/6] Backup API succeeded - chunk 1/{total_chunks}")

# Post-processing error
logger.error(f"❌ [STAGE 5/6] Output post-processing failed: {error_message}")
logger.error(f"   Raw LLM output: {llm_output[:200]}...")  # First 200 chars for debugging

# Complete failure
logger.error(f"❌ [STAGE 4/6] Both primary and backup APIs failed")
```

**Example Log Output (Success with Failover):**
```
INFO: 📥 [STAGE 1/6] Request received - file: research.pdf (2.3 MB)
INFO: ✅ [STAGE 1/6] Request validation passed
INFO: 📋 [STAGE 2/6] Parsing coding scheme...
INFO: ✅ [STAGE 2/6] Coding scheme parsed - 12 fields
INFO: 📄 [STAGE 3/6] Starting PDF text extraction...
INFO: ✅ [STAGE 3/6] PDF extracted - 15 pages, 45231 chars
INFO: 🤖 [STAGE 4/6] Starting LLM extraction (primary API) - chunk 1/3...
ERROR: ❌ [STAGE 4/6] Primary LLM API failed - chunk 1/3: insufficient_quota
INFO: 🔄 [STAGE 4/6] Retrying with backup API...
INFO: ✅ [STAGE 4/6] Backup API succeeded - chunk 1/3 in 23.4s
INFO: 🤖 [STAGE 4/6] Starting LLM extraction (backup API) - chunk 2/3...
INFO: ✅ [STAGE 4/6] Backup API succeeded - chunk 2/3 in 19.2s
INFO: 🤖 [STAGE 4/6] Starting LLM extraction (backup API) - chunk 3/3...
INFO: ✅ [STAGE 4/6] Backup API succeeded - chunk 3/3 in 21.1s
INFO: 🔧 [STAGE 5/6] Post-processing LLM output...
INFO: ✅ [STAGE 5/6] Output validated and transformed to frontend format
INFO: 📦 [STAGE 6/6] Sending response...
INFO: ✅ [STAGE 6/6] Request completed successfully
```

**Example Log Output (Post-Processing Error):**
```
INFO: 📥 [STAGE 1/6] Request received - file: malformed.pdf (1.2 MB)
INFO: ✅ [STAGE 1/6] Request validation passed
INFO: 📋 [STAGE 2/6] Parsing coding scheme...
INFO: ✅ [STAGE 2/6] Coding scheme parsed - 8 fields
INFO: 📄 [STAGE 3/6] Starting PDF text extraction...
INFO: ✅ [STAGE 3/6] PDF extracted - 5 pages, 12453 chars
INFO: 🤖 [STAGE 4/6] Starting LLM extraction (primary API) - chunk 1/1...
INFO: ✅ [STAGE 4/6] LLM extraction completed - chunk 1/1 in 15.3s
INFO: 🔧 [STAGE 5/6] Post-processing LLM output...
ERROR: ❌ [STAGE 5/6] Output post-processing failed: Missing required field 'study_design'
ERROR:    Raw LLM output: {"title": "Example Study", "author": "Smith et al.", "year": 2024, ...
```

## Implementation Plan

### Phase 1: Configuration Setup
1. **Add backup API configuration** (`backend/app/core/config.py`)
   - Add `BACKUP_LLM_API_KEY` environment variable (optional)
   - Add validation for backup configuration

2. **Update deployment configuration**
   - Add `BACKUP_LLM_API_KEY` to `.env.example`
   - Add `BACKUP_LLM_API_KEY` secret to GitHub Actions (`.github/workflows/deploy.yml`)
   - Add `backup_llm_api_key` variable to Terraform (`infra/variables.tf`, `infra/main.tf`)
   - Update `CLAUDE.md` with backup API documentation

### Phase 2: Backup API Implementation
3. **Modify LLM service** (`backend/app/services/llm_service.py`)
   - Create backup OpenAI client initialization (same URL/model, different key)
   - Implement error classification (recoverable vs non-recoverable)
   - Add failover logic to `extract_with_schema()` method
   - Add stage logging for LLM extraction

### Phase 3: Granular Stage Logging
4. **Add logging to extraction pipeline** (`backend/app/api/routes/extraction.py`)
   - Log STAGE 1: Request validation (file size, type)
   - Log STAGE 2: Coding scheme parsing and validation
   - Log STAGE 5: Output post-processing and transformation
   - Log STAGE 6: Response complete
   - Log errors with stage context and relevant data snippets

5. **Add logging to PDF processing** (`backend/app/services/pdf_processor.py`)
   - Log STAGE 3: PDF text extraction start
   - Log STAGE 3: PDF text extraction complete (with page count, text length)
   - Log errors in PDF extraction

6. **Add logging to LLM service** (`backend/app/services/llm_service.py`)
   - Log STAGE 4: LLM extraction start for each chunk (with provider: primary/backup)
   - Log STAGE 4: LLM extraction complete for each chunk (with duration)
   - Log failover events when switching to backup API
   - Log errors in LLM extraction with error type

### Phase 4: Testing & Documentation
7. **Test backup API failover**
   - Simulate primary API failure (invalid key)
   - Verify backup API is called
   - Verify logs show failover event
   - Test with actual rate limit error

8. **Test logging output**
   - Verify stage markers appear in correct order
   - Verify errors show which stage failed
   - Test in production with sample PDF

9. **Update documentation**
   - Add backup API setup instructions
   - Document stage-based logging format
   - Add debugging guide using stage markers

## Files to Modify/Create

### Modified Files
1. `backend/app/core/config.py` - Add BACKUP_LLM_API_KEY configuration
2. `backend/app/services/llm_service.py` - Implement failover logic and stage logging
3. `backend/app/services/pdf_processor.py` - Add stage logging
4. `backend/app/api/routes/extraction.py` - Add stage logging
5. `.env.example` - Document BACKUP_LLM_API_KEY
6. `.github/workflows/deploy.yml` - Add BACKUP_LLM_API_KEY secret
7. `infra/variables.tf` - Add backup_llm_api_key variable
8. `infra/main.tf` - Pass BACKUP_LLM_API_KEY to container
9. `CLAUDE.md` - Update documentation

### New Files
None - keeping it simple!

## Testing Strategy

### 1. Backup API Failover Testing
```bash
# Test with invalid primary API key (simulate billing failure)
LLM_API_KEY=invalid_key BACKUP_LLM_API_KEY=valid_key uv run uvicorn app.main:app --reload

# Upload test PDF, verify:
# - Primary API fails
# - Backup API is called
# - Extraction succeeds
# - Logs show failover event
```

### 2. Logging Verification
```bash
# Start server
uv run uvicorn app.main:app --reload

# Upload test PDF, check logs for:
# - [STAGE 1/6] Request validation
# - [STAGE 2/6] Coding scheme parsing
# - [STAGE 3/6] PDF text extraction
# - [STAGE 4/6] LLM extraction (multiple chunks if applicable)
# - [STAGE 5/6] Output post-processing
# - [STAGE 6/6] Response complete
# - Stage numbers in error messages
```

### 3. Production Testing
```bash
# After deployment, monitor Lightsail logs
aws lightsail get-container-log \
  --service-name metamate-backend \
  --container-name api \
  | grep "STAGE"

# Verify stage markers appear
# Verify failover works in production
```

## Expected Outcomes

### Before Implementation
- ❌ Single point of failure (primary LLM API)
- ❌ Complete service outage on billing issues
- ❌ Minimal logging (hard to identify which stage fails)
- ❌ Can't tell if error is from coding scheme parsing, PDF extraction, LLM calls, or post-processing
- ❌ No visibility into data transformation failures

### After Implementation
- ✅ Automatic failover to backup LLM API (same provider, different key)
- ✅ Service continues during primary API billing issues
- ✅ Granular 6-stage logging covering entire pipeline:
  - STAGE 1: Request validation
  - STAGE 2: Coding scheme parsing
  - STAGE 3: PDF extraction
  - STAGE 4: LLM extraction (with per-chunk logging)
  - STAGE 5: Output post-processing/transformation
  - STAGE 6: Response complete
- ✅ Can quickly identify exact failure point (parsing? extraction? validation? formatting?)
- ✅ Easy to debug production issues with `grep "STAGE"` or `grep "❌"`

### Reliability Improvement
- **Uptime**: 99.9% → 99.99% (estimated)
- **Mean Time To Recovery (MTTR)**: Hours → Seconds (automatic failover)
- **Debug Time**: Hours → Minutes (stage markers clearly show failure point)

## Cost Analysis

### Additional Costs
1. **Backup LLM API**: ~$5-20/month (only used on failover)
2. **Log Storage**: Negligible (minimal additional log lines)

**Total Additional Cost**: ~$5-20/month
**Value**: Service reliability + faster debugging = high ROI

## Monitoring & Alerts

### Metrics to Track
1. **Failover Events**: Count of primary → backup API switches
2. **Stage Failures**: Which stage fails most often
3. **Processing Duration**: Time spent in STAGE 3 (LLM)

### Recommended Alerts
1. **High Failover Rate**: Alert if >10% requests use backup API
2. **Backup API Failure**: Alert if backup API also fails
3. **Repeated Stage Failures**: Alert if same stage fails >5 times/hour

## Deployment Steps

### 1. Pre-Deployment (Local Testing)
```bash
# 1. Add backup API key to .env
cp .env .env.backup
cat >> .env <<EOF
BACKUP_LLM_API_KEY=sk-backup-...
EOF

# 2. Test locally
uv run uvicorn app.main:app --reload --port 8000

# 3. Test failover (invalid primary key)
# Verify extraction still works with backup API

# 4. Verify stage logging
# Check logs show [STAGE 1/4], [STAGE 2/4], [STAGE 3/4], [STAGE 4/4]
```

### 2. Update Production Configuration
```bash
# 1. Add GitHub secret
# Go to: Settings → Secrets and variables → Actions → New repository secret
# Add: BACKUP_LLM_API_KEY

# 2. Update Terraform variables
cd infra/
vim terraform.tfvars
# Add: backup_llm_api_key = "sk-backup-..."

# 3. Apply Terraform changes
terraform plan
terraform apply
```

### 3. Deploy to Production
```bash
# 1. Commit changes
git add .
git commit -m "feat: add backup LLM API and simple stage logging

- Add BACKUP_LLM_API_KEY for automatic failover (same URL/model)
- Implement error classification (recoverable vs non-recoverable)
- Add simple 4-stage logging to identify failure points
- Stages: Request → PDF Extraction → LLM Processing → Response
- Update documentation

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# 2. Push to main (triggers GitHub Actions)
git push origin main

# 3. Monitor deployment
# GitHub Actions: https://github.com/[your-org]/OpenMetaMate/actions
# Wait for deployment completion
```

### 4. Verify Production
```bash
# 1. Check health endpoint
curl https://api.metamate.online/health | jq

# 2. Check logs for stage markers
aws lightsail get-container-log \
  --service-name metamate-backend \
  --container-name api \
  | grep "STAGE" \
  | head -20

# 3. Test extraction
# Upload test PDF to https://metamate.online
# Verify extraction works
```

## Rollback Plan

If issues occur after deployment:

### Quick Rollback (disable backup API)
```bash
# 1. Remove BACKUP_LLM_API_KEY from GitHub secrets
# Go to: Settings → Secrets and variables → Actions → Delete BACKUP_LLM_API_KEY

# 2. Code will automatically handle missing backup key gracefully
# (No redeploy needed if code handles None value properly)
```

### Full Rollback (revert code changes)
```bash
# 1. Revert commit
git revert HEAD
git push origin main

# 2. Remove backup API secrets from GitHub
# Go to: Settings → Secrets and variables → Actions
# Delete: BACKUP_LLM_API_KEY

# 3. Revert Terraform changes
cd infra/
git checkout HEAD~1 -- *.tf
terraform apply
```

## Future Improvements

1. **Multiple Backup APIs**: Support different providers (e.g., OpenAI → Anthropic → OpenRouter)
2. **Cost Tracking**: Log cost per request (tokens × price)
3. **Metrics Dashboard**: Visualize failover events and stage durations
4. **Circuit Breaker**: Temporarily disable primary API after consecutive failures

## Related Documentation

- OpenAI API Error Codes: https://platform.openai.com/docs/guides/error-codes
- Python Logging: https://docs.python.org/3/library/logging.html
- FastAPI Logging: https://fastapi.tiangolo.com/tutorial/logging/
- AWS Lightsail Logs: https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-viewing-container-service-container-logs.html

## Risk Assessment

### Low Risk
- ✅ Backward compatible (backup API is optional)
- ✅ No breaking changes to API contract
- ✅ Can be disabled by not setting BACKUP_LLM_API_KEY
- ✅ Simple logging (minimal performance impact)

### Medium Risk
- ⚠️ Failover logic complexity (need thorough testing)
- ⚠️ Backup API same provider (both could fail if OpenAI is down)

### Mitigation
- ✅ Extensive local testing before deployment
- ✅ Backup API is optional (can omit if not needed)
- ✅ Gradual rollout (monitor first 100 requests)
- ✅ Rollback plan documented above

## Success Metrics

**Week 1 After Deployment:**
- [ ] Zero service outages due to primary API failures
- [ ] Failover events logged clearly
- [ ] Logs show stage markers for all requests
- [ ] Can identify failure stage within seconds

**Month 1 After Deployment:**
- [ ] 99.99% uptime achieved
- [ ] <5% requests use backup API (primary API stable)
- [ ] 3+ production issues debugged using stage logs

## Conclusion

This implementation provides:
1. **High Availability**: Automatic failover eliminates single point of failure
2. **Simple Debugging**: 4-stage logging makes it obvious where failures occur
3. **Cost Effective**: Backup API only used on failure (~$5-20/month), minimal overhead
4. **Low Risk**: Simple design, backward compatible, easy to rollback

**Recommendation**: Proceed with implementation. The benefits (reliability + debuggability) far outweigh the minimal cost and complexity.
